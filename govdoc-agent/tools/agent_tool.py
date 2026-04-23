from __future__ import annotations

from typing import Any, Callable

from app.a2a_runtime import ExecutionStep, title_for_skill
from app.config import settings
from agents.registry import get_agent_spec, selectable_sub_agents


class AgentTool:
    tool_name = "dispatch_sub_agent"

    def get_tool_schema(self) -> dict:
        agent_names = [item.name for item in selectable_sub_agents()]
        return {
            "type": "function",
            "function": {
                "name": self.tool_name,
                "description": (
                    "调度指定的 Sub Agent 执行一个自包含的子任务。Lead Agent 仅能通过本工具"
                    "把真正的产出工作下发给 Sub Agent；返回结果后必须由 Lead 再做整合。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "enum": agent_names,
                            "description": "要调用的 Sub Agent canonical 名称。",
                        },
                        "task_prompt": {
                            "type": "string",
                            "minLength": 8,
                            "description": (
                                "给 Sub Agent 的自包含任务描述，必须包含：用户最终目标、"
                                "需要产出的交付物、关键格式或字数约束。"
                            ),
                        },
                        "context": {
                            "type": "object",
                            "description": "需要传给 Sub Agent 的结构化上下文。",
                            "properties": {
                                "doc_content": {
                                    "type": "string",
                                    "description": "已有文档正文或草稿片段。",
                                },
                                "doc_type": {
                                    "type": "string",
                                    "description": "公文类型（通知/请示/报告 等）。",
                                },
                                "user_intent": {
                                    "type": "string",
                                    "description": "用户一句话目标。",
                                },
                                "context_brief": {
                                    "type": "string",
                                    "description": "已确认的背景要点 / 前序步骤摘要。",
                                },
                            },
                            "additionalProperties": False,
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "本步骤依赖的前序 step id 列表，可留空。",
                        },
                        "run_in_background": {
                            "type": "boolean",
                            "default": False,
                            "description": "是否允许异步后台执行。",
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
        if not agent_name:
            raise ValueError("dispatch_sub_agent 缺少 agent_name")
        agent = get_agent_spec(agent_name)
        context = arguments.get("context") or {}
        task_prompt = (arguments.get("task_prompt") or "").strip()
        if len(task_prompt) < 8:
            raise ValueError(f"dispatch_sub_agent 的 task_prompt 过短（agent={agent_name}）")
        objective = task_prompt or agent.default_objective
        if context.get("user_intent"):
            objective = f"{objective}\n用户意图：{context['user_intent']}"
        if context.get("context_brief"):
            objective = f"{objective}\n背景要点：{context['context_brief']}"
        depends_on = arguments.get("depends_on")
        if isinstance(depends_on, list) and depends_on:
            dependency_ids = [str(item) for item in depends_on if item]
        else:
            dependency_ids = list(previous_step_ids)
        return ExecutionStep(
            index=index,
            skill_name=agent.name,
            title=title_for_skill(agent.name),
            objective=objective,
            scope=agent.scope,
            depends_on=dependency_ids,
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

    def execute(
        self,
        arguments: dict[str, Any],
        *,
        requested_model: str | None,
        attachments: list[dict] | None = None,
        cookies: str | None = None,
        runtime_context: dict | None = None,
        memory_context: dict | None = None,
        task_packet: dict | None = None,
        on_text_delta: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        """作为 Claude SDK 风格的 tool 执行接口：返回结构化 tool_result payload。

        - 复用 `app.agent_capability_adapter.execute_skill` 的模型调用与校验；
        - 使用 `settings.subagent_max_depth` 做递归深度护栏；
        - 返回值形状：`{agent, status, summary, artifacts, citations, text, usage, error?}`。
        """
        from app.agent_capability_adapter import execute_skill

        agent_name = (arguments.get("agent_name") or "").strip()
        task_prompt = (arguments.get("task_prompt") or "").strip()
        if not agent_name:
            return {
                "agent": "",
                "status": "error",
                "summary": "缺少 agent_name",
                "artifacts": [],
                "citations": [],
                "text": "dispatch_sub_agent 调用参数不合法：缺少 agent_name。",
                "usage": {},
                "error": "missing_agent_name",
            }
        try:
            spec = get_agent_spec(agent_name)
        except ValueError:
            return {
                "agent": agent_name,
                "status": "error",
                "summary": f"未知 Sub Agent: {agent_name}",
                "artifacts": [],
                "citations": [],
                "text": f"未注册的 Sub Agent：{agent_name}。",
                "usage": {},
                "error": "unknown_agent",
            }
        if len(task_prompt) < 8:
            return {
                "agent": spec.name,
                "status": "error",
                "summary": "task_prompt 过短",
                "artifacts": [],
                "citations": [],
                "text": "dispatch_sub_agent 的 task_prompt 不能为空或过短。",
                "usage": {},
                "error": "task_prompt_too_short",
            }

        current_depth = int((runtime_context or {}).get("dispatch_depth") or 0)
        max_depth = max(0, int(getattr(settings, "subagent_max_depth", 3) or 3))
        if current_depth >= max_depth:
            return {
                "agent": spec.name,
                "status": "error",
                "summary": "sub-agent 调度深度超限",
                "artifacts": [],
                "citations": [],
                "text": (
                    f"已达到 sub-agent 调度最大深度 {max_depth}，不再继续派发。"
                    "请由当前 Agent 直接合成最终答复。"
                ),
                "usage": {},
                "error": "max_dispatch_depth_exceeded",
            }

        context_extra = arguments.get("context") or {}
        enriched_prompt = task_prompt
        if isinstance(context_extra, dict):
            if context_extra.get("user_intent"):
                enriched_prompt = f"{enriched_prompt}\n用户意图：{context_extra['user_intent']}"
            if context_extra.get("context_brief"):
                enriched_prompt = f"{enriched_prompt}\n背景要点：{context_extra['context_brief']}"
            if context_extra.get("doc_content"):
                enriched_prompt = f"{enriched_prompt}\n现有正文：\n{context_extra['doc_content']}"

        nested_ctx = dict(runtime_context or {})
        nested_ctx["dispatch_depth"] = current_depth + 1

        try:
            result = execute_skill(
                spec.name,
                enriched_prompt,
                requested_model,
                list(attachments or []),
                cookies,
                runtime_context=nested_ctx,
                memory_context=memory_context,
                task_packet=task_packet,
                on_text_delta=on_text_delta,
            )
        except Exception as exc:  # pragma: no cover - 保底兜底
            return {
                "agent": spec.name,
                "status": "error",
                "summary": f"Sub Agent 执行异常：{exc}",
                "artifacts": [],
                "citations": [],
                "text": str(exc) or "Sub Agent 执行异常",
                "usage": {},
                "error": "execution_exception",
            }

        normalized = dict(result.normalized_result or {})
        artifacts = [
            {
                "artifact_id": item.get("artifact_id") or item.get("id") or "",
                "title": item.get("title") or "",
                "version": item.get("version"),
                "workspace_node_id": item.get("workspace_node_id") or item.get("nodeId"),
            }
            for item in (result.artifact_refs or [])
        ]
        citations = list(normalized.get("citations") or [])
        summary_text = (
            normalized.get("summary")
            or normalized.get("answer")
            or normalized.get("abstract")
            or ""
        )
        document_text = str(normalized.get("document") or "").strip()
        text_payload = str(summary_text or document_text or "").strip()
        if not text_payload and result.render_blocks:
            text_payload = str(result.render_blocks[0].get("html") or "").strip()

        status: str
        if result.source_state == "model_error":
            status = "error"
        elif result.prompt_menu:
            status = "needs_user_input"
        else:
            status = "ok"

        payload: dict[str, Any] = {
            "agent": spec.name,
            "status": status,
            "summary": text_payload[:400],
            "artifacts": artifacts,
            "citations": citations,
            "text": text_payload,
            "usage": {},
        }
        if result.prompt_menu:
            payload["prompt_menu"] = result.prompt_menu
        if result.error_detail:
            payload["error"] = result.error_detail
        payload["_skill_execution_result"] = result
        return payload
