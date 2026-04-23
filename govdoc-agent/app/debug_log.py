"""运行期调试日志。

日志分路：
    - govdoc_agent.backend  → runtime_logs/backend.log     平台/路由/runtime/storage 等所有非 LLM stage
    - govdoc_agent.model    → runtime_logs/model.log       所有 llm.* stage（请求 / 响应 / 错误 / 流式收尾）

模型流式调用采用「聚合落盘」策略：在 llm.py 里的 call_chat_model_with_messages_raw
只会在首次发起请求时写一条 llm.request.{purpose}，待全部 chunk 收齐后再以 llm.response.{purpose}
作为单条聚合日志写入 model.log，避免 per-chunk 刷屏。

展示样式由 ``NEW_APP_DEBUG_LOG_STYLE`` 控制（默认 ``summary``）：
    - summary：人类可读的「汇总输入 / 汇总输出」分块，避免大段 JSON 像流式刷屏。
    - json：整条 payload 的缩进 JSON（旧版样式）。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]

from .config import settings


BACKEND_LOGGER_NAME = "govdoc_agent.backend"
MODEL_LOGGER_NAME = "govdoc_agent.model"

# 兼容旧名，避免外部直接 getLogger("govdoc_agent.runtime") 的地方拿不到 handler。
LEGACY_LOGGER_NAME = "govdoc_agent.runtime"


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


class _FlushingRotatingFileHandler(RotatingFileHandler):
    """每次写入后 flush，避免 IDE/部分环境长时间看不到尾部更新。"""

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        super().emit(record)
        self.flush()


def _ensure_parent(path: str) -> None:
    try:
        parent = Path(path).expanduser().resolve().parent
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _build_file_handler(path: str) -> logging.Handler:
    _ensure_parent(path)
    handler = _FlushingRotatingFileHandler(
        path,
        maxBytes=max(settings.log_file_max_bytes, 1024 * 1024),
        backupCount=max(settings.log_file_backup_count, 0),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT))
    return handler


def _configure(logger: logging.Logger, file_path: str) -> logging.Logger:
    if getattr(logger, "_govdoc_configured", False):
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.addHandler(_build_file_handler(file_path))
    except OSError as exc:  # pragma: no cover - 文件权限问题时兜底打到 stderr
        sys.stderr.write(f"[debug_log] failed to open {file_path}: {exc}\n")
    if settings.log_stage_echo_stdout:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT))
        logger.addHandler(stream_handler)
    logger._govdoc_configured = True  # type: ignore[attr-defined]
    return logger


def _backend_logger() -> logging.Logger:
    return _configure(logging.getLogger(BACKEND_LOGGER_NAME), settings.backend_log_path)


def _model_logger() -> logging.Logger:
    return _configure(logging.getLogger(MODEL_LOGGER_NAME), settings.model_log_path)


def _route_logger(stage: str) -> logging.Logger:
    """按 stage 前缀路由：llm.* 走模型日志，其它走后端日志。"""
    if stage.startswith("llm."):
        return _model_logger()
    return _backend_logger()


# 模块加载时立刻把旧名 logger 也挂上同样的 handler，便于老代码直接 getLogger 时不至于丢日志。
_backend_logger()
_model_logger()


def _clip_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]}\n...<truncated {omitted} chars>"


def _normalize(value: Any, max_string_chars: int, seen: set[int] | None = None) -> Any:
    seen = seen or set()
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _clip_text(value, max_string_chars)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if BaseModel is not None and isinstance(value, BaseModel):
        value_id = id(value)
        if value_id in seen:
            return f"<circular-ref {value.__class__.__name__}>"
        seen.add(value_id)
        try:
            return _normalize(value.model_dump(), max_string_chars, seen)
        finally:
            seen.discard(value_id)
    if is_dataclass(value):
        value_id = id(value)
        if value_id in seen:
            return f"<circular-ref {value.__class__.__name__}>"
        seen.add(value_id)
        try:
            return _normalize(asdict(value), max_string_chars, seen)
        finally:
            seen.discard(value_id)
    if isinstance(value, dict):
        value_id = id(value)
        if value_id in seen:
            return "<circular-ref dict>"
        seen.add(value_id)
        try:
            return {
                str(key): _normalize(item, max_string_chars, seen)
                for key, item in value.items()
            }
        finally:
            seen.discard(value_id)
    if isinstance(value, (list, tuple, set)):
        value_id = id(value)
        if value_id in seen:
            return f"<circular-ref {value.__class__.__name__}>"
        seen.add(value_id)
        try:
            return [_normalize(item, max_string_chars, seen) for item in value]
        finally:
            seen.discard(value_id)
    if hasattr(value, "__dict__"):
        value_id = id(value)
        if value_id in seen:
            return f"<circular-ref {value.__class__.__name__}>"
        seen.add(value_id)
        raw = {
            str(key): item
            for key, item in vars(value).items()
            if not str(key).startswith("_sa_")
        }
        if not raw:
            identity = getattr(value, "id", None)
            if identity is not None:
                seen.discard(value_id)
                return {
                    "__type__": value.__class__.__name__,
                    "id": identity,
                }
            seen.discard(value_id)
            return f"<object {value.__class__.__name__}>"
        raw["__type__"] = value.__class__.__name__
        try:
            return _normalize(raw, max_string_chars, seen)
        finally:
            seen.discard(value_id)
    return _clip_text(str(value), max_string_chars)


def _json_text(value: Any, max_chars: int, max_string_chars: int) -> str:
    normalized = _normalize(value, max_string_chars)
    text = json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True)
    return _clip_text(text, max_chars)


def _maybe_dump(obj: Any) -> Any:
    """把 Pydantic / dataclass / 带 snapshot 的运行期对象转成可遍历的 dict/list。"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_maybe_dump(x) for x in obj]
    if BaseModel is not None and isinstance(obj, BaseModel):
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump()
        except Exception:
            pass
    snap = getattr(obj, "snapshot", None)
    if callable(snap):
        try:
            return snap()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {
            str(k): v
            for k, v in vars(obj).items()
            if not str(k).startswith("_")
        }
    return str(obj)


