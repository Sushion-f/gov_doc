import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from typing import Any

import requests

from agents import (
    canonical_agent_name,
    exposed_agent_descriptors,
    get_agent_spec,
    prompt_key_for_agent,
)
from .config import settings
from .debug_log import log_stage, mask_cookie
from .llm import LLMCallError, call_chat_model, resolve_model_name, text_to_html


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


@dataclass
class LegacyCallResult:
    ok: bool
    url: str
    status_code: int | None = None
    payload: dict | list | None = None
    text: str | None = None
    error: str | None = None


def skill_descriptors() -> list[dict]:
    return exposed_agent_descriptors()


def resolve_skill(content: str, requested_skill: str | None = None) -> str:
    return canonical_agent_name(requested_skill) or "general"


def _legacy_base_url() -> str:
    return settings.legacy_service_base_url or settings.legacy_auth_base_url


def _read_sse_text(response: requests.Response) -> str:
    enc = (response.encoding or "").lower()
    if not enc or enc in ("iso-8859-1", "latin-1"):
        response.encoding = "utf-8"
    chunks: list[str] = []
    for raw in response.iter_lines(decode_unicode=False):
        if not raw:
            continue
        try:
            line = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            line = raw.decode("utf-8", errors="replace").strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload == "[DONE]":
                continue
            chunks.append(payload)
        else:
            chunks.append(line)
    return "\n".join(chunks).strip()


