"""
会话（对话）API：列表、详情、创建、重命名、删除，以及 **运行** 与 **SSE 事件流**。

- 前缀：/api/agentloop/conversations
- POST /{id}/run：同步返回 runId + streamUrl，实际生成在 BackgroundTasks（execute_prepared_run）
- GET /{id}/events：text/event-stream，按 seq_no 递增推送 V4TaskEvent，结束发送 data: [DONE]

事件展示辅助：_event_display_payload 为前端时间线卡片生成 display 字段。
"""

import json
import time
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import SessionLocal, get_db
from ..config import settings
from ..debug_log import log_stage, mask_cookie
from ..models import (
    V4CompressionSnapshot,
    V4Conversation,
    V4ConversationArtifact,
    V4ConversationMessage,
    V4ConversationRun,
    V4TaskEvent,
)
from ..runtime import (
    _artifact_contract_from_record,
    build_runtime_context,
    execute_prepared_run,
    maybe_compact_conversation,
    prepare_run_conversation,
    summarize_conversation_title_after_run,
)
from ..schemas import (
    AgentLoopResponse,
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationRunRequest,
)

router = APIRouter(prefix="/api/agentloop/conversations", tags=["agentloop-conversations"])


CANONICAL_EVENT_TYPES = {
    "message_created",
    "message_delta",
    "message_final",
    "planner_reasoning_delta",
    "planner_plan",
    "agent_invoke",
    "skill_invoke",
    "tool_call",
    "cli_exec",
    "search",
    "context_usage",
    "context_compacted",
    "artifact_created",
    "artifact_updated",
    "waiting_user",
    "error",
    "completed",
    "aborted",
}

TODO_AGENT_LABELS = {
    "retrieval": "检索专家",
    "search": "检索专家",
    "writing": "写作专家",
    "review": "审核专家",
    "dedup": "查重专家",
    "duplicate": "查重专家",
    "layout": "排版专家",
    "format": "排版专家",
    "formatting": "排版专家",
}

TODO_ROLE_TITLES = {
    "retrieval": "检索资料",
    "search": "检索资料",
    "writing": "整理资料并撰写内容",
    "review": "审核内容",
    "dedup": "查重比对",
    "duplicate": "查重比对",
    "layout": "格式化排版",
    "format": "格式化排版",
    "formatting": "格式化排版",
}

FLOW_ACTION_LABELS = {
    "retrieval": {"start": "开始检索资料", "done": "检索结果已返回"},
    "writing": {"start": "开始写作", "done": "写作结果已返回"},
    "review": {"start": "开始审核", "done": "审核结果已返回"},
    "dedup": {"start": "开始查重", "done": "查重结果已返回"},
    "layout": {"start": "开始排版", "done": "排版结果已返回"},
}


