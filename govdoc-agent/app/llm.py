import json
from html import escape
from typing import Any, Callable

import requests

from agents import canonical_agent_name, system_prompt_for_agent
from .config import settings
from .debug_log import log_stage
from .skills_registry import get_skill_overlay


# 仅保留「短别名 → 当前默认接入点」；真实 model id 不在此表则原样传给网关。
MODEL_ALIASES = {
    "minimax": settings.llm_default_model,
    "qwen 3.5": settings.llm_default_model,
    "qwen3-max": settings.llm_default_model,
    "deepseek": settings.llm_default_model,
    "deepseek-chat": settings.llm_default_model,
}

class LLMCallError(RuntimeError):
    pass


def chat_completions_post_url() -> str:
    """OpenAI 兼容 chat/completions 的完整 URL，仅来自 model.json。"""
    full = (settings.llm_chat_completions_url or "").strip().rstrip("/")
    if full:
        return full
    base = (settings.llm_base_url or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/chat/completions"


def resolve_model_name(requested_model: str | None) -> str:
    normalized = (requested_model or "").strip()
    if not normalized:
        return settings.llm_default_model
    return MODEL_ALIASES.get(normalized.lower(), normalized)


def build_messages(
    content: str,
    skill: str | None,
    runtime_context: dict | None = None,
    memory_context: dict | None = None,
    task_packet: dict | None = None,
):
    canonical_name = canonical_agent_name(skill) or "general"
    overlay = get_skill_overlay(canonical_name)
    if overlay and overlay.system_prompt:
        system_prompt = overlay.system_prompt
    else:
        system_prompt = system_prompt_for_agent(canonical_name)
    messages = [{"role": "system", "content": system_prompt}]

    context_lines: list[str] = []
    if task_packet:
        input_payload = task_packet.get("input_payload") or {}
        context_lines.extend(
            [
                "当前由 leader agent 下发结构化任务，请遵守执行契约。",
                f"- objective: {task_packet.get('objective') or ''}",
                f"- scope: {task_packet.get('scope') or ''}",
                f"- reporting_contract: {task_packet.get('reporting_contract') or ''}",
                f"- escalation_policy: {task_packet.get('escalation_policy') or ''}",
            ]
        )
        if input_payload.get("baseUserGoal"):
            context_lines.append(f"- 原始用户目标: {input_payload.get('baseUserGoal')}")
        if input_payload.get("operationType") or input_payload.get("rewriteMode"):
            context_lines.append(
                "- 本次动作类型: "
                f"{input_payload.get('operationType') or 'generate'}"
                f" / {input_payload.get('rewriteMode') or 'default'}"
            )
        if input_payload.get("latestAssistantSummary"):
            context_lines.append("最近一次结果摘要：")
            context_lines.append(str(input_payload.get("latestAssistantSummary")))
        latest_artifact_refs = input_payload.get("latestArtifactRefs") or []
        if latest_artifact_refs:
            context_lines.append("最近一次交付物引用：")
            for item in latest_artifact_refs[:3]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or "未命名交付物"
                summary = item.get("summary") or ""
                node_id = item.get("workspaceNodeId") or ""
                context_lines.append(
                    f"- {title}"
                    + (f" | {summary}" if summary else "")
                    + (f" | node={node_id}" if node_id else "")
                )
        attachment_context = input_payload.get("attachmentContext") or []
        if attachment_context:
            context_lines.append(f"附件背景素材（共 {len(attachment_context)} 个）：")
            for item in attachment_context[:4]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or "附件"
                summary = item.get("summary") or ""
                excerpt = item.get("excerpt") or ""
                context_lines.append(
                    f"- {title}"
                    + (f" | 摘要：{summary}" if summary else "")
                    + (f"\n  节选：{excerpt}" if excerpt else "")
                )
    if runtime_context:
        summary = runtime_context.get("summary") or ""
        recent_messages = runtime_context.get("recent_messages") or []
        if summary:
            context_lines.append("运行上下文摘要：")
            context_lines.append(summary)
        if recent_messages:
            context_lines.append("最近消息：")
            for item in recent_messages[-4:]:
                role = item.get("role") or "unknown"
                text = (item.get("content") or "").strip()
                context_lines.append(f"- {role}: {text}")
    if memory_context:
        identify_md = (memory_context.get("identify_markdown") or "").strip()
        memory_md = (memory_context.get("memory_markdown") or "").strip()
        session_summary = (memory_context.get("session_summary_markdown") or "").strip()
        if identify_md:
            context_lines.append("用户身份偏好：")
            context_lines.append(identify_md)
        if memory_md:
            context_lines.append("长期记忆：")
            context_lines.append(memory_md)
        if session_summary:
            context_lines.append("最近会话摘要：")
            context_lines.append(session_summary)

    if context_lines:
        messages.append({"role": "system", "content": "\n".join(context_lines)})

    messages.append({"role": "user", "content": content})
    return messages


def extract_json_object(text: str) -> dict:
    normalized = (text or "").strip()
    if not normalized:
        raise LLMCallError("模型未返回可解析的 JSON 内容")

    candidates = [normalized]
    if "```" in normalized:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start >= 0 and end > start:
            candidates.append(normalized[start : end + 1])
    else:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start >= 0 and end > start:
            candidates.append(normalized[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise LLMCallError("模型返回的规划结果不是有效 JSON 对象")


def _coerce_message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "").strip()
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        ).strip()
    return ""


def _coerce_delta_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            item.get("text", "")
            for item in value
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )
    return ""


