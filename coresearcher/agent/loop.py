from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from coresearcher.agent.context import ContextBuilder, ContextCompressor, TokenCounter
from coresearcher.agent.memory import MemoryStore
from coresearcher.agent.skills import SkillsLoader
from coresearcher.agent.subagent import SubagentManager
from coresearcher.agent.tools.registry import ToolRegistry, build_default_registry
from coresearcher.bus.events import InboundMessage, OutboundMessage
from coresearcher.bus.queue import MessageBus
from coresearcher.config.schema import Config
from coresearcher.providers.base import LLMProvider
from coresearcher.session import SessionManager


class AgentLoop:
    def __init__(
        self,
        config: Config,
        bus: MessageBus,
        provider: LLMProvider,
        *,
        session_manager: SessionManager | None = None,
        memory_store: MemoryStore | None = None,
        tool_registry: ToolRegistry | None = None,
        skills_loader: SkillsLoader | None = None,
        subagents: SubagentManager | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.provider = provider
        self.sessions = session_manager or SessionManager(config.memory.session_dir)
        self.memory_store = memory_store or MemoryStore(config.memory.directory)
        self.subagents = subagents or SubagentManager()
        self.skills_loader = skills_loader or SkillsLoader()
        self.context_builder = ContextBuilder(
            config,
            memory_store=self.memory_store,
            skills_loader=self.skills_loader,
        )
        _, provider_cfg = config.providers.resolve()
        self.compressor = ContextCompressor(
            TokenCounter(provider_cfg.model or config.providers.default_model),
            config.agents.max_context_tokens,
            config.agents.compression_ratio,
            config.agents.summary_ratio,
        )
        self.tools = tool_registry or build_default_registry(
            config,
            bus=bus,
            subagents=self.subagents,
            memory_search=self.memory_store.search,
        )

    async def run(self) -> None:
        while True:
            inbound = await self.bus.consume_inbound()
            try:
                await self._process_message(inbound)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Agent loop failed for session {}", inbound.session_key)
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=inbound.channel,
                        chat_id=inbound.chat_id,
                        content=f"Internal error: {type(exc).__name__}: {exc}",
                        reply_to=(inbound.metadata or {}).get("message_id"),
                        metadata=dict(inbound.metadata or {}),
                    )
                )

    async def _process_message(self, inbound: InboundMessage, *, trace_events: list[dict[str, Any]] | None = None, trace_sink=None, publish_outbound: bool = True) -> OutboundMessage:
        last_consolidated = self.sessions.get_last_consolidated(inbound.session_key)
        history_window = self.sessions.load_recent_window(
            inbound.session_key,
            self.config.agents.defaults.memory_window,
        )
        last_consolidated = await self._flush_backlog_before_window(
            inbound.session_key,
            history_window.start_index,
            last_consolidated,
        )
        history = history_window.messages

        final_response, new_records, _conversation, compressed = await self._run_react_task(
            inbound,
            inbound.content,
            history=history,
            history_start=history_window.start_index,
            last_consolidated=last_consolidated,
            trace_events=trace_events,
            trace_sink=trace_sink,
        )
        if compressed.new_last_consolidated is not None and compressed.new_last_consolidated > last_consolidated:
            self.sessions.set_last_consolidated(
                inbound.session_key,
                compressed.new_last_consolidated,
            )

        self.sessions.append_messages(inbound.session_key, new_records)

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=final_response,
            reply_to=(inbound.metadata or {}).get("message_id"),
            metadata=dict(inbound.metadata or {}),
        )
        self._trace(trace_events, trace_sink=trace_sink, kind="final_response", content=final_response[:2000])
        if publish_outbound:
            await self.bus.publish_outbound(outbound)
        return outbound

    async def _process_planned_message(self, inbound: InboundMessage, *, trace_events: list[dict[str, Any]] | None = None, trace_sink=None) -> str:
        plan = await self.planner.generate(
            inbound.content,
            self.provider,
            available_tools=self.tools.names(),
        )
        logger.info("Plan generated | session={}\n{}", inbound.session_key, plan.to_markdown())
        self._trace(trace_events, trace_sink=trace_sink, kind="plan_generated", plan=plan.to_markdown())

        executed = 0
        max_steps = max(12, len(plan.steps) + 6)
        while executed < max_steps:
            ready_steps = plan.ready_steps()
            if not ready_steps:
                break
            batch = ready_steps[: max(1, self.config.agents.max_parallel_steps)]
            logger.info(
                "Plan batch starting | session={} | steps={} | parallelism={}",
                inbound.session_key,
                [step.id for step in batch],
                len(batch),
            )
            self._trace(trace_events, trace_sink=trace_sink, kind="plan_batch", steps=[step.id for step in batch], parallelism=len(batch))
            results = await asyncio.gather(*(self._execute_parallel_step(inbound, plan, step, trace_events=trace_events, trace_sink=trace_sink) for step in batch))
            need_replan = False
            for step, result in zip(batch, results, strict=True):
                logger.info(
                    "Plan step finished | session={} | step={} | status={} | goal={} | result={}",
                    inbound.session_key,
                    step.id,
                    step.status,
                    step.goal,
                    (step.result or step.error or result)[:500],
                )
                self._trace(trace_events, trace_sink=trace_sink, kind="plan_step_finished", step_id=step.id, status=step.status, goal=step.goal, result=(step.result or step.error or result)[:2000])
                should_replan, reason = await self.replanner.should_replan(
                    plan,
                    step,
                    step.result or step.error or result,
                    provider=self.provider,
                )
                if should_replan:
                    plan = await self.replanner.replan(
                        plan,
                        step,
                        step.result or step.error or result,
                        provider=self.provider,
                        reason=reason,
                    )
                    logger.info("Plan replanned | session={} | reason={}\n{}", inbound.session_key, reason or "", plan.to_markdown())
                    self._trace(trace_events, trace_sink=trace_sink, kind="plan_replanned", reason=reason or "", plan=plan.to_markdown())
                    need_replan = True
                    break
            executed += len(batch)
            if need_replan:
                continue

        draft = await self._synthesize_plan(inbound, plan)
        return draft

    async def _execute_parallel_step(self, inbound: InboundMessage, plan, step, *, trace_events: list[dict[str, Any]] | None = None, trace_sink=None) -> str:
        try:
            return await self.step_executor.execute(
                step,
                lambda current_step: self._execute_plan_step(inbound, plan, current_step, trace_events=trace_events, trace_sink=trace_sink),
            )
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    async def _execute_plan_step(self, inbound: InboundMessage, plan, step, *, trace_events: list[dict[str, Any]] | None = None, trace_sink=None) -> str:
        completed = [f"- {item.id}: {item.result}" for item in plan.completed_steps() if item.result]
        extra_system = [
            "You are executing a single step inside a larger plan. Focus only on the current step.",
            f"Plan objective: {plan.objective}",
            f"Current step: {step.id} - {step.goal}",
        ]
        if step.tools_hint:
            extra_system.append(f"Suggested tools: {', '.join(step.tools_hint)}")
        if completed:
            extra_system.append("Completed step results:\n" + "\n".join(completed[-6:]))
        task_prompt = (
            f"Execute this step and return a concise, concrete result.\n"
            f"Step goal: {step.goal}\n"
            f"If you need tools, use them."
        )
        result, _records, _conversation, _compressed = await self._run_react_task(
            inbound,
            task_prompt,
            history=[],
            history_start=0,
            last_consolidated=0,
            extra_system_messages=extra_system,
            trace_events=trace_events,
            trace_sink=trace_sink,
        )
        return result

    async def _synthesize_plan(self, inbound: InboundMessage, plan, feedback: str | None = None) -> str:
        completed = [step for step in plan.topological_sort() if step.status == "done"]
        failed = [step for step in plan.steps if step.status == "failed"]
        plan_summary = "\n".join(
            f"- {step.id}: {step.goal}\n  result: {(step.result or step.error or '')[:800]}"
            for step in completed
        )
        user_prompt = (
            f"Original objective: {plan.objective}\n\n"
            f"Completed steps:\n{plan_summary or '- none'}\n\n"
            f"Failed steps:\n" + ("\n".join(f"- {step.id}: {step.error}" for step in failed) if failed else "- none")
        )
        if feedback:
            user_prompt += f"\n\nCritic feedback to address:\n{feedback}"
        messages = [
            {
                "role": "system",
                "content": "Synthesize the plan execution results into a final answer for the user. Mention blockers if any remain.",
            },
            {"role": "user", "content": user_prompt},
        ]
        response = await self.provider.chat(
            messages,
            model=self.provider.get_default_model(),
            max_tokens=self.config.agents.defaults.max_tokens,
            temperature=self.config.agents.defaults.temperature,
        )
        if response.content:
            return response.content
        fallback_lines = [f"Objective: {plan.objective}"]
        fallback_lines.extend(f"- {step.goal}: {step.result or step.error or ''}" for step in completed or plan.steps)
        return "\n".join(fallback_lines)

    async def _apply_reflexion(
        self,
        task: str,
        initial_output: str,
        reviser,
        *,
        trace_events: list[dict[str, Any]] | None = None,
        trace_sink=None,
    ) -> str:
        async def actor(feedback: str | None, attempt: int) -> str:
            if attempt == 1:
                return initial_output
            return await reviser(feedback)

        output, history = await self.reflexion.run(task, actor, provider=self.critic_provider)
        for idx, result in enumerate(history, start=1):
            logger.info(
                "Reflexion critic | attempt={} | passed={} | score={} | feedback={} | dimensions={}",
                idx,
                result.passed,
                result.score,
                result.feedback,
                result.dimensions,
            )
            self._trace(trace_events, trace_sink=trace_sink, kind="reflexion_critic", attempt=idx, passed=result.passed, score=result.score, feedback=result.feedback, dimensions=result.dimensions)
        return output

    async def _run_react_task(
        self,
        inbound: InboundMessage,
        user_content: str,
        *,
        history: list[dict[str, Any]],
        history_start: int,
        last_consolidated: int,
        extra_system_messages: list[str] | None = None,
        trace_events: list[dict[str, Any]] | None = None,
        trace_sink=None,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], Any]:
        temp_inbound = InboundMessage(
            channel=inbound.channel,
            sender_id=inbound.sender_id,
            chat_id=inbound.chat_id,
            content=user_content,
            media=list(inbound.media),
            metadata=dict(inbound.metadata),
        )
        messages = await self.context_builder.build_messages(temp_inbound, history=history)
        insert_at = 1
        for extra in extra_system_messages or []:
            messages.insert(insert_at, {"role": "system", "content": extra})
            insert_at += 1

        compressed = await self.compressor.compress(
            messages,
            provider=self.provider,
            memory_store=self.memory_store,
            session_key=inbound.session_key,
            history_count=len(history),
            history_start=history_start,
            last_consolidated=last_consolidated,
        )
        user_message = {"role": "user", "content": user_content}
        new_records: list[dict[str, Any]] = [user_message]
        conversation = list(compressed.messages)
        final_response = ""
        defaults = self.config.agents.defaults

        for _ in range(self.config.agents.max_iterations):
            response = await self.provider.chat(
                conversation,
                tools=self.tools.get_definitions(),
                model=self.provider.get_default_model(),
                max_tokens=defaults.max_tokens,
                temperature=defaults.temperature,
            )
            if getattr(response, "reasoning_content", None):
                self._trace(trace_events, trace_sink=trace_sink, kind="reasoning", content=str(response.reasoning_content)[:4000])
            assistant_record = self._assistant_record(response)
            conversation.append(assistant_record)
            new_records.append(assistant_record)

            if not response.has_tool_calls:
                final_response = response.content or ""
                break

            for tool_call in response.tool_calls:
                logger.info(
                    "Tool call triggered | session={} | tool={} | args={}",
                    inbound.session_key,
                    tool_call.name,
                    json.dumps(tool_call.arguments, ensure_ascii=False),
                )
                self._trace(trace_events, trace_sink=trace_sink, kind="tool_call", tool=tool_call.name, args=json.dumps(tool_call.arguments, ensure_ascii=False))
                try:
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                except Exception as exc:
                    logger.warning("Tool execution failed: {}", tool_call.name)
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                tool_record = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": self._stringify(result),
                }
                conversation.append(tool_record)
                new_records.append(tool_record)
                self._trace(trace_events, trace_sink=trace_sink, kind="tool_result", tool=tool_call.name, result=self._stringify(result)[:2000])

        if not final_response:
            final_response = "I could not produce a response."
        return final_response, new_records, conversation, compressed

    async def _flush_backlog_before_window(self, session_key: str, window_start: int, last_consolidated: int) -> int:
        if last_consolidated >= window_start:
            return last_consolidated
        backlog = self.sessions.load_message_range(session_key, last_consolidated, window_start)
        if not backlog:
            return last_consolidated
        logger.info(
            "Memory flush triggered | session={} | reason=history_window_trimmed | flush_count={} | last_consolidated={} | window_start={}",
            session_key,
            len(backlog),
            last_consolidated,
            window_start,
        )
        await self.memory_store.flush_messages(session_key, backlog, provider=self.provider)
        self.sessions.set_last_consolidated(session_key, window_start)
        return window_start

    def _reflexion_enabled(self) -> bool:
        return False

    def _reflexion_max_attempts(self) -> int:
        return self.config.agents.reflexion.max_attempts

    def _build_critic_provider(self) -> LLMProvider:
        return self.provider

    def _trace(self, trace_events: list[dict[str, Any]] | None, *, trace_sink=None, **payload: Any) -> None:
        if trace_events is not None:
            trace_events.append(payload)
        if trace_sink is not None:
            trace_sink(payload)

    def _assistant_record(self, response) -> dict[str, Any]:
        record: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
        if response.tool_calls:
            record["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                    },
                }
                for tool_call in response.tool_calls
            ]
        return record

    def _should_plan(self, content: str) -> bool:
        content = content.strip()
        return len(content) >= self.config.agents.planner_min_length or any(
            keyword in content.lower()
            for keyword in ["计划", "plan", "步骤", "roadmap", "拆解", "调研", "compare", "对比"]
        )

    def _stringify(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