def _conversation_or_404(db: Session, conversation_id: str, user_id: str) -> V4Conversation:
    conversation = db.execute(
        select(V4Conversation).where(
            V4Conversation.id == conversation_id,
            V4Conversation.user_id == user_id,
            V4Conversation.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


def _trim_text(value: str | None, limit: int = 120) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _safe_load_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _result_preview(payload: dict) -> str:
    normalized = payload.get("normalizedResult") or {}
    if isinstance(normalized, dict):
        for key in ("message", "text", "summary", "user_clarification", "question"):
            value = normalized.get(key)
            if isinstance(value, str) and value.strip():
                return _trim_text(value.strip())
        items = normalized.get("items") or []
        if isinstance(items, list) and items:
            first = items[0] or {}
            if isinstance(first, dict):
                text = first.get("summary") or first.get("title") or first.get("name")
                if isinstance(text, str) and text.strip():
                    return _trim_text(text.strip())
    error_detail = payload.get("errorDetail")
    if isinstance(error_detail, str) and error_detail.strip():
        return _trim_text(error_detail.strip())
    return "已生成结构化结果，可继续查看或进入下一步。"


def _skill_from_payload(payload: dict, canonical_type: str | None = None) -> str | None:
    task_packet = payload.get("taskPacket") or {}
    registry_packet = (payload.get("registry") or {}).get("taskPacket") or {}
    plan_steps = (payload.get("plan") or {}).get("steps") or []
    plan_step = plan_steps[0] if len(plan_steps) == 1 else {}
    candidates = [
        payload.get("skillName"),
        task_packet.get("skill_name"),
        registry_packet.get("skill_name"),
        plan_step.get("skillName"),
        payload.get("requestedSkill"),
    ]
    if canonical_type == "search":
        candidates.insert(0, "retrieval")
    for item in candidates:
        value = str(item or "").strip().lower()
        if value:
            return value
    title = " ".join(str(item or "") for item in [payload.get("title"), payload.get("summary")])
    lowered = title.lower()
    for key in TODO_AGENT_LABELS:
        if key in lowered:
            return key
    return None


def _normalize_skill_name(value: str | None) -> str:
    skill = str(value or "").strip().lower()
    if skill == "search":
        return "retrieval"
    if skill == "duplicate":
        return "dedup"
    if skill == "format":
        return "layout"
    if skill == "formatting":
        return "layout"
    return skill


def _todo_title_for_skill(skill_name: str | None, fallback: str | None = None) -> str:
    normalized = _normalize_skill_name(skill_name)
    return str(fallback or "").strip() or TODO_ROLE_TITLES.get(normalized) or "执行当前任务"


def _agent_label_for_skill(skill_name: str | None) -> str:
    return TODO_AGENT_LABELS.get(_normalize_skill_name(skill_name), "执行专家")


def _todo_list_from_plan_payload(plan_payload: dict | None, *, completed: bool = False) -> dict | None:
    if not isinstance(plan_payload, dict):
        return None
    raw_steps = plan_payload.get("steps") or []
    if not raw_steps:
        return None
    steps = []
    for index, item in enumerate(raw_steps, start=1):
        skill_name = _normalize_skill_name(item.get("skillName"))
        steps.append(
            {
                "id": f"step_{item.get('index') or index}",
                "title": _todo_title_for_skill(skill_name, item.get("title")),
                "agent_label": _agent_label_for_skill(skill_name),
                "skill_name": skill_name,
                "status": "completed" if completed else "pending",
            }
        )
    return {
        "steps": steps,
        "current_step_id": None if completed else steps[0]["id"],
        "summary": plan_payload.get("summary") or "",
    }


def _latest_todo_list_from_messages(messages: list[V4ConversationMessage], runtime_state: dict) -> dict | None:
    latest = runtime_state.get("latestTodoList")
    if isinstance(latest, dict) and latest.get("steps"):
        return latest
    for message in reversed(messages):
        meta = _safe_load_json(message.meta_json, {})
        leader_plan = meta.get("leaderPlan")
        todo = _todo_list_from_plan_payload(leader_plan, completed=(message.role == "assistant"))
        if todo:
            return todo
    return None


def _update_todo_status(todo_list: dict | None, step_id: str | None, status: str) -> dict | None:
    if not isinstance(todo_list, dict) or not step_id:
        return todo_list
    steps = []
    current_step_id = todo_list.get("current_step_id")
    for item in todo_list.get("steps") or []:
        next_item = dict(item)
        if next_item.get("id") == step_id:
            next_item["status"] = status
        steps.append(next_item)
    if status == "completed":
        pending = next((item for item in steps if item.get("status") not in {"completed", "failed"}), None)
        current_step_id = pending.get("id") if pending else None
    elif status == "running":
        current_step_id = step_id
    return {
        "steps": steps,
        "current_step_id": current_step_id,
        "summary": todo_list.get("summary") or "",
    }


def _step_id_for_skill(todo_list: dict | None, skill_name: str | None) -> str | None:
    normalized = _normalize_skill_name(skill_name)
    if not normalized or not isinstance(todo_list, dict):
        return None
    for item in todo_list.get("steps") or []:
        if _normalize_skill_name(item.get("skill_name")) == normalized:
            return item.get("id")
    return None


def _tool_display_label(payload: dict, event: V4TaskEvent, canonical_type: str, *, completed: bool) -> str:
    command = str(payload.get("command") or payload.get("toolName") or "").strip()
    internal_type = str(payload.get("internalEventType") or "").strip().lower()
    title = str(event.title or "").strip()
    detail = str(event.detail or "").strip()
    command_lower = command.lower()
    if canonical_type == "cli_exec":
        if any(token in command_lower for token in ["workspace.cat", "read", "cat "]):
            return "读取工作区文件"
        if any(token in command_lower for token in ["workspace.ls", "workspace.tree"]):
            return "浏览工作区文件"
        if any(token in command_lower for token in ["workspace.grep"]):
            return "检索工作区内容"
        if any(token in command_lower for token in ["workspace.write"]):
            return "写入工作区文件"
        return "执行工作区命令"
    if "docx" in command_lower or "write-docx" in command_lower or "docx" in internal_type:
        return "生成 DOCX 文件" if not completed else "DOCX 文件已生成"
    if canonical_type == "search":
        return "检索资料" if not completed else "检索结果已返回"
    if "retriev" in title.lower() or "retriev" in detail.lower():
        return "检索资料" if not completed else "检索结果已返回"
    return "调用工具" if not completed else "工具结果已返回"


def _flow_labels_for_skill(skill_name: str | None) -> dict[str, str]:
    normalized = _normalize_skill_name(skill_name)
    return FLOW_ACTION_LABELS.get(
        normalized,
        {
            "start": f"开始{_todo_title_for_skill(normalized)}",
            "done": f"{_todo_title_for_skill(normalized)}已返回",
        },
    )


def _assistant_blocks_from_message(
    message: V4ConversationMessage | None,
    *,
    todo_list: dict | None = None,
    prompt_menu: dict | None = None,
    include_todo: bool = True,
    include_artifacts: bool = True,
) -> list[dict]:
    if message is None:
        return []
    meta = _safe_load_json(message.meta_json, {})
    blocks: list[dict] = []
    planner_reasoning = str(meta.get("plannerReasoning") or "").strip()
    if planner_reasoning:
        blocks.append({"type": "thinking", "text": planner_reasoning})
    if todo_list and include_todo:
        blocks.append({"type": "todo", **todo_list})
    if prompt_menu:
        blocks.append(
            {
                "type": "input_request",
                "question": prompt_menu.get("question") or prompt_menu.get("description") or "请补充必要信息后继续执行。",
                "options": prompt_menu.get("options") or [],
                "missing_fields": prompt_menu.get("missingItems") or [],
                "resume_mode": prompt_menu.get("resumeMode") or "rebuild_todo_list",
            }
        )
    content = str(message.content or "").strip()
    if content:
        blocks.append({"type": "text", "text": content})
    if include_artifacts:
        artifact_refs = meta.get("artifactRefs") or []
        for item in artifact_refs:
            blocks.append({"type": "artifact", **item})
    return blocks


def _protocol_execution_message(
    *,
    event: V4TaskEvent,
    payload: dict,
    canonical_type: str,
    conversation_id: str,
    run_id: str,
    todo_list: dict | None,
) -> tuple[dict | None, str | None, str | None]:
    skill_name = _normalize_skill_name(_skill_from_payload(payload, canonical_type))
    step_id = _step_id_for_skill(todo_list, skill_name)
    timestamp = event.created_at.isoformat()
    if canonical_type == "agent_invoke":
        labels = _flow_labels_for_skill(skill_name)
        return (
            {
                "type": "assistant",
                "session_id": conversation_id,
                "run_id": run_id,
                "timestamp": timestamp,
                "message": {
                    "id": f"assistant-{event.id}",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"toolu-{event.id}",
                            "step_id": step_id,
                            "kind": "sub_agent",
                            "name": skill_name or "general",
                            "display_label": labels["start"],
                            "status": "running",
                            "metadata": {
                                "title": event.title,
                                "detail": event.detail,
                            },
                        }
                    ],
                },
            },
            step_id,
            "running",
        )
    if canonical_type in {"skill_invoke", "search"}:
        labels = _flow_labels_for_skill(skill_name or ("retrieval" if canonical_type == "search" else None))
        return (
            {
                "type": "assistant",
                "session_id": conversation_id,
                "run_id": run_id,
                "timestamp": timestamp,
                "message": {
                    "id": f"assistant-{event.id}",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": f"toolu-{payload.get('taskId') or event.task_id or step_id or event.id}",
                            "step_id": step_id,
                            "kind": "skill",
                            "name": skill_name or ("retrieval" if canonical_type == "search" else "general"),
                            "display_label": labels["done"],
                            "status": "completed",
                            "summary": _result_preview(payload),
                            "metadata": {
                                "title": event.title,
                                "detail": event.detail,
                                "citations": payload.get("citations")
                                or (payload.get("normalizedResult") or {}).get("citations")
                                or (payload.get("normalizedResult") or {}).get("items")
                                or [],
                            },
                        }
                    ],
                },
            },
            step_id,
            "completed",
        )
    if canonical_type in {"cli_exec", "tool_call"}:
        title = str(event.title or "")
        if "A2A Planning" in title or "Leader Agent -> Sub Agent" in title:
            return None, None, None
        completed = event.status == "completed"
        return (
            {
                "type": "assistant",
                "session_id": conversation_id,
                "run_id": run_id,
                "timestamp": timestamp,
                "message": {
                    "id": f"assistant-{event.id}",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_result" if completed else "tool_use",
                            "id": None if completed else f"toolu-{event.id}",
                            "tool_use_id": f"toolu-{event.id}" if completed else None,
                            "step_id": step_id,
                            "kind": "tool",
                            "name": str(payload.get("toolName") or payload.get("command") or canonical_type),
                            "display_label": _tool_display_label(payload, event, canonical_type, completed=completed),
                            "status": "completed" if completed else "running",
                            "summary": _trim_text(event.detail or "") if completed else None,
                            "metadata": {
                                "title": event.title,
                                "detail": event.detail,
                                "command": payload.get("command"),
                            },
                        }
                    ],
                },
            },
            step_id,
            None,
        )
    return None, None, None