def _tool_declarations_line(tools: Any) -> str:
    if not isinstance(tools, list) or not tools:
        return ""
    names: list[str] = []
    for t in tools[:48]:
        if not isinstance(t, dict):
            continue
        fn = t.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            names.append(str(fn["name"]))
    extra = f" …共{len(tools)}项" if len(tools) > len(names) else ""
    return f"--- tools ({len(tools)} 个) ---\n" + ", ".join(names) + extra


def _message_content_preview(content: Any, preview: int) -> list[str]:
    lines: list[str] = []
    if content is None:
        lines.append("  (无 content)")
        return lines
    if isinstance(content, str):
        s = content.strip()
        lines.append(f"  字符数: {len(content)}")
        lines.append(_clip_text(s, preview).replace("\n", "\n  "))
        return lines
    if isinstance(content, list):
        lines.append(f"  多段内容 parts={len(content)}")
        for j, part in enumerate(content[:6], 1):
            if isinstance(part, dict):
                ptype = part.get("type", "?")
                if ptype == "text":
                    t = str(part.get("text") or "")
                    lines.append(f"  [{j}] type=text chars={len(t)}")
                    lines.append("    " + _clip_text(t, min(preview, 2000)).replace("\n", "\n    "))
                else:
                    lines.append(f"  [{j}] type={ptype} keys={list(part.keys())[:8]}")
            else:
                lines.append(f"  [{j}] {type(part).__name__}")
        if len(content) > 6:
            lines.append(f"  … 余 {len(content) - 6} 段")
        return lines
    lines.append(f"  type={type(content).__name__}")
    return lines


