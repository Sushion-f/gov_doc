"""Assistant 消息的 content block 构造器。

对齐 Claude Agent SDK 的 `content[] block` 设计：assistant 消息由一串有序 block 组成，
持久化时直接写 `content_blocks_json`，前端按 block.type 渲染。

当前实现处于 Step 1（协议层）落地阶段：在 Step 2 把 dispatch_sub_agent
完全收编进原生 tool-call loop 之后，build_assistant_blocks 的输入会直接来自
Lead loop 的 tool_use/tool_result 记录；本阶段先由 step_outcomes 过渡性地铺块，
让后端先写出合法的 content_blocks_json 供前端试渲染。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable


def _ts() -> str:
    return datetime.utcnow().isoformat()


def _new_block_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _join_text(*parts: str | None) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def build_tool_use_block(
    *,
    tool_use_id: str,
    name: str,
    tool_input: dict[str, Any] | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    return {
        "id": _new_block_id("tu"),
        "type": "tool_use",
        "tool_use_id": tool_use_id,
        "name": name,
        "input": tool_input or {},
        "status": status,
        "created_at": _ts(),
    }


def build_tool_result_block(
    *,
    tool_use_id: str,
    content: list[dict[str, Any]],
    is_error: bool = False,
) -> dict[str, Any]:
    return {
        "id": _new_block_id("tr"),
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "is_error": is_error,
        "content": content,
        "created_at": _ts(),
    }


def build_text_block(text: str) -> dict[str, Any]:
    return {
        "id": _new_block_id("tx"),
        "type": "text",
        "text": text,
        "created_at": _ts(),
    }


def build_thinking_block(thinking: str) -> dict[str, Any]:
    return {
        "id": _new_block_id("th"),
        "type": "thinking",
        "thinking": thinking,
        "created_at": _ts(),
    }


def build_artifact_ref_block(
    *,
    artifact_id: str,
    title: str,
    version: int | None = None,
    workspace_node_id: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    return {
        "id": _new_block_id("ar"),
        "type": "artifact_ref",
        "artifact_id": artifact_id,
        "title": title,
        "version": version,
        "workspace_node_id": workspace_node_id,
        "summary": summary,
        "created_at": _ts(),
    }


def build_todo_list_block(items: list[dict[str, Any]]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": str(item.get("id") or _new_block_id("td")),
                "text": str(item.get("text") or ""),
                "status": str(item.get("status") or "pending"),
                "priority": item.get("priority"),
            }
        )
    return {
        "id": _new_block_id("tl"),
        "type": "todo_list",
        "items": normalized,
        "created_at": _ts(),
    }


def build_waiting_user_block(prompt_menu: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "id": _new_block_id("wu"),
        "type": "waiting_user",
        "prompt_menu": prompt_menu or {},
        "created_at": _ts(),
    }


def build_context_notice_block(
    *,
    kind: str = "usage",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    return {
        "id": _new_block_id("cn"),
        "type": "context_notice",
        "kind": kind,
        "before": before,
        "after": after,
        "summary": summary,
        "created_at": _ts(),
    }


def _outcome_to_blocks(outcome: dict[str, Any]) -> list[dict[str, Any]]:
    """把一个 step_outcome 展开成 tool_use + tool_result + 可选 artifact_ref 组合。"""
    skill = str(outcome.get("skill_name") or "sub_agent")
    title = str(outcome.get("title") or skill)
    tool_use_id = f"sub_{outcome.get('task_id') or _new_block_id('t')}"
    agent_name = skill
    tool_input = {
        "agent_name": agent_name,
        "task_prompt": outcome.get("summary") or title,
    }
    status = "error" if outcome.get("error_detail") else "ok"
    blocks: list[dict[str, Any]] = [
        build_tool_use_block(
            tool_use_id=tool_use_id,
            name="dispatch_sub_agent",
            tool_input=tool_input,
            status=status,
        )
    ]

    inner: list[dict[str, Any]] = []
    summary = str(outcome.get("summary") or "").strip()
    if summary:
        inner.append({"type": "text", "text": summary})
    for artifact in _safe_list(outcome.get("artifact_refs")):
        if not isinstance(artifact, dict):
            continue
        aid = artifact.get("artifact_id") or artifact.get("id")
        if not aid:
            continue
        inner.append(
            {
                "type": "artifact_ref",
                "artifact_id": str(aid),
                "title": artifact.get("title"),
                "version": artifact.get("version") or artifact.get("version_no"),
                "workspace_node_id": artifact.get("workspace_node_id")
                or artifact.get("workspaceNodeId"),
            }
        )
    err_detail = outcome.get("error_detail")
    if err_detail:
        inner.append({"type": "error", "message": str(err_detail)})

    blocks.append(
        build_tool_result_block(
            tool_use_id=tool_use_id,
            content=inner or [{"type": "text", "text": title}],
            is_error=bool(err_detail),
        )
    )
    return blocks


def build_assistant_blocks(
    *,
    plan: Any,
    step_outcomes: Iterable[dict[str, Any]] | None,
    pending_artifacts: Iterable[dict[str, Any]] | None = None,
    pending_prompt_menu: dict[str, Any] | None = None,
    planner_meta: dict[str, Any] | None = None,
    final_text: str | None = None,
    context_notice: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """按执行顺序铺 blocks：
    [thinking?] → [tool_use, tool_result]* → [artifact_ref*] → [todo_list?]
    → [waiting_user?] → [context_notice?] → [text]
    """
    blocks: list[dict[str, Any]] = []
    planner_meta = _safe_dict(planner_meta)

    reasoning = planner_meta.get("reasoningContent") or planner_meta.get("plannerReasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        blocks.append(build_thinking_block(reasoning.strip()))

    outcomes_list = list(step_outcomes or [])
    for outcome in outcomes_list:
        if not isinstance(outcome, dict):
            continue
        blocks.extend(_outcome_to_blocks(outcome))

    for artifact in pending_artifacts or []:
        if not isinstance(artifact, dict):
            continue
        aid = artifact.get("id") or artifact.get("artifact_id")
        if not aid:
            continue
        blocks.append(
            build_artifact_ref_block(
                artifact_id=str(aid),
                title=str(artifact.get("title") or "未命名产物"),
                version=artifact.get("version") or artifact.get("version_no"),
                workspace_node_id=artifact.get("workspace_node_id")
                or artifact.get("workspaceNodeId"),
                summary=artifact.get("summary"),
            )
        )

    if pending_prompt_menu:
        prompt_menu = pending_prompt_menu.get("promptMenu") or pending_prompt_menu
        blocks.append(build_waiting_user_block(prompt_menu))

    if context_notice:
        blocks.append(
            build_context_notice_block(
                kind=str(context_notice.get("kind") or "usage"),
                before=context_notice.get("before"),
                after=context_notice.get("after"),
                summary=context_notice.get("summary"),
            )
        )

    text_segments: list[str] = []
    if final_text:
        text_segments.append(final_text)
    elif outcomes_list:
        summaries = [str(o.get("summary") or "").strip() for o in outcomes_list if isinstance(o, dict)]
        merged = _join_text(*summaries)
        if merged:
            text_segments.append(merged)

    assistant_text = _join_text(*text_segments)
    if assistant_text:
        blocks.append(build_text_block(assistant_text))

    return blocks


def blocks_to_plain_text(blocks: Iterable[dict[str, Any]]) -> str:
    """从 block 序列中抽出 text block 拼成摘要（给 assistant.content 用）。"""
    chunks: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return _join_text(*chunks)


def blocks_to_snapshot_html(blocks: Iterable[dict[str, Any]]) -> str:
    """从 block 序列渲染一份列表快照 HTML（只保留 text + artifact_ref）。"""
    from html import escape as _escape

    sections: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                sections.append(f"<section class='assistant-block'><p>{_escape(text)}</p></section>")
        elif btype == "artifact_ref":
            title = _escape(str(block.get("title") or "产物"))
            sections.append(
                "<section class='assistant-block artifact-ref'>"
                f"<h4>交付物 · {title}</h4>"
                f"<p>artifact_id = {_escape(str(block.get('artifact_id') or ''))}</p>"
                "</section>"
            )
    if not sections:
        sections.append("<section class='assistant-block'><p>暂无内容。</p></section>")
    return "".join(sections)