def _canonical_event_type(event: V4TaskEvent, payload: dict) -> str:
    raw_type = event.event_type or ""
    title = event.title or ""
    normalized = payload.get("normalizedResult") or {}
    has_search_hits = bool(
        payload.get("citations")
        or (isinstance(normalized, dict) and (normalized.get("citations") or normalized.get("items")))
    )
    if raw_type in {
        "message_created",
        "message_delta",
        "message_final",
        "planner_reasoning_delta",
        "planner_plan",
        "agent_invoke",
        "skill_invoke",
        "cli_exec",
        "search",
        "context_usage",
        "context_compacted",
        "artifact_created",
        "artifact_updated",
        "waiting_user",
        "error",
        "completed",
        "aborted",
    }:
        return raw_type
    if raw_type == "created":
        return "message_created"
    if raw_type == "text_delta":
        return "message_delta"
    if raw_type == "failed":
        return "error"
    if raw_type == "planner_reasoning_delta":
        return "planner_reasoning_delta"
    if raw_type == "context_usage":
        return "context_usage"
    if raw_type == "context_compacted":
        return "context_compacted"
    if raw_type == "cli_exec":
        return "cli_exec"
    if raw_type == "waiting_user":
        return "waiting_user"
    if raw_type == "completed":
        return "completed"
    if raw_type == "conversation_title_updated":
        return "completed"
    if raw_type in {"artifact_created", "artifact_updated", "message_final", "aborted"}:
        return raw_type
    if has_search_hits:
        return "search"
    if raw_type == "running":
        if "执行计划" in title:
            return "planner_plan"
        if title.startswith(("Leader Agent ·", "Sub Agent ·")):
            return "agent_invoke"
        return "tool_call"
    if raw_type == "tool_call":
        if "A2A Planning" in title:
            return "planner_plan"
        if has_search_hits:
            return "search"
        if (
            payload.get("normalizedResult") is not None
            or payload.get("sourceState")
            or title.startswith(("Leader Agent Result ·", "Skill Broker ·", "Prompt Menu Resume ·"))
        ):
            return "skill_invoke"
        return "tool_call"
    return "tool_call"


def _looks_like_simple_writing_payload(payload: dict) -> bool:
    plan = payload.get("plan") or {}
    steps = plan.get("steps") or []
    if len(steps) == 1 and (steps[0].get("skillName") == "writing"):
        return True
    planner_meta = payload.get("plannerMeta") or {}
    if planner_meta.get("planner") == "simple_writing_shortcut":
        return True
    task_packet = payload.get("taskPacket") or {}
    input_payload = task_packet.get("input_payload") or {}
    if task_packet.get("skill_name") == "writing":
        plan_steps = input_payload.get("planSteps") or []
        if not plan_steps or plan_steps == ["writing"]:
            return True
    registry_packet = (payload.get("registry") or {}).get("taskPacket") or {}
    return registry_packet.get("skill_name") == "writing"


def _display_phase_for_event(canonical_type: str, payload: dict) -> tuple[str, str]:
    error_scope = payload.get("errorScope")
    if canonical_type == "planner_plan":
        return "todo", "To do list"
    if canonical_type in {"agent_invoke", "skill_invoke", "tool_call", "cli_exec", "search"}:
        return "write", "写作"
    if canonical_type == "message_final":
        return "result", "返回结果"
    if canonical_type in {"artifact_created", "artifact_updated"} or error_scope == "artifact":
        return "deliverable", "输出内容 / 交付物"
    if canonical_type == "waiting_user":
        return "waiting", "待补充"
    if canonical_type in {"error", "aborted"}:
        return "error", "异常"
    return "result", "返回结果"


