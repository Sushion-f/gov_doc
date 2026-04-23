"""Agent 基类：可作为父 Orchestrator 的 tool 调度子任务。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from context.builder import ContextBuilder
from model.client import ModelClient
from tool.registry import ToolContext, ToolResult
from workspace.registry import WorkspaceRegistry


@dataclass
class AgentRunOutput:
    text: str
    tool_calls_used: int = 0


class Agent:
    agent_type: str = "generic"
    agent_id: str = "agent"
    display_name: str = "Agent"

    def __init__(
        self,
        *,
        model: ModelClient,
        workspaces: WorkspaceRegistry,
        context_builder: ContextBuilder,
        system_prompt: str,
        skill_keys: list[str],
        tool_names: list[str] | None = None,
        use_stream: bool = False,
    ) -> None:
        self.model = model
        self.workspaces = workspaces
        self.context_builder = context_builder
        self.system_prompt = system_prompt
        self.skill_keys = skill_keys
        self.tool_names = tool_names or []
        self.use_stream = use_stream

    def to_tool_definition(self) -> dict[str, Any]:
        safe_name = f"dispatch_{self.agent_id}".replace("-", "_")
        return {
            "type": "function",
            "function": {
                "name": safe_name,
                "description": f"调度子代理：{self.display_name}。传入 task_prompt。",
                "parameters": {
                    "type": "object",
                    "properties": {"task_prompt": {"type": "string"}},
                    "required": ["task_prompt"],
                },
            },
        }

    def execute(self, inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
        prompt = str(inp.get("task_prompt") or "")
        out = self.run(prompt, ctx)
        return ToolResult(ok=True, output=out.text, data={"text": out.text})

    def run(
        self,
        user_input: str,
        tool_ctx: ToolContext,
        *,
        stream_handler: Callable[[str], None] | None = None,
    ) -> AgentRunOutput:
        ws = self.workspaces.get(tool_ctx.user_id)
        system = self.context_builder.build_for_agent(
            {"system": self.system_prompt, "skills": self.skill_keys},
            tool_ctx.user_id,
            ws,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_input},
        ]
        # 子 agent 当前简化：不重复挂载全量 tools，仅 complete 一轮
        if self.use_stream and stream_handler:
            def _on_chunk(ev: dict[str, Any]) -> None:
                choices = ev.get("choices") or []
                if not choices:
                    return
                delta = choices[0].get("delta") or {}
                t = delta.get("content")
                if isinstance(t, str) and t:
                    stream_handler(t)

            data = self.model.stream(messages, temperature=0.5, on_chunk=_on_chunk)
        else:
            data = self.model.complete(messages, temperature=0.4)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        text = (msg.get("content") or "").strip()
        return AgentRunOutput(text=text)
