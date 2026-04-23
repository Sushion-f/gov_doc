"""主控：tool_use 循环 + 事件推送。"""

from __future__ import annotations

import json
from typing import Any

from context.builder import ContextBuilder
from events.bus import EventBus, OrchestratorEvent
from model.client import ModelClient
from tool.builtin import register_builtin_tools
from tool.registry import ToolContext, ToolRegistry
from workspace.registry import WorkspaceRegistry
from workspace.session_store import SessionStore

from .completeness import check_completeness
from .planner import decompose_to_todos


class Orchestrator:
    def __init__(
        self,
        *,
        model: ModelClient,
        workspaces: WorkspaceRegistry,
        sessions: SessionStore,
        skills: Any,
        tools: ToolRegistry,
        context: ContextBuilder,
        bus: EventBus,
        data_root: Any,
        max_tool_rounds: int = 12,
    ) -> None:
        self.model = model
        self.workspaces = workspaces
        self.sessions = sessions
        self.skills = skills
        self.tools = tools
        self.context = context
        self.bus = bus
        self.data_root = data_root
        self.max_tool_rounds = max_tool_rounds
        register_builtin_tools(self.tools)

    def _parse_tool_calls(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        raw = message.get("tool_calls") or []
        out: list[dict[str, Any]] = []
        for tc in raw:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            out.append({"id": tc.get("id", ""), "name": name, "arguments": args})
        return out

    def run(
        self,
        user_message: str,
        *,
        user_id: str,
        session_id: str,
        skill_ids: list[str] | None = None,
        skip_checks: bool = False,
    ) -> str:
        ws = self.workspaces.get(user_id)
        ctx = ToolContext(
            user_id=user_id,
            session_id=session_id,
            workspace=ws,
            event_bus=self.bus,
        )
        sids = skill_ids or ["gov_doc_format"]

        if not skip_checks:
            chk = check_completeness(self.model, user_message)
            if not chk.get("is_complete", True):
                self.bus.publish(
                    {
                        "type": "clarification_needed",
                        "question": str(chk.get("question") or "请补充更多信息。"),
                    }
                )
                return ""

        todos = decompose_to_todos(self.model, user_message)
        self.bus.publish({"type": "todo_list", "tasks": todos})

        system = self.context.build_main(user_id, sids, ws)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]
        tools = self.tools.to_openai_tools()

        final_text = ""
        for _ in range(self.max_tool_rounds):
            data = self.model.complete(messages, tools=tools, temperature=0.4)
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            tcalls = self._parse_tool_calls(msg)
            if not tcalls:
                final_text = (msg.get("content") or "").strip()
                break
            messages.append(msg)
            for tc in tcalls:
                self.bus.publish(
                    {
                        "type": "task_start",
                        "task_id": tc["id"],
                        "agent_name": tc["name"],
                    }
                )
                res = self.tools.execute(tc["name"], tc["arguments"], ctx)
                self.bus.publish(
                    {
                        "type": "task_done" if res.ok else "task_failed",
                        "task_id": tc["id"],
                        "result": res.output,
                        "error": res.error or "",
                    }
                )
                payload = res.output if res.ok else (res.error or "error")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": payload if isinstance(payload, str) else json.dumps(res.data, ensure_ascii=False),
                    }
                )
                if res.data.get("path"):
                    self.bus.publish(
                        {
                            "type": "artifact_done",
                            "filename": tc["arguments"].get("name", ""),
                            "path": res.data["path"],
                            "editable": True,
                        }
                    )

        if final_text:
            self.bus.publish({"type": "final_answer", "content": final_text})
        self.sessions.append(
            user_id,
            session_id,
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": final_text},
        )
        return final_text