def _block_id_for_event(event: V4TaskEvent, prefix: str) -> str:
    return f"{prefix}_{event.id}"


def _tool_use_id_for(event: V4TaskEvent, payload: dict) -> str:
    task_id = payload.get("taskId") or event.task_id or event.id
    return f"toolu_{task_id}"


def _inner_text_blocks(*parts: str | None) -> list[dict]:
    blocks: list[dict] = []
    for part in parts:
        if isinstance(part, str) and part.strip():
            blocks.append({"type": "text", "text": part.strip()})
    return blocks


def _event_to_content_blocks(
    event: V4TaskEvent,
    payload: dict,
    canonical_type: str,
    *,
    message_id: str,
) -> list[dict]:
    """把一条 V4TaskEvent 转成 0..N 个 assistant content block。

    这些 block 与 content_blocks.py 中持久化写入的 schema 保持一致：
    `thinking` / `text` / `tool_use` / `tool_result` / `artifact_ref`
    / `todo_list` / `waiting_user` / `context_notice`。
    前端 store 收到后按 type 累积到 contentBlocks 数组即可。
    """
    timestamp = event.created_at.isoformat()
    base = {"message_id": message_id, "created_at": timestamp}

    if canonical_type == "planner_reasoning_delta":
        reasoning = str(payload.get("reasoningSoFar") or event.detail or "")
        if not reasoning:
            return []
        return [
            {
                **base,
                "id": _block_id_for_event(event, "th"),
                "type": "thinking",
                "thinking": reasoning,
                "update_kind": "replace",
            }
        ]

    if canonical_type == "message_delta":
        tail = str(payload.get("deltaTail") or payload.get("textSoFar") or event.detail or "")
        if not tail:
            return []
        return [
            {
                **base,
                "id": _block_id_for_event(event, "tx_delta"),
                "type": "text",
                "text": tail,
                "update_kind": "replace",
            }
        ]

    if canonical_type == "planner_plan":
        plan = payload.get("plan") or {}
        raw_steps = plan.get("steps") or []
        items: list[dict] = []
        for index, step in enumerate(raw_steps, start=1):
            skill = _normalize_skill_name(step.get("skillName"))
            items.append(
                {
                    "id": f"step_{step.get('index') or index}",
                    "text": _todo_title_for_skill(skill, step.get("title")),
                    "status": "pending",
                }
            )
        if not items:
            return []
        return [
            {
                **base,
                "id": _block_id_for_event(event, "tl"),
                "type": "todo_list",
                "items": items,
            }
        ]

    if canonical_type == "agent_invoke":
        skill = _normalize_skill_name(_skill_from_payload(payload, canonical_type))
        return [
            {
                **base,
                "id": _block_id_for_event(event, "tu"),
                "type": "tool_use",
                "tool_use_id": _tool_use_id_for(event, payload),
                "name": "dispatch_sub_agent",
                "input": {
                    "agent_name": skill or "general",
                    "task_prompt": payload.get("taskPacket", {}).get("objective") or event.detail or "",
                },
                "status": "running",
            }
        ]

    if canonical_type in {"skill_invoke", "search"}:
        skill = _normalize_skill_name(_skill_from_payload(payload, canonical_type)) or (
            "retrieval" if canonical_type == "search" else "general"
        )
        citations = (
            payload.get("citations")
            or (payload.get("normalizedResult") or {}).get("citations")
            or (payload.get("normalizedResult") or {}).get("items")
            or []
        )
        inner = _inner_text_blocks(_result_preview(payload))
        for citation in citations[:6]:
            if isinstance(citation, dict):
                title = citation.get("title") or citation.get("name") or citation.get("summary")
                if title:
                    inner.append({"type": "text", "text": f"• {title}"})
        return [
            {
                **base,
                "id": _block_id_for_event(event, "tr"),
                "type": "tool_result",
                "tool_use_id": _tool_use_id_for(event, payload),
                "is_error": False,
                "name": skill,
                "content": inner or [{"type": "text", "text": event.title or "已返回结果"}],
            }
        ]

    if canonical_type == "cli_exec":
        command = str(payload.get("command") or event.detail or "")
        completed = event.status == "completed"
        if completed:
            return [
                {
                    **base,
                    "id": _block_id_for_event(event, "tr_cli"),
                    "type": "tool_result",
                    "tool_use_id": _tool_use_id_for(event, payload),
                    "is_error": False,
                    "name": "workspace_cli",
                    "content": _inner_text_blocks(event.detail or command or "已执行"),
                }
            ]
        return [
            {
                **base,
                "id": _block_id_for_event(event, "tu_cli"),
                "type": "tool_use",
                "tool_use_id": _tool_use_id_for(event, payload),
                "name": "workspace_cli",
                "input": {"command": command},
                "status": "running",
            }
        ]

    if canonical_type == "tool_call":
        title = str(event.title or "")
        if "A2A Planning" in title or "Leader Agent -> Sub Agent" in title:
            return []
        completed = event.status == "completed"
        tool_name = str(payload.get("toolName") or payload.get("command") or "tool")
        if completed:
            return [
                {
                    **base,
                    "id": _block_id_for_event(event, "tr_tool"),
                    "type": "tool_result",
                    "tool_use_id": _tool_use_id_for(event, payload),
                    "is_error": False,
                    "name": tool_name,
                    "content": _inner_text_blocks(event.detail or ""),
                }
            ]
        return [
            {
                **base,
                "id": _block_id_for_event(event, "tu_tool"),
                "type": "tool_use",
                "tool_use_id": _tool_use_id_for(event, payload),
                "name": tool_name,
                "input": {"command": payload.get("command")},
                "status": "running",
            }
        ]

    if canonical_type in {"artifact_created", "artifact_updated"}:
        artifact_id = payload.get("id") or payload.get("artifactId")
        if not artifact_id:
            return []
        return [
            {
                **base,
                "id": _block_id_for_event(event, "ar"),
                "type": "artifact_ref",
                "artifact_id": str(artifact_id),
                "title": str(payload.get("title") or "产物"),
                "version": payload.get("versionNo") or payload.get("version"),
                "workspace_node_id": payload.get("workspaceNodeId") or payload.get("nodeId"),
                "summary": payload.get("summary"),
            }
        ]

    if canonical_type == "waiting_user":
        prompt_menu = payload.get("promptMenu") or {}
        return [
            {
                **base,
                "id": _block_id_for_event(event, "wu"),
                "type": "waiting_user",
                "prompt_menu": prompt_menu,
            }
        ]

    if canonical_type == "context_compacted":
        return [
            {
                **base,
                "id": _block_id_for_event(event, "cn_compact"),
                "type": "context_notice",
                "kind": "compact",
                "before": payload.get("contextUsageBefore"),
                "after": payload.get("contextUsageAfter"),
                "summary": (payload.get("summary") or "")[:400],
            }
        ]

    if canonical_type == "context_usage":
        return [
            {
                **base,
                "id": _block_id_for_event(event, "cn_usage"),
                "type": "context_notice",
                "kind": "usage",
                "before": None,
                "after": {"used": payload.get("used"), "window": payload.get("window")},
                "summary": None,
            }
        ]

    return []


