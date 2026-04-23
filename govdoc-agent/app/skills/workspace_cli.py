from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from ..storage import normalize_workspace_path, parse_workspace_file, workspace_abspath, workspace_files_root


def _request_path(value: str | None) -> str:
    raw = str(value or ".").strip()
    if raw in {"", "."}:
        return ""
    return normalize_workspace_path(raw)


def _display_path(value: str) -> str:
    return value or "."


def _clip(value: str, limit: int = 8000) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n..."


def _list_entries(path: Path) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError("路径不存在")
    if path.is_file():
        return [path]
    return sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))


def _relative_to_root(root: Path, path: Path) -> str:
    return normalize_workspace_path(str(path.relative_to(root)))


def _line_slice(text: str, range_arg: Any) -> str:
    if not range_arg:
        return text
    lines = text.splitlines()
    start = 1
    end = len(lines)
    if isinstance(range_arg, dict):
        start = max(int(range_arg.get("start") or 1), 1)
        end = max(int(range_arg.get("end") or len(lines)), start)
    elif isinstance(range_arg, str) and ":" in range_arg:
        left, right = range_arg.split(":", 1)
        if left.strip().isdigit():
            start = max(int(left.strip()), 1)
        if right.strip().isdigit():
            end = max(int(right.strip()), start)
    return "\n".join(lines[start - 1 : end])


@dataclass
class WorkspaceCliExecution:
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
        return {
            "event_type": "cli_exec",
            "status": "completed",
            "title": f"CLI 工具 · {self.display_name}",
            "detail": self.command,
            "detail_html": (
                "<pre class='cli-tool-block'>"
                f"{escape(self.command)}\n\n{escape(_clip(self.output_text, 12000))}"
                "</pre>"
            ),
            "payload": self.tool_message(),
        }


