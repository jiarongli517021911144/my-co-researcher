from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SkillSummary:
    name: str
    path: Path
    summary: str


class SkillsLoader:
    def __init__(self, roots: list[str | Path] | None = None) -> None:
        self.roots = [Path(root).expanduser() for root in (roots or ["~/.codex/skills"])]

    def discover(self) -> list[SkillSummary]:
        skills: list[SkillSummary] = []
        for root in self.roots:
            if not root.exists():
                continue
            for path in root.rglob("SKILL.md"):
                summary = self._read_summary(path)
                skills.append(SkillSummary(name=path.parent.name, path=path, summary=summary))
        return sorted(skills, key=lambda item: item.name)

    def describe_available_skills(self) -> str:
        skills = self.discover()
        return "\n".join(f"- {skill.name}: {skill.summary}" for skill in skills[:20])

    def _read_summary(self, path: Path) -> str:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:160]
        return "No summary"
