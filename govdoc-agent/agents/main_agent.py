from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .registry import AgentRegistry, canonical_agent_name, get_agent_spec
from app.a2a_runtime import ExecutionPlan, ExecutionStep, build_execution_plan as build_fallback_execution_plan
from app.config import settings
from app.debug_log import log_stage
from app.llm import LLMCallError, call_chat_model_with_messages_raw
from tools.agent_tool import AgentTool


class MainAgent:
    def __init__(self) -> None:
        self.registry = AgentRegistry
        self.agent_tool = AgentTool()

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
        tool_schema = self.agent_tool.get_tool_schema()
        log_stage(
            "planner.request",
            {
                "requestedModel": settings.planner_model or requested_model,
                "messages": messages,
                "toolSchema": tool_schema,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        try:
            use_stream = on_planner_stream is not None

            def _stream_cb(ev: dict[str, Any]) -> None:
                if on_planner_stream:
                    on_planner_stream(ev)

            response = call_chat_model_with_messages_raw(
                messages,
                settings.planner_model or requested_model,
                purpose="planner",
                temperature=settings.planner_temperature,
                extra_payload={
                    "tools": [tool_schema],
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
            plan, planner_meta = self._plan_from_response(user_message, response, attachments)
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
        tool_schema = self.agent_tool.get_tool_schema()
        return call_chat_model_with_messages_raw(
            messages,
            settings.planner_model or requested_model,
            purpose="leader_step",
            temperature=settings.planner_temperature,
            extra_payload={
                "tools": [tool_schema],
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
        prompt = get_agent_spec("general").prompt_path.parent.parent / "main_system.md"
        base = prompt.read_text(encoding="utf-8").strip()
        return base.replace("{{AGENT_REGISTRY_CONTEXT}}", self.registry.to_prompt_context())

    def _plan_from_response(
        self,
        user_message: str,
        response: dict[str, Any],
        attachments: list[dict[str, Any]],
    ) -> tuple[ExecutionPlan, dict[str, Any]]:
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        assistant_text = self._message_text(message).strip()
        reasoning_content = self._message_reasoning(message).strip()
        if tool_calls:
            steps: list[ExecutionStep] = []
            previous_step_ids: list[str] = []
            for index, tool_call in enumerate(tool_calls, start=1):
                function = tool_call.get("function") or {}
                if function.get("name") != self.agent_tool.tool_name:
                    continue
                arguments = json.loads(function.get("arguments") or "{}")
                step = self.agent_tool.to_execution_step(
                    arguments,
                    index=index,
                    previous_step_ids=previous_step_ids,
                )
                steps.append(step)
                previous_step_ids.append(f"step_{index:02d}_{step.skill_name}")
            if not steps:
                raise ValueError("主 Agent 返回了空的 sub-agent 调度计划")
            steps, normalization = self._normalize_document_steps(user_message, steps, reasoning_content)
            summary = assistant_text or f"主 Agent 已规划 {len(steps)} 个 sub-agent 步骤。"
            return (
                ExecutionPlan(
                    intent="document_workflow",
                    summary=summary,
                    steps=steps,
                ),
                {
                    "planner": "main_agent_tool_calls",
                    "fallback": False,
                    "dispatchMode": "tool_call_dispatch",
                    "modelName": response["model_name"],
                    "toolCalls": tool_calls,
                    "assistantText": assistant_text,
                    "reasoningContent": reasoning_content,
                    "normalization": normalization,
                    "raw": response["raw"],
                },
            )

        direct_plan = build_fallback_execution_plan(user_message, None, attachments)
        summary = assistant_text or "主 Agent 直接回答当前问题，无需调度 sub agent。"
        direct_plan.summary = summary
        return (
            direct_plan,
            {
                "planner": "main_agent_direct_answer",
                "fallback": False,
                "dispatchMode": "main_agent_direct",
                "modelName": response["model_name"],
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

    @staticmethod
    def _looks_like_writing_request(user_message: str) -> bool:
        text = (user_message or "").strip()
        if not text:
            return False
        strong_markers = (
            "不是只检索",
            "帮我写",
            "写一篇",
            "起草",
            "撰写",
            "生成",
        )
        doc_markers = (
            "报告",
            "通知",
            "方案",
            "请示",
            "总结",
            "汇报",
            "发言稿",
            "讲话稿",
            "公文",
            "正文",
        )
        return any(marker in text for marker in strong_markers) or (
            any(marker in text for marker in ("写", "起草", "撰写", "生成"))
            and any(marker in text for marker in doc_markers)
        )

    def _normalize_document_steps(
        self,
        user_message: str,
        steps: list[ExecutionStep],
        reasoning_content: str = "",
    ) -> tuple[list[ExecutionStep], dict[str, Any] | None]:
        if not steps or not self._looks_like_writing_request(user_message):
            return steps, None
        if any(step.skill_name == "writing" for step in steps):
            return steps, None
        if not any(step.skill_name == "retrieval" for step in steps):
            return steps, None

        writing_spec = get_agent_spec("writing")
        depends_on = [f"step_{steps[-1].index:02d}_{steps[-1].skill_name}"]
        normalized_steps = list(steps)
        normalized_steps.append(
            ExecutionStep(
                index=len(normalized_steps) + 1,
                skill_name=writing_spec.name,
                title=writing_spec.title,
                objective=(
                    "根据前序检索结果与用户需求，起草完整公文正文；"
                    "若用户明确要求的是报告，则输出报告草稿。"
                ),
                scope=writing_spec.scope,
                depends_on=depends_on,
                subtask_role=writing_spec.default_subtask_role,
            )
        )
        return normalized_steps, {
            "type": "append_writing_after_retrieval",
            "reason": "user_requires_document_draft",
            "dependsOn": depends_on,
            "reasoningMentionsWriting": "writing" in reasoning_content.lower() or "写" in reasoning_content,
        }
