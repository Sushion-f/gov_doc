import json
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .a2a_runtime import (
    ExecutionPlan,
    ExecutionStep,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    a2a_task_registry,
    build_handoff_content,
    build_root_task_packet,
    build_synthetic_dispatch_tool_calls,
    build_subtask_packet,
    format_dispatch_tool_result_json,
    title_for_skill,
)
from .compression import (
    SummaryCompressionBudget,
    apply_leader_context_guard,
    build_structured_summary,
    compress_summary_text,
    estimate_tokens,
    summarize_memory_for_context,
)
from .content_blocks import (
    build_assistant_blocks,
    blocks_to_plain_text,
    blocks_to_snapshot_html,
    build_context_notice_block,
    build_text_block,
)
from .config import settings
from .context_usage import get_usage as get_api_usage, record_usage as record_api_usage
from .debug_log import log_stage, mask_cookie
from .models import (
    V4CompressionSnapshot,
    V4Conversation,
    V4ConversationArtifact,
    V4ConversationMessage,
    V4ConversationRun,
    V4TaskEvent,
    V4UserProfile,
    V4WorkspaceAttachmentLink,
    V4WorkspaceNode,
)
from .planner import build_model_execution_plan
from agents.main_agent import MainAgent
from .agent_capability_adapter import (
    SkillExecutionResult,
    execute_skill,
    render_assistant_html,
)
from .storage import (
    build_docx_bytes,
    clear_user_memory_subdir,
    ensure_unique_workspace_path,
    html_to_plain_text,
    parse_workspace_file,
    read_user_doc,
    resolve_writable_file_path,
    write_workspace_bytes,
    write_memory_doc,
    write_workspace_version,
)
from .llm import LLMCallError, call_chat_model_with_messages, text_to_html
from tools.agent_tool import AgentTool


@dataclass
class RuntimeTaskEvent:
    event_type: str
    status: str
    title: str
    detail: str
    detail_html: str
    payload: dict


INTERACTIVE_SKILLS = {"retrieval", "writing", "review", "dedup", "layout"}
MEMORY_MANUAL_HEADING = "## 手工备注"
GENERIC_ASSISTANT_CONTENTS = {
    "主 Agent 回复",
    "检索结果",
    "审核结果",
    "查重报告",
    "排版结果",
    "公文写作结果",
    "任务未执行",
    "执行失败",
}
TITLE_SUMMARY_INTERVAL = 4
TITLE_SUMMARY_MAX_MESSAGES = 10
WRITING_DOC_MARKERS = ("通知", "报告", "请示", "函", "通报", "公告", "公报", "决定", "纪要", "方案", "讲话稿", "发言稿")
WRITING_ACTION_MARKERS = ("写", "起草", "撰写", "生成", "拟写", "草拟")


class TaskRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def next_task_id(self, conversation_id: str) -> str:
        value = self._counters.get(conversation_id, 0) + 1
        self._counters[conversation_id] = value
        return f"task_{conversation_id[:8]}_{value:04d}"


task_registry = TaskRegistry()


def clip_title(text: str) -> str:
    return (text or "新对话").strip()[:24] or "新对话"


