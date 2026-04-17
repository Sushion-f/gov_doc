from __future__ import annotations

from typing import Any

from app.a2a_runtime import ExecutionStep, title_for_skill
from agents.registry import get_agent_spec, selectable_sub_agents


class AgentTool:
    tool_name = "dispatch_sub_agent"

    def get_tool_schema(self) -> dict:
        agent_names = [item.name for item in selectable_sub_agents()]
        return {
            "type": "function",
            "function": {
                "name": self.tool_name,
                "description": "调度指定的 Sub Agent 执行子任务，返回结果后继续主流程。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "enum": agent_names,
                            "description": "要调用的 Sub Agent 名称。",
                        },
                        "task_prompt": {
                            "type": "string",
                            "description": "给 Sub Agent 的自包含任务描述。",
                        },
                        "context": {
                            "type": "object",
                            "description": "需要传给 Sub Agent 的上下文数据。",
                            "properties": {
                                "doc_content": {"type": "string"},
                                "doc_type": {"type": "string"},
                                "user_intent": {"type": "string"},
                            },
                        },
                        "run_in_background": {
                            "type": "boolean",
                            "default": False,
                            "description": "是否后台异步执行。",
                        },
                    },
                    "required": ["agent_name", "task_prompt"],
                    "additionalProperties": False,
                },
            },
        }

    def to_execution_step(
        self,
        arguments: dict[str, Any],
        *,
        index: int,
        previous_step_ids: list[str],
    ) -> ExecutionStep:
        agent_name = arguments.get("agent_name")
        agent = get_agent_spec(agent_name)
        context = arguments.get("context") or {}
        task_prompt = (arguments.get("task_prompt") or "").strip()
        objective = task_prompt or agent.default_objective
        if context.get("user_intent"):
            objective = f"{objective}\n用户意图：{context['user_intent']}"
        return ExecutionStep(
            index=index,
            skill_name=agent.name,
            title=title_for_skill(agent.name),
            objective=objective,
            scope=agent.scope,
            depends_on=list(previous_step_ids),
            subtask_role=agent.default_subtask_role,
        )

    def call(
        self,
        *,
        agent_name: str,
        task_prompt: str,
        requested_model: str | None,
        attachments: list[dict],
        cookies: str | None,
        runtime_context: dict | None,
        memory_context: dict | None,
        task_packet: dict | None,
        on_text_delta=None,
    ):
        from app.agent_capability_adapter import execute_skill

        return execute_skill(
            agent_name,
            task_prompt,
            requested_model,
            attachments,
            cookies,
            runtime_context=runtime_context,
            memory_context=memory_context,
            task_packet=task_packet,
            on_text_delta=on_text_delta,
        )