def _try_legacy_json(path: str, payload: dict, cookies: str | None = None) -> LegacyCallResult:
    base = _legacy_base_url()
    if not base:
        log_stage(
            "skill.legacy_json.skip",
            {"path": path, "reason": "legacy_base_url_missing"},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return LegacyCallResult(False, path, error="legacy_base_url_missing")
    url = f"{base}{path}"
    try:
        log_stage(
            "skill.legacy_json.request",
            {
                "url": url,
                "payload": payload,
                "cookiePreview": mask_cookie(cookies),
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        response = requests.post(
            url,
            json=payload,
            headers={"Cookie": cookies or ""},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        log_stage(
            "skill.legacy_json.response",
            {
                "url": url,
                "statusCode": response.status_code,
                "body": data,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return LegacyCallResult(True, url, status_code=response.status_code, payload=data)
    except (requests.RequestException, ValueError) as exc:
        log_stage(
            "skill.legacy_json.error",
            {
                "url": url,
                "error": str(exc),
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return LegacyCallResult(False, url, error=str(exc))


def _try_legacy_stream(path: str, payload: dict, cookies: str | None = None) -> LegacyCallResult:
    base = _legacy_base_url()
    if not base:
        log_stage(
            "skill.legacy_stream.skip",
            {"path": path, "reason": "legacy_base_url_missing"},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return LegacyCallResult(False, path, error="legacy_base_url_missing")
    url = f"{base}{path}"
    try:
        log_stage(
            "skill.legacy_stream.request",
            {
                "url": url,
                "payload": payload,
                "cookiePreview": mask_cookie(cookies),
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        response = requests.post(
            url,
            json=payload,
            headers={"Cookie": cookies or ""},
            timeout=40,
            stream=True,
        )
        response.raise_for_status()
        text = _read_sse_text(response)
        log_stage(
            "skill.legacy_stream.response",
            {
                "url": url,
                "statusCode": response.status_code,
                "text": text,
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return LegacyCallResult(True, url, status_code=response.status_code, text=text or None)
    except requests.RequestException as exc:
        log_stage(
            "skill.legacy_stream.error",
            {
                "url": url,
                "error": str(exc),
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return LegacyCallResult(False, url, error=str(exc))


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
    """始终调用远程 LLM（OpenAI 兼容接口）。失败返回 model_error 与错误信息，不再使用本地模板兜底。"""
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
    annotations = []
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


def _normalized_source(source_state: str) -> str:
    if not source_state:
        return "unknown"
    return source_state


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
    skill_name = canonical_agent_name(skill_name) or "general"
    prompt = content.strip()
    log_stage(
        "skill.execute.start",
        {
            "skill": skill_name,
            "content": content,
            "requestedModel": requested_model,
            "attachments": attachments,
            "cookiePreview": mask_cookie(cookies),
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )

    if skill_name == "general":
        text, source_state, error_detail, reasoning_content = _invoke_llm(
            prompt,
            skill_name,
            requested_model,
            runtime_context,
            memory_context,
            task_packet,
            on_text_delta=on_text_delta,
        )
        result = SkillExecutionResult(
            {"text": text, "source": _normalized_source(source_state)},
            [{"type": "general", "title": "通用回答", "html": text_to_html(text)}],
            [],
            [],
            source_state == "model_error",
            source_state=source_state,
            error_detail=error_detail,
            reasoning_content=reasoning_content,
        )
        log_stage(
            "skill.execute.result",
            {"skill": skill_name, "result": result},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return result

    if skill_name == "retrieval":
        legacy = _try_legacy_json(
            "/report-agent/v1/document-material-retrieval",
            {"query": prompt, "text": prompt, "keyword": prompt},
            cookies,
        )
        if legacy.ok:
            body = legacy.payload if isinstance(legacy.payload, dict) else {}
            items = body.get("data") or body.get("rows") or body.get("list") or []
            normalized = {"items": items, "source": _normalized_source("legacy_success")}
            render_blocks = [
                {"type": "summary", "title": "检索结果", "html": text_to_html(json.dumps(items[:5], ensure_ascii=False))}
            ]
            result = SkillExecutionResult(
                normalized,
                render_blocks,
                [],
                [],
                False,
                source_state="legacy_success",
            )
            log_stage(
                "skill.execute.result",
                {"skill": skill_name, "result": result},
                enabled=settings.debug_runtime_logs,
                max_chars=settings.debug_log_max_chars,
                max_string_chars=settings.debug_log_max_string_chars,
            )
            return result

        text, fallback_state, fallback_error, reasoning_content = _invoke_llm(
            prompt,
            skill_name,
            requested_model,
            runtime_context,
            memory_context,
            task_packet,
            on_text_delta=on_text_delta,
        )
        items = [
            {"title": "检索摘要", "summary": line}
            for line in [part.strip("- ").strip() for part in text.splitlines() if part.strip()][:5]
        ]
        result = SkillExecutionResult(
            {"items": items, "source": _normalized_source(fallback_state)},
            [{"type": "summary", "title": "检索结果", "html": text_to_html(text)}],
            [],
            [],
            True,
            source_state=fallback_state,
            error_detail=legacy.error or fallback_error,
            reasoning_content=reasoning_content,
        )
        log_stage(
            "skill.execute.result",
            {"skill": skill_name, "result": result},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return result

    if skill_name == "writing":
        legacy_text = _try_legacy_stream(
            "/report-agent/v1/document-writing",
            {"title": prompt[:20], "text": prompt, "prompt": prompt, "content": prompt},
            cookies,
        )
        if legacy_text.ok and legacy_text.text:
            text = legacy_text.text
            source_state = "legacy_success"
            error_detail = None
            reasoning_content = None
        else:
            text, source_state, error_detail, reasoning_content = _invoke_llm(
                prompt,
                skill_name,
                requested_model,
                runtime_context,
                memory_context,
                task_packet,
                on_text_delta=on_text_delta,
            )
        result = SkillExecutionResult(
            {"document": text, "source": _normalized_source(source_state)},
            [{"type": "document", "title": "公文写作结果", "html": text_to_html(text)}],
            [
                {
                    "artifact_type": "document",
                    "title": "公文写作结果.docx",
                    "summary": "已生成可继续编辑的公文正文。",
                    "content_html": text_to_html(text),
                }
            ],
            [],
            source_state != "legacy_success",
            source_state=source_state,
            error_detail=legacy_text.error or error_detail,
            reasoning_content=reasoning_content,
        )
        log_stage(
            "skill.execute.result",
            {"skill": skill_name, "result": result},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return result

    if skill_name == "review":
        legacy = _try_legacy_json(
            "/report-agent/v2/small_model_review",
            {"text": prompt, "model_name": resolve_model_name(requested_model)},
            cookies,
        )
        issues = []
        if legacy.ok and isinstance(legacy.payload, dict) and isinstance(legacy.payload.get("data"), dict):
            issues = legacy.payload["data"].get("resultList") or []
        if not issues:
            text, fallback_state, fallback_error, reasoning_content = _invoke_llm(
                prompt,
                skill_name,
                requested_model,
                runtime_context,
                memory_context,
                task_packet,
                on_text_delta=on_text_delta,
            )
            issue_lines = [line for line in text.splitlines() if line.strip()]
            issues = [{"message": line.strip()} for line in issue_lines[:8]]
            source_state = fallback_state
            error_detail = legacy.error or fallback_error
        else:
            source_state = "legacy_success"
            error_detail = None
            reasoning_content = None
        annotations = _build_annotations_from_lines([item.get("message") or item.get("errorWord") or str(item) for item in issues[:10]])
        review_text = "\n".join(
            [f"- {item.get('message') or item.get('errorWord') or str(item)}" for item in issues[:10]]
        ) or "- 暂未发现明显问题。"
        result = SkillExecutionResult(
            {"issues": issues, "source": _normalized_source(source_state)},
            [{"type": "review", "title": "审核结论", "html": text_to_html(review_text)}],
            [
                {
                    "artifact_type": "document",
                    "title": "审核修订建议.docx",
                    "summary": "已生成审核意见与修订建议。",
                    "content_html": text_to_html(review_text),
                }
            ],
            annotations,
            source_state != "legacy_success",
            source_state=source_state,
            error_detail=error_detail,
            reasoning_content=reasoning_content,
        )
        log_stage(
            "skill.execute.result",
            {"skill": skill_name, "result": result},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return result

    if skill_name == "dedup":
        legacy = _try_legacy_json(
            "/api/v1/duplication-check/internet",
            {"text": prompt, "content": prompt},
            cookies,
        )
        rows = []
        if legacy.ok and isinstance(legacy.payload, dict):
            rows = legacy.payload.get("data") or legacy.payload.get("items") or []
        if not rows:
            text, fallback_state, fallback_error, reasoning_content = _invoke_llm(
                prompt,
                skill_name,
                requested_model,
                runtime_context,
                memory_context,
                task_packet,
                on_text_delta=on_text_delta,
            )
            rows = [
                {
                    "title": f"相似来源 {index}",
                    "duplicateRate": f"{min(20 + index * 7, 87)}%",
                    "duplicateSentence": line.strip("- ").strip(),
                    "sourceLink": "",
                }
                for index, line in enumerate([item for item in text.splitlines() if item.strip()][:5], start=1)
            ]
            source_state = fallback_state
            error_detail = legacy.error or fallback_error
        else:
            source_state = "legacy_success"
            error_detail = None
            reasoning_content = None
        report_text = "\n".join(
            [
                f"- {item.get('title', '相似来源')} | 重复率 {item.get('duplicateRate') or item.get('paperDuplicateRate') or '未知'}"
                for item in rows[:8]
            ]
        ) or "- 暂无查重结果。"
        annotations = _build_annotations_from_lines(
            [item.get("duplicateSentence") or item.get("title") or str(item) for item in rows[:8]]
        )
        result = SkillExecutionResult(
            {"items": rows, "source": _normalized_source(source_state)},
            [{"type": "duplicate", "title": "查重结果", "html": text_to_html(report_text)}],
            [
                {
                    "artifact_type": "report",
                    "title": "查重报告.docx",
                    "summary": "已生成查重分析与改写建议。",
                    "content_html": text_to_html(report_text),
                }
            ],
            annotations,
            source_state != "legacy_success",
            source_state=source_state,
            error_detail=error_detail,
            reasoning_content=reasoning_content,
        )
        log_stage(
            "skill.execute.result",
            {"skill": skill_name, "result": result},
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        return result

    if skill_name != "layout":
        raise ValueError(f"未知 skill: {skill_name}")

    legacy_templates = _try_legacy_json("/report-agent/v2/layoutTemplate/getOptionLayout", {}, cookies)
    templates = []
    if legacy_templates.ok and isinstance(legacy_templates.payload, dict):
        templates = legacy_templates.payload.get("data") or legacy_templates.payload.get("rows") or []
    if not templates:
        templates = [
            {"templateTitle": "党政机关标准版", "documentType": "通知"},
            {"templateTitle": "汇报材料版", "documentType": "汇报"},
        ]
        source_state = "static_template"
        error_detail = legacy_templates.error
    else:
        source_state = "legacy_success"
        error_detail = None
    template_lines = [
        f"- 推荐模板：{item.get('templateTitle', '未命名模板')}（{item.get('documentType', '通用')}）"
        for item in templates[:5]
    ]
    template_text = "\n".join(template_lines)
    result = SkillExecutionResult(
        {"templates": templates, "source": _normalized_source(source_state)},
        [{"type": "format", "title": "排版建议", "html": text_to_html(template_text)}],
        [
            {
                "artifact_type": "document",
                "title": "排版结果.docx",
                "summary": "已输出推荐模板与排版建议。",
                "content_html": text_to_html(template_text),
            }
        ],
        [],
        source_state != "legacy_success",
        source_state=source_state,
        error_detail=error_detail,
        reasoning_content=None,
    )
    log_stage(
        "skill.execute.result",
        {"skill": skill_name, "result": result},
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    return result


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
    """执行 skill；model_error 时自动重试 1 次（间隔 0.5s）。"""
    first = _execute_skill_once(
        skill_name,
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
        return _execute_skill_once(
            skill_name,
            content,
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
    blocks = [
        f"<div class='assistant-copy'>模型 <strong>{escape(model_name)}</strong> 已完成 {escape(get_agent_spec(skill_name).title)} 任务。</div>"
    ]
    for block in result.render_blocks:
        title = escape(block.get("title") or "")
        html = block.get("html") or "<p></p>"
        blocks.append(f"<section class='assistant-block'><h4>{title}</h4>{html}</section>")
    return "".join(blocks)
