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
    build_runtime_context,
    execute_prepared_run,
    prepare_run_conversation,
)
from ..schemas import (
    AgentLoopResponse,
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationRunRequest,
)

router = APIRouter(prefix="/api/agentloop/conversations", tags=["agentloop-conversations"])


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


def _event_display_payload(event: V4TaskEvent) -> dict:
    payload = json.loads(event.payload_json or "{}")
    title = event.title or ""
    task_packet = payload.get("taskPacket") or {}
    prompt_menu = payload.get("promptMenu") or {}
    task_id = payload.get("taskId") or event.task_id
    step_title = title.split("·", 1)[1].strip() if "·" in title else title
    visible = False
    status = event.status or event.event_type
    subtitle = event.detail or event.event_type
    card_key = task_id or event.id

    if event.event_type == "running" and title.startswith(("Leader Agent ·", "Sub Agent ·")):
        visible = True
        status = "running"
        objective = task_packet.get("objective") or task_packet.get("scope") or event.detail
        subtitle = _trim_text(f"正在执行“{step_title}”，{objective or '准备生成结果。'}")
    elif event.event_type == "tool_call" and title.startswith(("Leader Agent Result ·", "Skill Broker ·")):
        visible = True
        status = "completed"
        subtitle = _result_preview(payload)
    elif event.event_type == "waiting_user":
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
    elif event.event_type == "failed":
        visible = True
        status = "failed"
        subtitle = _trim_text(payload.get("errorDetail") or event.detail or "执行失败。")
    elif event.event_type == "text_delta":
        visible = False
        status = "running"
        subtitle = _trim_text((payload.get("textSoFar") or event.detail or "")[-120:])
    elif event.event_type == "planner_reasoning_delta":
        visible = False
        status = "running"
        subtitle = _trim_text((payload.get("reasoningSoFar") or event.detail or "")[-120:])

    return {
        "visible": visible,
        "cardKey": card_key,
        "title": step_title,
        "subtitle": subtitle,
        "status": status,
        "replace": visible,
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
    latest_assistant = next((item for item in reversed(messages) if item.role == "assistant"), None)
    latest_assistant_meta = json.loads(latest_assistant.meta_json or "{}") if latest_assistant else {}
    return AgentLoopResponse(
        data={
            "id": conversation.id,
            "title": conversation.title,
            "pinned": conversation.pinned,
            "runningContext": build_runtime_context(db, conversation),
            "pendingPromptMenu": runtime_state.get("pendingPromptMenu"),
            "taskTree": runtime_state.get("taskTree") or [],
            "messageActions": latest_assistant_meta.get("messageActions")
            or {
                "canCopy": True,
                "canLike": True,
                "canDislike": True,
                "canRegenerate": True,
            },
            "stepOutcomes": latest_assistant_meta.get("stepOutcomes") or [],
            "messages": [
                {
                    "id": message.id,
                    "runId": message.run_id,
                    "role": message.role,
                    "skillName": message.skill_name,
                    "content": message.content,
                    "contentHtml": message.content_html,
                    "model": message.model_name,
                    "annotations": json.loads(message.annotations_json or "[]"),
                    "meta": json.loads(message.meta_json or "{}"),
                    "createdAt": message.created_at.isoformat(),
                }
                for message in messages
            ],
            "artifacts": [
                {
                    "id": artifact.id,
                    "messageId": artifact.message_id,
                    "title": artifact.title,
                    "summary": artifact.summary,
                    "artifactType": artifact.artifact_type,
                    "contentHtml": artifact.content_html,
                    "workspaceNodeId": artifact.workspace_node_id,
                    "meta": json.loads(artifact.meta_json or "{}"),
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
        conversation.title = payload.title
    if payload.pinned is not None:
        conversation.pinned = payload.pinned
    conversation.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(
        data={"id": conversation.id, "title": conversation.title, "pinned": conversation.pinned}
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
        cookies=request.headers.get("cookie"),
        resume_from_waiting=prepared["request"]["resumeFromWaiting"],
        selected_option=prepared["request"]["selectedOption"],
        prompt_menu_input=prepared["request"]["promptMenuInput"],
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
        try:
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
                    yield "data: " + json.dumps(
                        {
                            "id": event.id,
                            "runId": event.run_id,
                            "taskId": event.task_id,
                            "parentTaskId": event.parent_task_id,
                            "seqNo": event.seq_no,
                            "eventType": event.event_type,
                            "status": event.status,
                            "title": event.title,
                            "detail": event.detail,
                            "detailHtml": event.detail_html,
                            "payload": payload,
                            "display": _event_display_payload(event),
                            "createdAt": event.created_at.isoformat(),
                        },
                        ensure_ascii=False,
                    ) + "\n\n"
                    sent_seq_no = event.seq_no

                if current_run.status in {"completed", "failed", "waiting_user"}:
                    yield "data: [DONE]\n\n"
                    return

                stream_db.expire_all()
                time.sleep(0.25)
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream; charset=utf-8")
