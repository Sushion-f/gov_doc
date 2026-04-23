"""EventBus：解耦 orchestrator / tools 与 WebSocket 推送。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict


class OrchestratorEvent(TypedDict, total=False):
    type: str
    question: str
    tasks: list[dict[str, Any]]
    task_id: str
    agent_name: str
    delta: str
    result: Any
    error: str
    filename: str
    mode: str
    chunk: str
    path: str
    editable: bool
    content: str


Handler = Callable[[OrchestratorEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def clear(self) -> None:
        self._handlers.clear()

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def publish(self, event: OrchestratorEvent) -> None:
        for h in self._handlers:
            h(event)