def _message_block_lines(idx: int, msg: dict[str, Any], preview: int) -> list[str]:
    role = msg.get("role", "?")
    name = msg.get("name")
    head = f"[{idx}] role={role}"
    if name:
        head += f" name={name}"
    lines = [head]
    lines.extend(_message_content_preview(msg.get("content"), preview))
    tcs = msg.get("tool_calls")
    if isinstance(tcs, list) and tcs:
        names: list[str] = []
        for tc in tcs:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function")
            if isinstance(fn, dict) and fn.get("name"):
                names.append(str(fn["name"]))
        if names:
            lines.append(f"  assistant.tool_calls: {', '.join(names)}")
    return lines


def _summarize_llm_request_dict(d: dict[str, Any], preview: int) -> list[str]:
    lines: list[str] = []
    lines.append(f"url: {d.get('url')}")
    lines.append(
        f"model: {d.get('model')} | requested_model: {d.get('requested_model')} | purpose: {d.get('purpose')}"
    )
    lines.append(f"timeoutSeconds: {d.get('timeoutSeconds')}")
    inner = d.get("payload")
    if not isinstance(inner, dict):
        lines.append(f"payload: <{type(inner).__name__}> {inner}")
        return lines
    lines.append(f"stream: {inner.get('stream')} | temperature: {inner.get('temperature')}")
    msgs = inner.get("messages")
    if isinstance(msgs, list):
        lines.append(f"--- messages（共 {len(msgs)} 条，以下为汇总，非流式分片）---")
        for i, m in enumerate(msgs, 1):
            if isinstance(m, dict):
                lines.extend(_message_block_lines(i, m, preview))
            else:
                lines.append(f"[{i}] <{type(m).__name__}>")
    tools = inner.get("tools")
    if tools:
        lines.append(_tool_declarations_line(tools))
    return lines


def _summarize_llm_response_dict(d: dict[str, Any], preview: int) -> list[str]:
    lines: list[str] = []
    lines.append(
        f"HTTP {d.get('statusCode')} | model={d.get('model')} | streamed={d.get('streamed')} | "
        f"streamChunkCount={d.get('streamChunkCount', 'n/a')}"
    )
    usage = d.get("usage")
    if isinstance(usage, dict) and usage:
        lines.append(f"usage: {json.dumps(usage, ensure_ascii=False)}")
    text = d.get("text")
    text_s = text if isinstance(text, str) else ""
    lines.append(f"--- 合并正文（{len(text_s)} 字符）---")
    lines.append(_clip_text(text_s.strip(), preview).replace("\n", "\n"))
    msg = d.get("message")
    if isinstance(msg, dict):
        rc = msg.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            lines.append(f"--- reasoning（{len(rc)} 字符）---")
            lines.append(_clip_text(rc.strip(), preview).replace("\n", "\n"))
    tcs = d.get("toolCalls")
    if isinstance(tcs, list) and tcs:
        lines.append("--- tool_calls（汇总）---")
        for tc in tcs:
            if not isinstance(tc, dict):
                lines.append(f"  {tc!r}")
                continue
            fn = tc.get("function")
            if isinstance(fn, dict):
                nm = fn.get("name", "?")
                raw_args = fn.get("arguments", "")
                arg_s = raw_args if isinstance(raw_args, str) else json.dumps(raw_args, ensure_ascii=False)
                lines.append(f"  - {nm} args(len={len(arg_s)}): {_clip_text(arg_s, min(preview, 4000))}")
            else:
                lines.append(f"  - {tc.get('id', '?')}: {json.dumps(tc, ensure_ascii=False)[:400]}…")
    if d.get("raw") and not d.get("streamed"):
        raw_s = json.dumps(d["raw"], ensure_ascii=False)
        lines.append("--- 原始 raw（非流式，已截断）---")
        lines.append(_clip_text(raw_s, min(preview, 12000)))
    return lines


def _summarize_llm_error_dict(d: dict[str, Any], preview: int) -> list[str]:
    lines = [
        f"model: {d.get('model')} | purpose: {d.get('purpose')}",
        f"error: {_clip_text(str(d.get('error', '')), preview)}",
    ]
    return lines


def _rough_json_len(obj: Any) -> int:
    try:
        return len(json.dumps(obj, ensure_ascii=False, default=str))
    except Exception:
        return len(str(obj))