class WorkspaceCliToolset:
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            self._tool_schema(
                "workspace.ls",
                "列出工作区目录内容；当用户询问云盘、文件、目录结构时优先使用。",
                {
                    "path": {"type": "string", "default": ".", "description": "相对于工作区 files/ 的路径。"},
                    "depth": {"type": "integer", "default": 1, "minimum": 1, "maximum": 5},
                },
                [],
            ),
            self._tool_schema(
                "workspace.tree",
                "以 ASCII 树形式查看工作区目录结构。",
                {
                    "path": {"type": "string", "default": ".", "description": "相对于工作区 files/ 的路径。"},
                    "max_depth": {"type": "integer", "default": 3, "minimum": 1, "maximum": 6},
                },
                [],
            ),
            self._tool_schema(
                "workspace.cat",
                "读取工作区文件解析后的纯文本内容。",
                {
                    "path": {"type": "string", "description": "要读取的文件路径。"},
                    "range": {
                        "description": "可选行范围，支持 {start,end} 或 '1:20'。",
                        "anyOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "start": {"type": "integer"},
                                    "end": {"type": "integer"},
                                },
                            },
                        ],
                    },
                    "max_chars": {"type": "integer", "default": 8000, "minimum": 200, "maximum": 20000},
                },
                ["path"],
            ),
            self._tool_schema(
                "workspace.grep",
                "在工作区文件中检索匹配行。",
                {
                    "pattern": {"type": "string", "description": "要搜索的文本或正则。"},
                    "path": {"type": "string", "default": ".", "description": "目录或文件路径。"},
                    "flags": {"type": "string", "default": "-i", "description": "支持 -i。"},
                },
                ["pattern"],
            ),
            self._tool_schema(
                "workspace.stat",
                "查看工作区文件或目录的元信息和摘要。",
                {
                    "path": {"type": "string", "description": "目录或文件路径。"},
                },
                ["path"],
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

    def execute(self, function_name: str, arguments: dict[str, Any], runtime_context: dict[str, Any] | None) -> WorkspaceCliExecution:
        runtime_context = runtime_context or {}
        user_id = runtime_context.get("workspaceUserId")
        if not user_id:
            raise ValueError("缺少 workspaceUserId，上下文无法访问工作区")
        root = workspace_files_root(user_id)

        if function_name == "workspace.ls":
            return self._execute_ls(user_id, root, arguments)
        if function_name == "workspace.tree":
            return self._execute_tree(user_id, root, arguments)
        if function_name == "workspace.cat":
            return self._execute_cat(user_id, root, arguments)
        if function_name == "workspace.grep":
            return self._execute_grep(user_id, root, arguments)
        if function_name == "workspace.stat":
            return self._execute_stat(user_id, root, arguments)
        raise ValueError(f"未知 workspace 工具: {function_name}")

    def _execute_ls(self, user_id: str, root: Path, arguments: dict[str, Any]) -> WorkspaceCliExecution:
        relative = _request_path(arguments.get("path"))
        depth = max(1, min(int(arguments.get("depth") or 1), 5))
        target = workspace_abspath(user_id, relative)
        rows: list[dict[str, Any]] = []

        def visit(path: Path, current_depth: int) -> None:
            for item in _list_entries(path):
                rel = _relative_to_root(root, item)
                rows.append(
                    {
                        "name": item.name,
                        "type": "file" if item.is_file() else "dir",
                        "size": item.stat().st_size if item.is_file() else None,
                        "mtime": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
                        "path": rel,
                        "depth": current_depth,
                    }
                )
                if item.is_dir() and current_depth < depth:
                    visit(item, current_depth + 1)

        visit(target, 1)
        if not rows:
            output = "(空目录)"
        else:
            output = "\n".join(
                f"{'  ' * (item['depth'] - 1)}{'[D]' if item['type'] == 'dir' else '[F]'} {item['path']}"
                for item in rows
            )
        return WorkspaceCliExecution(
            tool_name="workspace.ls",
            display_name="workspace.ls",
            command=f"workspace.ls(path={json.dumps(_display_path(relative), ensure_ascii=False)}, depth={depth})",
            output_text=output,
            payload={"items": rows, "path": _display_path(relative), "depth": depth},
        )

    def _execute_tree(self, user_id: str, root: Path, arguments: dict[str, Any]) -> WorkspaceCliExecution:
        relative = _request_path(arguments.get("path"))
        max_depth = max(1, min(int(arguments.get("max_depth") or 3), 6))
        target = workspace_abspath(user_id, relative)
        lines = [f"{_display_path(relative)}/" if target.is_dir() else _display_path(relative)]

        def walk(path: Path, prefix: str, depth: int) -> None:
            if depth > max_depth or not path.is_dir():
                return
            entries = _list_entries(path)
            for index, item in enumerate(entries):
                branch = "└── " if index == len(entries) - 1 else "├── "
                lines.append(f"{prefix}{branch}{item.name}")
                if item.is_dir():
                    extension = "    " if index == len(entries) - 1 else "│   "
                    walk(item, prefix + extension, depth + 1)

        walk(target, "", 1)
        return WorkspaceCliExecution(
            tool_name="workspace.tree",
            display_name="workspace.tree",
            command=f"workspace.tree(path={json.dumps(_display_path(relative), ensure_ascii=False)}, max_depth={max_depth})",
            output_text="\n".join(lines),
            payload={"tree": "\n".join(lines), "path": _display_path(relative), "maxDepth": max_depth},
        )

    def _execute_cat(self, user_id: str, root: Path, arguments: dict[str, Any]) -> WorkspaceCliExecution:
        relative = _request_path(arguments.get("path"))
        max_chars = max(200, min(int(arguments.get("max_chars") or 8000), 20000))
        parsed = parse_workspace_file(user_id, relative)
        text = _line_slice(parsed["content_text"], arguments.get("range"))
        clipped = _clip(text, max_chars)
        return WorkspaceCliExecution(
            tool_name="workspace.cat",
            display_name="workspace.cat",
            command=(
                f"workspace.cat(path={json.dumps(_display_path(relative), ensure_ascii=False)}, "
                f"range={json.dumps(arguments.get('range'), ensure_ascii=False)}, max_chars={max_chars})"
            ),
            output_text=clipped,
            payload={
                "path": _display_path(relative),
                "range": arguments.get("range"),
                "maxChars": max_chars,
                "parser": parsed["meta"].get("parser"),
            },
        )

    def _execute_grep(self, user_id: str, root: Path, arguments: dict[str, Any]) -> WorkspaceCliExecution:
        relative = _request_path(arguments.get("path"))
        flags = str(arguments.get("flags") or "-i")
        pattern = str(arguments.get("pattern") or "").strip()
        if not pattern:
            raise ValueError("workspace.grep 缺少 pattern")
        regex_flags = re.IGNORECASE if "-i" in flags else 0
        regex = re.compile(pattern, regex_flags)
        target = workspace_abspath(user_id, relative)
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        hits: list[dict[str, Any]] = []
        for item in candidates:
            if not item.is_file():
                continue
            rel = _relative_to_root(root, item)
            parsed = parse_workspace_file(user_id, rel)
            for line_no, line in enumerate(parsed["content_text"].splitlines(), start=1):
                if regex.search(line):
                    hits.append({"path": rel, "line": line_no, "text": line.strip()})
                    if len(hits) >= 80:
                        break
            if len(hits) >= 80:
                break
        output = "\n".join(f"{item['path']}:{item['line']}: {item['text']}" for item in hits) or "(无匹配结果)"
        return WorkspaceCliExecution(
            tool_name="workspace.grep",
            display_name="workspace.grep",
            command=(
                f"workspace.grep(pattern={json.dumps(pattern, ensure_ascii=False)}, "
                f"path={json.dumps(_display_path(relative), ensure_ascii=False)}, flags={json.dumps(flags)})"
            ),
            output_text=output,
            payload={"hits": hits, "path": _display_path(relative), "flags": flags, "pattern": pattern},
        )

    def _execute_stat(self, user_id: str, root: Path, arguments: dict[str, Any]) -> WorkspaceCliExecution:
        relative = _request_path(arguments.get("path"))
        target = workspace_abspath(user_id, relative)
        if not target.exists():
            raise FileNotFoundError("路径不存在")
        stat = target.stat()
        payload: dict[str, Any] = {
            "path": _display_path(relative),
            "type": "file" if target.is_file() else "dir",
            "size": stat.st_size if target.is_file() else None,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "name": target.name or ".",
        }
        output_lines = [
            f"path: {_display_path(relative)}",
            f"type: {payload['type']}",
            f"mtime: {payload['mtime']}",
        ]
        if target.is_file():
            parsed = parse_workspace_file(user_id, relative)
            preview = _clip(parsed["content_text"], 600)
            payload["parser"] = parsed["meta"].get("parser")
            payload["preview"] = preview
            payload["size"] = stat.st_size
            output_lines.extend(
                [
                    f"size: {stat.st_size}",
                    f"parser: {payload['parser']}",
                    "",
                    preview,
                ]
            )
        else:
            children = _list_entries(target)
            payload["childrenCount"] = len(children)
            output_lines.append(f"children: {len(children)}")
        return WorkspaceCliExecution(
            tool_name="workspace.stat",
            display_name="workspace.stat",
            command=f"workspace.stat(path={json.dumps(_display_path(relative), ensure_ascii=False)})",
            output_text="\n".join(output_lines),
            payload=payload,
        )
