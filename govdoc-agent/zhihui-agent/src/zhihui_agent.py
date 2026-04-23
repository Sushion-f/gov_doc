"""ZhihuiAgent 门面：依赖注入与 chat 入口。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from context.builder import ContextBuilder
from events.bus import EventBus, OrchestratorEvent
from model.client import ModelClient
from orchestrator.orchestrator import Orchestrator
from skill.builtin import load_builtin_skills
from skill.registry import SkillRegistry
from tool.registry import ToolRegistry
from workspace.registry import WorkspaceRegistry
from workspace.session_store import SessionStore


class ZhihuiAgent:
    def __init__(
        self,
        *,
        root: Path,
        model: ModelClient,
        skills: SkillRegistry,
        tools: ToolRegistry,
        context: ContextBuilder,
        orchestrator: Orchestrator,
        bus: EventBus,
    ) -> None:
        self.root = root
        self.model = model
        self.skills = skills
        self.tools = tools
        self.context = context
        self.orchestrator = orchestrator
        self.bus = bus

    def chat(
        self,
        user_message: str,
        handler: Callable[[OrchestratorEvent], None],
        *,
        user_id: str,
        session_id: str,
        skill_ids: list[str] | None = None,
    ) -> str:
        if handler is not None:
            self.bus.clear()
            self.bus.subscribe(handler)
        return self.orchestrator.run(
            user_message,
            user_id=user_id,
            session_id=session_id,
            skill_ids=skill_ids,
        )


def create_zhihui_agent(config: dict[str, Any] | None = None) -> ZhihuiAgent:
    cfg = config or {}
    root = Path(cfg.get("root") or Path(__file__).resolve().parents[1])
    data_root = Path(cfg.get("data_root") or root / "data")
    skills_dir = Path(cfg.get("skills_dir") or root / "skills")
    data_root.mkdir(parents=True, exist_ok=True)

    model = ModelClient(
        base_url=cfg.get("base_url"),
        api_key=cfg.get("api_key"),
        default_model=cfg.get("default_model"),
    )
    skills = SkillRegistry.instance()
    load_builtin_skills(skills_dir)
    tools = ToolRegistry()
    workspaces = WorkspaceRegistry(data_root)
    sessions = SessionStore(data_root)
    context = ContextBuilder(skills)
    bus = EventBus()
    orch = Orchestrator(
        model=model,
        workspaces=workspaces,
        sessions=sessions,
        skills=skills,
        tools=tools,
        context=context,
        bus=bus,
        data_root=data_root,
    )
    return ZhihuiAgent(
        root=root,
        model=model,
        skills=skills,
        tools=tools,
        context=context,
        orchestrator=orch,
        bus=bus,
    )


__all__ = ["ZhihuiAgent", "create_zhihui_agent"]
