from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .registry import AgentRegistry, canonical_agent_name, get_agent_spec
from app.a2a_runtime import ExecutionPlan, build_execution_plan as build_fallback_execution_plan
from app.config import settings
from app.debug_log import log_stage
from app.llm import LLMCallError, call_chat_model_with_messages_raw
from app.skills import MemoryToolset, WorkspaceCliToolset
from tools.agent_tool import AgentTool


class MainAgent:
    def __init__(self) -> None:
        self.registry = AgentRegistry
        self.agent_tool = AgentTool()
        self.workspace_cli = WorkspaceCliToolset()
        self.memory_tools = MemoryToolset()

    def plan(
        self,
        user_message: str,
        requested_model: str | None,
        *,
        attachments: list[dict[str, Any]] | None = None,
        runtime_context: dict | None = None,
        memory_context: dict | None = None,
        direct_agent: str | None = None,
        on_planner_stream: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[ExecutionPlan, dict[str, Any]]:
        attachments = attachments or []
        canonical_direct_agent = canonical_agent_name(direct_agent)
        if direct_agent and not canonical_direct_agent:
            raise ValueError(f"未知 skill: {direct_agent}")
        if canonical_direct_agent and canonical_direct_agent != "general":
            plan = build_fallback_execution_plan(user_message, canonical_direct_agent, attachments)
            return plan, {
                "planner": "direct_subagent_dispatch",
                "fallback": False,
                "requestedSkill": canonical_direct_agent,
                "dispatchMode": "direct_subagent",
            }
        if not settings.enable_model_planner:
            plan = build_fallback_execution_plan(user_message, None, attachments)
            return plan, {
                "planner": "main_agent_direct_disabled",
                "fallback": True,
                "dispatchMode": "main_agent_direct",
            }

        messages = self._build_messages(user_message, attachments, runtime_context, memory_context)
        tool_schemas = self._tool_schemas()
        log_stage(
            "planner.request",
            {
                "requestedModel": settings.planner_model or requested_model,
                "messages": messages,
                "toolSchema": tool_schemas,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        try:
            response, planner_cli_events, inline_outcomes, inline_artifacts = self._run_planner_tool_loop(
                messages,
                requested_model,
                runtime_context,
                attachments=attachments,
                memory_context=memory_context,
                on_planner_stream=on_planner_stream,
            )
            plan, planner_meta = self._plan_from_response(
                user_message,
                response,
                attachments,
                planner_cli_events=planner_cli_events,
                inline_outcomes=inline_outcomes,
                inline_artifacts=inline_artifacts,
            )
            log_stage(
                "planner.response",
                {
                    "normalizedPlan": {
                        "intent": plan.intent,
                        "summary": plan.summary,
                        "steps": [
                            {
                                "index": step.index,
                                "skillName": step.skill_name,
                                "title": step.title,
                                "objective": step.objective,
                                "scope": step.scope,
                                "dependsOn": step.depends_on,
                                "subtaskRole": step.subtask_role,
                            }
                            for step in plan.steps
                        ],
                    },
                    "plannerMeta": planner_meta,
                    "modelName": response["model_name"],
                },
                enabled=settings.debug_runtime_logs,
                max_chars=settings.debug_log_max_chars,
                max_string_chars=settings.debug_log_max_string_chars,
            )
            return plan, planner_meta
        except (LLMCallError, ValueError, json.JSONDecodeError) as exc:
            fallback_plan = build_fallback_execution_plan(user_message, None, attachments)
            log_stage(
                "planner.fallback",
                {
                    "reason": str(exc),
                    "fallbackPlan": {
                        "intent": fallback_plan.intent,
                        "summary": fallback_plan.summary,
                        "steps": [step.skill_name for step in fallback_plan.steps],
                    },
                },
                enabled=settings.debug_runtime_logs,
                max_chars=settings.debug_log_max_chars,
                max_string_chars=settings.debug_log_max_string_chars,
            )
            return fallback_plan, {
                "planner": "main_agent_fallback",
                "fallback": True,
                "error": str(exc),
                "dispatchMode": "main_agent_direct",
            }

    def leader_step(
        self,
        messages: list[dict[str, Any]],
        requested_model: str | None,
        *,
        on_stream_event: Callable[[dict[str, Any]], None] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Leader 闭环：在完整 messages（含 tool 结果）上再调一次 Planner 模型以决策下一步。"""
        tool_schemas = self._tool_schemas()
        return call_chat_model_with_messages_raw(
            messages,
            settings.planner_model or requested_model,
            purpose="leader_step",
            temperature=settings.planner_temperature,
            extra_payload={
                "tools": tool_schemas,
                "tool_choice": "auto",
            },
            stream=stream,
            on_stream_event=on_stream_event,
        )

    def _build_messages(
        self,
        user_message: str,
        attachments: list[dict[str, Any]],
        runtime_context: dict | None,
        memory_context: dict | None,
    ) -> list[dict[str, str]]:
        recent_messages = runtime_context.get("recent_messages") if runtime_context else []
        context_lines = [f"当前用户输入：{user_message}", f"附件数量：{len(attachments)}"]
        if attachments:
            attachment_names = [item.get("name") or item.get("title") or "附件" for item in attachments]
            context_lines.append("附件列表：" + "、".join(attachment_names))
        if runtime_context and runtime_context.get("summary"):
            context_lines.append("运行摘要：")
            context_lines.append(runtime_context["summary"])
        pending_task = runtime_context.get("pending_task") if runtime_context else None
        if pending_task:
            context_lines.append("存在等待中的任务：")
            context_lines.append(
                "- skill: "
                f"{pending_task.get('skillName') or 'unknown'}"
                f" | title: {pending_task.get('title') or '待处理任务'}"
                f" | resume_mode: {pending_task.get('resumeMode') or 'unknown'}"
            )
        pending_question = runtime_context.get("pending_question") if runtime_context else None
        if pending_question:
            context_lines.append("上一轮待回答的问题：")
            context_lines.append(str(pending_question))
        pending_answer = runtime_context.get("user_answer_to_pending") if runtime_context else None
        if pending_answer:
            context_lines.append("当前消息可能是在回答上一轮澄清，请优先判断是否应继续 pending task：")
            context_lines.append(str(pending_answer))
        if recent_messages:
            context_lines.append("最近消息：")
            for item in recent_messages[-4:]:
                context_lines.append(f"- {(item.get('role') or 'unknown')}: {(item.get('content') or '').strip()}")
        if memory_context:
            identify_md = (memory_context.get("identify_markdown") or "").strip()
            memory_md = (memory_context.get("memory_markdown") or "").strip()
            session_summary_md = (memory_context.get("session_summary_markdown") or "").strip()
            if identify_md:
                context_lines.append("identify.md：")
                context_lines.append(identify_md)
            if memory_md:
                context_lines.append("memory.md：")
                context_lines.append(memory_md)
            if session_summary_md:
                context_lines.append("session_summary.md：")
                context_lines.append(session_summary_md)
        return [
            {"role": "system", "content": self._build_main_system_prompt()},
            {"role": "user", "content": "\n".join(context_lines)},
        ]

    def _build_main_system_prompt(self) -> str:
        prompts_root = get_agent_spec("general").prompt_path.parent.parent
        lead_path = prompts_root / "LEAD.md"
        legacy_path = prompts_root / "main_system.md"
        prompt_path = lead_path if lead_path.exists() else legacy_path
        base = prompt_path.read_text(encoding="utf-8").strip()
        return base.replace("{{AGENT_REGISTRY_CONTEXT}}", self.registry.to_prompt_context())

    def _tool_schemas(self) -> list[dict[str, Any]]:
        return [
            self.agent_tool.get_tool_schema(),
            *self.workspace_cli.tool_schemas(),
            *self.memory_tools.tool_schemas(),
        ]

    def _call_planner_model(
        self,
        messages: list[dict[str, Any]],
        requested_model: str | None,
        *,
        purpose: str,
        on_planner_stream: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        use_stream = on_planner_stream is not None

        def _stream_cb(ev: dict[str, Any]) -> None:
            if on_planner_stream:
                on_planner_stream(ev)

        response = call_chat_model_with_messages_raw(
            messages,
            settings.planner_model or requested_model,
            purpose=purpose,
            temperature=settings.planner_temperature,
            extra_payload={
                "tools": self._tool_schemas(),
                "tool_choice": "auto",
            },
            stream=use_stream,
            on_stream_event=_stream_cb if use_stream else None,
        )
        message = response.get("message") or {}
        if on_planner_stream:
            on_planner_stream(
                {
                    "reasoning": self._message_reasoning(message),
                    "text": self._message_text(message),
                    "flush": True,
                }
            )
        return response

    def _run_planner_tool_loop(
        self,
        messages: list[dict[str, Any]],
        requested_model: str | None,
        runtime_context: dict[str, Any] | None,
        *,
        attachments: list[dict[str, Any]] | None = None,
        memory_context: dict | None = None,
        on_planner_stream: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Flat agent loop：所有工具调用（workspace.* / memory.* / dispatch_sub_agent）
        都在同一循环中执行并把结构化 tool_result 回灌给模型，直到模型不再发起
        tool_calls 或达到 ``settings.planner_max_tool_rounds``。
        """
        cli_events: list[dict[str, Any]] = []
        inline_outcomes: list[dict[str, Any]] = []
        inline_artifacts: list[dict[str, Any]] = []
        attachments = attachments or []

        response = self._call_planner_model(
            messages,
            requested_model,
            purpose="planner",
            on_planner_stream=on_planner_stream,
        )
        max_rounds = max(1, int(settings.planner_max_tool_rounds or 1))
        for round_index in range(max_rounds):
            message = response.get("message") or {}
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return response, cli_events, inline_outcomes, inline_artifacts

            tool_messages: list[dict[str, Any]] = []
            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                name = function.get("name") or ""
                arguments = json.loads(function.get("arguments") or "{}")
                if name.startswith("workspace."):
                    execution = self.workspace_cli.execute(name, arguments, runtime_context)
                    cli_events.append(execution.runtime_event())
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(execution.tool_message(), ensure_ascii=False),
                        }
                    )
                    continue
                if name.startswith("memory."):
                    execution = self.memory_tools.execute(name, arguments, runtime_context)
                    cli_events.append(execution.runtime_event())
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(execution.tool_message(), ensure_ascii=False),
                        }
                    )
                    continue
                if name == self.agent_tool.tool_name:
                    tool_result = self.agent_tool.execute(
                        arguments,
                        requested_model=requested_model,
                        attachments=attachments,
                        cookies=(runtime_context or {}).get("cookies"),
                        runtime_context=runtime_context,
                        memory_context=memory_context,
                        task_packet=(runtime_context or {}).get("task_packet"),
                    )
                    outcome_index = len(inline_outcomes) + 1
                    skill_result = tool_result.pop("_skill_execution_result", None)
                    outcome = self._inline_outcome_from_tool_result(
                        index=outcome_index,
                        arguments=arguments,
                        tool_result=tool_result,
                        skill_result=skill_result,
                        requested_model=requested_model or "",
                    )
                    inline_outcomes.append(outcome)
                    if skill_result is not None:
                        inline_artifacts.extend(skill_result.artifact_refs or [])
                    compact_payload = {
                        "agent": tool_result.get("agent"),
                        "status": tool_result.get("status"),
                        "summary": tool_result.get("summary"),
                        "artifacts": tool_result.get("artifacts"),
                        "citations": tool_result.get("citations"),
                    }
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(compact_payload, ensure_ascii=False),
                        }
                    )
                    continue
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(
                            {"status": "error", "error": f"unsupported_tool:{name}"},
                            ensure_ascii=False,
                        ),
                    }
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": self._message_text(message) or None,
                    "tool_calls": tool_calls,
                }
            )
            messages.extend(tool_messages)
            response = self._call_planner_model(
                messages,
                requested_model,
                purpose=f"planner_tool_round_{round_index + 2}",
                on_planner_stream=on_planner_stream,
            )
        log_stage(
            "planner.max_rounds_reached",
            {"maxRounds": max_rounds, "inlineOutcomes": len(inline_outcomes)},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return response, cli_events, inline_outcomes, inline_artifacts

    def _inline_outcome_from_tool_result(
        self,
        *,
        index: int,
        arguments: dict[str, Any],
        tool_result: dict[str, Any],
        skill_result: Any,
        requested_model: str,
    ) -> dict[str, Any]:
        from app.a2a_runtime import title_for_skill
        from app.agent_capability_adapter import render_assistant_html

        agent_name = tool_result.get("agent") or arguments.get("agent_name") or "general"
        status = tool_result.get("status") or "ok"
        summary_text = tool_result.get("summary") or ""
        text_payload = tool_result.get("text") or summary_text
        normalized_result = {}
        annotations = []
        retryable = False
        source_state = "model_success"
        error_detail = tool_result.get("error")
        reasoning_content = None
        html = ""
        if skill_result is not None:
            normalized_result = skill_result.normalized_result or {}
            annotations = skill_result.editor_annotations or []
            retryable = bool(skill_result.retryable)
            source_state = skill_result.source_state or "model_success"
            error_detail = skill_result.error_detail or error_detail
            reasoning_content = skill_result.reasoning_content
            try:
                html = render_assistant_html(agent_name, skill_result, requested_model)
            except Exception:  # pragma: no cover
                html = ""
        else:
            normalized_result = {"summary": summary_text, "text": text_payload}
            if status == "error":
                source_state = "model_error"
        return {
            "index": index,
            "task_id": f"inline_{index:02d}_{agent_name}",
            "skill_name": agent_name,
            "title": title_for_skill(agent_name),
            "summary": summary_text or title_for_skill(agent_name),
            "html": html,
            "normalized_result": normalized_result,
            "annotations": annotations,
            "retryable": retryable,
            "source_state": source_state,
            "error_detail": error_detail,
            "reasoning_content": reasoning_content,
            "inline": True,
        }

    def _plan_from_response(
        self,
        user_message: str,
        response: dict[str, Any],
        attachments: list[dict[str, Any]],
        planner_cli_events: list[dict[str, Any]] | None = None,
        inline_outcomes: list[dict[str, Any]] | None = None,
        inline_artifacts: list[dict[str, Any]] | None = None,
    ) -> tuple[ExecutionPlan, dict[str, Any]]:
        """Flat loop 下 `tool_calls` 已在 `_run_planner_tool_loop` 内执行并回灌，
        本函数只需要把 loop 尾巴的 assistant text / inline outcomes 映射成外层
        runtime 需要的 ExecutionPlan 语义——当有 inline outcomes 时返回 direct_plan
        （空 steps），通过 `planner_meta` 携带 outcomes，让 runtime 跳过旧的
        `ExecutionPlan.steps` 迭代逻辑。
        """
        message = response.get("message") or {}
        assistant_text = self._message_text(message).strip()
        reasoning_content = self._message_reasoning(message).strip()
        direct_plan = build_fallback_execution_plan(user_message, None, attachments)
        inline_outcomes = inline_outcomes or []
        inline_artifacts = inline_artifacts or []

        if inline_outcomes:
            summary = (
                assistant_text
                or f"主 Agent 内联执行了 {len(inline_outcomes)} 个子 agent，已汇总结果。"
            )
            direct_plan.summary = summary
            return (
                direct_plan,
                {
                    "planner": "main_agent_flat_loop",
                    "fallback": False,
                    "dispatchMode": "flat_tool_loop",
                    "modelName": response["model_name"],
                    "plannerCliEvents": planner_cli_events or [],
                    "assistantText": assistant_text,
                    "reasoningContent": reasoning_content,
                    "directAnswer": assistant_text,
                    "inlineStepOutcomes": inline_outcomes,
                    "inlineArtifacts": inline_artifacts,
                    "raw": response["raw"],
                },
            )

        summary = assistant_text or "主 Agent 直接回答当前问题，无需调度 sub agent。"
        direct_plan.summary = summary
        return (
            direct_plan,
            {
                "planner": "main_agent_direct_answer",
                "fallback": False,
                "dispatchMode": "main_agent_direct",
                "modelName": response["model_name"],
                "plannerCliEvents": planner_cli_events or [],
                "assistantText": assistant_text,
                "reasoningContent": reasoning_content,
                "directAnswer": assistant_text,
                "raw": response["raw"],
            },
        )

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
            )
        return ""

    @staticmethod
    def _message_reasoning(message: dict[str, Any]) -> str:
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str):
            return reasoning
        if isinstance(reasoning, list):
            return "\n".join(
                item.get("text", "")
                for item in reasoning
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
            )
        return ""

