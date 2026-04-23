"""工具注册与 OpenAI function schema 输出。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from events.bus import EventBus
    from workspace.workspace import Workspace


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    user_id: str
    session_id: str
    workspace: Workspace
    event_bus: EventBus
    extra: dict[str, Any] = field(default_factory=dict)


ToolFn = Callable[[dict[str, Any], ToolContext], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolFn, dict[str, Any]]] = {}

    def register(self, name: str, fn: ToolFn, schema: dict[str, Any]) -> None:
        self._tools[name] = (fn, schema)

    def register_all(self, items: list[tuple[str, ToolFn, dict[str, Any]]]) -> None:
        for name, fn, schema in items:
            self.register(name, fn, schema)

    def register_agent(self, agent: Any) -> None:
        """将子 Agent 注册为 dispatch 工具（由 agent.to_tool_definition() 提供）。"""
        td = agent.to_tool_definition()
        name = td["function"]["name"]
        schema = td["function"]["parameters"]

        def _run(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
            return agent.execute(inp, ctx)

        self.register(name, _run, {"type": "function", "function": {"name": name, "parameters": schema}})

    def to_openai_tools(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for n, (_, spec) in self._tools.items():
            if names is not None and n not in names:
                continue
            if spec.get("type") == "function":
                out.append(spec)
            else:
                out.append({"type": "function", "function": {"name": n, "parameters": spec}})
        return out

    def execute(self, name: str, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        if name not in self._tools:
            return ToolResult(ok=False, error=f"unknown_tool:{name}")
        fn, _ = self._tools[name]
        return fn(input, ctx)
