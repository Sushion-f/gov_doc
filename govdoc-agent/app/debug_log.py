import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]


LOGGER_NAME = "govdoc_agent.runtime"


def _get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


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
    logger = _get_logger()
    try:
        if payload is None:
            logger.info("[debug:%s]", stage)
            return
        logger.info(
            "[debug:%s]\n%s",
            stage,
            _json_text(payload, max_chars=max_chars, max_string_chars=max_string_chars),
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("[debug:%s] log serialization failed: %s", stage, exc)
