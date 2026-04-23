"""Skills registry: 加载用户可上传的 SKILL.md 配方，覆盖内置 sub-agent。

目录约定：
    govdoc-agent/skills_store/<name>/SKILL.md

SKILL.md 格式（YAML frontmatter + markdown body）：

    ---
    name: retrieval
    display: 检索专家 Claw
    tools: [workspace.ls, workspace.cat, memory.read]
    output_schema: { type: object, required: [citations] }
    temperature: 0.3
    ---
    ## 角色
    你是一名资料检索专家……

* 只覆盖 **system prompt** / display / tools / output_schema / temperature；
  调度路径、render_blocks 归一化仍由 ``agent_capability_adapter`` 控制。
* 目录支持热重载：每次访问时若文件 mtime 变化会重新解析。
* 仅允许 ASCII/中文字母 + 下划线的 skill name，防止目录穿越。
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import settings  # noqa: F401  # 保留便于后续加开关


_SKILLS_STORE_ROOT = Path(__file__).resolve().parent.parent / "skills_store"
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


@dataclass
class SkillOverlay:
    name: str
    display_name: str = ""
    description: str = ""
    system_prompt: str = ""
    tools: list[str] | None = None
    output_schema: dict | None = None
    temperature: float | None = None
    model_hint: str | None = None
    source_path: Path | None = None
    mtime: float = 0.0


class _OverlayCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, SkillOverlay] = {}

    def get(self, name: str) -> SkillOverlay | None:
        name = (name or "").strip().lower()
        if not name or not _NAME_PATTERN.match(name):
            return None
        with self._lock:
            overlay = self._items.get(name)
        path = _resolve_skill_md_path(name)
        if path is None or not path.is_file():
            if overlay is not None:
                with self._lock:
                    self._items.pop(name, None)
            return None
        mtime = path.stat().st_mtime
        if overlay is not None and overlay.mtime == mtime:
            return overlay
        parsed = _parse_skill_file(name, path)
        if parsed is None:
            return None
        with self._lock:
            self._items[name] = parsed
        return parsed

    def invalidate(self, name: str | None = None) -> None:
        with self._lock:
            if name is None:
                self._items.clear()
            else:
                self._items.pop((name or "").strip().lower(), None)


_CACHE = _OverlayCache()


def skills_store_root() -> Path:
    _SKILLS_STORE_ROOT.mkdir(parents=True, exist_ok=True)
    return _SKILLS_STORE_ROOT


def _resolve_skill_md_path(name: str) -> Path | None:
    if not _NAME_PATTERN.match(name or ""):
        return None
    candidate = skills_store_root() / name / "SKILL.md"
    try:
        # 防止符号链接逃逸
        resolved = candidate.resolve()
        root = skills_store_root().resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    text = (raw or "").lstrip()
    if not text.startswith("---"):
        return {}, raw
    end = text.find("\n---", 3)
    if end < 0:
        return {}, raw
    header = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    metadata = _parse_simple_yaml(header)
    return metadata, body


def _parse_simple_yaml(block: str) -> dict:
    """极简 YAML 解析：仅支持 ``key: value`` 行；value 可以是 JSON 片段。"""
    data: dict = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value_raw = stripped.partition(":")
        key = key.strip()
        value = value_raw.strip()
        if not key:
            continue
        parsed: object = value
        if value.startswith(("[", "{")):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                if value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1]
                    parsed = [
                        item.strip().strip("'\"")
                        for item in inner.split(",")
                        if item.strip()
                    ]
                else:
                    parsed = value
        elif value.lower() in {"true", "false"}:
            parsed = value.lower() == "true"
        elif value == "null":
            parsed = None
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        data[key] = parsed
    return data


def _parse_skill_file(name: str, path: Path) -> SkillOverlay | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    metadata, body = _split_frontmatter(raw)
    tools = metadata.get("tools")
    if isinstance(tools, str):
        tools = [item.strip() for item in tools.split(",") if item.strip()]
    elif isinstance(tools, list):
        tools = [str(item).strip() for item in tools if str(item).strip()]
    else:
        tools = None
    output_schema = metadata.get("output_schema")
    if not isinstance(output_schema, dict):
        output_schema = None
    temperature = metadata.get("temperature")
    temperature_value: float | None
    try:
        temperature_value = float(temperature) if temperature is not None else None
    except (TypeError, ValueError):
        temperature_value = None
    return SkillOverlay(
        name=name,
        display_name=str(metadata.get("display") or metadata.get("display_name") or "").strip(),
        description=str(metadata.get("description") or metadata.get("summary") or "").strip(),
        system_prompt=body.strip(),
        tools=tools,
        output_schema=output_schema,
        temperature=temperature_value,
        model_hint=str(metadata.get("model") or metadata.get("model_hint") or "").strip() or None,
        source_path=path,
        mtime=path.stat().st_mtime,
    )


def get_skill_overlay(name: str) -> SkillOverlay | None:
    return _CACHE.get(name)


def list_overlays() -> list[SkillOverlay]:
    root = skills_store_root()
    items: list[SkillOverlay] = []
    if not root.is_dir():
        return items
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        overlay = get_skill_overlay(entry.name)
        if overlay is not None:
            items.append(overlay)
    return items


def save_skill_markdown(name: str, content: str) -> Path:
    """把上传的 SKILL.md 落盘并返回路径。"""
    safe_name = (name or "").strip().lower()
    if not _NAME_PATTERN.match(safe_name):
        raise ValueError("skill name 只允许字母、数字、下划线和中划线")
    folder = skills_store_root() / safe_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text((content or "").strip() + "\n", encoding="utf-8")
    _CACHE.invalidate(safe_name)
    return path


def delete_skill_overlay(name: str) -> bool:
    safe_name = (name or "").strip().lower()
    if not _NAME_PATTERN.match(safe_name):
        return False
    path = _resolve_skill_md_path(safe_name)
    if path is None or not path.is_file():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    _CACHE.invalidate(safe_name)
    return True


def read_skill_markdown(name: str) -> str | None:
    path = _resolve_skill_md_path(name)
    if path is None or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
