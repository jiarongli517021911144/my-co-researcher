from __future__ import annotations

import json
from typing import Any

import json_repair

from coresearcher.eval.types import EvalReport, EvalTask
from coresearcher.providers.base import LLMProvider


_DEFAULT_DIMENSIONS = [
    "tool_usage",
    "reasoning",
    "format_compliance",
    "factual_accuracy",
    "completeness",
    "efficiency",
]


class EvalJudge:
    def __init__(self, provider: LLMProvider | None = None, judge_model: str | None = None) -> None:
        self.provider = provider
        self.judge_model = judge_model or (provider.get_default_model() if provider else "heuristic")

    async def evaluate(self, task: EvalTask, output: str, trace: str | None = None) -> EvalReport:
        if self.provider is not None:
            try:
                return await self._llm_evaluate(task, output, trace)
            except Exception:
                pass
        return self._heuristic(task, output, trace)

    async def _llm_evaluate(self, task: EvalTask, output: str, trace: str | None) -> EvalReport:
        dimensions = task.dimension_names() or list(_DEFAULT_DIMENSIONS)
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are an evaluation judge. Compare the actual output and actual trajectory against the task prompt, ground truth, and reference trajectory. "
                    "Return JSON only with keys: overall_score (0-10), passed (bool), feedback, dimension_scores (object), failure_analysis, suggestions (list)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task ID: {task.id}\n"
                    f"Category: {task.category}\n"
                    f"Prompt: {task.prompt}\n"
                    f"Ground truth: {json.dumps(task.ground_truth, ensure_ascii=False)}\n"
                    f"Dimensions: {dimensions}\n"
                    f"Reference trajectory:\n{task.standard_trace or '(none)'}\n\n"
                    f"Actual trajectory:\n{trace or ''}\n\n"
                    f"Actual output:\n{output}"
                ),
            },
        ]
        response = await self.provider.chat(prompt, model=self.judge_model, max_tokens=1400, temperature=0.1)
        payload = json_repair.loads(response.content or "{}")
        scores = {str(k): float(v) for k, v in dict(payload.get("dimension_scores", {})).items()}
        overall = float(payload.get("overall_score", 0.0))
        return EvalReport(
            task_id=task.id,
            title=task.title,
            category=task.category,
            overall_score=round(overall, 2),
            passed=bool(payload.get("passed", overall >= 7.0)),
            feedback=str(payload.get("feedback") or "llm-judge"),
            output=output,
            trace=trace or "",
            reference_trace=task.standard_trace,
            dimension_scores=scores,
            failure_analysis=str(payload.get("failure_analysis") or ""),
            suggestions=[str(item) for item in (payload.get("suggestions") or [])],
            judge_model=self.judge_model,
        )

    def _heuristic(self, task: EvalTask, output: str, trace: str | None) -> EvalReport:
        output = output.strip()
        trace = (trace or "").strip()
        reference_trace = task.standard_trace.strip()
        dimensions = task.dimension_names() or list(_DEFAULT_DIMENSIONS)

        ground_truth_text = json.dumps(task.ground_truth, ensure_ascii=False) if isinstance(task.ground_truth, (dict, list)) else str(task.ground_truth or "")
        trace_overlap = _trace_overlap(trace, reference_trace)
        scores: dict[str, float] = {}
        for dimension in dimensions:
            score = 6.0
            if output:
                score += 1.0
            if len(output) > 120:
                score += 1.0
            if ground_truth_text and any(fragment in output for fragment in _ground_truth_fragments(task.ground_truth)):
                score += 1.0
            if dimension in {"tool_usage", "reasoning", "recovery", "interaction", "efficiency"}:
                score += round(trace_overlap * 2.0, 1)
            if dimension in {"format_compliance", "source_citation"} and ("- " in output or "|" in output or "http" in output or "\n" in output):
                score += 1.0
            scores[dimension] = min(10.0, round(score, 1))

        overall = round(sum(scores.values()) / max(len(scores), 1), 2)
        passed = overall >= 7.0
        failure_analysis = (
            "Output or trajectory diverged from the reference behavior."
            if not passed
            else "Minor improvements remain, but overall quality is solid."
        )
        suggestions = [
            "Align tool usage more closely with the reference trajectory.",
            "Keep final formatting explicit and easy to scan.",
        ]
        return EvalReport(
            task_id=task.id,
            title=task.title,
            category=task.category,
            overall_score=overall,
            passed=passed,
            feedback="heuristic judge",
            output=output,
            trace=trace,
            reference_trace=task.standard_trace,
            dimension_scores=scores,
            failure_analysis=failure_analysis,
            suggestions=suggestions,
            judge_model=self.judge_model,
        )


def _ground_truth_fragments(ground_truth: Any) -> list[str]:
    if isinstance(ground_truth, str):
        return [ground_truth] if ground_truth else []
    if isinstance(ground_truth, dict):
        fragments: list[str] = []
        for key, value in ground_truth.items():
            fragments.append(str(key))
            fragments.append(str(value))
        return fragments
    if isinstance(ground_truth, list):
        return [str(item) for item in ground_truth]
    return []


def _trace_overlap(actual: str, reference: str) -> float:
    if not actual or not reference:
        return 0.0
    actual_tokens = set(actual.lower().split())
    reference_tokens = set(reference.lower().split())
    if not actual_tokens or not reference_tokens:
        return 0.0
    return len(actual_tokens & reference_tokens) / max(len(reference_tokens), 1)
