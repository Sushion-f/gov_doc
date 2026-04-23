"""内置技能列表占位；实际以 skills/ 目录 + load_from_dir 为准。"""

from __future__ import annotations

from pathlib import Path

from .registry import SkillDefinition, SkillRegistry


def load_builtin_skills(skills_dir: Path) -> list[SkillDefinition]:
    reg = SkillRegistry.instance()
    reg.load_from_dir(skills_dir)
    return reg.all_skills()


BUILTIN_SKILLS: list[SkillDefinition] = []
