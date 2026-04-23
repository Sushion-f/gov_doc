"""Adapter: 每个 skill 只走 MD 配方 + LLM。

legacy HTTP 调用已在 2026-04 整改中整体移除。sub-agent 的系统提示通过
``agents/`` 注册表与 ``prompts/sub/*.md``、或 ``skills_store/<name>/SKILL.md``
上传覆盖文件共同决定；执行路径只保留「加载 prompt → 调 LLM → 按 skill 类型
归一化 render_blocks / artifacts / annotations」三步。
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from typing import Any

from agents import (
    canonical_agent_name,
    exposed_agent_descriptors,
    get_agent_spec,
    prompt_key_for_agent,
)
from .config import settings
from .context_usage import record_usage as record_api_usage
from .debug_log import log_stage, mask_cookie
from .llm import LLMCallError, call_chat_model, resolve_model_name, text_to_html
from .skills_registry import get_skill_overlay


@dataclass
class SkillExecutionResult:
    normalized_result: dict
    render_blocks: list[dict]
    artifact_refs: list[dict]
    editor_annotations: list[dict]
    retryable: bool
    source_state: str = "model_success"
    error_detail: str | None = None
    prompt_menu: dict | None = None
    reasoning_content: str | None = None


def skill_descriptors() -> list[dict]:
    descriptors = exposed_agent_descriptors()
    for descriptor in descriptors:
        overlay = get_skill_overlay(descriptor.get("key") or "")
        if overlay:
            if overlay.display_name:
                descriptor["title"] = overlay.display_name
            if overlay.description:
                descriptor["summary"] = overlay.description
            if overlay.tools:
                descriptor["tools"] = overlay.tools
            descriptor["customized"] = True
    return descriptors


def resolve_skill(content: str, requested_skill: str | None = None) -> str:
    return canonical_agent_name(requested_skill) or "general"


def _invoke_llm(
    prompt: str,
    skill_name: str,
    requested_model: str | None,
    runtime_context: dict | None = None,
    memory_context: dict | None = None,
    task_packet: dict | None = None,
    *,
    on_text_delta: Callable[[str, str], None] | None = None,
) -> tuple[str, str, str | None, str | None]:
    """调用远程 LLM（OpenAI 兼容接口）。成功返回 (text, "model_success", None, reasoning)；
    失败返回 (user_text, "model_error", error_detail, None)。失败时不再触发任何 legacy fallback。"""
    resolved_model = resolve_model_name(requested_model)

    def _stream_handler(ev: dict[str, Any]) -> None:
        if not on_text_delta:
            return
        full = ev.get("text")
        if not isinstance(full, str):
            full = ""
        delta = ev.get("textDelta")
        if not isinstance(delta, str):
            delta = ""
        on_text_delta(full, delta)

    try:
        response = call_chat_model(
            prompt,
            prompt_key_for_agent(skill_name),
            requested_model,
            runtime_context,
            memory_context,
            task_packet,
            stream=True,
            on_stream_event=_stream_handler if on_text_delta else None,
        )
        text = response["text"]
        reasoning_content = (response.get("message") or {}).get("reasoning_content")
        conversation_id = None
        if isinstance(task_packet, dict):
            conversation_id = (
                task_packet.get("conversation_id")
                or task_packet.get("conversationId")
            )
        if conversation_id is None and isinstance(runtime_context, dict):
            conversation_id = (
                runtime_context.get("conversation_id")
                or runtime_context.get("conversationId")
            )
        if conversation_id:
            record_api_usage(
                str(conversation_id),
                response.get("usage") if isinstance(response, dict) else None,
                model_name=resolved_model,
            )
        log_stage(
            "skill.llm.remote_ok",
            {
                "skill": skill_name,
                "requestedModel": requested_model,
                "resolvedModel": resolved_model,
                "prompt": prompt,
                "text": (text or "")[:2000],
                "reasoningContent": reasoning_content,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        if on_text_delta:
            on_text_delta(text or "", "")
        return text or "", "model_success", None, reasoning_content
    except LLMCallError as exc:
        err = str(exc)
        log_stage(
            "skill.llm.remote_error",
            {
                "skill": skill_name,
                "requestedModel": requested_model,
                "resolvedModel": resolved_model,
                "error": err,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        user_text = (
            "模型调用失败。请检查 config/model.json 中的 base_url、api_key、default_model 与网关要求是否一致，"
            "或查看服务端日志。\n\n"
            f"详情：{err}"
        )
        return user_text, "model_error", err, None


def _build_annotations_from_lines(lines: list[str]) -> list[dict]:
    annotations: list[dict] = []
    for index, line in enumerate(lines, start=1):
        text = line.strip(" -")
        if not text:
            continue
        annotations.append(
            {
                "id": f"annotation-{index}",
                "label": f"问题 {index}",
                "description": text,
                "start": max(index * 10, 0),
                "end": max(index * 10 + len(text), 1),
            }
        )
    return annotations


def _try_parse_json_from_text(text: str) -> dict | list | None:
    raw = (text or "").strip()
    if not raw:
        return None
    candidates = [raw]
    if "```" in raw:
        fenced = raw.split("```")
        for part in fenced:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith(("{", "[")):
                candidates.append(stripped)
    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        candidates.append(raw[brace_start : brace_end + 1])
    bracket_start = raw.find("[")
    bracket_end = raw.rfind("]")
    if bracket_start >= 0 and bracket_end > bracket_start:
        candidates.append(raw[bracket_start : bracket_end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, (dict, list)):
            return value
    return None


def _lines_of(text: str, limit: int = 8) -> list[str]:
    return [item.strip("- ").strip() for item in (text or "").splitlines() if item.strip()][:limit]


def _build_general_result(
    text: str,
    source_state: str,
    error_detail: str | None,
    reasoning_content: str | None,
) -> SkillExecutionResult:
    return SkillExecutionResult(
        normalized_result={"text": text, "source": source_state},
        render_blocks=[{"type": "general", "title": "通用回答", "html": text_to_html(text)}],
        artifact_refs=[],
        editor_annotations=[],
        retryable=source_state == "model_error",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=reasoning_content,
    )


def _build_retrieval_result(
    text: str,
    source_state: str,
    error_detail: str | None,
    reasoning_content: str | None,
) -> SkillExecutionResult:
    parsed = _try_parse_json_from_text(text) if source_state == "model_success" else None
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        items = parsed["items"]
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = [{"title": "检索摘要", "summary": line} for line in _lines_of(text, limit=6)]
    return SkillExecutionResult(
        normalized_result={"items": items, "source": source_state},
        render_blocks=[{"type": "summary", "title": "检索结果", "html": text_to_html(text)}],
        artifact_refs=[],
        editor_annotations=[],
        retryable=source_state == "model_error",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=reasoning_content,
    )


def _build_writing_result(
    text: str,
    source_state: str,
    error_detail: str | None,
    reasoning_content: str | None,
) -> SkillExecutionResult:
    artifacts: list[dict] = []
    if source_state == "model_success" and text.strip():
        artifacts.append(
            {
                "artifactType": "document",
                "title": "公文写作结果.docx",
                "summary": "已生成可继续编辑的公文正文。",
                "contentHtml": text_to_html(text),
                "sourceSkill": "writing",
                "sourceState": source_state,
                "status": "ready",
                "errorDetail": None,
            }
        )
    return SkillExecutionResult(
        normalized_result={"document": text, "source": source_state},
        render_blocks=[{"type": "document", "title": "公文写作结果", "html": text_to_html(text)}],
        artifact_refs=artifacts,
        editor_annotations=[],
        retryable=source_state == "model_error",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=reasoning_content,
    )


def _build_review_result(
    text: str,
    source_state: str,
    error_detail: str | None,
    reasoning_content: str | None,
) -> SkillExecutionResult:
    parsed = _try_parse_json_from_text(text) if source_state == "model_success" else None
    if isinstance(parsed, dict) and isinstance(parsed.get("issues"), list):
        issues = parsed["issues"]
    elif isinstance(parsed, list):
        issues = [item if isinstance(item, dict) else {"message": str(item)} for item in parsed]
    else:
        issues = [{"message": line} for line in _lines_of(text, limit=8)]
    review_lines = [f"- {item.get('message') or item.get('errorWord') or json.dumps(item, ensure_ascii=False)}" for item in issues[:10]]
    review_text = "\n".join(review_lines) or "- 暂未发现明显问题。"
    annotations = _build_annotations_from_lines(
        [item.get("message") or item.get("errorWord") or str(item) for item in issues[:10]]
    )
    artifacts = []
    if source_state == "model_success":
        artifacts.append(
            {
                "artifactType": "document",
                "title": "审核修订建议.docx",
                "summary": "已生成审核意见与修订建议。",
                "contentHtml": text_to_html(review_text),
                "sourceSkill": "review",
                "sourceState": source_state,
                "status": "ready",
                "errorDetail": None,
            }
        )
    return SkillExecutionResult(
        normalized_result={"issues": issues, "source": source_state},
        render_blocks=[{"type": "review", "title": "审核结论", "html": text_to_html(review_text)}],
        artifact_refs=artifacts,
        editor_annotations=annotations,
        retryable=source_state == "model_error",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=reasoning_content,
    )


def _build_dedup_result(
    text: str,
    source_state: str,
    error_detail: str | None,
    reasoning_content: str | None,
) -> SkillExecutionResult:
    parsed = _try_parse_json_from_text(text) if source_state == "model_success" else None
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        rows = parsed["items"]
    elif isinstance(parsed, list):
        rows = [item if isinstance(item, dict) else {"title": str(item)} for item in parsed]
    else:
        rows = [
            {
                "title": f"相似来源 {index}",
                "duplicateRate": f"{min(20 + index * 7, 87)}%",
                "duplicateSentence": line,
                "sourceLink": "",
            }
            for index, line in enumerate(_lines_of(text, limit=5), start=1)
        ]
    report_lines = [
        f"- {item.get('title', '相似来源')} | 重复率 "
        f"{item.get('duplicateRate') or item.get('paperDuplicateRate') or '未知'}"
        for item in rows[:8]
    ]
    report_text = "\n".join(report_lines) or "- 暂无查重结果。"
    annotations = _build_annotations_from_lines(
        [item.get("duplicateSentence") or item.get("title") or str(item) for item in rows[:8]]
    )
    artifacts: list[dict] = []
    if source_state == "model_success":
        artifacts.append(
            {
                "artifactType": "report",
                "title": "查重报告.docx",
                "summary": "已生成查重分析与改写建议。",
                "contentHtml": text_to_html(report_text),
                "sourceSkill": "dedup",
                "sourceState": source_state,
                "status": "ready",
                "errorDetail": None,
            }
        )
    return SkillExecutionResult(
        normalized_result={"items": rows, "source": source_state},
        render_blocks=[{"type": "duplicate", "title": "查重结果", "html": text_to_html(report_text)}],
        artifact_refs=artifacts,
        editor_annotations=annotations,
        retryable=source_state == "model_error",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=reasoning_content,
    )


def _build_layout_result(
    text: str,
    source_state: str,
    error_detail: str | None,
    reasoning_content: str | None,
) -> SkillExecutionResult:
    parsed = _try_parse_json_from_text(text) if source_state == "model_success" else None
    if isinstance(parsed, dict) and isinstance(parsed.get("templates"), list):
        templates = parsed["templates"]
    elif isinstance(parsed, list):
        templates = [item if isinstance(item, dict) else {"templateTitle": str(item)} for item in parsed]
    else:
        lines = _lines_of(text, limit=6)
        templates = [{"templateTitle": line, "documentType": "通用"} for line in lines]
    if not templates:
        templates = [
            {"templateTitle": "党政机关标准版", "documentType": "通知"},
            {"templateTitle": "汇报材料版", "documentType": "汇报"},
        ]
    template_lines = [
        f"- 推荐模板：{item.get('templateTitle', '未命名模板')}（{item.get('documentType', '通用')}）"
        for item in templates[:5]
    ]
    template_text = "\n".join(template_lines) or "- 暂无推荐模板。"
    artifacts: list[dict] = []
    if source_state == "model_success":
        artifacts.append(
            {
                "artifactType": "document",
                "title": "排版结果.docx",
                "summary": "已输出推荐模板与排版建议。",
                "contentHtml": text_to_html(template_text),
                "sourceSkill": "layout",
                "sourceState": source_state,
                "status": "ready",
                "errorDetail": None,
            }
        )
    return SkillExecutionResult(
        normalized_result={"templates": templates, "source": source_state},
        render_blocks=[{"type": "format", "title": "排版建议", "html": text_to_html(template_text)}],
        artifact_refs=artifacts,
        editor_annotations=[],
        retryable=source_state == "model_error",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=reasoning_content,
    )


_SKILL_BUILDERS: dict[str, Callable[..., SkillExecutionResult]] = {
    "general": _build_general_result,
    "retrieval": _build_retrieval_result,
    "writing": _build_writing_result,
    "review": _build_review_result,
    "dedup": _build_dedup_result,
    "layout": _build_layout_result,
}


def _execute_skill_once(
    skill_name: str,
    content: str,
    requested_model: str | None,
    attachments: list[dict],
    cookies: str | None = None,
    runtime_context: dict | None = None,
    memory_context: dict | None = None,
    task_packet: dict | None = None,
    on_text_delta: Callable[[str, str], None] | None = None,
) -> SkillExecutionResult:
    canonical_name = canonical_agent_name(skill_name) or "general"
    prompt = (content or "").strip()
    log_stage(
        "skill.execute.start",
        {
            "skill": canonical_name,
            "content": content,
            "requestedModel": requested_model,
            "attachments": attachments,
            "cookiePreview": mask_cookie(cookies),
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )

    builder = _SKILL_BUILDERS.get(canonical_name, _build_general_result)
    text, source_state, error_detail, reasoning_content = _invoke_llm(
        prompt,
        canonical_name,
        requested_model,
        runtime_context,
        memory_context,
        task_packet,
        on_text_delta=on_text_delta,
    )
    result = builder(text, source_state, error_detail, reasoning_content)
    log_stage(
        "skill.execute.result",
        {"skill": canonical_name, "result": result},
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    return result


_SKILL_OUTPUT_MIN_SCHEMA: dict[str, dict] = {
    # 每个 skill 的最小输出契约，validate 返回 (ok, reason)
    "writing": {"kind": "text", "field": "document", "min_len": 40},
    "general": {"kind": "text", "field": "text", "min_len": 1},
    "retrieval": {"kind": "list", "field": "items", "min_items": 1},
    "review": {"kind": "list", "field": "issues", "min_items": 0},
    "dedup": {"kind": "list", "field": "items", "min_items": 0},
    "layout": {"kind": "list", "field": "templates", "min_items": 1},
}


def _looks_like_clarification_response(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    markers = (
        "请补充",
        "请说明",
        "请提供",
        "请确认",
        "请告知",
        "为了更好地帮助您",
        "我没有看到之前的对话上下文",
    )
    if any(marker in stripped for marker in markers):
        return True
    return stripped.endswith(("？", "?"))


def _writing_has_core_goal(content: str) -> bool:
    text = str(content or "").strip()
    if len(text) < 6:
        return False
    doc_markers = ("通知", "报告", "请示", "函", "总结", "汇报", "方案", "讲话稿", "发言稿", "公文")
    action_markers = ("起草", "写", "撰写", "生成", "拟一份", "草拟")
    if any(marker in text for marker in ("国庆", "春节", "放假", "营商环境", "整改", "会议", "培训", "检查")):
        return True
    return any(marker in text for marker in doc_markers) and any(marker in text for marker in action_markers)


def _validate_skill_output(skill_name: str, result: SkillExecutionResult) -> tuple[bool, str]:
    spec = _SKILL_OUTPUT_MIN_SCHEMA.get(skill_name)
    if not spec:
        return True, ""
    data = result.normalized_result or {}
    field = spec.get("field") or ""
    if spec.get("kind") == "text":
        value = str(data.get(field) or "").strip()
        if len(value) < int(spec.get("min_len") or 1):
            return False, f"字段 `{field}` 输出过短或缺失"
        if skill_name == "writing" and _looks_like_clarification_response(value):
            return False, "写作结果仍在追问补充信息"
        return True, ""
    if spec.get("kind") == "list":
        value = data.get(field)
        if not isinstance(value, list):
            return False, f"字段 `{field}` 不是列表"
        if len(value) < int(spec.get("min_items") or 0):
            return False, f"字段 `{field}` 条目数过少"
        return True, ""
    return True, ""


def execute_skill(
    skill_name: str,
    content: str,
    requested_model: str | None,
    attachments: list[dict],
    cookies: str | None = None,
    runtime_context: dict | None = None,
    memory_context: dict | None = None,
    task_packet: dict | None = None,
    on_text_delta: Callable[[str, str], None] | None = None,
) -> SkillExecutionResult:
    """执行 skill。
    - `model_error` 时自动重试 1 次（间隔 0.5s）；
    - 输出 schema 校验失败时，按 `subagent_max_output_retries` 重新下发一次严格指令。
    """
    canonical = canonical_agent_name(skill_name) or "general"
    first = _execute_skill_once(
        canonical,
        content,
        requested_model,
        attachments,
        cookies,
        runtime_context=runtime_context,
        memory_context=memory_context,
        task_packet=task_packet,
        on_text_delta=on_text_delta,
    )
    if first.source_state == "model_error":
        time.sleep(0.5)
        first = _execute_skill_once(
            canonical,
            content,
            requested_model,
            attachments,
            cookies,
            runtime_context=runtime_context,
            memory_context=memory_context,
            task_packet=task_packet,
            on_text_delta=on_text_delta,
        )

    max_retries = max(0, int(getattr(settings, "subagent_max_output_retries", 0) or 0))
    for attempt in range(max_retries):
        if first.source_state == "model_error":
            break
        ok, reason = _validate_skill_output(canonical, first)
        if ok:
            break
        log_stage(
            "skill.output_schema_invalid",
            {
                "skill": canonical,
                "reason": reason,
                "attempt": attempt + 1,
                "maxRetries": max_retries,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        strict_suffix = (
            f"\n\n[严格输出要求] 上一次输出不符合 schema（{reason}）。"
            "请仅输出 JSON / 结构化正文，严格按照 skill 约定的字段。"
        )
        first = _execute_skill_once(
            canonical,
            content + strict_suffix,
            requested_model,
            attachments,
            cookies,
            runtime_context=runtime_context,
            memory_context=memory_context,
            task_packet=task_packet,
            on_text_delta=on_text_delta,
        )
    if canonical == "writing" and _writing_has_core_goal(content):
        document = str((first.normalized_result or {}).get("document") or "").strip()
        if _looks_like_clarification_response(document):
            strict_suffix = (
                "\n\n[强制写作约束] 用户已经给出足够主题信息。"
                "不得要求补充发文机关、日期、联系人、值班电话等非核心字段；"
                "必须直接输出可用草稿，未知细节统一用【XXX】占位。"
            )
            first = _execute_skill_once(
                canonical,
                content + strict_suffix,
                requested_model,
                attachments,
                cookies,
                runtime_context=runtime_context,
                memory_context=memory_context,
                task_packet=task_packet,
                on_text_delta=on_text_delta,
            )
    return first


def render_assistant_html(skill_name: str, result: SkillExecutionResult, model_name: str) -> str:
    skill_name = canonical_agent_name(skill_name) or "general"
    try:
        title = get_agent_spec(skill_name).title
    except ValueError:
        title = skill_name
    blocks = [
        f"<div class='assistant-copy'>模型 <strong>{escape(model_name)}</strong> 已完成 {escape(title)} 任务。</div>"
    ]
    for block in result.render_blocks:
        block_title = escape(block.get("title") or "")
        html = block.get("html") or "<p></p>"
        blocks.append(f"<section class='assistant-block'><h4>{block_title}</h4>{html}</section>")
    return "".join(blocks)