def _merge_tool_call_chunks(existing: list[dict], delta_calls: list[dict]) -> list[dict]:
    merged = list(existing or [])
    for delta_call in delta_calls or []:
        if not isinstance(delta_call, dict):
            continue
        index = delta_call.get("index")
        if not isinstance(index, int):
            index = len(merged)
        while len(merged) <= index:
            merged.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
        current = merged[index]
        current["id"] = delta_call.get("id") or current.get("id") or ""
        current["type"] = delta_call.get("type") or current.get("type") or "function"
        current_function = current.setdefault("function", {})
        delta_function = delta_call.get("function") or {}
        current_function["name"] = delta_function.get("name") or current_function.get("name") or ""
        current_function["arguments"] = (
            (current_function.get("arguments") or "") + (delta_function.get("arguments") or "")
        )
    return merged


def call_chat_model_with_messages_raw(
    messages: list[dict],
    requested_model: str | None,
    *,
    purpose: str = "chat",
    temperature: float = 0.4,
    extra_payload: dict | None = None,
    stream: bool = False,
    on_stream_event: Callable[[dict[str, Any]], None] | None = None,
):
    model_name = resolve_model_name(requested_model)
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if extra_payload:
        payload.update(extra_payload)
    post_url = chat_completions_post_url()
    log_stage(
        f"llm.request.{purpose}",
        {
            "url": post_url,
            "model": model_name,
            "requested_model": requested_model,
            "purpose": purpose,
            "timeoutSeconds": settings.llm_timeout_seconds,
            "payload": payload,
        },
        enabled=settings.debug_runtime_logs,
        max_chars=settings.debug_log_max_chars,
        max_string_chars=settings.debug_log_max_string_chars,
    )
    if not post_url:
        raise LLMCallError("model.json 未配置 llm.base_url 或 llm.chat_completions_url，无法调用模型")
    try:
        response = requests.post(
            post_url,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.llm_timeout_seconds,
            stream=stream,
        )
        response.raise_for_status()
        # 流式接口常省略 charset；requests 可能按 ISO-8859-1 解码，导致 UTF-8 中文变成 mojibake
        enc = (response.encoding or "").lower()
        if not enc or enc in ("iso-8859-1", "latin-1"):
            response.encoding = "utf-8"
        if stream:
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            tool_calls: list[dict] = []
            chunks: list[dict] = []
            for raw in response.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                chunk_text = line[5:].strip()
                if not chunk_text or chunk_text == "[DONE]":
                    if chunk_text == "[DONE]":
                        break
                    continue
                try:
                    data = json.loads(chunk_text)
                except json.JSONDecodeError as exc:
                    # 部分网关/代理会偶发推送非完整 JSON 行；整段失败会表现为
                    # "Unterminated string starting at: line 1 column N"。跳过坏行以免整次 skill 崩溃。
                    log_stage(
                        "llm.stream.chunk_json_skip",
                        {
                            "purpose": purpose,
                            "model": model_name,
                            "error": str(exc),
                            "preview": (chunk_text[:240] + "…") if len(chunk_text) > 240 else chunk_text,
                        },
                        enabled=settings.debug_runtime_logs,
                        max_chars=settings.debug_log_max_chars,
                        max_string_chars=settings.debug_log_max_string_chars,
                    )
                    continue
                chunks.append(data)
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                delta_text = _coerce_delta_text(delta.get("content"))
                delta_reasoning = _coerce_delta_text(
                    delta.get("reasoning_content") or delta.get("reasoning") or delta.get("reasoningContent")
                )
                if delta_text:
                    text_parts.append(delta_text)
                if delta_reasoning:
                    reasoning_parts.append(delta_reasoning)
                tool_calls = _merge_tool_call_chunks(tool_calls, delta.get("tool_calls") or [])
                if on_stream_event and (delta_text or delta_reasoning):
                    on_stream_event(
                        {
                            "textDelta": delta_text,
                            "reasoningDelta": delta_reasoning,
                            "text": "".join(text_parts),
                            "reasoning": "".join(reasoning_parts),
                            "toolCalls": tool_calls,
                            "raw": data,
                        }
                    )
            text = "".join(text_parts).strip()
            reasoning_content = "".join(reasoning_parts).strip()
            message = {
                "role": "assistant",
                "content": text,
                "reasoning_content": reasoning_content,
            }
            if tool_calls:
                message["tool_calls"] = tool_calls
            # 很多 OpenAI 兼容网关会在最后一个 chunk 里带上 usage；优先取最后看到的非空 usage。
            stream_usage: dict | None = None
            for chunk in reversed(chunks):
                candidate = chunk.get("usage") if isinstance(chunk, dict) else None
                if isinstance(candidate, dict) and candidate:
                    stream_usage = candidate
                    break
            data = {
                "object": "chat.completion.chunk.stream",
                "chunks": chunks,
                "message": message,
                "usage": stream_usage or {},
            }
        else:
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise LLMCallError("模型返回空结果")
            message = choices[0].get("message") or {}
        text = _coerce_message_text(message)
        tool_calls = message.get("tool_calls") or []
        if not text and not tool_calls:
            raise LLMCallError("模型返回内容为空")
        # 约定：流式调用也只在流全部结束后以单条聚合日志写入 model.log，避免 per-chunk 刷屏。
        # 因此流式模式下**绝不**把每个 chunk 的 choices/delta 原样写进 raw；
        # 只保留合并后的 message / usage / chunk 数量等摘要信息。非流式时才写完整 raw。
        response_payload: dict[str, Any] = {
            "statusCode": response.status_code,
            "model": model_name,
            "streamed": bool(stream),
            "text": text,
            "toolCalls": tool_calls,
            "message": message,
        }
        if stream:
            chunks_list = data.get("chunks") if isinstance(data, dict) else None
            response_payload["streamChunkCount"] = len(chunks_list) if isinstance(chunks_list, list) else 0
            response_payload["usage"] = data.get("usage") if isinstance(data, dict) else {}
        else:
            response_payload["raw"] = data
        log_stage(
            f"llm.response.{purpose}",
            response_payload,
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        usage_payload = data.get("usage") if isinstance(data, dict) else None
        return {
            "model_name": model_name,
            "text": text,
            "message": message,
            "tool_calls": tool_calls,
            "usage": usage_payload if isinstance(usage_payload, dict) else {},
            "raw": data,
        }
    except requests.RequestException as exc:
        log_stage(
            f"llm.error.{purpose}",
            {
                "model": model_name,
                "purpose": purpose,
                "error": str(exc),
            },
            enabled=settings.debug_runtime_logs,
            max_chars=settings.debug_log_max_chars,
            max_string_chars=settings.debug_log_max_string_chars,
        )
        raise LLMCallError(f"模型调用失败: {exc}") from exc


def call_chat_model_with_messages(
    messages: list[dict],
    requested_model: str | None,
    *,
    purpose: str = "chat",
    temperature: float = 0.4,
    extra_payload: dict | None = None,
    stream: bool = False,
    on_stream_event: Callable[[dict[str, Any]], None] | None = None,
):
    response = call_chat_model_with_messages_raw(
        messages,
        requested_model,
        purpose=purpose,
        temperature=temperature,
        extra_payload=extra_payload,
        stream=stream,
        on_stream_event=on_stream_event,
    )
    if not response["text"]:
        raise LLMCallError("模型返回内容为空")
    return response


def call_chat_model(
    content: str,
    skill: str | None,
    requested_model: str | None,
    runtime_context: dict | None = None,
    memory_context: dict | None = None,
    task_packet: dict | None = None,
    *,
    stream: bool = False,
    on_stream_event: Callable[[dict[str, Any]], None] | None = None,
):
    messages = build_messages(content, skill, runtime_context, memory_context, task_packet)
    return call_chat_model_with_messages(
        messages,
        requested_model,
        purpose=f"skill.{skill or 'general'}",
        temperature=0.4,
        stream=stream,
        on_stream_event=on_stream_event,
    )


def text_to_html(text: str) -> str:
    blocks = [block.strip() for block in text.replace("\r\n", "\n").split("\n\n") if block.strip()]
    html_parts = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if all(line.startswith(("-", "*", "1.", "2.", "3.")) for line in lines):
            html_parts.append(
                "<ul>" + "".join(f"<li>{escape(line.lstrip('-*1234567890. '))}</li>" for line in lines) + "</ul>"
            )
        else:
            html_parts.append(f"<p>{escape(' '.join(lines))}</p>")
    return "".join(html_parts) or "<p></p>"
