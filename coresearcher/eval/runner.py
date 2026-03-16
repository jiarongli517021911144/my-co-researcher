from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from coresearcher.eval.judge import EvalJudge
from coresearcher.eval.types import EvalReport, EvalRunResult, EvalTask


class EvalRunner:
    def __init__(self, judge: EvalJudge | None = None, reports_dir: str | Path = "eval/reports") -> None:
        self.judge = judge or EvalJudge()
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = self.reports_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def load_dataset(self, path: str | Path) -> list[EvalTask]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return [EvalTask.from_payload(item) for item in payload]

    async def run(
        self,
        tasks: list[EvalTask],
        actor: Callable[[EvalTask], Awaitable[str | dict[str, Any] | EvalRunResult] | str | dict[str, Any] | EvalRunResult],
    ) -> list[EvalReport]:
        reports: list[EvalReport] = []
        for task in tasks:
            raw_result = actor(task)
            if hasattr(raw_result, "__await__"):
                raw_result = await raw_result
            run_result = self._coerce_run_result(task, raw_result)
            reports.append(await self.judge.evaluate(task, run_result.output, trace=run_result.trace))
        return reports

    async def run_dataset(
        self,
        dataset_path: str | Path,
        actor: Callable[[EvalTask], Awaitable[str | dict[str, Any] | EvalRunResult] | str | dict[str, Any] | EvalRunResult],
    ) -> tuple[str, list[EvalTask], list[EvalReport], Path]:
        path = Path(dataset_path)
        dataset_name = path.stem
        tasks = self.load_dataset(path)
        reports = await self.run(tasks, actor)
        report_path = self.render_markdown_report(reports, dataset_name=dataset_name)
        return dataset_name, tasks, reports, report_path

    def summarize(self, reports: list[EvalReport]) -> dict[str, object]:
        if not reports:
            return {"average_score": 0.0, "best_dimension": None, "worst_dimension": None}
        average_score = round(sum(report.overall_score for report in reports) / len(reports), 2)
        dimension_totals: dict[str, list[float]] = {}
        for report in reports:
            for name, score in report.dimension_scores.items():
                dimension_totals.setdefault(name, []).append(score)
        dimension_averages = {name: round(sum(scores) / len(scores), 2) for name, scores in dimension_totals.items()}
        best_dimension = max(dimension_averages, key=dimension_averages.get)
        worst_dimension = min(dimension_averages, key=dimension_averages.get)
        return {
            "average_score": average_score,
            "best_dimension": (best_dimension, dimension_averages[best_dimension]),
            "worst_dimension": (worst_dimension, dimension_averages[worst_dimension]),
        }

    def render_markdown_report(
        self,
        reports: list[EvalReport],
        path: str | Path | None = None,
        *,
        dataset_name: str | None = None,
    ) -> Path:
        target = self._resolve_report_path(path, dataset_name=dataset_name)
        summary = self.summarize(reports)
        lines = ["# Evaluation Report", ""]
        lines.append(f"Run ID: `{self.run_id}`")
        lines.append("")
        if dataset_name:
            lines.extend([f"Dataset: `{dataset_name}`", ""])
        for report in reports:
            lines.append(f"## {report.task_id} — {report.title}")
            lines.append("")
            lines.append(f"- Category: `{report.category}`")
            lines.append(f"- Judge: `{report.judge_model}`")
            lines.append("")
            lines.append("| Dimension | Score |")
            lines.append("|---|---:|")
            for name, score in report.dimension_scores.items():
                lines.append(f"| {name} | {score:.1f} |")
            lines.append(f"| Overall | {report.overall_score:.2f} |")
            lines.append("")
            if report.reference_trace:
                lines.append("Reference trajectory:")
                lines.append("```text")
                lines.append(report.reference_trace)
                lines.append("```")
                lines.append("")
            if report.trace:
                lines.append("Actual trajectory:")
                lines.append("```text")
                lines.append(report.trace)
                lines.append("```")
                lines.append("")
            lines.append(f"Failure analysis: {report.failure_analysis}")
            if report.suggestions:
                lines.append("")
                lines.append("Suggestions:")
                for suggestion in report.suggestions:
                    lines.append(f"- {suggestion}")
            lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Average score: {summary['average_score']}")
        lines.append(f"- Best dimension: {summary['best_dimension']}")
        lines.append(f"- Worst dimension: {summary['worst_dimension']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    def _resolve_report_path(self, path: str | Path | None, *, dataset_name: str | None) -> Path:
        if path is None:
            return self.run_dir / f"eval_report_{dataset_name or 'all'}.md"
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.run_dir / candidate.name

    def _coerce_run_result(self, task: EvalTask, raw_result: Any) -> EvalRunResult:
        if isinstance(raw_result, EvalRunResult):
            return raw_result
        if isinstance(raw_result, str):
            return EvalRunResult(output=raw_result, trace=task.mock_trace)
        if isinstance(raw_result, dict):
            return EvalRunResult(
                output=str(raw_result.get("output") or task.mock_output or ""),
                trace=str(raw_result.get("trace") or task.mock_trace or ""),
                metadata={k: v for k, v in raw_result.items() if k not in {"output", "trace"}},
            )
        return EvalRunResult(output=task.mock_output, trace=task.mock_trace)