def _summarize_generic_dict(obj: Any, preview: int, depth: int, indent: str) -> list[str]:
    """通用 dict/list 折叠为大对象时只保留规模与短预览。"""
    prefix = indent
    if depth > 6:
        return [prefix + "<省略：递归过深>"]
    if obj is None or isinstance(obj, (int, float, bool)):
        return [prefix + str(obj)]
    if isinstance(obj, str):
        if len(obj) <= preview:
            return [prefix + obj]
        return [prefix + f"(字符串 {len(obj)} 字符)", _clip_text(obj, preview).replace("\n", "\n" + prefix)]
    if isinstance(obj, list):
        if not obj:
            return [prefix + "[]"]
        if len(obj) > 8 or _rough_json_len(obj) > 6000:
            lines = [prefix + f"<list len={len(obj)}>"]
            for i, item in enumerate(obj[:5], 1):
                lines.append(f"{prefix}  --- item {i} ---")
                lines.extend(_summarize_generic_dict(item, min(preview, 1200), depth + 1, prefix + "  "))
            if len(obj) > 5:
                lines.append(f"{prefix}  … 余 {len(obj) - 5} 项")
            return lines
        lines = [prefix + "["]
        for i, item in enumerate(obj, 1):
            lines.append(f"{prefix}  [{i}]")
            lines.extend(_summarize_generic_dict(item, preview, depth + 1, prefix + "    "))
        lines.append(prefix + "]")
        return lines
    if isinstance(obj, dict):
        lines = [prefix + "{"]
        keys = list(obj.keys())
        for k in keys[:40]:
            v = obj[k]
            key_s = str(k)
            if key_s in ("runtimeContext", "memoryContext", "taskPacket", "rootTask", "leaderPlan", "recentMessages"):
                dumped = _maybe_dump(v)
                rz = _rough_json_len(dumped)
                lines.append(f"{prefix}  {key_s}: <对象 约 {rz} 字符>")
                if isinstance(dumped, dict):
                    if key_s == "runtimeContext":
                        sm = dumped.get("summary") or dumped.get("running_context_summary")
                        if isinstance(sm, str) and sm.strip():
                            nl = "\n" + prefix + "    "
                            lines.append(
                                f"{prefix}    summary 预览: "
                                f"{_clip_text(sm.strip(), min(preview, 2000)).replace(chr(10), nl)}"
                            )
                        rm = dumped.get("recent_messages") or dumped.get("recentMessages")
                        if isinstance(rm, list):
                            lines.append(f"{prefix}    recent_messages: {len(rm)} 条")
                            for i, m in enumerate(rm[:4], 1):
                                if isinstance(m, dict):
                                    lines.extend(
                                        _summarize_generic_dict(
                                            {
                                                "role": m.get("role"),
                                                "content_preview": _clip_text(
                                                    str(m.get("content") or ""), 240
                                                ),
                                            },
                                            400,
                                            depth + 2,
                                            prefix + "      ",
                                        )
                                    )
                    elif key_s == "memoryContext" and isinstance(dumped, dict):
                        for mk, mv in list(dumped.items())[:12]:
                            if isinstance(mv, str):
                                lines.append(
                                    f"{prefix}    {mk}: (str {len(mv)} 字符) "
                                    f"{_clip_text(mv, 200).replace(chr(10), ' ')}"
                                )
                            else:
                                lines.append(f"{prefix}    {mk}: {_rough_json_len(mv)} 字符规模")
                    elif key_s in ("taskPacket", "rootTask") and isinstance(dumped, dict):
                        for short_k in (
                            "task_id",
                            "taskId",
                            "conversation_id",
                            "conversationId",
                            "objective",
                            "skill_name",
                            "skillName",
                        ):
                            if short_k in dumped:
                                lines.append(f"{prefix}    {short_k}: {dumped.get(short_k)!r}"[:500])
                    elif key_s == "leaderPlan" and isinstance(dumped, dict):
                        steps = dumped.get("steps")
                        if isinstance(steps, list):
                            lines.append(f"{prefix}    steps: {len(steps)} 步")
                            for st in steps[:12]:
                                if isinstance(st, dict):
                                    lines.append(
                                        f"{prefix}      - #{st.get('index')} {st.get('skillName') or st.get('skill_name')}: "
                                        f"{_clip_text(str(st.get('title') or ''), 120)}"
                                    )
                elif isinstance(dumped, list) and key_s in (
                    "recentMessages",
                    "recent_messages",
                    "sourceMessageIds",
                ):
                    lines.append(f"{prefix}    {key_s}: list len={len(dumped)}")
                    for i, m in enumerate(dumped[:5], 1):
                        if isinstance(m, dict):
                            lines.extend(
                                _summarize_generic_dict(
                                    {
                                        "role": m.get("role"),
                                        "id": m.get("id"),
                                        "content_preview": _clip_text(str(m.get("content") or ""), 200),
                                    },
                                    400,
                                    depth + 2,
                                    prefix + "      ",
                                )
                            )
                        else:
                            lines.append(f"{prefix}      [{i}] {str(m)[:120]}")
                    if len(dumped) > 5:
                        lines.append(f"{prefix}    … 余 {len(dumped) - 5} 项")
                continue
            rz = _rough_json_len(v)
            if rz > max(4000, preview * 2) and not isinstance(v, (str, int, float, bool)):
                lines.append(f"{prefix}  {key_s}: <{_type_name(v)} 约 {rz} 字符，已折叠>")
                continue
            lines.append(f"{prefix}  {key_s}:")
            lines.extend(_summarize_generic_dict(v, preview, depth + 1, prefix + "    "))
        if len(keys) > 40:
            lines.append(f"{prefix}  … 余 {len(keys) - 40} 个键")
        lines.append(prefix + "}")
        return lines
    return [prefix + str(obj)[:preview]]


