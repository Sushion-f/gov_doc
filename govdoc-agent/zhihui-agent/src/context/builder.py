"""拼接 system prompt：GLOBAL_INST → identity → memory → skills → agent_role。"""

from __future__ import annotations

from typing import Any

from skill.registry import SkillRegistry
from workspace.workspace import Workspace

GLOBAL_INST = """你是「智慧公文」多技能助手，需遵守政务文书规范与用户工作区约束。
工具返回 JSON 时请保证可解析。优先使用已提供的 workspace 工具读写产物。"""


class ContextBuilder:
    def __init__(self, skills: SkillRegistry) -> None:
        self._skills = skills

    def build_main(
        self,
        user_id: str,
        skill_ids: list[str],
        ws: Workspace,
        *,
        assets_summary: str | None = None,
    ) -> str:
        identity = ws.read_identity()
        memory = ws.read_memory()
        skill_block = self._skills.resolve(skill_ids, {"user_id": user_id})
        parts = [
            GLOBAL_INST,
            "## identity.md\n" + identity,
            "## memory.md\n" + memory,
            "## Skills\n" + skill_block,
        ]
        if assets_summary:
            parts.append("## 用户素材\n" + assets_summary)
        return "\n\n".join(parts)

    def build_for_agent(self, agent_cfg: dict[str, Any], user_id: str, ws: Workspace) -> str:
        role = str(agent_cfg.get("system") or agent_cfg.get("role") or "你是专业助手。")
        sids = list(agent_cfg.get("skills") or [])
        base = self.build_main(user_id, sids, ws)
        return base + "\n\n## 当前角色\n" + role