def normalize_conversation_title(text: str) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", (text or "").strip())
    cleaned = re.sub(r"[\"'“”‘’《》【】\[\](){}:：;；,.，。!?！？]+", "", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned:
        return ""
    return cleaned[:14]


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _trim_snippet(value: str | None, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _looks_like_document_request(text: str | None) -> bool:
    content = str(text or "").strip()
    if not content:
        return False
    return any(marker in content for marker in WRITING_DOC_MARKERS) and any(
        marker in content for marker in WRITING_ACTION_MARKERS
    )


def _needs_writing_brief(text: str | None) -> bool:
    content = re.sub(r"\s+", "", str(text or ""))
    if not content:
        return True
    generic_patterns = [
        r"^(写|起草|生成|撰写)(一份|一个|一篇)?(通知|报告|请示|方案|总结|汇报|讲话稿|发言稿|公文)$",
        r"^(帮我)?(写|起草|生成)(个|一份)?(通知|报告|请示|方案)$",
    ]
    if any(re.match(pattern, content) for pattern in generic_patterns):
        return True
    return len(content) <= 8 and any(marker in content for marker in WRITING_DOC_MARKERS)


def _needs_retrieval_brief(text: str | None) -> bool:
    content = re.sub(r"\s+", "", str(text or ""))
    if not content:
        return True
    generic_patterns = [
        r"^(搜一下|查一下|检索一下|帮我搜索|帮我检索)$",
        r"^(搜|查|检索)(资料|文件|政策|内容)?$",
    ]
    return any(re.match(pattern, content) for pattern in generic_patterns)


def _build_main_agent_prompt_menu(
    plan: ExecutionPlan,
    effective_goal: str,
    attachments: list[dict] | None,
) -> dict | None:
    missing_items: list[str] = []
    step_skills = [step.skill_name for step in plan.steps]
    text = str(effective_goal or "").strip()
    if "writing" in step_skills and _needs_writing_brief(text):
        missing_items.append("请补充要写的文种、主题或对象，例如“国庆放假通知”“营商环境整改报告”。")
    if "retrieval" in step_skills and _needs_retrieval_brief(text):
        missing_items.append("请补充检索主题、关键词或范围，例如政策方向、时间范围、目标单位。")
    if any(skill in step_skills for skill in {"review", "dedup", "layout"}) and not (attachments or []):
        short_text = len(re.sub(r"\s+", "", text))
        if short_text < 40:
            missing_items.append("请提供要处理的正文，或先上传待审核/查重/排版的文件。")
    if not missing_items:
        return None
    question = "为了避免后续多个子智能体分别追问，请先一次性补充以下关键信息：\n" + "\n".join(
        f"{index}. {item}" for index, item in enumerate(missing_items, start=1)
    )
    return {
        "type": "clarification",
        "title": "Main Agent 需要补充信息",
        "description": question,
        "question": question,
        "options": [
            {"key": "custom_input", "label": "补充信息", "recommended": True},
        ],
        "resumeMode": "prompt_menu_choice",
        "missingItems": missing_items,
    }


def _normalize_operation_context(operation_context: dict | None) -> dict:
    raw = operation_context if isinstance(operation_context, dict) else {}
    latest_refs = []
    for item in raw.get("latestArtifactRefs") or []:
        if not isinstance(item, dict):
            continue
        latest_refs.append(
            {
                "id": item.get("id"),
                "artifactType": item.get("artifactType"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "contentHtml": item.get("contentHtml"),
                "workspaceNodeId": item.get("workspaceNodeId"),
                "relativePath": item.get("relativePath"),
                "versionPath": item.get("versionPath"),
                "sourceSkill": item.get("sourceSkill"),
                "sourceState": item.get("sourceState"),
                "status": item.get("status"),
                "errorDetail": item.get("errorDetail"),
            }
        )
    return {
        "intentType": str(raw.get("intentType") or "").strip() or None,
        "rewriteMode": str(raw.get("rewriteMode") or "").strip() or None,
        "baseUserGoal": str(raw.get("baseUserGoal") or "").strip() or None,
        "latestAssistantSummary": str(raw.get("latestAssistantSummary") or "").strip() or None,
        "latestArtifactRefs": latest_refs,
    }


def _expand_effective_goal(content: str, operation_context: dict | None) -> tuple[str, str | None]:
    normalized = _normalize_operation_context(operation_context)
    base_goal = normalized.get("baseUserGoal") or (content or "").strip()
    rewrite_mode = normalized.get("rewriteMode") or normalized.get("intentType")
    latest_summary = normalized.get("latestAssistantSummary") or ""
    latest_refs = normalized.get("latestArtifactRefs") or []
    if not rewrite_mode:
        return base_goal, None

    mode_label = {
        "regenerate": "重生成",
        "rewrite": "改写",
        "continue": "续写",
        "polish": "润色",
    }.get(rewrite_mode, rewrite_mode)
    lines = [
        f"当前动作：{mode_label}",
        f"原始用户目标：{base_goal}",
    ]
    if latest_summary:
        lines.extend(["最近一次结果摘要：", latest_summary])
    if latest_refs:
        lines.append("最近一次交付物引用：")
        for item in latest_refs[:3]:
            title = item.get("title") or "未命名交付物"
            summary = item.get("summary") or ""
            node_id = item.get("workspaceNodeId") or ""
            lines.append(f"- {title}" + (f" | {summary}" if summary else "") + (f" | node={node_id}" if node_id else ""))
    lines.append("请基于以上上下文继续完成当前写作任务；缺少非核心信息时请使用占位符，不要转而要求用户补充。")
    return "\n".join(lines).strip(), rewrite_mode


def _normalize_artifact_contract(
    artifact: dict | None,
    *,
    default_source_skill: str | None = None,
    default_source_state: str | None = None,
    default_status: str = "ready",
    error_detail: str | None = None,
) -> dict:
    payload = dict(artifact or {})
    return {
        "id": payload.get("id"),
        "artifactType": payload.get("artifactType") or payload.get("artifact_type") or "document",
        "title": payload.get("title") or "未命名产物",
        "summary": payload.get("summary"),
        "contentHtml": payload.get("contentHtml") or payload.get("content_html"),
        "workspaceNodeId": payload.get("workspaceNodeId") or payload.get("workspace_node_id"),
        "relativePath": payload.get("relativePath") or payload.get("relative_path"),
        "versionPath": payload.get("versionPath") or payload.get("version_path"),
        "sourceSkill": payload.get("sourceSkill") or payload.get("source_skill") or default_source_skill,
        "sourceState": payload.get("sourceState") or payload.get("source_state") or default_source_state,
        "status": payload.get("status") or default_status,
        "errorDetail": payload.get("errorDetail") or payload.get("error_detail") or error_detail,
    }


def _artifact_contract_from_record(artifact: V4ConversationArtifact) -> dict:
    meta = _loads(artifact.meta_json, {})
    return _normalize_artifact_contract(
        {
            "id": artifact.id,
            "artifactType": artifact.artifact_type,
            "title": artifact.title,
            "summary": artifact.summary,
            "contentHtml": artifact.content_html,
            "workspaceNodeId": artifact.workspace_node_id,
            "relativePath": meta.get("relativePath"),
            "versionPath": meta.get("versionPath"),
            "sourceSkill": meta.get("sourceSkill"),
            "sourceState": meta.get("sourceState"),
            "status": meta.get("status") or "ready",
            "errorDetail": meta.get("errorDetail"),
        }
    )


def _artifact_ref_payloads(artifacts: list[V4ConversationArtifact]) -> list[dict]:
    return [_artifact_contract_from_record(item) for item in artifacts]


def _build_attachment_context(db: Session, current_user, attachments: list[dict] | None) -> list[dict]:
    contexts: list[dict] = []
    for item in attachments or []:
        if not isinstance(item, dict):
            continue
        node_id = item.get("workspaceNodeId") or item.get("nodeId") or item.get("id")
        title = item.get("title") or item.get("name") or "附件"
        if not node_id:
            continue
        node = db.execute(
            select(V4WorkspaceNode).where(
                V4WorkspaceNode.id == str(node_id),
                V4WorkspaceNode.owner_user_id == current_user.user_id,
                V4WorkspaceNode.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if node is None or not node.path:
            continue
        try:
            parsed = parse_workspace_file(current_user.user_id, node.path)
        except Exception:
            continue
        content_text = _trim_snippet(parsed.get("content_text") or "", 1200)
        meta = parsed.get("meta") or {}
        contexts.append(
            {
                "workspaceNodeId": node.id,
                "title": title,
                "path": node.path,
                "fileType": (meta.get("path") or node.path or "").rsplit(".", 1)[-1].lower() if "." in (node.path or "") else "document",
                "parser": meta.get("parser"),
                "summary": _trim_snippet(node.summary or content_text, 180),
                "excerpt": content_text,
            }
        )
    return contexts


def _trim_prompt_text(value: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _index_relative_paths(markdown: str | None, *, prefix: str) -> list[str]:
    if not markdown:
        return []
    found: list[str] = []
    for line in markdown.splitlines():
        match = re.search(r"->\s*见\s+([^\s]+)", line.strip())
        if not match:
            continue
        relative = match.group(1).strip()
        if not relative.startswith(prefix):
            continue
        if relative not in found:
            found.append(relative)
    return found


def _expand_memory_index_markdown(
    user_id: str,
    index_markdown: str,
    *,
    prefix: str,
    max_files: int,
    max_chars_per_file: int,
    section_title: str,
) -> str:
    if not index_markdown.strip():
        return ""
    parts = [index_markdown.strip()]
    expanded: list[tuple[str, str]] = []
    for relative in _index_relative_paths(index_markdown, prefix=prefix)[:max_files]:
        content = read_user_doc(user_id, f"memory/{relative}")
        if not content.strip():
            continue
        expanded.append((relative, content.strip()[:max_chars_per_file].rstrip()))
    if not expanded:
        return "\n".join(parts).strip()
    parts.extend(["", f"## {section_title}", ""])
    for relative, content in expanded:
        parts.append(f"### {relative}")
        parts.append("")
        parts.append(content)
        parts.append("")
    return "\n".join(parts).strip()


def _assistant_prompt_preview(message: V4ConversationMessage) -> str:
    content = (message.content or "").strip()
    if content and content not in GENERIC_ASSISTANT_CONTENTS and content != "执行中":
        return _trim_prompt_text(content, 240)

    # 优先从 schema v2 的 content_blocks_json 里抽 text/artifact_ref 做摘要
    blocks_raw = getattr(message, "content_blocks_json", None)
    if blocks_raw:
        blocks = _loads(blocks_raw, [])
        if isinstance(blocks, list):
            fragments: list[str] = []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text = str(block.get("text") or "").strip()
                    if text:
                        fragments.append(text)
                elif btype == "artifact_ref":
                    title = str(block.get("title") or "").strip()
                    if title:
                        fragments.append(f"交付物：{title}")
            if fragments:
                return _trim_prompt_text(" | ".join(fragments), 320)

    html_preview = _trim_prompt_text(_strip_html(message.content_html or ""), 260)
    if html_preview:
        return html_preview
    if content:
        return _trim_prompt_text(content, 160)
    return "助手已回复。"


def _message_prompt_content(message: V4ConversationMessage) -> str:
    if message.role == "assistant":
        return _assistant_prompt_preview(message)
    return _trim_prompt_text(message.content or "", 240)


def _default_memory_state() -> dict:
    return {
        "skillUsage": {},
        "stylePreferences": [],
        "recentFocus": [],
        "commonFeedback": [],
        "manualNotes": "",
    }


def _normalize_memory_state(value) -> dict:
    normalized = _default_memory_state()
    if not isinstance(value, dict):
        return normalized
    for key, item in value.items():
        if key not in normalized:
            normalized[key] = item

    skill_usage = {}
    for key, item in (value.get("skillUsage") or {}).items():
        try:
            score = int(item)
        except (TypeError, ValueError):
            continue
        if score > 0:
            skill_usage[str(key)] = score
    normalized["skillUsage"] = skill_usage

    style_preferences: list[str] = []
    for item in value.get("stylePreferences") or []:
        text = str(item).strip()
        if text and text not in style_preferences:
            style_preferences.append(text)
    normalized["stylePreferences"] = style_preferences[-5:]

    recent_focus: list[dict] = []
    for item in value.get("recentFocus") or []:
        if not isinstance(item, dict):
            continue
        conversation_id = str(item.get("conversationId") or "").strip()
        title = str(item.get("title") or "").strip()
        skill = str(item.get("skill") or "").strip()
        updated_at = str(item.get("updatedAt") or "").strip()
        if not conversation_id and not title:
            continue
        recent_focus.append(
            {
                "conversationId": conversation_id,
                "title": title,
                "skill": skill,
                "updatedAt": updated_at,
            }
        )
    normalized["recentFocus"] = recent_focus[:8]

    common_feedback: list[str] = []
    for item in value.get("commonFeedback") or []:
        text = str(item).strip()
        if text and text not in common_feedback:
            common_feedback.append(text)
    normalized["commonFeedback"] = common_feedback[:20]

    normalized["manualNotes"] = str(value.get("manualNotes") or "").strip()
    return normalized


def _extract_manual_notes_from_memory_markdown(markdown: str | None) -> str:
    if not markdown:
        return ""
    if MEMORY_MANUAL_HEADING in markdown:
        return markdown.split(MEMORY_MANUAL_HEADING, 1)[1].strip()

    cleaned: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "# memory":
            continue
        if stripped.startswith("- 这是用户长期记忆入口文件"):
            continue
        if stripped.startswith("- 暂无。可在设置页补充个人注记或入口说明。"):
            continue
        if stripped.startswith(("- 推荐摘要:", "- 技能使用统计:", "- 风格偏好:")):
            continue
        if "-> 见 topics/" in stripped or "-> 见 sessions/" in stripped:
            continue
        if stripped.startswith("## ") and "手工备注" not in stripped:
            continue
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip()


def _trim_memory_line(value: str, limit: int = 140) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _format_time(value: str | None) -> str:
    if not value:
        return "未知"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _render_memory_index(manual_notes: str) -> str:
    lines = [
        "# memory",
        "",
        "- 这是用户长期记忆入口文件，具体内容见下列主题文件。",
        "",
        "## 用户习惯",
        "- 工作习惯与处理路径 -> 见 topics/habits.md",
        "",
        "## 常用技能与工作偏好",
        "- 常用技能统计与入口偏好 -> 见 topics/skill_preferences.md",
        "",
        "## 写作与模型风格",
        "- 默认模型与近期模型偏好 -> 见 topics/style_preferences.md",
        "",
        "## 近期高频主题",
        "- 最近会话主题与跟进方向 -> 见 topics/recent_focus.md",
        "",
        "## 常见反馈",
        "- 手工补充的注意事项与常见反馈 -> 见 topics/common_feedback.md",
        "",
        MEMORY_MANUAL_HEADING,
    ]
    if manual_notes:
        lines.extend(["", manual_notes])
    else:
        lines.extend(["", "- 暂无。可在设置页补充个人注记或入口说明。"])
    return "\n".join(lines).strip() + "\n"


def _render_topic_markdown(title: str, lines: list[str]) -> str:
    content = [f"# {title}", ""]
    if lines:
        content.extend(lines)
    else:
        content.append("- 暂无记录。")
    return "\n".join(content).strip() + "\n"


def _build_memory_topics(profile: V4UserProfile, memory: dict, preferred_skills: list[str]) -> dict[str, str]:
    skill_usage = memory.get("skillUsage") or {}
    ordered_skills = sorted(skill_usage.items(), key=lambda item: (-item[1], item[0]))
    top_skills = [name for name, _ in ordered_skills[:3]]
    recent_focus = memory.get("recentFocus") or []
    latest_focus = recent_focus[0] if recent_focus else {}
    latest_title = latest_focus.get("title") or "暂无"

    habits_lines = []
    if top_skills:
        habits_lines.append(f"- 高频技能：{'、'.join(top_skills)}")
    if profile.recommendation_summary:
        habits_lines.append(f"- 当前推荐方向：{_trim_memory_line(profile.recommendation_summary)}")
    habits_lines.append(f"- 最近会话关注：{_trim_memory_line(latest_title)}")

    skill_lines = []
    if preferred_skills:
        skill_lines.append(f"- 常用技能入口：{'、'.join(preferred_skills)}")
    for name, score in ordered_skills[:8]:
        skill_lines.append(f"- {name}：{score} 次")

    style_lines = [
        f"- 默认模型：{profile.default_model or '未设置'}",
    ]
    style_preferences = memory.get("stylePreferences") or []
    if style_preferences:
        style_lines.append(f"- 近期模型偏好：{'、'.join(style_preferences)}")

    focus_lines = []
    for item in recent_focus[:8]:
        title = item.get("title") or item.get("conversationId") or "未命名会话"
        skill = item.get("skill") or "unknown"
        updated_at = _format_time(item.get("updatedAt"))
        focus_lines.append(f"- {_trim_memory_line(title, 80)}｜技能：{skill}｜更新：{updated_at}")

    feedback_lines = []
    for item in memory.get("commonFeedback") or []:
        feedback_lines.append(f"- {_trim_memory_line(str(item), 120)}")
    manual_notes = memory.get("manualNotes") or ""
    if manual_notes:
        for line in manual_notes.splitlines():
            text = line.strip()
            if text:
                feedback_lines.append(f"- {_trim_memory_line(text, 120)}")
    if not feedback_lines:
        feedback_lines.append("- 暂无反馈记录。")

    return {
        "topics/habits.md": _render_topic_markdown("habits", habits_lines),
        "topics/skill_preferences.md": _render_topic_markdown("skill_preferences", skill_lines),
        "topics/style_preferences.md": _render_topic_markdown("style_preferences", style_lines),
        "topics/recent_focus.md": _render_topic_markdown("recent_focus", focus_lines),
        "topics/common_feedback.md": _render_topic_markdown("common_feedback", feedback_lines),
    }


def _render_identify_markdown(profile: V4UserProfile, current_user, preferred_skills: list[str], recent_title: str | None) -> str:
    identity = _loads(profile.identity_json, {})
    lines = [
        "# identify",
        "",
        f"- 用户姓名: {identity.get('name') or current_user.name}",
        f"- 账号: {identity.get('account') or current_user.account}",
        f"- 单位: {identity.get('orgName') or current_user.org_name or '未知'}",
        f"- 默认模型: {profile.default_model or current_user.default_model or '未设置'}",
        f"- 常用技能: {', '.join(preferred_skills) or '待学习'}",
    ]
    if recent_title:
        lines.append(f"- 最近会话: {recent_title}")
    return "\n".join(lines).strip() + "\n"


def _sync_profile_memory_projection(
    db: Session,
    current_user,
    profile: V4UserProfile,
    *,
    conversation: V4Conversation | None = None,
) -> V4UserProfile:
    preferred_skills = _loads(profile.preferred_skills_json, [])
    memory = _normalize_memory_state(_loads(profile.memory_json, {}))
    existing_memory_md = read_user_doc(current_user.user_id, profile.memory_md_path)
    if not memory.get("manualNotes"):
        memory["manualNotes"] = _extract_manual_notes_from_memory_markdown(existing_memory_md)
    profile.memory_json = _json(memory)

    recent_title = None
    if conversation is not None:
        recent_title = conversation.title
    elif memory.get("recentFocus"):
        recent_title = memory["recentFocus"][0].get("title")

    profile.identify_md_path = write_memory_doc(
        current_user.user_id,
        "identify.md",
        _render_identify_markdown(profile, current_user, preferred_skills, recent_title),
    )
    for relative_path, content in _build_memory_topics(profile, memory, preferred_skills).items():
        write_memory_doc(current_user.user_id, relative_path, content)
    profile.memory_md_path = write_memory_doc(
        current_user.user_id,
        "memory.md",
        _render_memory_index(memory.get("manualNotes") or ""),
    )
    if not profile.last_session_summary_md_path:
        profile.last_session_summary_md_path = write_memory_doc(
            current_user.user_id,
            "session_summary.md",
            "# session_summary\n\n- 暂无会话摘要。\n",
        )
    db.flush()
    return profile


def _render_session_detail_markdown(conversation: V4Conversation, summary: str, pending_question: str | None) -> str:
    lines = [
        "# session",
        "",
        "## 会话信息",
        f"- 标题: {conversation.title}",
        f"- 会话ID: {conversation.id}",
        f"- 更新时间: {_format_time(conversation.updated_at.isoformat())}",
        "",
        "## 关键摘要",
        summary or "暂无摘要。",
        "",
        "## 待续事项",
    ]
    if pending_question:
        lines.append(f"- {_trim_memory_line(pending_question, 120)}")
    else:
        lines.append("- 暂无。")
    return "\n".join(lines).strip() + "\n"


def _sync_session_summary_projection(db: Session, current_user, profile: V4UserProfile) -> V4UserProfile:
    snapshots = db.execute(
        select(V4CompressionSnapshot)
        .where(V4CompressionSnapshot.user_id == current_user.user_id)
        .order_by(V4CompressionSnapshot.created_at.desc())
    ).scalars().all()

    latest_by_conversation: dict[str, V4CompressionSnapshot] = {}
    for snapshot in snapshots:
        latest_by_conversation.setdefault(snapshot.conversation_id, snapshot)

    if not latest_by_conversation:
        profile.last_session_summary_md_path = write_memory_doc(
            current_user.user_id,
            "session_summary.md",
            "# session_summary\n\n- 暂无会话摘要。\n",
        )
        db.flush()
        return profile

    conversation_ids = list(latest_by_conversation.keys())
    conversations = db.execute(
        select(V4Conversation).where(V4Conversation.id.in_(conversation_ids))
    ).scalars().all()
    conversation_map = {item.id: item for item in conversations}

    index_lines = [
        "# session_summary",
        "",
        "- 这是近期会话摘要入口文件，按更新时间倒序查看。",
        "",
    ]
    for conversation_id, snapshot in list(latest_by_conversation.items())[:8]:
        conversation = conversation_map.get(conversation_id)
        if conversation is None:
            continue
        runtime_state = _read_runtime_state(conversation)
        pending_prompt = runtime_state.get("pendingPromptMenu") or {}
        pending_question = pending_prompt.get("question") or pending_prompt.get("description")
        write_memory_doc(
            current_user.user_id,
            f"sessions/{conversation_id}.md",
            _render_session_detail_markdown(conversation, snapshot.summary_markdown, pending_question),
        )
        index_lines.append(
            f"- {clip_title(conversation.title)}（{snapshot.created_at.strftime('%m-%d %H:%M')}） -> 见 sessions/{conversation_id}.md"
        )
    if len(index_lines) == 4:
        index_lines.append("- 暂无会话摘要。")
    profile.last_session_summary_md_path = write_memory_doc(
        current_user.user_id,
        "session_summary.md",
        "\n".join(index_lines).strip() + "\n",
    )
    db.flush()
    return profile


def _get_or_create_profile(db: Session, current_user) -> V4UserProfile:
    profile = db.execute(
        select(V4UserProfile).where(V4UserProfile.user_id == current_user.user_id)
    ).scalar_one_or_none()
    if profile is None:
        profile = V4UserProfile(
            user_id=current_user.user_id,
            default_model=current_user.default_model,
            preferred_skills_json=_json([]),
            identity_json=_json(
                {
                    "name": current_user.name,
                    "account": current_user.account,
                    "orgName": current_user.org_name,
                    "orgCode": current_user.org_code,
                }
            ),
            memory_json=_json(_default_memory_state()),
        )
        db.add(profile)
        db.flush()
    return profile


def _ensure_memory_docs(db: Session, current_user) -> V4UserProfile:
    profile = _get_or_create_profile(db, current_user)
    _sync_profile_memory_projection(db, current_user, profile)
    _sync_session_summary_projection(db, current_user, profile)
    return profile


def _context_usage_payload(
    *,
    summary: str,
    recent_messages: list[dict],
    current_input: str = "",
    conversation_id: str | None = None,
) -> dict:
    prompt_messages: list[dict[str, str]] = []
    if (summary or "").strip():
        prompt_messages.append({"role": "system", "content": summary.strip()})
    for item in recent_messages:
        prompt_messages.append(
            {
                "role": str(item.get("role") or "user"),
                "content": str(item.get("content") or ""),
            }
        )
    if (current_input or "").strip():
        prompt_messages.append({"role": "user", "content": current_input.strip()})

    estimated = estimate_tokens(prompt_messages) if prompt_messages else 0
    used = estimated
    source = "estimate"
    api_payload: dict | None = None
    api_usage = get_api_usage(conversation_id) if conversation_id else None
    if api_usage and api_usage.prompt_tokens > 0:
        # 以 API 最近一次 prompt_tokens 为基线；加上「估算中新增的那部分」避免只读历史不更新。
        baseline = api_usage.prompt_tokens
        used = max(baseline, estimated)
        source = "api"
        api_payload = api_usage.asdict()
    window = max(1, settings.context_window_tokens)
    ratio = used / window
    will_compact_at = max(1, int(window * settings.context_compact_trigger_ratio))
    payload = {
        "used": used,
        "window": window,
        "ratio": round(ratio, 4),
        "willCompactAt": will_compact_at,
        "source": source,
        "estimated": estimated,
        "triggerRatio": settings.context_compact_trigger_ratio,
    }
    if api_payload is not None:
        payload["apiUsage"] = api_payload
    return payload


def build_runtime_context(db: Session, conversation: V4Conversation) -> dict:
    messages = db.execute(
        select(V4ConversationMessage)
        .where(V4ConversationMessage.conversation_id == conversation.id)
        .order_by(V4ConversationMessage.created_at.asc())
    ).scalars().all()
    simplified = [
        {
            "id": message.id,
            "role": message.role,
            "content": _message_prompt_content(message),
            "skill_name": message.skill_name,
            "meta": _loads(message.meta_json, {}),
        }
        for message in messages
    ]
    recent = simplified[-settings.compaction_preserve_recent_messages :]
    summary = conversation.running_context_summary or ""
    context_usage = _context_usage_payload(
        summary=summary,
        recent_messages=recent,
        conversation_id=conversation.id,
    )
    return {
        "summary": summary,
        "recent_messages": recent,
        "message_count": len(simplified),
        "contextUsage": context_usage,
    }


def maybe_compact_conversation(
    db: Session,
    conversation: V4Conversation,
    current_user,
    *,
    force: bool = False,
) -> dict | None:
    messages = db.execute(
        select(V4ConversationMessage)
        .where(V4ConversationMessage.conversation_id == conversation.id)
        .order_by(V4ConversationMessage.created_at.asc())
    ).scalars().all()
    simplified = [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "meta": _loads(message.meta_json, {}),
        }
        for message in messages
    ]
    if len(simplified) <= settings.compaction_preserve_recent_messages:
        log_stage(
            "runtime.compaction.skip",
            {
                "conversationId": conversation.id,
                "reason": "message_count_not_enough",
                "messageCount": len(simplified),
                "preserveRecentMessages": settings.compaction_preserve_recent_messages,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return None

    prompt_recent = [
        {
            "id": item["id"],
            "role": item["role"],
            "content": _trim_prompt_text(item["content"], 240),
            "skill_name": None,
            "meta": item.get("meta") or {},
        }
        for item in simplified[-settings.compaction_preserve_recent_messages :]
    ]
    pre_usage = _context_usage_payload(
        summary=conversation.running_context_summary or "",
        recent_messages=prompt_recent,
        conversation_id=conversation.id,
    )
    trigger_ratio = settings.context_compact_trigger_ratio
    if not force and pre_usage["ratio"] < trigger_ratio:
        log_stage(
            "runtime.compaction.skip",
            {
                "conversationId": conversation.id,
                "reason": "context_ratio_below_threshold",
                "contextUsage": pre_usage,
                "triggerRatio": trigger_ratio,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return None

    older = simplified[: -settings.compaction_preserve_recent_messages]
    recent = simplified[-settings.compaction_preserve_recent_messages :]
    tool_names = []
    key_files = []
    for item in older + recent:
        meta = item.get("meta") or {}
        tool_names.extend(meta.get("tools", []))
        key_files.extend(meta.get("keyFiles", []))

    summary = build_structured_summary(older, recent, tool_names, key_files)
    compressed, stats = compress_summary_text(
        summary,
        SummaryCompressionBudget(
            max_chars=settings.compaction_summary_max_chars,
            max_lines=settings.compaction_summary_max_lines,
            max_line_chars=settings.compaction_summary_max_line_chars,
        ),
    )
    snapshot = V4CompressionSnapshot(
        conversation_id=conversation.id,
        user_id=current_user.user_id,
        summary=compressed,
        summary_markdown=compressed,
        source_message_ids_json=_json([item["id"] for item in older]),
        stats_json=_json(stats),
    )
    conversation.running_context_summary = compressed
    post_usage = _context_usage_payload(summary=compressed, recent_messages=prompt_recent)
    conversation.running_context_json = _json(
        {
            "summary": compressed,
            "recentMessages": recent,
            "messageCount": len(simplified),
            "stats": stats,
            "contextUsage": post_usage,
        }
    )
    db.add(snapshot)
    db.flush()
    log_stage(
        "runtime.compaction.created",
        {
            "conversationId": conversation.id,
            "summary": compressed,
            "stats": stats,
            "sourceMessageIds": [item["id"] for item in older],
            "recentMessages": recent,
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )

    profile = _ensure_memory_docs(db, current_user)
    _sync_session_summary_projection(db, current_user, profile)
    return {
        "snapshotId": snapshot.id,
        "summary": compressed,
        "stats": stats,
        "messageCount": len(simplified),
        "sourceMessageIds": [item["id"] for item in older],
        "force": force,
        "contextUsageBefore": pre_usage,
        "contextUsageAfter": post_usage,
    }


def _create_artifact_and_workspace_entry(
    db: Session,
    current_user,
    conversation: V4Conversation,
    run: V4ConversationRun,
    assistant_message: V4ConversationMessage,
    artifact: dict,
    annotations: list[dict],
) -> V4ConversationArtifact:
    artifact_contract = _normalize_artifact_contract(artifact)
    desired_path = ensure_unique_workspace_path(
        current_user.user_id,
        resolve_writable_file_path(artifact_contract["title"]),
        is_dir=False,
    )
    node = V4WorkspaceNode(
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        parent_id=None,
        node_type="document",
        source="conversation",
        name=desired_path.rsplit("/", 1)[-1],
        summary=artifact_contract.get("summary"),
        path=desired_path,
        relative_path=desired_path,
        kind="document",
    )
    content_text = html_to_plain_text(artifact_contract.get("contentHtml"), artifact_contract.get("summary"))
    file_bytes = build_docx_bytes(artifact_contract["title"], artifact_contract.get("contentHtml"), content_text)
    write_workspace_bytes(current_user.user_id, desired_path, file_bytes)
    db.add(node)
    db.flush()

    version_path = write_workspace_version(
        current_user.user_id,
        node.id,
        1,
        node.name,
        artifact_contract.get("contentHtml"),
        content_text,
        annotations,
        file_relative_path=desired_path,
        extra_meta={"source": "conversation"},
    )
    db.add(
        V4WorkspaceAttachmentLink(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            node_id=node.id,
            attachment_role="artifact",
        )
    )
    saved = V4ConversationArtifact(
        conversation_id=conversation.id,
        run_id=run.id,
        message_id=assistant_message.id,
        user_id=current_user.user_id,
        artifact_type=artifact_contract["artifactType"],
        title=artifact_contract["title"],
        summary=artifact_contract.get("summary"),
        content_html=artifact_contract.get("contentHtml"),
        workspace_node_id=node.id,
        meta_json=_json(
            {
                "relativePath": desired_path,
                "versionPath": version_path,
                "sourceSkill": artifact_contract.get("sourceSkill"),
                "sourceState": artifact_contract.get("sourceState"),
                "status": "ready",
                "errorDetail": None,
            }
        ),
    )
    db.add(saved)
    db.flush()
    return saved


def _next_event_seq_no(db: Session, run_id: str) -> int:
    row = db.execute(
        select(func.coalesce(func.max(V4TaskEvent.seq_no), 0)).where(V4TaskEvent.run_id == run_id)
    ).scalar_one()
    return int(row or 0) + 1


def _save_events(
    db: Session,
    run: V4ConversationRun,
    current_user,
    runtime_events: list[RuntimeTaskEvent],
    *,
    start_seq_no: int = 1,
) -> list[V4TaskEvent]:
    saved = []
    for seq_no, event in enumerate(runtime_events, start=start_seq_no):
        item = V4TaskEvent(
            run_id=run.id,
            conversation_id=run.conversation_id,
            user_id=current_user.user_id,
            task_id=run.task_id,
            parent_task_id=run.parent_task_id,
            seq_no=seq_no,
            event_type=event.event_type,
            status=event.status,
            title=event.title,
            detail=event.detail,
            detail_html=event.detail_html,
            payload_json=_json(event.payload),
        )
        db.add(item)
        saved.append(item)
    db.flush()
    return saved


def _save_new_events(
    db: Session,
    run: V4ConversationRun,
    current_user,
    runtime_events: list[RuntimeTaskEvent],
    saved_count: int,
) -> tuple[list[V4TaskEvent], int]:
    pending = runtime_events[saved_count:]
    if not pending:
        return [], saved_count
    next_seq = _next_event_seq_no(db, run.id)
    saved = _save_events(
        db,
        run,
        current_user,
        pending,
        start_seq_no=next_seq,
    )
    db.commit()
    return saved, len(runtime_events)


def _planner_cli_events(planner_meta: dict[str, Any]) -> list[RuntimeTaskEvent]:
    results: list[RuntimeTaskEvent] = []
    for item in planner_meta.get("plannerCliEvents") or []:
        results.append(
            RuntimeTaskEvent(
                item.get("event_type") or "cli_exec",
                item.get("status") or "completed",
                item.get("title") or "CLI 工具",
                item.get("detail") or "",
                item.get("detail_html") or "<pre></pre>",
                item.get("payload") or {},
            )
        )
    return results


def _touch_profile_after_run(
    db: Session,
    current_user,
    conversation: V4Conversation,
    skill_name: str,
    requested_model: str | None,
) -> V4UserProfile:
    profile = _ensure_memory_docs(db, current_user)
    memory = _normalize_memory_state(_loads(profile.memory_json, {}))
    skill_usage = memory.setdefault("skillUsage", {})
    skill_usage[skill_name] = int(skill_usage.get(skill_name, 0)) + 1
    if requested_model:
        memory.setdefault("stylePreferences", [])
        if requested_model not in memory["stylePreferences"]:
            memory["stylePreferences"].append(requested_model)
            memory["stylePreferences"] = memory["stylePreferences"][-5:]
    recent_focus = [item for item in memory.get("recentFocus", []) if item.get("conversationId") != conversation.id]
    recent_focus.insert(
        0,
        {
            "conversationId": conversation.id,
            "title": conversation.title,
            "skill": skill_name,
            "updatedAt": datetime.utcnow().isoformat(),
        },
    )
    memory["recentFocus"] = recent_focus[:8]
    profile.memory_json = _json(memory)
    profile.updated_at = datetime.utcnow()
    _sync_profile_memory_projection(db, current_user, profile, conversation=conversation)
    return profile


def _plan_payload(plan) -> dict:
    return {
        "intent": plan.intent,
        "summary": plan.summary,
        "requiresUserInput": plan.requires_user_input,
        "clarificationQuestion": plan.clarification_question,
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
    }


def _step_payload(step: ExecutionStep) -> dict:
    return {
        "index": step.index,
        "skillName": step.skill_name,
        "title": step.title,
        "objective": step.objective,
        "scope": step.scope,
        "dependsOn": step.depends_on,
        "subtaskRole": step.subtask_role,
    }


def _plan_from_payload(plan_payload: dict) -> ExecutionPlan:
    steps = [
        ExecutionStep(
            index=item.get("index", index),
            skill_name=item.get("skillName") or "general",
            title=item.get("title") or title_for_skill(item.get("skillName") or "general"),
            objective=item.get("objective") or "完成当前子任务。",
            scope=item.get("scope") or "完成当前任务。",
            depends_on=item.get("dependsOn") or [],
            subtask_role=item.get("subtaskRole") or "skill_worker",
        )
        for index, item in enumerate(plan_payload.get("steps") or [], start=1)
    ]
    return ExecutionPlan(
        intent=plan_payload.get("intent") or "document_workflow",
        summary=plan_payload.get("summary") or "leader 执行计划",
        steps=steps,
        requires_user_input=bool(plan_payload.get("requiresUserInput")),
        clarification_question=plan_payload.get("clarificationQuestion"),
    )


def _collect_task_tree(task_ids: list[str]) -> list[dict]:
    snapshots: list[dict] = []
    for task_id in task_ids:
        snapshot = a2a_task_registry.get_snapshot(task_id)
        if snapshot:
            snapshots.append(snapshot)
    return snapshots


def _read_runtime_state(conversation: V4Conversation) -> dict:
    state = _loads(conversation.running_context_json, {})
    if not isinstance(state, dict):
        return {}
    return state


def _merge_runtime_state(conversation: V4Conversation, runtime_context: dict, updates: dict) -> dict:
    current = _read_runtime_state(conversation)
    merged = {
        "summary": runtime_context.get("summary") or current.get("summary") or "",
        "recentMessages": runtime_context.get("recent_messages") or current.get("recentMessages") or [],
        "messageCount": runtime_context.get("message_count") or current.get("messageCount") or 0,
        "contextUsage": runtime_context.get("contextUsage") or current.get("contextUsage") or {},
    }
    merged.update({key: value for key, value in current.items() if key not in merged})
    merged.update(updates)
    conversation.running_context_json = _json(merged)
    return merged


def _assistant_turn_count(db: Session, conversation_id: str) -> int:
    messages = db.execute(
        select(V4ConversationMessage)
        .where(
            V4ConversationMessage.conversation_id == conversation_id,
            V4ConversationMessage.role == "assistant",
        )
        .order_by(V4ConversationMessage.created_at.asc())
    ).scalars().all()
    return len(messages)


def _should_summarize_conversation_title(db: Session, conversation: V4Conversation) -> bool:
    if conversation.title_locked:
        return False
    assistant_count = _assistant_turn_count(db, conversation.id)
    if assistant_count <= 0:
        return False
    return assistant_count == 1 or assistant_count % TITLE_SUMMARY_INTERVAL == 0


def _conversation_excerpt_for_title(messages: list[V4ConversationMessage]) -> str:
    lines: list[str] = []
    total_chars = 0
    for message in messages[-TITLE_SUMMARY_MAX_MESSAGES:]:
        role = "用户" if message.role == "user" else "助手"
        content = _trim_prompt_text(_message_prompt_content(message), 240)
        if not content:
            continue
        line = f"{role}: {content}"
        if total_chars + len(line) > settings.compaction_summary_max_chars:
            break
        lines.append(line)
        total_chars += len(line)
    return "\n".join(lines)


def _summarize_conversation_title(messages: list[V4ConversationMessage]) -> str:
    excerpt = _conversation_excerpt_for_title(messages)
    if not excerpt.strip():
        return ""
    prompt = (
        "基于以下对话，生成一个 6-14 字中文标题。"
        "要求：简洁、具体，不要标点，不要引号，不要输出解释，只输出标题本身。\n\n"
        f"{excerpt}"
    )
    response = call_chat_model_with_messages(
        [{"role": "user", "content": prompt}],
        settings.planner_model or settings.llm_default_model,
        purpose="conversation_title",
        temperature=0.2,
    )
    return normalize_conversation_title(response.get("text") or "")


def summarize_conversation_title_after_run(
    conversation_id: str,
    user_id: str,
    run_id: str,
) -> None:
    db = SessionLocal()
    try:
        conversation = db.execute(
            select(V4Conversation).where(
                V4Conversation.id == conversation_id,
                V4Conversation.user_id == user_id,
                V4Conversation.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        run = db.execute(
            select(V4ConversationRun).where(
                V4ConversationRun.id == run_id,
                V4ConversationRun.conversation_id == conversation_id,
                V4ConversationRun.user_id == user_id,
            )
        ).scalar_one_or_none()
        if conversation is None or run is None:
            return
        if not _should_summarize_conversation_title(db, conversation):
            return

        messages = db.execute(
            select(V4ConversationMessage)
            .where(V4ConversationMessage.conversation_id == conversation.id)
            .order_by(V4ConversationMessage.created_at.asc())
        ).scalars().all()
        if not messages:
            return

        try:
            title = _summarize_conversation_title(messages)
        except LLMCallError:
            return
        title = normalize_conversation_title(title)
        if not title:
            return

        db.expire_all()
        fresh_conversation = db.execute(
            select(V4Conversation).where(
                V4Conversation.id == conversation_id,
                V4Conversation.user_id == user_id,
                V4Conversation.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if fresh_conversation is None or fresh_conversation.title_locked:
            return

        fresh_conversation.title = title
        fresh_conversation.title_version = int(fresh_conversation.title_version or 0) + 1
        fresh_conversation.title_last_summarized_at = datetime.utcnow()
        fresh_conversation.updated_at = datetime.utcnow()

        event = V4TaskEvent(
            run_id=run.id,
            conversation_id=fresh_conversation.id,
            user_id=user_id,
            task_id=run.task_id,
            parent_task_id=run.parent_task_id,
            seq_no=_next_event_seq_no(db, run.id),
            event_type="conversation_title_updated",
            status="completed",
            title="会话标题已更新",
            detail=f"AI 已生成标题：{title}",
            detail_html=f"<p>AI 已生成标题：{escape(title)}</p>",
            payload_json=_json(
                {
                    "conversationId": fresh_conversation.id,
                    "title": title,
                    "titleVersion": fresh_conversation.title_version,
                    "titleLocked": fresh_conversation.title_locked,
                    "source": "ai_summary",
                    "runId": run.id,
                }
            ),
        )
        db.add(event)
        db.commit()
    finally:
        db.close()


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").replace("&nbsp;", " ").strip()


def _collect_followup_texts(skill_result: SkillExecutionResult) -> list[str]:
    lines: list[str] = []
    for block in skill_result.render_blocks:
        plain = _strip_html(block.get("html") or "")
        for line in plain.splitlines():
            text = line.strip(" -*#\t")
            if text:
                lines.append(text)

    def walk(value):
        if isinstance(value, str):
            text = _strip_html(value)
            if text:
                lines.append(text)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(skill_result.normalized_result)
    deduped: list[str] = []
    seen = set()
    for line in lines:
        key = line[:200]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _clarification_fallback(skill_name: str) -> str:
    mapping = {
        "retrieval": "当前还缺少更具体的检索范围，请补充资料方向、侧重点或项目名称后继续。",
        "writing": "当前还缺少更明确的写作要求，请补充文种、对象、重点或语气后继续。",
        "review": "当前还缺少审核范围，请补充需要重点检查的部分后继续。",
        "dedup": "当前还缺少查重范围，请补充目标文本或查重侧重点后继续。",
        "layout": "当前还缺少排版要求，请补充模板、格式或特殊约束后继续。",
    }
    return mapping.get(skill_name, "当前还缺少关键信息，请补充后继续。")


def _extract_followup_question(skill_result: SkillExecutionResult) -> str | None:
    markers = ("请补充", "请说明", "请确认", "请问", "可否", "是指什么", "需要哪方面", "请提供", "请告知")
    for line in _collect_followup_texts(skill_result):
        parts = re.split(r"[。！？?!]", line)
        candidates = [item.strip() for item in parts if item.strip()]
        for candidate in candidates:
            if candidate.endswith(("？", "?")) or any(marker in candidate for marker in markers):
                if len(candidate) <= 90 and not candidate.startswith(("您好", "我是")):
                    return candidate[:160]
        if line.endswith(("？", "?")) or any(marker in line for marker in markers):
            if len(line) <= 90 and not line.startswith(("您好", "我是")):
                return line[:160]
    return None


def _build_pending_context(runtime_context: dict, runtime_state: dict, user_message: str) -> dict:
    pending = runtime_state.get("pendingPromptMenu")
    if not pending:
        return runtime_context
    prompt_menu = pending.get("promptMenu") or {}
    enriched = dict(runtime_context)
    enriched["pending_task"] = {
        "skillName": pending.get("skillName"),
        "title": pending.get("title"),
        "resumeMode": pending.get("resumeMode"),
        "sourceState": pending.get("sourceState"),
    }
    enriched["pending_question"] = (
        prompt_menu.get("question")
        or prompt_menu.get("description")
        or prompt_menu.get("title")
        or pending.get("title")
    )
    enriched["user_answer_to_pending"] = (user_message or "").strip() or None
    return enriched


def _message_actions() -> dict:
    return {
        "canCopy": True,
        "canLike": True,
        "canDislike": True,
        "canRegenerate": True,
    }


def _build_prompt_menu(
    step: ExecutionStep,
    normalized_result: dict,
    annotations: list[dict],
    skill_result: SkillExecutionResult,
) -> dict:
    if step.skill_name == "review":
        return {
            "type": "review_actions",
            "title": "共审核出以下问题，接下来怎么处理？",
            "description": "可以全部修改、让我核对，或补充新的要求。",
            "options": [
                {"key": "accept_all", "label": "全部修改", "recommended": True},
                {"key": "manual_review", "label": "让我核对", "recommended": False},
                {"key": "custom_input", "label": "都不是，我来补充", "recommended": False},
            ],
            "annotations": annotations,
            "resultPreview": normalized_result,
        }
    if step.skill_name == "dedup":
        return {
            "type": "duplicate_actions",
            "title": "是否继续生成查重报告？",
            "description": "可以直接生成报告，也可以补充改写要求。",
            "options": [
                {"key": "generate_report", "label": "是", "recommended": True},
                {"key": "skip_report", "label": "否", "recommended": False},
                {"key": "custom_input", "label": "都不是，我来补充", "recommended": False},
            ],
            "annotations": annotations,
            "resultPreview": normalized_result,
        }
    if step.skill_name == "layout":
        templates = normalized_result.get("templates") or []
        return {
            "type": "format_actions",
            "title": "是否应用推荐模板，或手动选择模板？",
            "description": "可以直接套用推荐模板，也可以手动选择或补充特殊要求。",
            "options": [
                {"key": "apply_recommended", "label": "推荐模板", "recommended": True},
                {"key": "choose_template", "label": "手动选择模板", "recommended": False},
                {"key": "custom_input", "label": "都不是，我来补充", "recommended": False},
            ],
            "templates": templates,
            "resultPreview": normalized_result,
        }
    if skill_result.prompt_menu:
        return skill_result.prompt_menu
    question = _extract_followup_question(skill_result)
    if question and (skill_result.retryable or step.skill_name in INTERACTIVE_SKILLS):
        return {
            "type": "clarification",
            "title": f"{title_for_skill(step.skill_name)}需要补充信息",
            "description": question,
            "question": question,
            "options": [
                {"key": "custom_input", "label": "补充信息", "recommended": True},
            ],
            "resultPreview": normalized_result,
            "resumeMode": "rerun_current_step",
        }
    return {}


def _resolve_prompt_menu_choice(
    menu_state: dict,
    selected_option: str | None,
    prompt_menu_input: str | None,
) -> tuple[dict, list[dict], list[dict], list[dict], dict | None]:
    skill_name = menu_state.get("skillName") or "general"
    title = menu_state.get("title") or title_for_skill(skill_name)
    normalized_result = menu_state.get("normalizedResult") or {}
    annotations = menu_state.get("annotations") or []
    selected = selected_option or ""
    custom_text = (prompt_menu_input or "").strip()
    prompt_menu = menu_state.get("promptMenu") or {}

    if prompt_menu.get("type") == "clarification":
        answer_text = custom_text or selected or "已补充信息。"
        question_text = prompt_menu.get("question") or prompt_menu.get("description") or title
        return (
            {
                "question": question_text,
                "user_clarification": answer_text,
                "mode": "clarification_reply",
            },
            [
                {
                    "type": "clarification",
                    "title": title,
                    "html": (
                        f"<p>已补充信息：{escape(answer_text)}</p>"
                        f"<p>针对问题：{escape(question_text)}</p>"
                    ),
                }
            ],
            [],
            annotations,
            None,
        )

    if skill_name == "review":
        if selected == "manual_review":
            return (
                {
                    "issues": normalized_result.get("issues") or [],
                    "mode": "manual_review",
                    "message": "已进入人工核对模式，可在编辑器中逐条核对问题。",
                },
                [
                    {
                        "type": "review",
                        "title": "人工核对模式",
                        "html": "<p>已切换到人工核对模式，请在右侧联动编辑器中逐条核对问题。</p>",
                    }
                ],
                [
                    {
                        "artifactType": "document",
                        "title": "审核联动核对稿.docx",
                        "summary": "已生成带审核标注的联动核对稿。",
                        "contentHtml": "<p>已切换到人工核对模式，请在编辑器中处理审核问题。</p>",
                        "sourceSkill": "review",
                        "status": "ready",
                    }
                ],
                annotations,
                None,
            )
        revised_text = custom_text or "已根据审核意见自动修订正文，并生成修订稿。"
        return (
            {
                "issues": normalized_result.get("issues") or [],
                "mode": "apply_review",
                "message": revised_text,
            },
            [
                {
                    "type": "document",
                    "title": "审核修订结果",
                    "html": f"<p>{escape(revised_text)}</p>",
                }
            ],
            [
                {
                    "artifactType": "document",
                    "title": "审核修订稿.docx",
                    "summary": "已根据审核意见生成修订稿。",
                    "contentHtml": f"<p>{escape(revised_text)}</p>",
                    "sourceSkill": "review",
                    "status": "ready",
                }
            ],
            [],
            None,
        )

    if skill_name == "dedup":
        if selected == "skip_report":
            return (
                {
                    "items": normalized_result.get("items") or [],
                    "mode": "skip_report",
                    "message": "已保留查重明细，不生成正式查重报告。",
                },
                [{"type": "duplicate", "title": "查重后续处理", "html": "<p>已保留查重明细，不生成正式报告。</p>"}],
                [],
                annotations,
                None,
            )
        report_text = custom_text or "已根据查重结果生成结构化查重报告。"
        return (
            {
                "items": normalized_result.get("items") or [],
                "mode": "generate_report",
                "message": report_text,
            },
            [{"type": "duplicate", "title": "查重报告", "html": f"<p>{escape(report_text)}</p>"}],
            [
                {
                    "artifactType": "report",
                    "title": "查重报告.docx",
                    "summary": "已生成正式查重报告。",
                    "contentHtml": f"<p>{escape(report_text)}</p>",
                    "sourceSkill": "dedup",
                    "status": "ready",
                }
            ],
            annotations,
            None,
        )

    if skill_name == "layout":
        templates = normalized_result.get("templates") or []
        if selected == "choose_template" and not custom_text:
            template_options = [
                {
                    "key": f"template::{index}",
                    "label": item.get("templateTitle") or item.get("title") or f"模板 {index}",
                    "recommended": index == 1,
                }
                for index, item in enumerate(templates[:8], start=1)
            ]
            return (
                {},
                [],
                [],
                [],
                {
                    "type": "template_picker",
                    "title": "请选择一个排版模板",
                    "description": "可直接选择模板，或在输入框中补充模板要求。",
                    "options": template_options,
                },
            )
        template_name = custom_text or "党政机关标准版"
        if selected.startswith("template::"):
            try:
                template_index = int(selected.split("::", 1)[1]) - 1
                template = templates[template_index]
                template_name = template.get("templateTitle") or template.get("title") or template_name
            except (IndexError, ValueError):
                template_name = template_name
        return (
            {
                "templates": templates,
                "mode": "apply_template",
                "templateName": template_name,
            },
            [{"type": "format", "title": "排版结果", "html": f"<p>已应用模板：{escape(template_name)}</p>"}],
            [
                {
                    "artifactType": "document",
                    "title": "排版完成稿.docx",
                    "summary": f"已应用模板：{template_name}",
                    "contentHtml": f"<p>已应用模板：{escape(template_name)}</p>",
                    "sourceSkill": "layout",
                    "status": "ready",
                }
            ],
            [],
            None,
        )

    return (
        {
            "message": custom_text or f"已处理 {title} 的后续操作。",
        },
        [{"type": "general", "title": title, "html": f"<p>{escape(custom_text or f'已处理 {title} 的后续操作。')}</p>"}],
        [],
        annotations,
        None,
    )


def _build_final_assistant_output(
    requested_model: str | None,
    plan,
    step_outcomes: list[dict],
) -> tuple[str, str]:
    if not step_outcomes:
        return "任务未执行", "<p>当前未生成有效结果。</p>"

    if len(step_outcomes) == 1:
        outcome = step_outcomes[0]
        return outcome["summary"], outcome["html"]

    completed_titles = [item["title"] for item in step_outcomes]
    summary = "已完成" + "、".join(completed_titles)
    sections = [
        (
            "<div class='assistant-copy'>模型 "
            f"<strong>{escape(requested_model or '')}</strong> 已按 A2A 执行计划完成 "
            f"{len(step_outcomes)} 个子任务。</div>"
        ),
        f"<section class='assistant-block'><h4>Leader Plan</h4><p>{escape(plan.summary)}</p></section>",
    ]
    for outcome in step_outcomes:
        sections.append(
            (
                "<section class='assistant-block'>"
                f"<h4>Step {outcome['index']} · {escape(outcome['title'])}</h4>"
                f"{outcome['html']}"
                "</section>"
            )
        )
    return summary, "".join(sections)


def _merge_annotations(step_outcomes: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for outcome in step_outcomes:
        merged.extend(outcome.get("annotations") or [])
    return merged


def _subtask_trace(step_outcomes: list[dict]) -> list[dict]:
    return [
        {
            "taskId": item["task_id"],
            "skillName": item["skill_name"],
            "title": item["title"],
            "summary": item["summary"],
            "retryable": item["retryable"],
            "normalizedResult": item["normalized_result"],
        }
        for item in step_outcomes
    ]


def _step_sid(step: ExecutionStep) -> str:
    return f"step_{step.index:02d}_{step.skill_name}"


def _execution_step_waves(steps: list[ExecutionStep]) -> list[list[ExecutionStep]]:
    """按 depends_on 分层；同波次内无未满足依赖的步骤可并行执行（opt5）。"""
    if not steps:
        return []
    pending = sorted(steps, key=lambda s: s.index)
    by_sid = {_step_sid(s): s for s in pending}
    completed: set[str] = set()
    waves: list[list[ExecutionStep]] = []
    remaining = list(pending)
    while remaining:
        ready: list[ExecutionStep] = []
        for s in list(remaining):
            deps = s.depends_on or []
            blocked = False
            for d in deps:
                if d in by_sid and d not in completed:
                    blocked = True
                    break
            if not blocked:
                ready.append(s)
        if not ready:
            s = min(remaining, key=lambda x: x.index)
            ready = [s]
        ready.sort(key=lambda x: x.index)
        waves.append(ready)
        for s in ready:
            remaining.remove(s)
            completed.add(_step_sid(s))
    return waves


def _html_from_blocks(
    requested_model: str | None,
    summary: str,
    blocks: list[dict],
    *,
    lead_copy: str,
) -> str:
    sections = [f"<div class='assistant-copy'>{lead_copy}</div>"]
    for block in blocks:
        sections.append(
            "<section class='assistant-block'>"
            f"<h4>{escape(block.get('title') or summary)}</h4>"
            f"{block.get('html') or '<p></p>'}"
            "</section>"
        )
    if not blocks:
        sections.append(f"<section class='assistant-block'><h4>{escape(summary)}</h4><p>暂无内容。</p></section>")
    return "".join(sections)


def _make_planner_stream_batcher(
    push_event: Callable[[RuntimeTaskEvent], None],
) -> Callable[[dict[str, Any]], None]:
    """Batch planner SSE chunks into planner_reasoning_delta DB events for early UI updates."""
    last_flush_len = 0
    last_t = time.monotonic()
    batch_chars = 72
    flush_interval = 0.35

    def _emit(display: str) -> None:
        push_event(
            RuntimeTaskEvent(
                "planner_reasoning_delta",
                "running",
                "Lead Agent 思考中",
                display,
                f"<pre class='planner-reasoning'>{escape(display[-12000:])}</pre>",
                {"reasoningSoFar": display, "phase": "planner_stream"},
            )
        )

    def on_planner(ev: dict[str, Any]) -> None:
        nonlocal last_flush_len, last_t
        if ev.get("flush"):
            reasoning = (ev.get("reasoning") or "").strip()
            text = (ev.get("text") or "").strip()
            display = reasoning or text
            if len(display) > last_flush_len or display:
                _emit(display)
                last_flush_len = len(display)
                last_t = time.monotonic()
            return
        reasoning = ev.get("reasoning") or ""
        text = ev.get("text") or ""
        display = reasoning.strip() and reasoning or text
        if not display:
            return
        now = time.monotonic()
        n = len(display)
        if n - last_flush_len >= batch_chars or (now - last_t) >= flush_interval:
            _emit(display)
            last_flush_len = n
            last_t = now

    return on_planner


def prepare_run_conversation(
    db: Session,
    conversation: V4Conversation,
    current_user,
    content: str,
    requested_skill: str | None,
    requested_model: str | None,
    attachments: list[dict],
    operation_context: dict | None,
    cookies: str | None,
    resume_from_waiting: bool = False,
    selected_option: str | None = None,
    prompt_menu_input: str | None = None,
) -> dict:
    requested_model = requested_model or current_user.default_model
    operation_context = _normalize_operation_context(operation_context)
    runtime_state = _read_runtime_state(conversation)
    pending_prompt_menu = runtime_state.get("pendingPromptMenu")
    auto_resume_waiting = (
        bool(pending_prompt_menu)
        and not resume_from_waiting
        and not selected_option
        and not (prompt_menu_input or "").strip()
        and (pending_prompt_menu.get("resumeMode") == "rerun_current_step")
        and bool((content or "").strip())
    )
    if auto_resume_waiting:
        resume_from_waiting = True
        selected_option = "custom_input"
        prompt_menu_input = content

    if resume_from_waiting and not pending_prompt_menu:
        raise ValueError("当前会话没有等待中的任务")
    if resume_from_waiting and not (selected_option or (prompt_menu_input or "").strip()):
        raise ValueError("请先选择一个后续操作，或输入补充要求")

    task_id = task_registry.next_task_id(conversation.id)
    run = V4ConversationRun(
        conversation_id=conversation.id,
        user_id=current_user.user_id,
        task_id=task_id,
        objective=content,
        requested_skill=requested_skill or (pending_prompt_menu or {}).get("skillName"),
        status="queued",
        model_name=requested_model,
        input_payload_json=_json(
            {
                "content": content,
                "requestedSkill": requested_skill,
                "requestedModel": requested_model,
                "attachments": attachments,
                "operationContext": operation_context,
                "resumeFromWaiting": resume_from_waiting,
                "selectedOption": selected_option,
                "promptMenuInput": prompt_menu_input,
                "cookiePreview": mask_cookie(cookies),
            }
        ),
        context_snapshot_json=_json(runtime_state),
    )
    db.add(run)
    conversation.last_run_id = run.id
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    # 尽早落库一条 created，使前端在规划完成前即可拉 SSE 看到反馈（opt3）
    _save_events(
        db,
        run,
        current_user,
        [
            RuntimeTaskEvent(
                "created",
                "created",
                "Lead Agent 已接收任务",
                "任务已创建，正在排队执行。",
                "<p>任务已创建，正在排队执行。</p>",
                {
                    "phase": "prepared",
                    "runId": run.id,
                    "taskId": task_id,
                    "requestedSkill": requested_skill,
                },
            )
        ],
        start_seq_no=1,
    )
    db.commit()
    return {
        "run": run,
        "request": {
            "content": content,
            "requestedSkill": requested_skill,
            "requestedModel": requested_model,
            "attachments": attachments,
            "operationContext": operation_context,
            "resumeFromWaiting": resume_from_waiting,
            "selectedOption": selected_option,
            "promptMenuInput": prompt_menu_input,
        },
    }


def run_conversation(
    db: Session,
    conversation: V4Conversation,
    current_user,
    content: str,
    requested_skill: str | None,
    requested_model: str | None,
    attachments: list[dict],
    operation_context: dict | None,
    cookies: str | None,
    resume_from_waiting: bool = False,
    selected_option: str | None = None,
    prompt_menu_input: str | None = None,
    prepared_run_id: str | None = None,
    prepared_task_id: str | None = None,
) -> dict:
    requested_model = requested_model or current_user.default_model
    operation_context = _normalize_operation_context(operation_context)
    effective_goal, rewrite_mode = _expand_effective_goal(content, operation_context)
    runtime_state = _read_runtime_state(conversation)
    pending_prompt_menu = runtime_state.get("pendingPromptMenu")
    auto_resume_waiting = (
        bool(pending_prompt_menu)
        and not resume_from_waiting
        and not selected_option
        and not (prompt_menu_input or "").strip()
        and (pending_prompt_menu.get("resumeMode") == "rerun_current_step")
        and bool((content or "").strip())
    )
    if auto_resume_waiting:
        resume_from_waiting = True
        selected_option = "custom_input"
        prompt_menu_input = content

    if resume_from_waiting and not pending_prompt_menu:
        raise ValueError("当前会话没有等待中的任务")
    if resume_from_waiting and not (selected_option or (prompt_menu_input or "").strip()):
        raise ValueError("请先选择一个后续操作，或输入补充要求")

    log_stage(
        "runtime.run.start",
        {
            "conversationId": conversation.id,
            "conversationTitle": conversation.title,
            "user": {
                "userId": current_user.user_id,
                "name": current_user.name,
                "account": current_user.account,
                "orgName": current_user.org_name,
            },
            "request": {
                "content": content,
                "requestedSkill": requested_skill,
                "resolvedSkill": requested_skill or "pending_model_planner",
                "requestedModel": requested_model,
                "attachments": attachments,
                "operationContext": operation_context,
                "effectiveGoal": effective_goal,
                "rewriteMode": rewrite_mode,
                "cookiePreview": mask_cookie(cookies),
                "resumeFromWaiting": resume_from_waiting,
                "selectedOption": selected_option,
                "promptMenuInput": prompt_menu_input,
            },
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )

    profile = _ensure_memory_docs(db, current_user)
    memory_context = build_prompt_profile_docs(current_user, profile)
    runtime_context = build_runtime_context(db, conversation)
    runtime_context = _build_pending_context(runtime_context, runtime_state, content)
    runtime_context["workspaceUserId"] = current_user.user_id
    runtime_context["conversationId"] = conversation.id
    runtime_context["contextUsage"] = _context_usage_payload(
        summary=runtime_context.get("summary") or "",
        recent_messages=runtime_context.get("recent_messages") or [],
        current_input=effective_goal,
        conversation_id=conversation.id,
    )
    attachment_context = _build_attachment_context(db, current_user, attachments)

    if resume_from_waiting:
        resume_mode = pending_prompt_menu.get("resumeMode") or "prompt_menu_choice"
        plan_steps_payload = pending_prompt_menu.get("remainingSteps") or []
        if resume_mode == "rerun_current_step" and pending_prompt_menu.get("resumeCurrentStep"):
            plan_steps_payload = [pending_prompt_menu["resumeCurrentStep"], *plan_steps_payload]
        plan = ExecutionPlan(
            intent=(pending_prompt_menu.get("plan") or {}).get("intent") or "document_workflow",
            summary=f"恢复执行：{pending_prompt_menu.get('title') or '待处理任务'}",
            steps=[
                ExecutionStep(
                    index=item.get("index", index),
                    skill_name=item.get("skillName") or "general",
                    title=item.get("title") or title_for_skill(item.get("skillName") or "general"),
                    objective=item.get("objective") or "完成当前子任务。",
                    scope=item.get("scope") or "完成当前任务。",
                    depends_on=item.get("dependsOn") or [],
                    subtask_role=item.get("subtaskRole") or "skill_worker",
                )
                for index, item in enumerate(plan_steps_payload, start=1)
            ],
        )
        planner_meta = {
            "planner": "resume_from_waiting",
            "fallback": False,
            "resumeToken": pending_prompt_menu.get("resumeToken"),
            "sourceSkill": pending_prompt_menu.get("skillName"),
            "resumeMode": resume_mode,
        }
        primary_skill = (
            (pending_prompt_menu.get("resumeCurrentStep") or {}).get("skillName")
            or pending_prompt_menu.get("skillName")
            or requested_skill
            or "general"
        )
        content = (prompt_menu_input or selected_option or content or "").strip() or "继续执行"
        effective_goal = pending_prompt_menu.get("resumeInput") or effective_goal or content
        planning_pre_events = None
        planning_saved_count = 0
        planning_run: V4ConversationRun | None = None
    else:
        planning_pre_events = None
        planning_saved_count = 0
        planning_run = None
        if prepared_run_id:
            planning_run = db.execute(
                select(V4ConversationRun).where(
                    V4ConversationRun.id == prepared_run_id,
                    V4ConversationRun.conversation_id == conversation.id,
                    V4ConversationRun.user_id == current_user.user_id,
                )
            ).scalar_one()
            pre_events: list[RuntimeTaskEvent] = []
            saved_pre = 0

            def push_planning_event(event: RuntimeTaskEvent) -> None:
                nonlocal saved_pre
                pre_events.append(event)
                _, saved_pre = _save_new_events(db, planning_run, current_user, pre_events, saved_pre)

            on_planner = _make_planner_stream_batcher(push_planning_event)
            plan, planner_meta = build_model_execution_plan(
                effective_goal,
                requested_skill,
                attachments,
                requested_model,
                runtime_context=runtime_context,
                memory_context=memory_context,
                on_planner_stream=on_planner,
            )
            primary_skill = plan.primary_skill
            planning_pre_events = pre_events
            planning_saved_count = saved_pre
        else:
            plan, planner_meta = build_model_execution_plan(
                effective_goal,
                requested_skill,
                attachments,
                requested_model,
                runtime_context=runtime_context,
                memory_context=memory_context,
            )
            primary_skill = plan.primary_skill

    log_stage(
        "runtime.memory.refs",
        {
            "conversationId": conversation.id,
            "identifyMdPath": profile.identify_md_path,
            "memoryMdPath": profile.memory_md_path,
            "sessionSummaryMdPath": profile.last_session_summary_md_path,
            "recommendationSummary": profile.recommendation_summary,
            "memoryContext": memory_context,
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    log_stage(
        "runtime.context.built",
        {
            "conversationId": conversation.id,
            "runtimeContext": runtime_context,
            "runningContextJson": runtime_state,
            "plannerMeta": planner_meta,
            "leaderPlan": _plan_payload(plan),
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )

    task_id = task_registry.next_task_id(conversation.id)
    user_memory_refs = [
        value
        for value in [
            profile.identify_md_path,
            profile.memory_md_path,
            profile.last_session_summary_md_path,
        ]
        if value
    ]
    packet = build_root_task_packet(
        task_id=task_id,
        conversation_id=conversation.id,
        objective=effective_goal if not resume_from_waiting else f"恢复执行：{effective_goal}",
        requested_model=requested_model,
        plan=plan,
        attachments=attachments,
        runtime_context_summary=runtime_context["summary"],
        user_memory_refs=user_memory_refs,
    )
    packet.input_payload["content"] = effective_goal
    packet.input_payload["operationType"] = operation_context.get("intentType")
    packet.input_payload["rewriteMode"] = rewrite_mode
    packet.input_payload["baseUserGoal"] = operation_context.get("baseUserGoal") or effective_goal
    packet.input_payload["latestAssistantSummary"] = operation_context.get("latestAssistantSummary")
    packet.input_payload["latestArtifactRefs"] = operation_context.get("latestArtifactRefs") or []
    packet.input_payload["attachmentContext"] = attachment_context
    if resume_from_waiting:
        packet.resume_token = pending_prompt_menu.get("resumeToken")
        packet.prompt_menu_contract = pending_prompt_menu.get("promptMenu") or {}

    root_task = a2a_task_registry.register(
        packet,
        "Leader Agent Root Task",
        team_id="leader-agent",
    )
    a2a_task_registry.append_message(task_id, "user", effective_goal)
    log_stage(
        "runtime.task_packet",
        {
            "conversationId": conversation.id,
            "taskPacket": packet,
            "leaderPlan": _plan_payload(plan),
            "plannerMeta": planner_meta,
            "rootTask": root_task.snapshot(),
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )

    user_message = V4ConversationMessage(
        conversation_id=conversation.id,
        user_id=current_user.user_id,
        role="user",
        skill_name=primary_skill,
        model_name=requested_model,
        content=content,
        content_html=f"<p>{escape(content)}</p>",
        meta_json=_json(
            {
                "attachments": attachments,
                "effectiveGoal": effective_goal,
                "operationType": operation_context.get("intentType"),
                "regenerateContext": operation_context,
                "tools": ["lead_agent"],
                "leaderPlan": _plan_payload(plan),
                "plannerMeta": planner_meta,
                "resumeFromWaiting": resume_from_waiting,
                "selectedOption": selected_option,
            }
        ),
    )
    db.add(user_message)
    db.flush()

    if planning_run is not None:
        run = planning_run
        run.task_id = prepared_task_id or run.task_id or task_id
        run.objective = effective_goal
        run.requested_skill = primary_skill
        run.status = "running"
        run.model_name = requested_model
        run.input_payload_json = _json(
            {
                "taskPacket": packet.model_dump(),
                "leaderPlan": _plan_payload(plan),
                "plannerMeta": planner_meta,
                "operationContext": operation_context,
                "pendingPromptMenu": pending_prompt_menu if resume_from_waiting else None,
            }
        )
        run.context_snapshot_json = _json(runtime_context)
        run.updated_at = datetime.utcnow()
    elif prepared_run_id:
        run = db.execute(
            select(V4ConversationRun).where(
                V4ConversationRun.id == prepared_run_id,
                V4ConversationRun.conversation_id == conversation.id,
                V4ConversationRun.user_id == current_user.user_id,
            )
        ).scalar_one()
        run.task_id = prepared_task_id or run.task_id or task_id
        run.objective = effective_goal
        run.requested_skill = primary_skill
        run.status = "running"
        run.model_name = requested_model
        run.input_payload_json = _json(
            {
                "taskPacket": packet.model_dump(),
                "leaderPlan": _plan_payload(plan),
                "plannerMeta": planner_meta,
                "operationContext": operation_context,
                "pendingPromptMenu": pending_prompt_menu if resume_from_waiting else None,
            }
        )
        run.context_snapshot_json = _json(runtime_context)
        run.updated_at = datetime.utcnow()
    else:
        run = V4ConversationRun(
            conversation_id=conversation.id,
            user_id=current_user.user_id,
            task_id=task_id,
            objective=effective_goal,
            requested_skill=primary_skill,
            status="running",
            model_name=requested_model,
            input_payload_json=_json(
                {
                    "taskPacket": packet.model_dump(),
                    "leaderPlan": _plan_payload(plan),
                    "plannerMeta": planner_meta,
                    "operationContext": operation_context,
                    "pendingPromptMenu": pending_prompt_menu if resume_from_waiting else None,
                }
            ),
            context_snapshot_json=_json(runtime_context),
        )
        db.add(run)
    db.flush()

    if planning_pre_events is not None:
        runtime_events = planning_pre_events
        saved_events_count = planning_saved_count
        runtime_events.extend(
            [
                RuntimeTaskEvent(
                    "context_usage",
                    "info",
                    "上下文使用情况",
                    (
                        f"{runtime_context['contextUsage']['used']} / "
                        f"{runtime_context['contextUsage']['window']} tokens"
                    ),
                    (
                        "<p>已完成本轮 prompt 上下文计量。</p>"
                        f"<pre>used = {runtime_context['contextUsage']['used']}\n"
                        f"window = {runtime_context['contextUsage']['window']}\n"
                        f"ratio = {runtime_context['contextUsage']['ratio']}\n"
                        f"willCompactAt = {runtime_context['contextUsage']['willCompactAt']}</pre>"
                    ),
                    runtime_context["contextUsage"],
                ),
            ]
            + _planner_cli_events(planner_meta)
            + [
                RuntimeTaskEvent(
                    "running",
                    "running",
                    "Lead Agent 生成执行计划",
                    "已完成执行计划生成与校验。",
                    (
                        "<p>已完成执行计划生成。</p>"
                        + (
                            f"<pre>{escape(planner_meta.get('reasoningContent') or '')}</pre>"
                            if planner_meta.get("reasoningContent")
                            else ""
                        )
                    ),
                    {"plan": _plan_payload(plan), "context": runtime_context, "plannerMeta": planner_meta},
                ),
                RuntimeTaskEvent(
                    "tool_call",
                    "running",
                    "Leader Agent · A2A Planning",
                    f"已生成 {len(plan.steps)} 个执行步骤，并构造根 TaskPacket。",
                    (
                        f"<pre>intent = {escape(plan.intent)}\nsteps = {escape(' -> '.join(step.skill_name for step in plan.steps) or 'none')}\nmodel = {escape(requested_model or '')}</pre>"
                        + (
                            f"<pre>{escape(planner_meta.get('reasoningContent') or '')}</pre>"
                            if planner_meta.get("reasoningContent")
                            else ""
                        )
                    ),
                    {"taskPacket": packet.model_dump(), "plan": _plan_payload(plan), "plannerMeta": planner_meta},
                ),
            ]
        )
    else:
        runtime_events = [
            RuntimeTaskEvent(
                "created",
                "created",
                "Lead Agent 已接收任务",
                f"任务已创建，准备处理 {primary_skill}。",
                "<p>任务已创建，准备处理当前请求。</p>",
                {"taskPacket": packet.model_dump(), "registry": root_task.snapshot()},
            ),
            RuntimeTaskEvent(
                "context_usage",
                "info",
                "上下文使用情况",
                (
                    f"{runtime_context['contextUsage']['used']} / "
                    f"{runtime_context['contextUsage']['window']} tokens"
                ),
                (
                    "<p>已完成本轮 prompt 上下文计量。</p>"
                    f"<pre>used = {runtime_context['contextUsage']['used']}\n"
                    f"window = {runtime_context['contextUsage']['window']}\n"
                    f"ratio = {runtime_context['contextUsage']['ratio']}\n"
                    f"willCompactAt = {runtime_context['contextUsage']['willCompactAt']}</pre>"
                ),
                runtime_context["contextUsage"],
            ),
            *_planner_cli_events(planner_meta),
            RuntimeTaskEvent(
                "running",
                "running",
                "Lead Agent 生成执行计划",
                "正在结合用户输入、上下文摘要和个性化记忆生成 A2A 执行计划。",
                (
                    "<p>正在结合用户输入、上下文摘要和个性化记忆生成 A2A 执行计划。</p>"
                    + (
                        f"<pre>{escape(planner_meta.get('reasoningContent') or '')}</pre>"
                        if planner_meta.get("reasoningContent")
                        else ""
                    )
                ),
                {"plan": _plan_payload(plan), "context": runtime_context, "plannerMeta": planner_meta},
            ),
            RuntimeTaskEvent(
                "tool_call",
                "running",
                "Leader Agent · A2A Planning",
                f"已生成 {len(plan.steps)} 个执行步骤，并构造根 TaskPacket。",
                (
                    f"<pre>intent = {escape(plan.intent)}\nsteps = {escape(' -> '.join(step.skill_name for step in plan.steps) or 'none')}\nmodel = {escape(requested_model or '')}</pre>"
                    + (
                        f"<pre>{escape(planner_meta.get('reasoningContent') or '')}</pre>"
                        if planner_meta.get("reasoningContent")
                        else ""
                    )
                ),
                {"taskPacket": packet.model_dump(), "plan": _plan_payload(plan), "plannerMeta": planner_meta},
            ),
        ]
        saved_events_count = 0
    db.commit()
    _, saved_events_count = _save_new_events(db, run, current_user, runtime_events, saved_events_count)

    def push_event(event: RuntimeTaskEvent) -> None:
        nonlocal saved_events_count
        runtime_events.append(event)
        _, saved_events_count = _save_new_events(db, run, current_user, runtime_events, saved_events_count)

    def persist_main_agent_waiting(prompt_menu: dict) -> dict:
        pending_state = {
            "resumeToken": f"{run.id}:{task_id}:preflight",
            "taskId": task_id,
            "parentTaskId": None,
            "skillName": primary_skill,
            "stepIndex": 0,
            "title": "Main Agent 预补充",
            "promptMenu": prompt_menu,
            "resumeMode": prompt_menu.get("resumeMode") or "prompt_menu_choice",
            "resumeCurrentStep": None,
            "normalizedResult": {},
            "annotations": [],
            "remainingSteps": [_step_payload(item) for item in plan.steps],
            "plan": _plan_payload(plan),
            "resumeInput": effective_goal,
            "sourceState": "main_agent_preflight",
            "errorDetail": None,
        }
        preflight_text = (
            prompt_menu.get("description") or prompt_menu.get("title") or "请先补充信息后继续。"
        )
        preflight_blocks = build_assistant_blocks(
            plan=plan,
            step_outcomes=[],
            pending_artifacts=[],
            pending_prompt_menu={"promptMenu": prompt_menu, "title": "Main Agent 预补充"},
            planner_meta=planner_meta,
            final_text=preflight_text,
        )
        assistant_message = V4ConversationMessage(
            conversation_id=conversation.id,
            run_id=run.id,
            user_id=current_user.user_id,
            role="assistant",
            skill_name=primary_skill,
            model_name=requested_model,
            content=preflight_text,
            content_html=blocks_to_snapshot_html(preflight_blocks),
            annotations_json=_json([]),
            content_blocks_json=_json(preflight_blocks),
            schema_version=2,
            meta_json=_json(
                {
                    "tools": ["lead_agent"],
                    "effectiveGoal": effective_goal,
                    "operationType": operation_context.get("intentType"),
                    "regenerateContext": operation_context,
                    "plannerMeta": planner_meta,
                    "artifactRefs": [],
                    "pendingPromptMenu": prompt_menu,
                }
            ),
        )
        db.add(assistant_message)
        db.flush()
        a2a_task_registry.set_output(task_id, prompt_menu.get("description") or "等待用户补充信息")
        a2a_task_registry.set_status(task_id, TASK_STATUS_RUNNING)
        run.status = "waiting_user"
        run.assistant_message_id = assistant_message.id
        run.result_summary = prompt_menu.get("description") or "等待用户补充信息"
        run.updated_at = datetime.utcnow()
        conversation.last_run_id = run.id
        conversation.updated_at = datetime.utcnow()
        conversation.last_message_at = conversation.updated_at
        _merge_runtime_state(
            conversation,
            runtime_context,
            {
                "pendingPromptMenu": pending_state,
                "taskTree": _collect_task_tree(task_ids),
            },
        )
        db.commit()
        push_event(
            RuntimeTaskEvent(
                "waiting_user",
                "waiting_user",
                "等待用户补充 · Main Agent",
                prompt_menu.get("description") or prompt_menu.get("title") or "请补充信息后继续。",
                f"<p>{escape(prompt_menu.get('description') or prompt_menu.get('title') or '请补充信息后继续。')}</p>",
                {
                    "taskId": task_id,
                    "parentTaskId": None,
                    "promptMenu": prompt_menu,
                    "resumeToken": pending_state["resumeToken"],
                    "sourceState": "main_agent_preflight",
                    "assistantMessageId": assistant_message.id,
                },
            )
        )
        return {
            "run": run,
            "events": db.execute(
                select(V4TaskEvent).where(V4TaskEvent.run_id == run.id).order_by(V4TaskEvent.seq_no.asc())
            ).scalars().all(),
            "assistant_message": assistant_message,
            "artifacts": [],
            "profile": profile,
        }

    preflight_prompt_menu = None if resume_from_waiting else _build_main_agent_prompt_menu(plan, effective_goal, attachments)
    if preflight_prompt_menu:
        return persist_main_agent_waiting(preflight_prompt_menu)

    def make_stream_delta_callback():
        last_flush_len = 0
        last_flush_t = time.monotonic()
        batch_chars = 80
        flush_interval = 0.4

        def on_text_delta(full_text: str, delta: str) -> None:
            nonlocal last_flush_len, last_flush_t
            text = full_text or ""
            now = time.monotonic()
            is_final = delta == ""
            n = len(text)
            should_push = False
            if is_final and n > 0:
                should_push = n > last_flush_len
            elif n > 0:
                grown = n - last_flush_len
                if grown >= batch_chars or (now - last_flush_t) >= flush_interval:
                    should_push = True
            if should_push:
                push_event(
                    RuntimeTaskEvent(
                        "text_delta",
                        "running",
                        "模型输出",
                        text,
                        f"<pre class='stream-chunk'>{escape(text[-4000:])}</pre>",
                        {"textSoFar": text, "deltaTail": text[last_flush_len:]},
                    )
                )
                last_flush_len = n
                last_flush_t = now

        return on_text_delta

    stream_delta_cb = make_stream_delta_callback()

    a2a_task_registry.set_status(task_id, TASK_STATUS_RUNNING)
    current_input = pending_prompt_menu.get("resumeInput") if resume_from_waiting and pending_prompt_menu else effective_goal
    step_outcomes: list[dict] = []
    pending_artifacts: list[dict] = []
    task_ids = [task_id]
    agent_tool = AgentTool()
    pending_direct_answer = planner_meta.get("directAnswer") if not resume_from_waiting else None

    inline_outcomes = planner_meta.get("inlineStepOutcomes") or []
    inline_artifacts = planner_meta.get("inlineArtifacts") or []
    if inline_outcomes and not resume_from_waiting:
        step_outcomes.extend(inline_outcomes)
        pending_artifacts.extend(inline_artifacts)
        log_stage(
            "runtime.flat_loop.seed",
            {
                "conversationId": conversation.id,
                "inlineOutcomes": len(inline_outcomes),
                "inlineArtifacts": len(inline_artifacts),
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        for outcome in inline_outcomes:
            outcome_task_id = outcome.get("task_id") or f"inline_{outcome.get('index') or 0}"
            skill_name = outcome.get("skill_name") or "general"
            title = outcome.get("title") or title_for_skill(skill_name)
            push_event(
                RuntimeTaskEvent(
                    "running",
                    "running",
                    f"Sub Agent · {title}",
                    f"Lead Agent 已在 flat loop 内调度 sub-agent {skill_name}。",
                    f"<p>Lead Agent 已在 flat loop 内调用 <strong>{escape(skill_name)}</strong>。</p>",
                    {
                        "taskId": outcome_task_id,
                        "parentTaskId": task_id,
                        "skillName": skill_name,
                        "dispatchMode": "flat_tool_loop",
                    },
                )
            )
            push_event(
                RuntimeTaskEvent(
                    "tool_call",
                    "completed" if outcome.get("source_state") != "model_error" else "failed",
                    f"Skill Broker · {title}",
                    outcome.get("summary") or "已返回 sub-agent 结果。",
                    outcome.get("html") or "",
                    {
                        "taskId": outcome_task_id,
                        "skillName": skill_name,
                        "normalizedResult": outcome.get("normalized_result") or {},
                        "retryable": outcome.get("retryable"),
                        "sourceState": outcome.get("source_state"),
                        "errorDetail": outcome.get("error_detail"),
                        "annotations": outcome.get("annotations") or [],
                        "dispatchMode": "flat_tool_loop",
                    },
                )
            )

    def persist_run(status: str, pending_state: dict | None = None) -> dict:
        legacy_summary, _legacy_html = _build_final_assistant_output(
            requested_model,
            plan,
            step_outcomes,
        )
        content_blocks = build_assistant_blocks(
            plan=plan,
            step_outcomes=step_outcomes,
            pending_artifacts=pending_artifacts,
            pending_prompt_menu=pending_state,
            planner_meta=planner_meta,
            final_text=legacy_summary if legacy_summary and legacy_summary != "任务未执行" else None,
        )
        assistant_summary = (
            blocks_to_plain_text(content_blocks)
            or legacy_summary
            or ("等待你的下一步选择" if pending_state else "任务已完成")
        )
        assistant_html = blocks_to_snapshot_html(content_blocks)
        merged_annotations = _merge_annotations(step_outcomes)
        assistant_message = V4ConversationMessage(
            conversation_id=conversation.id,
            run_id=run.id,
            user_id=current_user.user_id,
            role="assistant",
            skill_name=primary_skill,
            model_name=requested_model,
            content=assistant_summary,
            content_html=assistant_html,
            annotations_json=_json(merged_annotations),
            content_blocks_json=_json(content_blocks),
            schema_version=2,
            meta_json=_json(
                {
                    "tools": ["lead_agent", *[item["skill_name"] for item in step_outcomes]],
                    "keyFiles": [],
                    "effectiveGoal": effective_goal,
                    "operationType": operation_context.get("intentType"),
                    "regenerateContext": operation_context,
                    "plannerMeta": planner_meta,
                    "artifactRefs": [],
                    "pendingPromptMenu": pending_state["promptMenu"] if pending_state else None,
                }
            ),
        )
        db.add(assistant_message)
        db.flush()
        artifacts: list[V4ConversationArtifact] = []

        a2a_task_registry.set_output(task_id, assistant_summary or "任务已完成")
        a2a_task_registry.set_status(
            task_id,
            TASK_STATUS_RUNNING if pending_state else TASK_STATUS_COMPLETED,
        )

        run.status = status
        run.assistant_message_id = assistant_message.id
        run.result_summary = assistant_summary or ("等待用户继续选择" if pending_state else "任务已完成")
        run.updated_at = datetime.utcnow()
        conversation.last_run_id = run.id
        conversation.updated_at = datetime.utcnow()
        conversation.last_message_at = conversation.updated_at
        _merge_runtime_state(
            conversation,
            runtime_context,
            {
                "pendingPromptMenu": pending_state,
                "taskTree": _collect_task_tree(task_ids),
            },
        )
        compaction_result = maybe_compact_conversation(db, conversation, current_user)
        current_profile = _touch_profile_after_run(
            db,
            current_user,
            conversation,
            primary_skill,
            requested_model,
        )
        db.commit()
        push_event(
            RuntimeTaskEvent(
                "message_final",
                "completed",
                "助手消息已生成",
                "最终回答已写入当前会话。",
                "<p>最终回答已写入当前会话。</p>",
                {
                    "assistantMessageId": assistant_message.id,
                    "artifactIds": [],
                },
            )
        )
        artifact_error_payload = None
        artifact_draft = _normalize_artifact_contract(
            pending_artifacts[0] if pending_artifacts else None,
            default_source_skill=primary_skill,
            default_status="artifact_error",
        )
        if pending_artifacts:
            try:
                for artifact in pending_artifacts:
                    artifacts.append(
                        _create_artifact_and_workspace_entry(
                            db,
                            current_user,
                            conversation,
                            run,
                            assistant_message,
                            artifact,
                            merged_annotations,
                        )
                    )
                assistant_meta = _loads(assistant_message.meta_json, {})
                assistant_meta["artifactRefs"] = _artifact_ref_payloads(artifacts)
                assistant_message.meta_json = _json(assistant_meta)
                db.commit()
            except Exception as artifact_exc:
                db.rollback()
                artifact_error_payload = {
                    "assistantMessageId": assistant_message.id,
                    "errorScope": "artifact",
                    "errorDetail": str(artifact_exc),
                    "artifactDraft": _normalize_artifact_contract(
                        artifact_draft,
                        default_source_skill=primary_skill,
                        default_status="artifact_error",
                        error_detail=str(artifact_exc),
                    ),
                }
                db.refresh(run)
                db.refresh(conversation)
                db.refresh(assistant_message)
        if artifacts:
            for artifact in artifacts:
                artifact_payload = _artifact_contract_from_record(artifact)
                push_event(
                    RuntimeTaskEvent(
                        "artifact_created",
                        "completed",
                        f"产物已生成 · {artifact.title}",
                        artifact.summary or "已生成新的工作区产物。",
                        f"<p>已生成产物 <strong>{escape(artifact.title)}</strong>。</p>",
                        artifact_payload,
                    )
                )
        if artifact_error_payload:
            push_event(
                RuntimeTaskEvent(
                    "failed",
                    "failed",
                    "交付物生成失败",
                    artifact_error_payload["errorDetail"],
                    f"<p>{escape(artifact_error_payload['errorDetail'])}</p>",
                    artifact_error_payload,
                )
            )
        if compaction_result:
            push_event(
                RuntimeTaskEvent(
                    "context_compacted",
                    "completed",
                    "上下文压缩",
                    "已自动压缩较早消息，保留近期上下文。",
                    (
                        "<p>已自动压缩较早消息，保留近期上下文。</p>"
                        f"<pre>before = {compaction_result['contextUsageBefore']['used']} / {compaction_result['contextUsageBefore']['window']}\n"
                        f"after = {compaction_result['contextUsageAfter']['used']} / {compaction_result['contextUsageAfter']['window']}\n"
                        f"summarySnapshot = {escape(compaction_result['summary'][:1200])}</pre>"
                    ),
                    compaction_result,
                )
            )
        if pending_state:
            push_event(
                RuntimeTaskEvent(
                    "waiting_user",
                    "waiting_user",
                    f"等待用户确认 · {pending_state.get('title') or title_for_skill(primary_skill)}",
                    pending_state["promptMenu"].get("title") or "等待用户继续输入",
                    f"<p>{escape(pending_state['promptMenu'].get('description') or pending_state['promptMenu'].get('title') or '等待用户继续输入')}</p>",
                    {
                        "taskId": pending_state.get("taskId"),
                        "parentTaskId": pending_state.get("parentTaskId"),
                        "promptMenu": pending_state["promptMenu"],
                        "resumeToken": pending_state["resumeToken"],
                        "sourceState": pending_state.get("sourceState"),
                        "errorDetail": pending_state.get("errorDetail"),
                        "assistantMessageId": assistant_message.id,
                        "artifactIds": [item.id for item in artifacts],
                    },
                )
            )
        else:
            push_event(
                RuntimeTaskEvent(
                    "completed",
                    "completed",
                    "任务执行完成",
                    "已生成回答、步骤流和关联产物。",
                    "<p>已生成回答、步骤流和关联产物。</p>",
                    {
                        "assistantMessageId": assistant_message.id,
                        "artifactIds": [item.id for item in artifacts],
                    },
                )
            )
        return {
            "run": run,
            "events": db.execute(
                select(V4TaskEvent).where(V4TaskEvent.run_id == run.id).order_by(V4TaskEvent.seq_no.asc())
            ).scalars().all(),
            "assistant_message": assistant_message,
            "artifacts": artifacts,
            "profile": current_profile,
        }

    def persist_failure(exc: Exception) -> dict:
        failure_text = str(exc) or "执行失败"
        content_blocks = build_assistant_blocks(
            plan=plan,
            step_outcomes=step_outcomes,
            pending_artifacts=pending_artifacts,
            pending_prompt_menu=None,
            planner_meta=planner_meta,
            final_text=failure_text,
        )
        assistant_html = blocks_to_snapshot_html(content_blocks)
        assistant_message = V4ConversationMessage(
            conversation_id=conversation.id,
            run_id=run.id,
            user_id=current_user.user_id,
            role="assistant",
            skill_name=primary_skill,
            model_name=requested_model,
            content="执行失败",
            content_html=assistant_html,
            annotations_json=_json([]),
            content_blocks_json=_json(content_blocks),
            schema_version=2,
            meta_json=_json(
                {
                    "tools": ["lead_agent", *[item["skill_name"] for item in step_outcomes]],
                    "keyFiles": [],
                    "plannerMeta": planner_meta,
                    "pendingPromptMenu": None,
                }
            ),
        )
        db.add(assistant_message)
        db.flush()
        a2a_task_registry.set_output(task_id, failure_text)
        a2a_task_registry.set_status(task_id, TASK_STATUS_FAILED)
        run.status = "failed"
        run.assistant_message_id = assistant_message.id
        run.result_summary = failure_text
        run.updated_at = datetime.utcnow()
        conversation.last_run_id = run.id
        conversation.updated_at = datetime.utcnow()
        conversation.last_message_at = conversation.updated_at
        _merge_runtime_state(
            conversation,
            runtime_context,
            {
                "pendingPromptMenu": None,
                "taskTree": _collect_task_tree(task_ids),
            },
        )
        db.commit()
        push_event(
            RuntimeTaskEvent(
                "failed",
                "failed",
                "任务执行失败",
                failure_text,
                f"<p>{escape(failure_text)}</p>",
                {
                    "assistantMessageId": assistant_message.id,
                    "errorDetail": failure_text,
                },
            )
        )
        return {
            "run": run,
            "events": db.execute(
                select(V4TaskEvent).where(V4TaskEvent.run_id == run.id).order_by(V4TaskEvent.seq_no.asc())
            ).scalars().all(),
            "assistant_message": assistant_message,
            "artifacts": [],
            "profile": profile,
        }

    try:
        if resume_from_waiting:
            choice_result, choice_blocks, choice_artifacts, choice_annotations, next_prompt_menu = _resolve_prompt_menu_choice(
                pending_prompt_menu,
                selected_option,
                prompt_menu_input,
            )
            choice_title = pending_prompt_menu.get("title") or title_for_skill(primary_skill)
            choice_task_id = task_registry.next_task_id(conversation.id)
            choice_step = ExecutionStep(
                index=0,
                skill_name=primary_skill,
                title=choice_title,
                objective="根据用户对 Prompt Menu 的选择继续执行。",
                scope="恢复等待中的多阶段任务。",
            )
            choice_packet = build_subtask_packet(
                task_id=choice_task_id,
                parent_task_id=task_id,
                conversation_id=conversation.id,
                step=choice_step,
                requested_model=requested_model,
                step_input=current_input,
                attachments=attachments,
                runtime_context_summary=runtime_context["summary"],
                user_memory_refs=user_memory_refs,
                handoff_trace=[],
                operation_type=operation_context.get("intentType"),
                rewrite_mode=rewrite_mode,
                base_user_goal=operation_context.get("baseUserGoal") or effective_goal,
                latest_assistant_summary=operation_context.get("latestAssistantSummary"),
                latest_artifact_refs=operation_context.get("latestArtifactRefs") or [],
                attachment_context=attachment_context,
            )
            a2a_task_registry.register(
                choice_packet,
                f"Resume Step · {choice_title}",
                parent_task_id=task_id,
                team_id=f"resume-{primary_skill}",
            )
            a2a_task_registry.set_status(choice_task_id, TASK_STATUS_RUNNING)
            a2a_task_registry.append_message(choice_task_id, "user", content)
            a2a_task_registry.set_output(choice_task_id, json.dumps(choice_result, ensure_ascii=False))
            a2a_task_registry.set_status(choice_task_id, TASK_STATUS_COMPLETED)
            task_ids.append(choice_task_id)
            push_event(
                RuntimeTaskEvent(
                    "tool_call",
                    "running",
                    f"Prompt Menu Resume · {choice_title}",
                    "已接收用户对等待中任务的选择，继续执行后续链路。",
                    f"<p>已选择 <strong>{escape(selected_option or '自定义补充')}</strong>，正在继续执行。</p>",
                    {
                        "selectedOption": selected_option,
                        "promptMenuInput": prompt_menu_input,
                        "resumeToken": pending_prompt_menu.get("resumeToken"),
                        "taskPacket": choice_packet.model_dump(),
                    },
                )
            )
            choice_summary = choice_blocks[0].get("title") if choice_blocks else choice_title
            step_outcomes.append(
                {
                    "index": 0,
                    "task_id": choice_task_id,
                    "skill_name": primary_skill,
                    "title": choice_title,
                    "summary": choice_summary,
                    "html": _html_from_blocks(
                        requested_model,
                        choice_summary,
                        choice_blocks,
                        lead_copy="已根据你的选择继续执行。",
                    ),
                    "normalized_result": choice_result,
                    "annotations": choice_annotations,
                    "retryable": False,
                    "source_state": "workflow_resume",
                    "error_detail": None,
                    "reasoning_content": None,
                }
            )
            pending_artifacts.extend(choice_artifacts)
            current_input = build_handoff_content(
                current_input,
                primary_skill,
                choice_result,
            )
            if next_prompt_menu:
                return persist_run(
                    "waiting_user",
                    {
                        "resumeToken": f"{run.id}:{choice_task_id}",
                        "taskId": choice_task_id,
                        "parentTaskId": task_id,
                        "skillName": primary_skill,
                        "stepIndex": 0,
                        "title": choice_title,
                        "promptMenu": next_prompt_menu,
                        "normalizedResult": choice_result,
                        "annotations": choice_annotations,
                        "remainingSteps": [_step_payload(step) for step in plan.steps],
                        "plan": _plan_payload(plan),
                        "resumeInput": current_input,
                        "sourceState": "workflow_resume",
                        "errorDetail": None,
                    },
                )

        main_agent_inst = MainAgent()
        leader_messages: list[dict] | None = None
        if plan.steps:
            leader_messages = main_agent_inst._build_messages(
                effective_goal, attachments, runtime_context, memory_context
            )
            last_user = leader_messages[-1]
            u = last_user.get("content", "")
            last_user["content"] = (
                (u if isinstance(u, str) else str(u))
                + "\n\n【Leader 闭环】sub-agent 的结构化结果将以 OpenAI tool 消息追加；每波执行后 Leader 将再读上下文（opt1）。"
            )

        event_lock = threading.Lock()

        def safe_push(ev: RuntimeTaskEvent) -> None:
            with event_lock:
                push_event(ev)

        def drive_step(step: ExecutionStep, cin: str) -> tuple[dict | None, SkillExecutionResult, str, str]:
            """执行单步；若有提前结束则返回 persist_run 结果字典。"""
            nonlocal pending_direct_answer
            subtask_id = task_registry.next_task_id(conversation.id)
            task_ids.append(subtask_id)
            handoff_trace = _subtask_trace(step_outcomes)
            is_main_agent_step = step.subtask_role == "main_agent"
            subtask_packet = build_subtask_packet(
                task_id=subtask_id,
                parent_task_id=task_id,
                conversation_id=conversation.id,
                step=step,
                requested_model=requested_model,
                step_input=cin,
                attachments=attachments,
                runtime_context_summary=runtime_context["summary"],
                user_memory_refs=user_memory_refs,
                handoff_trace=handoff_trace,
                operation_type=operation_context.get("intentType"),
                rewrite_mode=rewrite_mode,
                base_user_goal=operation_context.get("baseUserGoal") or effective_goal,
                latest_assistant_summary=operation_context.get("latestAssistantSummary"),
                latest_artifact_refs=operation_context.get("latestArtifactRefs") or [],
                attachment_context=attachment_context,
            )
            subtask_record = a2a_task_registry.register(
                subtask_packet,
                f"{'Leader Agent' if is_main_agent_step else 'Sub Agent'} · {step.title}",
                parent_task_id=task_id,
                team_id=subtask_packet.team_id,
            )
            a2a_task_registry.append_message(subtask_id, "leader", cin)
            safe_push(
                RuntimeTaskEvent(
                    "tool_call",
                    "running",
                    f"{'Leader Agent Direct' if is_main_agent_step else 'Leader Agent -> Sub Agent'} · {step.title}",
                    (
                        "leader 判断当前请求可由主 Agent 直接处理。"
                        if is_main_agent_step
                        else f"leader 已把任务下发给 {step.skill_name} sub-agent。"
                    ),
                    (
                        f"<pre>subtask = {escape(subtask_id)}\n"
                        f"skill = {escape(step.skill_name)}\n"
                        f"depends_on = {escape(', '.join(step.depends_on) or 'none')}</pre>"
                    ),
                    {
                        "taskPacket": subtask_packet.model_dump(),
                        "registry": subtask_record.snapshot(),
                    },
                )
            )
            a2a_task_registry.set_status(subtask_id, TASK_STATUS_RUNNING)
            safe_push(
                RuntimeTaskEvent(
                    "running",
                    "running",
                    f"{'Leader Agent' if is_main_agent_step else 'Sub Agent'} · {step.title}",
                    (
                        f"主 Agent 正在直接处理 {step.skill_name} 任务。"
                        if is_main_agent_step
                        else f"子代理正在执行 {step.skill_name} 任务。"
                    ),
                    (
                        f"<p>主 Agent 正在直接处理 <strong>{escape(step.skill_name)}</strong> 任务。</p>"
                        if is_main_agent_step
                        else f"<p>子代理正在执行 <strong>{escape(step.skill_name)}</strong> 任务。</p>"
                    ),
                    {
                        "taskId": subtask_id,
                        "parentTaskId": task_id,
                        "taskPacket": subtask_packet.model_dump(),
                    },
                )
            )
            if is_main_agent_step and pending_direct_answer:
                skill_result = SkillExecutionResult(
                    normalized_result={"text": pending_direct_answer, "source": "planner_direct_answer"},
                    render_blocks=[{"type": "general", "title": "主 Agent 回复", "html": text_to_html(pending_direct_answer)}],
                    artifact_refs=[],
                    editor_annotations=[],
                    retryable=False,
                    source_state="planner_direct_answer",
                    error_detail=None,
                )
                pending_direct_answer = None
            elif is_main_agent_step:
                skill_result = execute_skill(
                    step.skill_name,
                    cin,
                    requested_model,
                    attachments,
                    cookies,
                    runtime_context=runtime_context,
                    memory_context=memory_context,
                    task_packet=subtask_packet.model_dump(),
                    on_text_delta=stream_delta_cb,
                )
            else:
                skill_result = agent_tool.call(
                    agent_name=step.skill_name,
                    task_prompt=cin,
                    requested_model=requested_model,
                    attachments=attachments,
                    cookies=cookies,
                    runtime_context=runtime_context,
                    memory_context=memory_context,
                    task_packet=subtask_packet.model_dump(),
                    on_text_delta=stream_delta_cb,
                )
            step_html = render_assistant_html(step.skill_name, skill_result, requested_model or "")
            step_summary = skill_result.render_blocks[0].get("title") if skill_result.render_blocks else title_for_skill(step.skill_name)
            a2a_task_registry.append_message(subtask_id, "sub_agent", step_summary)
            a2a_task_registry.set_output(
                subtask_id,
                json.dumps(skill_result.normalized_result, ensure_ascii=False),
            )
            a2a_task_registry.set_status(subtask_id, TASK_STATUS_COMPLETED)
            safe_push(
                RuntimeTaskEvent(
                    "tool_call",
                    "running",
                    f"{'Leader Agent Result' if is_main_agent_step else 'Skill Broker'} · {step.title}",
                    (
                        "主 Agent 已完成直接处理并生成结构化结果。"
                        if is_main_agent_step
                        else "sub-agent 已调用 skill 适配器并返回结构化结果。"
                    ),
                    (
                        f"<p>主 Agent 已完成 <strong>{escape(step.skill_name)}</strong> 处理并生成结果。</p>"
                        if is_main_agent_step
                        else f"<p>已完成 <strong>{escape(step.skill_name)}</strong> skill 调用，并把结果回传给 leader。</p>"
                    ),
                    {
                        "taskId": subtask_id,
                        "normalizedResult": skill_result.normalized_result,
                        "retryable": skill_result.retryable,
                        "sourceState": skill_result.source_state,
                        "errorDetail": skill_result.error_detail,
                        "attachmentCount": len(attachment_context),
                        "operationType": operation_context.get("intentType"),
                        "rewriteMode": rewrite_mode,
                        "registry": a2a_task_registry.get_snapshot(subtask_id),
                    },
                )
            )
            step_outcomes.append(
                {
                    "index": step.index,
                    "task_id": subtask_id,
                    "skill_name": step.skill_name,
                    "title": step.title,
                    "summary": step_summary,
                    "html": step_html,
                    "normalized_result": skill_result.normalized_result,
                    "annotations": skill_result.editor_annotations,
                    "retryable": skill_result.retryable,
                    "source_state": skill_result.source_state,
                    "error_detail": skill_result.error_detail,
                    "reasoning_content": skill_result.reasoning_content,
                }
            )
            pending_artifacts.extend(skill_result.artifact_refs)
            next_cin = build_handoff_content(
                cin,
                step.skill_name,
                skill_result.normalized_result,
            )
            if step.skill_name == "writing" and skill_result.source_state == "model_error":
                return (
                    persist_run(
                        "waiting_user",
                        {
                            "resumeToken": f"{run.id}:{subtask_id}",
                            "taskId": subtask_id,
                            "parentTaskId": task_id,
                            "skillName": step.skill_name,
                            "stepIndex": step.index,
                            "title": step.title,
                            "promptMenu": {
                                "type": "clarification",
                                "title": "写作模型调用失败",
                                "description": skill_result.error_detail or "模型调用失败，请检查网关配置后重试或补充要求。",
                                "question": skill_result.error_detail,
                                "options": [{"key": "custom_input", "label": "补充说明并重试", "recommended": True}],
                                "resultPreview": skill_result.normalized_result,
                                "resumeMode": "rerun_current_step",
                            },
                            "resumeMode": "rerun_current_step",
                            "resumeCurrentStep": _step_payload(step),
                            "normalizedResult": skill_result.normalized_result,
                            "annotations": skill_result.editor_annotations,
                            "remainingSteps": [_step_payload(item) for item in plan.steps if item.index > step.index],
                            "plan": _plan_payload(plan),
                            "resumeInput": next_cin,
                            "sourceState": skill_result.source_state,
                            "errorDetail": skill_result.error_detail,
                        },
                    ),
                    skill_result,
                    subtask_id,
                    next_cin,
                )
            if step.skill_name in INTERACTIVE_SKILLS:
                prompt_menu = (
                    {}
                    if (
                        step.skill_name == "writing"
                        and _looks_like_document_request(cin)
                        and skill_result.source_state != "model_error"
                    )
                    else _build_prompt_menu(
                        step,
                        skill_result.normalized_result,
                        skill_result.editor_annotations,
                        skill_result,
                    )
                )
                if prompt_menu:
                    return (
                        persist_run(
                            "waiting_user",
                            {
                                "resumeToken": f"{run.id}:{subtask_id}",
                                "taskId": subtask_id,
                                "parentTaskId": task_id,
                                "skillName": step.skill_name,
                                "stepIndex": step.index,
                                "title": step.title,
                                "promptMenu": prompt_menu,
                                "resumeMode": prompt_menu.get("resumeMode") or "prompt_menu_choice",
                                "resumeCurrentStep": (
                                    _step_payload(step)
                                    if prompt_menu.get("resumeMode") == "rerun_current_step"
                                    else None
                                ),
                                "normalizedResult": skill_result.normalized_result,
                                "annotations": skill_result.editor_annotations,
                                "remainingSteps": [_step_payload(item) for item in plan.steps if item.index > step.index],
                                "plan": _plan_payload(plan),
                                "resumeInput": next_cin,
                                "sourceState": skill_result.source_state,
                                "errorDetail": skill_result.error_detail,
                            },
                        ),
                        skill_result,
                        subtask_id,
                        next_cin,
                    )
            return None, skill_result, subtask_id, next_cin

        waves = _execution_step_waves(plan.steps)
        for wave_idx, wave in enumerate(waves):
            if (
                leader_messages is not None
                and wave_idx > 0
                and settings.enable_model_planner
            ):
                try:
                    guarded = apply_leader_context_guard(
                        leader_messages,
                        max_context_tokens=settings.context_window_tokens,
                    )
                    reflect = main_agent_inst.leader_step(guarded, requested_model)
                    log_stage(
                        "leader.reflect",
                        {
                            "conversationId": conversation.id,
                            "modelName": reflect.get("model_name"),
                            "hasToolCalls": bool((reflect.get("message") or {}).get("tool_calls")),
                            "estimatedTokens": estimate_tokens(guarded),
                        },
                        enabled=settings.debug_runtime_logs,
                        max_chars=settings.debug_log_max_chars,
                        max_string_chars=settings.debug_log_max_string_chars,
                    )
                except Exception as exc:
                    log_stage(
                        "leader.reflect.error",
                        {"error": str(exc)},
                        enabled=settings.debug_runtime_logs,
                        max_chars=settings.debug_log_max_chars,
                        max_string_chars=settings.debug_log_max_string_chars,
                    )

            wave_steps = sorted(wave, key=lambda s: s.index)
            wave_inputs: list[str] = []
            wave_results: list[SkillExecutionResult] = []
            wave_ids: list[str] = []
            use_parallel = (
                len(wave_steps) > 1
                and not pending_direct_answer
            )
            if use_parallel:
                wave_input_base = current_input

                def _run_parallel(st: ExecutionStep) -> tuple[ExecutionStep, dict | None, SkillExecutionResult, str, str]:
                    return (st, *drive_step(st, wave_input_base))

                with ThreadPoolExecutor(max_workers=min(4, len(wave_steps))) as pool:
                    futs = [pool.submit(_run_parallel, st) for st in wave_steps]
                    ordered: list[tuple] = []
                    for fut in as_completed(futs):
                        ordered.append(fut.result())
                    ordered.sort(key=lambda row: row[0].index)
                    for st, early, sr, sid, nxt in ordered:
                        if early is not None:
                            return early
                        wave_results.append(sr)
                        wave_ids.append(sid)
                        wave_inputs.append(wave_input_base)
                    merged = wave_input_base
                    for st, _early, sr, _sid, _nxt in ordered:
                        merged = build_handoff_content(merged, st.skill_name, sr.normalized_result)
                    current_input = merged
            else:
                for step in wave_steps:
                    step_input_snapshot = current_input
                    early, sr, sid, next_cin = drive_step(step, current_input)
                    if early is not None:
                        return early
                    wave_results.append(sr)
                    wave_ids.append(sid)
                    wave_inputs.append(step_input_snapshot)
                    current_input = next_cin

            if leader_messages is not None and wave_steps:
                tool_calls, _call_ids = build_synthetic_dispatch_tool_calls(
                    wave_steps,
                    task_prompts=wave_inputs,
                )
                leader_messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    }
                )
                for tc, st, sid, res in zip(tool_calls, wave_steps, wave_ids, wave_results):
                    leader_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": format_dispatch_tool_result_json(
                                step=st,
                                subtask_id=sid,
                                normalized_result=res.normalized_result,
                                source_state=res.source_state,
                                error_detail=res.error_detail,
                                retryable=res.retryable,
                            ),
                        }
                    )

        return persist_run("completed")
    except Exception as exc:
        return persist_failure(exc)


def execute_prepared_run(
    conversation_id: str,
    current_user,
    *,
    run_id: str,
    task_id: str,
    content: str,
    requested_skill: str | None,
    requested_model: str | None,
    attachments: list[dict],
    operation_context: dict | None,
    cookies: str | None,
    resume_from_waiting: bool = False,
    selected_option: str | None = None,
    prompt_menu_input: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        conversation = db.execute(
            select(V4Conversation).where(
                V4Conversation.id == conversation_id,
                V4Conversation.user_id == current_user.user_id,
                V4Conversation.is_deleted.is_(False),
            )
        ).scalar_one()
        run_conversation(
            db,
            conversation,
            current_user,
            content,
            requested_skill,
            requested_model,
            attachments,
            operation_context,
            cookies,
            resume_from_waiting,
            selected_option,
            prompt_menu_input,
            prepared_run_id=run_id,
            prepared_task_id=task_id,
        )
    finally:
        db.close()


def first_login_to_agent_app(db: Session, user_id: str) -> bool:
    count = db.execute(
        select(func.count()).select_from(V4Conversation).where(
            V4Conversation.user_id == user_id, V4Conversation.is_deleted.is_(False)
        )
    ).scalar_one()
    return count == 0



def read_profile_docs(current_user, profile: V4UserProfile) -> dict:
    identify_markdown = read_user_doc(current_user.user_id, profile.identify_md_path)
    memory_markdown = read_user_doc(current_user.user_id, profile.memory_md_path)
    session_summary_markdown = read_user_doc(
        current_user.user_id, profile.last_session_summary_md_path
    )
    return {
        "identify_markdown": identify_markdown,
        "memory_markdown": memory_markdown,
        "session_summary_markdown": session_summary_markdown,
    }


def build_prompt_profile_docs(current_user, profile: V4UserProfile) -> dict:
    raw_docs = read_profile_docs(current_user, profile)
    mem_expanded = _expand_memory_index_markdown(
        current_user.user_id,
        raw_docs["memory_markdown"],
        prefix="topics/",
        max_files=8,
        max_chars_per_file=1200,
        section_title="已展开的关键主题内容",
    )
    sess_expanded = _expand_memory_index_markdown(
        current_user.user_id,
        raw_docs["session_summary_markdown"],
        prefix="sessions/",
        max_files=2,
        max_chars_per_file=1200,
        section_title="已展开的最近会话摘要",
    )
    return {
        "identify_markdown": summarize_memory_for_context(raw_docs["identify_markdown"] or "", max_chars=1200),
        "memory_markdown": summarize_memory_for_context(mem_expanded, max_chars=3600),
        "session_summary_markdown": summarize_memory_for_context(sess_expanded, max_chars=1600),
    }