def _type_name(v: Any) -> str:
    return type(v).__name__


def _summarize_planner_response_dict(d: dict[str, Any], preview: int) -> list[str]:
    lines: list[str] = ["===== 汇总输出（Planner） ====="]
    lines.append(f"modelName: {d.get('modelName')}")
    meta = d.get("plannerMeta")
    if meta is not None:
        try:
            lines.append(f"plannerMeta: {json.dumps(meta, ensure_ascii=False)[:min(preview, 4000)]}")
        except Exception:
            lines.append(f"plannerMeta: {str(meta)[:500]}")
    np = d.get("normalizedPlan")
    if isinstance(np, dict):
        lines.append(f"intent: {np.get('intent')} | summary: {_clip_text(str(np.get('summary') or ''), 800)}")
        steps = np.get("steps")
        if isinstance(steps, list):
            lines.append(f"--- steps（共 {len(steps)} 步）---")
            for st in steps:
                if not isinstance(st, dict):
                    continue
                lines.append(
                    f"  #{st.get('index')} [{st.get('skillName')}] {st.get('title')}\n"
                    f"    objective: {_clip_text(str(st.get('objective') or ''), 400)}"
                )
    return lines


def _summarize_planner_fallback_dict(d: dict[str, Any], preview: int) -> list[str]:
    lines = ["===== 汇总输出（Planner 降级） =====", f"reason: {d.get('reason')}"]
    fp = d.get("fallbackPlan")
    if isinstance(fp, dict):
        lines.append(f"intent: {fp.get('intent')} | summary: {fp.get('summary')}")
        st = fp.get("steps")
        if isinstance(st, list):
            lines.append("steps: " + ", ".join(str(x) for x in st))
    return lines


