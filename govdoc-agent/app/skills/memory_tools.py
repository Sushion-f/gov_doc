"""Memory toolset: 让模型按需读取 `users/<id>/memory/topics/*.md` 与 sessions 摘要。

- `memory.list`：列出 topic / session 文件清单（仅路径，不带内容）。
- `memory.read`：读取单个 topic 或 session 文件原文。
- `memory.search`：跨所有 topic/session 做文本模糊匹配，返回命中行 + 上下文。

所有访问都限定在 `users/<user_id>/memory/` 目录下，防止越权读取。
工具调用会复用 `WorkspaceCliExecution` 的事件格式，前端仍按 `cli_exec` 卡渲染。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..storage import user_memory_root

_TOPIC_PREFIXES = ("topics/", "sessions/")


def _safe_relative(relative: str | None) -> str:
    raw = (relative or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        return ""
    parts = [segment for segment in raw.split("/") if segment not in {"", "."}]
    if any(segment == ".." for segment in parts):
        raise ValueError("非法 memory 路径")
    return "/".join(parts)


def _resolve_memory_path(user_id: str, relative: str) -> Path:
    normalized = _safe_relative(relative)
    if not normalized:
        return user_memory_root(user_id)
    # 允许传入 "common_feedback"、"topics/common_feedback" 或 "topics/common_feedback.md"
    candidate_names: list[str] = []
    if "/" in normalized:
        candidate_names.append(normalized)
        if not normalized.endswith(".md"):
            candidate_names.append(normalized + ".md")
    else:
        for prefix in _TOPIC_PREFIXES:
            candidate_names.append(f"{prefix}{normalized}.md")
            candidate_names.append(f"{prefix}{normalized}")
        candidate_names.append(f"{normalized}.md")
        candidate_names.append(normalized)
    root = user_memory_root(user_id)
    root_resolved = root.resolve()
    for name in candidate_names:
        candidate = (root / name).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            continue
        if candidate.exists():
            return candidate
    # 没有落地文件也返回 topics/<name>.md 的拼接结果，由上层决定报错
    return (root / candidate_names[0]).resolve() if candidate_names else root


@dataclass
class MemoryToolExecution:
    tool_name: str
    display_name: str
    command: str
    output_text: str
    payload: dict[str, Any]

    def tool_message(self) -> dict[str, Any]:
        return {
            "toolName": self.display_name,
            "command": self.command,
            "output": self.output_text,
            **self.payload,
        }

    def runtime_event(self) -> dict[str, Any]:
        from html import escape

        preview = self.output_text if len(self.output_text) < 8000 else self.output_text[:8000] + "\n..."
        return {
            "event_type": "cli_exec",
            "status": "completed",
            "title": f"记忆工具 · {self.display_name}",
            "detail": self.command,
            "detail_html": (
                "<pre class='cli-tool-block memory-tool-block'>"
                f"{escape(self.command)}\n\n{escape(preview)}"
                "</pre>"
            ),
            "payload": self.tool_message(),
        }


class MemoryToolset:
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            self._tool_schema(
                "memory.list",
                "列出当前用户 memory/topics 与 memory/sessions 下的 Markdown 文件清单。"
                "当用户问题涉及个人偏好 / 历史决定 / 常见反馈时，优先调用以发现 topic。",
                {
                    "scope": {
                        "type": "string",
                        "enum": ["all", "topics", "sessions"],
                        "default": "all",
                        "description": "限制列举范围。",
                    },
                },
                [],
            ),
            self._tool_schema(
                "memory.read",
                "读取指定 topic 或 session 的 Markdown 原文。name 可以是 "
                "'common_feedback'、'topics/common_feedback' 或完整相对路径。",
                {
                    "name": {
                        "type": "string",
                        "description": "topic 名或相对路径。",
                    },
                    "max_chars": {
                        "type": "integer",
                        "default": 6000,
                        "minimum": 200,
                        "maximum": 20000,
                    },
                },
                ["name"],
            ),
            self._tool_schema(
                "memory.search",
                "在所有 topic 与 session 文件中做文本匹配（默认忽略大小写），返回命中文件与命中行。",
                {
                    "query": {"type": "string", "description": "要搜索的关键字或正则。"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 80},
                    "case_sensitive": {"type": "boolean", "default": False},
                },
                ["query"],
            ),
        ]

    @staticmethod
    def _tool_schema(
        name: str,
        description: str,
        properties: dict[str, Any],
        required: list[str],
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        }

    def execute(
        self,
        function_name: str,
        arguments: dict[str, Any],
        runtime_context: dict[str, Any] | None,
    ) -> MemoryToolExecution:
        runtime_context = runtime_context or {}
        user_id = (
            runtime_context.get("workspaceUserId")
            or runtime_context.get("memoryUserId")
            or runtime_context.get("userId")
        )
        if not user_id:
            raise ValueError("缺少 userId，memory 工具无法访问用户目录")
        if function_name == "memory.list":
            return self._execute_list(user_id, arguments)
        if function_name == "memory.read":
            return self._execute_read(user_id, arguments)
        if function_name == "memory.search":
            return self._execute_search(user_id, arguments)
        raise ValueError(f"未知 memory 工具: {function_name}")

    def _execute_list(self, user_id: str, arguments: dict[str, Any]) -> MemoryToolExecution:
        scope = str(arguments.get("scope") or "all").lower()
        root = user_memory_root(user_id)
        items: list[dict[str, Any]] = []
        candidates: list[Path] = []
        if scope in {"all", "topics"}:
            candidates.extend(sorted((root / "topics").glob("*.md")) if (root / "topics").is_dir() else [])
        if scope in {"all", "sessions"}:
            candidates.extend(sorted((root / "sessions").glob("*.md")) if (root / "sessions").is_dir() else [])
        for path in candidates:
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            stat = path.stat()
            items.append(
                {
                    "name": path.stem,
                    "path": rel,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
        if items:
            output = "\n".join(f"- {item['path']} ({item['size']} bytes, {item['mtime']})" for item in items)
        else:
            output = "(暂无 topic / session 文件)"
        return MemoryToolExecution(
            tool_name="memory.list",
            display_name="memory.list",
            command=f"memory.list(scope={json.dumps(scope, ensure_ascii=False)})",
            output_text=output,
            payload={"items": items, "scope": scope},
        )

    def _execute_read(self, user_id: str, arguments: dict[str, Any]) -> MemoryToolExecution:
        name = str(arguments.get("name") or "").strip()
        if not name:
            raise ValueError("memory.read 缺少 name")
        max_chars = max(200, min(int(arguments.get("max_chars") or 6000), 20000))
        path = _resolve_memory_path(user_id, name)
        if not path.is_file():
            return MemoryToolExecution(
                tool_name="memory.read",
                display_name="memory.read",
                command=f"memory.read(name={json.dumps(name, ensure_ascii=False)})",
                output_text=f"(未找到 topic 文件：{name})",
                payload={"name": name, "found": False, "path": str(path)},
            )
        text = path.read_text(encoding="utf-8")
        clipped = text if len(text) <= max_chars else text[:max_chars].rstrip() + "\n..."
        root = user_memory_root(user_id)
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        return MemoryToolExecution(
            tool_name="memory.read",
            display_name="memory.read",
            command=f"memory.read(name={json.dumps(rel, ensure_ascii=False)}, max_chars={max_chars})",
            output_text=clipped,
            payload={"name": rel, "found": True, "bytes": len(text.encode('utf-8')), "clipped": len(text) > max_chars},
        )

    def _execute_search(self, user_id: str, arguments: dict[str, Any]) -> MemoryToolExecution:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("memory.search 缺少 query")
        limit = max(1, min(int(arguments.get("limit") or 20), 80))
        case_sensitive = bool(arguments.get("case_sensitive") or False)
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(query, flags)
        except re.error:
            regex = re.compile(re.escape(query), flags)
        root = user_memory_root(user_id)
        hits: list[dict[str, Any]] = []
        for folder_name in ("topics", "sessions"):
            folder = root / folder_name
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.md")):
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        rel = path.relative_to(root).as_posix()
                        hits.append({"path": rel, "line": line_no, "content": line.strip()[:240]})
                        if len(hits) >= limit:
                            break
                if len(hits) >= limit:
                    break
            if len(hits) >= limit:
                break
        if hits:
            output = "\n".join(f"{hit['path']}:{hit['line']}: {hit['content']}" for hit in hits)
        else:
            output = f"(未匹配到 `{query}`)"
        return MemoryToolExecution(
            tool_name="memory.search",
            display_name="memory.search",
            command=(
                f"memory.search(query={json.dumps(query, ensure_ascii=False)}, "
                f"limit={limit}, case_sensitive={json.dumps(case_sensitive)})"
            ),
            output_text=output,
            payload={"items": hits, "query": query, "caseSensitive": case_sensitive, "limit": limit},
        )