def _event_display_payload(event: V4TaskEvent) -> dict:
    payload = json.loads(event.payload_json or "{}")
    canonical_type = _canonical_event_type(event, payload)
    title = event.title or ""
    task_packet = payload.get("taskPacket") or {}
    prompt_menu = payload.get("promptMenu") or {}
    task_id = payload.get("taskId") or event.task_id
    step_title = title.split("·", 1)[1].strip() if "·" in title else title
    visible = False
    status = canonical_type
    subtitle = event.detail or canonical_type
    card_key = task_id or event.id

    planner_meta = payload.get("plannerMeta") or {}
    dispatch_mode = str(planner_meta.get("dispatchMode") or "")
    is_direct_answer_run = dispatch_mode == "main_agent_direct" and bool(
        planner_meta.get("directAnswer") or planner_meta.get("assistantText")
    )
    plan_payload = payload.get("plan") or {}
    plan_step_count = len(plan_payload.get("steps") or [])
    compact = _looks_like_simple_writing_payload(payload)
    phase, phase_label = _display_phase_for_event(canonical_type, payload)

    if canonical_type == "agent_invoke":
        visible = not (is_direct_answer_run or compact)
        status = "agent_invoke"
        objective = task_packet.get("objective") or task_packet.get("scope") or event.detail
        subtitle = _trim_text(f"正在执行“{step_title}”，{objective or '准备生成结果。'}")
        card_key = f"agent:{task_id or event.id}"
    elif canonical_type == "planner_plan":
        visible = compact or not (is_direct_answer_run or plan_step_count <= 1)
        status = "planner_plan"
        subtitle = _trim_text(
            plan_payload.get("summary")
            or event.detail
            or "已生成执行计划。"
        )
        card_key = f"plan:{task_id or event.id}"
    elif canonical_type == "skill_invoke":
        visible = True
        status = "skill_invoke"
        subtitle = _result_preview(payload)
        card_key = f"skill:{task_id or event.id}"
    elif canonical_type == "tool_call":
        is_a2a_planning = "A2A Planning" in title
        visible = not (is_a2a_planning or compact)
        status = "tool_call"
        subtitle = _trim_text(event.detail or "已执行通用工具调用。")
        card_key = f"tool:{task_id or event.id}"
    elif canonical_type == "waiting_user":
        visible = True
        status = "waiting_user"
        subtitle = _trim_text(
            prompt_menu.get("description")
            or prompt_menu.get("question")
            or event.detail
            or "当前缺少关键信息，等待用户补充后继续执行。"
        )
        card_key = payload.get("taskId") or card_key
        if "·" in title:
            step_title = title.split("·", 1)[1].strip()
    elif canonical_type == "error":
        visible = True
        status = "error"
        subtitle = _trim_text(payload.get("errorDetail") or event.detail or "执行失败。")
        card_key = f"error:{task_id or event.id}"
    elif canonical_type == "cli_exec":
        visible = True
        status = "cli_exec"
        subtitle = _trim_text(payload.get("command") or event.detail or "已执行 CLI 工作区工具。")
        card_key = event.id
    elif canonical_type == "search":
        visible = True
        status = "search"
        citations = payload.get("citations") or (payload.get("normalizedResult") or {}).get("citations") or (payload.get("normalizedResult") or {}).get("items") or []
        subtitle = _trim_text(event.detail or f"已返回 {len(citations)} 条检索结果。")
        card_key = f"search:{task_id or event.id}"
    elif canonical_type == "context_usage":
        visible = False
        status = "context_usage"
        subtitle = _trim_text(
            f"{payload.get('used') or 0} / {payload.get('window') or 0} tokens"
        )
        card_key = event.id
    elif canonical_type == "context_compacted":
        visible = True
        status = "context_compacted"
        before = (payload.get("contextUsageBefore") or {}).get("used")
        after = (payload.get("contextUsageAfter") or {}).get("used")
        if before and after:
            subtitle = _trim_text(f"上下文已压缩：{before} -> {after} tokens")
        else:
            subtitle = _trim_text(event.detail or "已完成上下文压缩。")
        card_key = event.id
    elif canonical_type == "artifact_created":
        visible = True
        status = "artifact_created"
        subtitle = _trim_text(payload.get("summary") or event.detail or "已生成新的工作区产物。")
        card_key = f"artifact:{payload.get('id') or payload.get('artifactId') or event.id}"
    elif canonical_type == "artifact_updated":
        visible = True
        status = "artifact_updated"
        subtitle = _trim_text(payload.get("summary") or event.detail or "已更新工作区产物。")
        card_key = f"artifact:{payload.get('id') or payload.get('artifactId') or event.id}"
    elif event.event_type == "conversation_title_updated":
        visible = False
        status = "conversation_title_updated"
        subtitle = _trim_text(payload.get("title") or event.detail or "会话标题已更新。")
        card_key = event.id
    elif canonical_type == "message_delta":
        visible = False
        status = "running"
        subtitle = _trim_text((payload.get("textSoFar") or event.detail or "")[-120:])
    elif canonical_type == "planner_reasoning_delta":
        visible = False
        status = "running"
        subtitle = _trim_text((payload.get("reasoningSoFar") or event.detail or "")[-120:])
    elif canonical_type == "message_created":
        visible = False
        status = "message_created"
        subtitle = _trim_text(event.detail or "消息已创建。")
    elif canonical_type == "message_final":
        visible = False
        status = "message_final"
        subtitle = _trim_text(event.detail or "助手消息已生成。")
    elif canonical_type == "completed":
        visible = True
        status = "completed"
        subtitle = _trim_text(event.detail or "执行完成。")
        card_key = f"completed:{task_id or event.id}"
    elif canonical_type == "aborted":
        visible = True
        status = "aborted"
        subtitle = _trim_text(event.detail or "执行已中止。")
        card_key = f"aborted:{task_id or event.id}"

    return {
        "visible": visible,
        "cardKey": card_key,
        "title": step_title,
        "subtitle": subtitle,
        "status": status,
        "eventType": canonical_type,
        "replace": visible,
        "phase": phase,
        "phaseLabel": phase_label,
        "compact": compact,
    }