def _summarize_runtime_run_start(d: dict[str, Any], preview: int) -> list[str]:
    lines = ["===== 汇总输入（运行开始） ====="]
    lines.append(f"conversationId: {d.get('conversationId')} | title: {d.get('conversationTitle')}")
    u = d.get("user")
    if isinstance(u, dict):
        lines.append(f"user: {u.get('name')} ({u.get('userId')}) account={u.get('account')}")
    req = d.get("request")
    if isinstance(req, dict):
        lines.append("--- 用户请求 content ---")
        c = req.get("content")
        if isinstance(c, str):
            lines.append(_clip_text(c, preview).replace("\n", "\n"))
        at = req.get("attachments")
        if isinstance(at, list):
            lines.append(f"attachments: {len(at)} 个")
        lines.append(
            f"skill: requested={req.get('requestedSkill')} resolved={req.get('resolvedSkill')} | "
            f"model={req.get('requestedModel')} | resume={req.get('resumeFromWaiting')}"
        )
        eg = req.get("effectiveGoal")
        if isinstance(eg, str) and eg and eg != c:
            lines.append("--- effectiveGoal ---")
            lines.append(_clip_text(eg, preview).replace("\n", "\n"))
    return lines


def _summarize_skill_stage(stage: str, plain: Any, preview: int) -> list[str]:
    if not isinstance(plain, dict):
        return ["===== 汇总 =====", str(plain)[:preview]]
    if stage == "skill.execute.start":
        lines = ["===== 汇总输入（Skill） =====", f"skill: {plain.get('skill')}", f"model: {plain.get('requestedModel')}"]
        c = plain.get("content")
        if isinstance(c, str):
            lines.append("--- content ---")
            lines.append(_clip_text(c, preview).replace("\n", "\n"))
        at = plain.get("attachments")
        if isinstance(at, list):
            lines.append(f"attachments: {len(at)}")
        lines.append(f"cookiePreview: {plain.get('cookiePreview')}")
        return lines
    if stage == "skill.execute.result":
        lines = ["===== 汇总输出（Skill） =====", f"skill: {plain.get('skill')}"]
        result = plain.get("result")
        dumped = _maybe_dump(result)
        lines.extend(_summarize_generic_dict(dumped, min(preview, 8000), 0, ""))
        return lines
    if stage == "skill.llm.remote_ok":
        lines = [
            "===== 汇总输出（Skill 远端 LLM） =====",
            f"skill: {plain.get('skill')} | requestedModel: {plain.get('requestedModel')} | resolved: {plain.get('resolvedModel')}",
        ]
        pr = plain.get("prompt")
        if isinstance(pr, str):
            lines.append(f"--- prompt（{len(pr)} 字符）---")
            lines.append(_clip_text(pr, preview).replace("\n", "\n"))
        tx = plain.get("text")
        if isinstance(tx, str):
            lines.append(f"--- 模型文本（截断展示，全量 {len(tx)} 字符）---")
            lines.append(_clip_text(tx, min(preview, 4000)).replace("\n", "\n"))
        rc = plain.get("reasoningContent")
        if isinstance(rc, str) and rc.strip():
            lines.append(f"--- reasoning（{len(rc)} 字符）---")
            lines.append(_clip_text(rc, min(preview, 4000)).replace("\n", "\n"))
        return lines
    if stage == "skill.llm.remote_error":
        return [
            "===== 汇总输出（Skill 远端错误） =====",
            f"skill: {plain.get('skill')} | error: {plain.get('error')}",
        ]
    lines = [f"===== 汇总 ({stage}) ====="]
    lines.extend(_summarize_generic_dict(plain, preview, 0, ""))
    return lines


def _summarize_api_stage(stage: str, plain: Any, preview: int) -> list[str]:
    if not isinstance(plain, dict):
        return [str(plain)[:preview]]
    if "request" in stage:
        title = "===== 汇总输入（API） ====="
    elif "response" in stage:
        title = "===== 汇总输出（API） ====="
    else:
        title = "===== 汇总（API） ====="
    lines = [title]
    lines.extend(_summarize_generic_dict(plain, preview, 0, ""))
    return lines


