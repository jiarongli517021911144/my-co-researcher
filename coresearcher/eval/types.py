from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvalTask:
    id: str
    prompt: str
    title: str = ""
    category: str = ""
    ground_truth: Any = ""
    eval_dimensions: Any = field(default_factory=list)
    mock_output: str = ""
    mock_trace: str = ""
    standard_trace: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EvalTask":
        task_id = payload.get("id") or payload.get("task_id") or payload.get("name")
        if not task_id:
            raise ValueError("EvalTask requires id/task_id")
        standard_trace = str(payload.get("standard_trace") or payload.get("mock_trace") or "")
        return cls(
            id=str(task_id),
            title=str(payload.get("title") or payload.get("name") or ""),
            category=str(payload.get("category") or ""),
            prompt=str(payload.get("prompt") or ""),
            ground_truth=payload.get("ground_truth", ""),
            eval_dimensions=payload.get("eval_dimensions", []),
            mock_output=str(payload.get("mock_output") or ""),
            mock_trace=str(payload.get("mock_trace") or standard_trace),
            standard_trace=standard_trace,
            metadata={k: v for k, v in payload.items() if k not in {"id", "task_id", "name", "title", "category", "prompt", "ground_truth", "eval_dimensions", "mock_output", "mock_trace", "standard_trace"}},
        )

    def dimension_names(self) -> list[str]:
        dimensions = self.eval_dimensions
        if isinstance(dimensions, list):
            return [str(item) for item in dimensions]
        if isinstance(dimensions, dict):
            names: list[str] = []
            for _, value in dimensions.items():
                if isinstance(value, dict):
                    names.extend(str(k) for k in value.keys())
                else:
                    names.append(str(value))
            return names
        return []


@dataclass(slots=True)
class EvalRunResult:
    output: str
    trace: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvalReport:
    task_id: str
    title: str
    category: str
    overall_score: float
    passed: bool
    feedback: str
    output: str
    trace: str = ""
    reference_trace: str = ""
    dimension_scores: dict[str, float] = field(default_factory=dict)
    failure_analysis: str = ""
    suggestions: list[str] = field(default_factory=list)
    judge_model: str = "heuristic"

    @property
    def score(self) -> float:
        return self.overall_score