@router.get("", response_model=AgentLoopResponse)
def list_conversations(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.execute(
        select(V4Conversation)
        .where(
            V4Conversation.user_id == current_user.user_id,
            V4Conversation.is_deleted.is_(False),
        )
        .order_by(V4Conversation.pinned.desc(), V4Conversation.last_message_at.desc())
    ).scalars().all()
    return AgentLoopResponse(
        data=[
            {
                "id": item.id,
                "title": item.title,
                "pinned": item.pinned,
                "updatedAt": item.updated_at.isoformat(),
                "lastRunId": item.last_run_id,
                "meta": "刚刚更新"
                if (datetime.utcnow() - item.updated_at).seconds < 120
                else item.updated_at.strftime("%m月%d日 %H:%M"),
            }
            for item in items
        ]
    )


@router.post("", response_model=AgentLoopResponse)
def create_conversation(
    payload: ConversationCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log_stage(
        "api.agentloop.conversations.create.request",
        {
            "userId": current_user.user_id,
            "payload": payload,
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    item = V4Conversation(user_id=current_user.user_id, title=payload.title or "新对话")
    db.add(item)
    db.commit()
    db.refresh(item)
    response_payload = {"id": item.id, "title": item.title}
    log_stage(
        "api.agentloop.conversations.create.response",
        {
            "userId": current_user.user_id,
            "data": response_payload,
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    return AgentLoopResponse(data=response_payload)


@router.get("/{conversation_id}", response_model=AgentLoopResponse)
def get_conversation(
    conversation_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = _conversation_or_404(db, conversation_id, current_user.user_id)
    messages = db.execute(
        select(V4ConversationMessage)
        .where(V4ConversationMessage.conversation_id == conversation.id)
        .order_by(V4ConversationMessage.created_at.asc())
    ).scalars().all()
    artifacts = db.execute(
        select(V4ConversationArtifact)
        .where(V4ConversationArtifact.conversation_id == conversation.id)
        .order_by(V4ConversationArtifact.created_at.asc())
    ).scalars().all()
    snapshots = db.execute(
        select(V4CompressionSnapshot)
        .where(V4CompressionSnapshot.conversation_id == conversation.id)
        .order_by(V4CompressionSnapshot.created_at.desc())
    ).scalars().all()
    runtime_state = json.loads(conversation.running_context_json or "{}") if conversation.running_context_json else {}
    latest_todo_list = _latest_todo_list_from_messages(messages, runtime_state)
    return AgentLoopResponse(
        data={
            "id": conversation.id,
            "title": conversation.title,
            "pinned": conversation.pinned,
            "titleLocked": conversation.title_locked,
            "titleVersion": conversation.title_version,
            "runningContext": build_runtime_context(db, conversation),
            "pendingPromptMenu": runtime_state.get("pendingPromptMenu"),
            "latestTodoList": latest_todo_list,
            "taskTree": runtime_state.get("taskTree") or [],
            "messageActions": {
                "canCopy": True,
                "canLike": True,
                "canDislike": True,
                "canRegenerate": True,
            },
            "messages": [
                {
                    "id": message.id,
                    "runId": message.run_id,
                    "role": message.role,
                    "skillName": message.skill_name,
                    "content": message.content,
                    "contentHtml": message.content_html,
                    "contentBlocks": json.loads(getattr(message, "content_blocks_json", None) or "[]"),
                    "schemaVersion": getattr(message, "schema_version", 1) or 1,
                    "model": message.model_name,
                    "annotations": json.loads(message.annotations_json or "[]"),
                    "meta": json.loads(message.meta_json or "{}"),
                    "createdAt": message.created_at.isoformat(),
                }
                for message in messages
            ],
            "artifacts": [
                {
                    **_artifact_contract_from_record(artifact),
                    "messageId": artifact.message_id,
                }
                for artifact in artifacts
            ],
            "compressionSnapshots": [
                {
                    "id": snapshot.id,
                    "summary": snapshot.summary,
                    "summaryMarkdown": snapshot.summary_markdown,
                    "stats": json.loads(snapshot.stats_json or "{}"),
                    "createdAt": snapshot.created_at.isoformat(),
                }
                for snapshot in snapshots
            ],
        }
    )


@router.put("/{conversation_id}", response_model=AgentLoopResponse)
def update_conversation(
    conversation_id: str,
    payload: ConversationRenameRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation_or_404(db, conversation_id, current_user.user_id)
    if payload.title is not None:
        conversation.title = (payload.title or "").strip() or conversation.title
        conversation.title_locked = True
        conversation.title_version = int(conversation.title_version or 0) + 1
    if payload.pinned is not None:
        conversation.pinned = payload.pinned
    conversation.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(
        data={
            "id": conversation.id,
            "title": conversation.title,
            "pinned": conversation.pinned,
            "titleLocked": conversation.title_locked,
            "titleVersion": conversation.title_version,
        }
    )


@router.delete("/{conversation_id}", response_model=AgentLoopResponse)
def delete_conversation(
    conversation_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = _conversation_or_404(db, conversation_id, current_user.user_id)
    conversation.is_deleted = True
    conversation.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data=True)


@router.post("/{conversation_id}/compact", response_model=AgentLoopResponse)
def compact_conversation(
    conversation_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation_or_404(db, conversation_id, current_user.user_id)
    result = maybe_compact_conversation(db, conversation, current_user, force=True)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    return AgentLoopResponse(
        data={
            "compacted": bool(result),
            "result": result,
            "runningContext": build_runtime_context(db, conversation),
        }
    )


@router.post("/{conversation_id}/run", response_model=AgentLoopResponse)
def run(
    conversation_id: str,
    payload: ConversationRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation_or_404(db, conversation_id, current_user.user_id)
    log_stage(
        "api.agentloop.conversations.run.request",
        {
            "conversationId": conversation.id,
            "conversationTitle": conversation.title,
            "userId": current_user.user_id,
            "payload": payload,
            "cookiePreview": mask_cookie(request.headers.get("cookie")),
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    try:
        # prepare_run 已落库 created 事件；此处立即返回 streamUrl，前端可零延迟拉 SSE（与 runtime 早推事件配合）
        prepared = prepare_run_conversation(
            db,
            conversation,
            current_user,
            payload.content,
            payload.skill,
            payload.model,
            payload.attachments,
            payload.operation_context.model_dump() if payload.operation_context else None,
            request.headers.get("cookie"),
            payload.resume_from_waiting,
            payload.selected_option,
            payload.prompt_menu_input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(
        execute_prepared_run,
        conversation.id,
        current_user,
        run_id=prepared["run"].id,
        task_id=prepared["run"].task_id,
        content=prepared["request"]["content"],
        requested_skill=prepared["request"]["requestedSkill"],
        requested_model=prepared["request"]["requestedModel"],
        attachments=prepared["request"]["attachments"],
        operation_context=prepared["request"]["operationContext"],
        cookies=request.headers.get("cookie"),
        resume_from_waiting=prepared["request"]["resumeFromWaiting"],
        selected_option=prepared["request"]["selectedOption"],
        prompt_menu_input=prepared["request"]["promptMenuInput"],
    )
    background_tasks.add_task(
        summarize_conversation_title_after_run,
        conversation.id,
        current_user.user_id,
        prepared["run"].id,
    )
    response_payload = {
        "conversationId": conversation.id,
        "conversationTitle": conversation.title,
        "runId": prepared["run"].id,
        "taskId": prepared["run"].task_id,
        "streamUrl": f"/api/agentloop/conversations/{conversation.id}/events?run_id={prepared['run'].id}",
        "assistantMessage": None,
        "artifacts": [],
        "pendingPromptMenu": None,
    }
    log_stage(
        "api.agentloop.conversations.run.response",
        {
            "conversationId": conversation.id,
            "runId": prepared["run"].id,
            "taskId": prepared["run"].task_id,
            "data": response_payload,
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    return AgentLoopResponse(data=response_payload)


@router.get("/{conversation_id}/events")
def stream_events(
    conversation_id: str,
    run_id: str | None = Query(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _conversation_or_404(db, conversation_id, current_user.user_id)
    if run_id is None:
        run_id = conversation.last_run_id
    if not run_id:
        raise HTTPException(status_code=404, detail="暂无运行记录")

    run = db.execute(
        select(V4ConversationRun).where(
            V4ConversationRun.id == run_id,
            V4ConversationRun.conversation_id == conversation.id,
            V4ConversationRun.user_id == current_user.user_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    def event_stream():
        stream_db = SessionLocal()
        sent_seq_no = 0
        final_idle_cycles = 0
        message_id = f"msg_{run.id}"
        emitted_block_ids: set[str] = set()
        # tool_use → tool_result 配对用：某些 tool_use 已追加后，对应 tool_result 需要
        # 通过 block_update 改其状态；这里记录 tool_use_id 到 block id 的映射。
        tool_use_block_by_tool_id: dict[str, str] = {}

        def emit(data: dict) -> str:
            return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

        def emit_block(block: dict, *, update_kind: str = "append") -> str:
            envelope = {
                "type": "block_update" if update_kind != "append" else "block_append",
                "session_id": conversation.id,
                "run_id": run.id,
                "message_id": message_id,
                "timestamp": block.get("created_at") or datetime.utcnow().isoformat(),
                "block": block,
            }
            return emit(envelope)

        try:
            yield emit(
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": conversation.id,
                    "run_id": run.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "conversation_id": conversation.id,
                        "conversation_title": conversation.title,
                        "message_id": message_id,
                        "protocol_version": "content-blocks-v2",
                    },
                }
            )
            while True:
                current_run = stream_db.execute(
                    select(V4ConversationRun).where(
                        V4ConversationRun.id == run.id,
                        V4ConversationRun.conversation_id == conversation.id,
                        V4ConversationRun.user_id == current_user.user_id,
                    )
                ).scalar_one_or_none()
                if current_run is None:
                    yield "data: [DONE]\n\n"
                    return

                events = stream_db.execute(
                    select(V4TaskEvent)
                    .where(V4TaskEvent.run_id == run.id, V4TaskEvent.seq_no > sent_seq_no)
                    .order_by(V4TaskEvent.seq_no.asc())
                ).scalars().all()

                for event in events:
                    payload = json.loads(event.payload_json or "{}")
                    canonical_type = _canonical_event_type(event, payload)
                    payload.setdefault("internalEventType", event.event_type)
                    timestamp = event.created_at.isoformat()

                    # 把事件翻译成 0..N 个 assistant content block
                    new_blocks = _event_to_content_blocks(
                        event, payload, canonical_type, message_id=message_id
                    )
                    for block in new_blocks:
                        block_id = block.get("id") or f"blk_{uuid4().hex[:8]}"
                        block["id"] = block_id
                        update_kind_raw = block.pop("update_kind", None)
                        if block.get("type") == "tool_use":
                            tool_use_block_by_tool_id[block.get("tool_use_id")] = block_id
                        # tool_result 本身独立追加 —— 但前端可根据 tool_use_id 做视觉关联。
                        if block_id in emitted_block_ids and update_kind_raw != "replace":
                            yield emit_block(block, update_kind="update")
                        elif update_kind_raw == "replace":
                            emitted_block_ids.add(block_id)
                            yield emit_block(block, update_kind="update")
                        else:
                            emitted_block_ids.add(block_id)
                            yield emit_block(block, update_kind="append")

                    if canonical_type == "waiting_user":
                        prompt_menu = payload.get("promptMenu") or {}
                        yield emit(
                            {
                                "type": "system",
                                "subtype": "waiting_input",
                                "session_id": conversation.id,
                                "run_id": run.id,
                                "message_id": message_id,
                                "timestamp": timestamp,
                                "data": {
                                    "reason": "missing_required_inputs",
                                    "question": prompt_menu.get("question")
                                    or prompt_menu.get("description")
                                    or event.detail
                                    or "为了顺利执行后续步骤，请先补充这些信息。",
                                    "missing_fields": [
                                        {
                                            "key": f"missing_{index + 1}",
                                            "label": str(item),
                                            "required": True,
                                            "hint": str(item),
                                        }
                                        for index, item in enumerate(prompt_menu.get("missingItems") or [])
                                    ],
                                    "options": prompt_menu.get("options") or [],
                                    "resume_mode": prompt_menu.get("resumeMode") or "rebuild_todo_list",
                                    "promptMenu": prompt_menu,
                                },
                            }
                        )
                    elif canonical_type == "message_final":
                        assistant_message_id = payload.get("assistantMessageId")
                        assistant_message = None
                        if assistant_message_id:
                            assistant_message = stream_db.execute(
                                select(V4ConversationMessage).where(V4ConversationMessage.id == assistant_message_id)
                            ).scalar_one_or_none()
                        if assistant_message is None:
                            assistant_message = stream_db.execute(
                                select(V4ConversationMessage)
                                .where(
                                    V4ConversationMessage.conversation_id == conversation.id,
                                    V4ConversationMessage.run_id == run.id,
                                    V4ConversationMessage.role == "assistant",
                                )
                                .order_by(V4ConversationMessage.created_at.desc())
                            ).scalars().first()
                        final_blocks: list[dict] = []
                        if assistant_message is not None and getattr(
                            assistant_message, "content_blocks_json", None
                        ):
                            try:
                                parsed = json.loads(assistant_message.content_blocks_json or "[]")
                                if isinstance(parsed, list):
                                    final_blocks = [b for b in parsed if isinstance(b, dict)]
                            except json.JSONDecodeError:
                                final_blocks = []
                        final_message_id = (
                            assistant_message.id if assistant_message else message_id
                        )
                        yield emit(
                            {
                                "type": "message_complete",
                                "session_id": conversation.id,
                                "run_id": run.id,
                                "message_id": final_message_id,
                                "timestamp": timestamp,
                                "content": final_blocks,
                            }
                        )
                    elif canonical_type == "error":
                        if payload.get("errorScope") == "artifact":
                            artifact_payload = payload.get("artifactDraft") or {}
                            yield emit(
                                {
                                    "type": "assistant",
                                    "session_id": conversation.id,
                                    "run_id": run.id,
                                    "timestamp": timestamp,
                                    "message": {
                                        "id": f"assistant-{event.id}",
                                        "role": "assistant",
                                        "content": [
                                            {
                                                "type": "artifact",
                                                **artifact_payload,
                                            }
                                        ],
                                    },
                                }
                            )
                        else:
                            yield emit(
                                {
                                    "type": "result",
                                    "session_id": conversation.id,
                                    "run_id": run.id,
                                    "timestamp": timestamp,
                                    "subtype": "error",
                                    "is_error": True,
                                    "summary": event.detail or "执行失败。",
                                    "error": {
                                        "scope": payload.get("errorScope") or "execution",
                                        "message": payload.get("errorDetail") or event.detail or "执行失败。",
                                    },
                                }
                            )
                    elif canonical_type == "aborted":
                        yield emit(
                            {
                                "type": "result",
                                "session_id": conversation.id,
                                "run_id": run.id,
                                "timestamp": timestamp,
                                "subtype": "error",
                                "is_error": True,
                                "summary": event.detail or "执行已中止。",
                                "error": {
                                    "scope": "execution",
                                    "message": event.detail or "执行已中止。",
                                },
                            }
                        )
                    elif canonical_type == "completed":
                        yield emit(
                            {
                                "type": "result",
                                "session_id": conversation.id,
                                "run_id": run.id,
                                "timestamp": timestamp,
                                "subtype": "success",
                                "is_error": False,
                                "summary": event.detail or "已完成本轮任务。",
                            }
                        )
                    sent_seq_no = event.seq_no
                if events:
                    final_idle_cycles = 0

                if current_run.status in {"completed", "failed", "waiting_user"}:
                    if events:
                        stream_db.expire_all()
                        time.sleep(0.25)
                        continue
                    final_idle_cycles += 1
                    if final_idle_cycles >= 8:
                        yield "data: [DONE]\n\n"
                        return

                stream_db.expire_all()
                time.sleep(0.25)
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream; charset=utf-8")