def _format_stage_summary(stage: str, payload: Any, max_string_chars: int, max_chars: int) -> str:
    plain = _maybe_dump(payload)
    preview = max(400, min(max_string_chars, 20000))
    lines: list[str] = []

    if stage.startswith("llm.request.") and isinstance(plain, dict):
        lines.append("===== 汇总输入（模型 HTTP 请求体语义） =====")
        lines.extend(_summarize_llm_request_dict(plain, preview))
    elif stage.startswith("llm.response.") and isinstance(plain, dict):
        lines.append("===== 汇总输出（模型 HTTP 响应语义，整段流合并后一条） =====")
        lines.extend(_summarize_llm_response_dict(plain, preview))
    elif stage.startswith("llm.error.") and isinstance(plain, dict):
        lines.extend(_summarize_llm_error_dict(plain, preview))
    elif stage == "llm.stream.chunk_json_skip":
        if isinstance(plain, dict):
            lines.append(
                "===== 流式解析（单行摘要，非正文流） =====\n"
                f"purpose={plain.get('purpose')} | model={plain.get('model')} | error={plain.get('error')}\n"
                f"preview: {plain.get('preview')}"
            )
        else:
            lines.append(str(plain))
    elif stage == "planner.request" and isinstance(plain, dict):
        lines.append("===== 汇总输入（Planner → 模型） =====")
        lines.append(f"requestedModel: {plain.get('requestedModel')}")
        msgs = plain.get("messages")
        if isinstance(msgs, list):
            lines.append(f"--- messages（共 {len(msgs)} 条）---")
            for i, m in enumerate(msgs, 1):
                if isinstance(m, dict):
                    lines.extend(_message_block_lines(i, m, preview))
        ts = plain.get("toolSchema") or plain.get("tools")
        if ts:
            lines.append(_tool_declarations_line(ts if isinstance(ts, list) else [ts]))
    elif stage == "planner.response" and isinstance(plain, dict):
        lines.extend(_summarize_planner_response_dict(plain, preview))
    elif stage == "planner.fallback" and isinstance(plain, dict):
        lines.extend(_summarize_planner_fallback_dict(plain, preview))
    elif stage == "runtime.run.start" and isinstance(plain, dict):
        lines.extend(_summarize_runtime_run_start(plain, preview))
    elif stage == "runtime.context.built" and isinstance(plain, dict):
        lines.append("===== 汇总（运行上下文已构建） =====")
        lines.extend(_summarize_generic_dict(plain, preview, 0, ""))
    elif stage == "runtime.memory.refs" and isinstance(plain, dict):
        lines.append("===== 汇总（记忆文件引用 + memoryContext 规模） =====")
        lines.extend(_summarize_generic_dict(plain, preview, 0, ""))
    elif stage == "runtime.task_packet" and isinstance(plain, dict):
        lines.append("===== 汇总（根任务 packet / plan） =====")
        lines.extend(_summarize_generic_dict(plain, preview, 0, ""))
    elif stage.startswith("skill."):
        lines.extend(_summarize_skill_stage(stage, plain, preview))
    elif stage.startswith("api."):
        lines.extend(_summarize_api_stage(stage, plain, preview))
    else:
        lines.append("===== 汇总 =====")
        lines.extend(_summarize_generic_dict(plain, preview, 0, ""))

    text = "\n".join(lines).strip()
    return _clip_text(text, max_chars)


def mask_cookie(cookie: str | None, preview_chars: int = 120) -> str | None:
    if not cookie:
        return None
    return _clip_text(cookie, preview_chars)


def log_stage(
    stage: str,
    payload: Any | None = None,
    *,
    enabled: bool,
    max_chars: int,
    max_string_chars: int,
) -> None:
    if not enabled:
        return
    logger = _route_logger(stage)
    try:
        if payload is None:
            logger.info("[debug:%s]", stage)
            return
        if getattr(settings, "debug_log_style", "summary") == "json":
            body = _json_text(payload, max_chars=max_chars, max_string_chars=max_string_chars)
        else:
            body = _format_stage_summary(stage, payload, max_string_chars, max_chars)
        logger.info("[debug:%s]\n%s", stage, body)
    except Exception as exc:  # pragma: no cover
        logger.exception("[debug:%s] log serialization failed: %s", stage, exc)


__all__ = [
    "log_stage",
    "mask_cookie",
    "BACKEND_LOGGER_NAME",
    "MODEL_LOGGER_NAME",
]
