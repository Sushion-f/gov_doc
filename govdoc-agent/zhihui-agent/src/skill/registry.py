"""Skill 注册：从 skills/ 目录加载 SKILL.md。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillDefinition:
    id: str
    name: str
    description: str
    applicable_to: list[str] = field(default_factory=list)
    version: str = "1"
    body: str = ""


def _parse_skill_md(text: str) -> SkillDefinition:
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].strip()
            body = text[end + 4 :].lstrip("\n")
            for line in raw.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                meta[k] = v
    app = meta.get("applicableTo") or meta.get("applicable_to") or ""
    applicable = [x.strip() for x in str(app).strip("[]").split(",") if x.strip()]
    return SkillDefinition(
        id=meta.get("id", "unknown"),
        name=meta.get("name", meta.get("id", "Skill")),
        description=meta.get("description", ""),
        applicable_to=applicable,
        version=str(meta.get("version", "1")),
        body=body.strip(),
    )


class SkillRegistry:
    _instance: SkillRegistry | None = None

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    @classmethod
    def instance(cls) -> SkillRegistry:
        if cls._instance is None:
            cls._instance = SkillRegistry()
        return cls._instance

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill

    def register_all(self, skills: list[SkillDefinition]) -> None:
        for s in skills:
            self.register(s)

    def load_from_dir(self, path: Path) -> None:
        if not path.is_dir():
            return
        for skill_dir in sorted(path.iterdir()):
            if not skill_dir.is_dir():
                continue
            md = skill_dir / "SKILL.md"
            if md.is_file():
                sk = _parse_skill_md(md.read_text(encoding="utf-8"))
                if sk.id == "unknown":
                    sk.id = skill_dir.name.replace("-", "_")
                self.register(sk)

    def resolve(self, skill_ids: list[str], ctx: dict[str, Any] | None = None) -> str:
        parts: list[str] = []
        for sid in skill_ids:
            s = self._skills.get(sid)
            if s:
                parts.append(f"### {s.name}\n{s.body}\n")
        return "\n".join(parts)

    def get_applicable(self, agent_type: str) -> list[SkillDefinition]:
        return [
            s
            for s in self._skills.values()
            if not s.applicable_to or agent_type in s.applicable_to or "all" in s.applicable_to
        ]

    def all_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())
