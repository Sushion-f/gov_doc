from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents.main_agent import MainAgent


def build_model_execution_plan(
    content: str,
    requested_skill: str | None,
    attachments: list[dict[str, Any]] | None,
    requested_model: str | None,
    runtime_context: dict | None = None,
    memory_context: dict | None = None,
    on_planner_stream: Callable[[dict[str, Any]], None] | None = None,
):
    main_agent = MainAgent()
    return main_agent.plan(
        content,
        requested_model,
        attachments=attachments or [],
        runtime_context=runtime_context,
        memory_context=memory_context,
        direct_agent=requested_skill,
        on_planner_stream=on_planner_stream,
    )
