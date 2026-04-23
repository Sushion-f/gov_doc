"""内置工具：file_* / memory_update / todo_write。"""

from __future__ import annotations

import json
from typing import Any

from tool.registry import ToolContext, ToolRegistry, ToolResult


def _emit_artifact(ctx: ToolContext, event_type: str, **kwargs: Any) -> None:
    ctx.event_bus.publish({"type": event_type, **kwargs})  # type: ignore[arg-type]


def file_write(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    name = str(inp.get("name") or inp.get("filename") or "output.md")
    content = str(inp.get("content") or "")
    mode = str(inp.get("mode") or "overwrite")
    if mode == "append":
        path = ctx.workspace.append_artifact(name, content)
    else:
        _emit_artifact(ctx, "artifact_open", filename=name, mode="streaming")
        path = ctx.workspace.write_artifact(name, content)
    _emit_artifact(ctx, "artifact_done", filename=name, path=path, editable=True)
    return ToolResult(ok=True, output=path, data={"path": path})


def file_append(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    name = str(inp.get("name") or inp.get("filename") or "output.md")
    chunk = str(inp.get("chunk") or inp.get("content") or "")
    path = ctx.workspace.append_artifact(name, chunk)
    _emit_artifact(ctx, "artifact_delta", filename=name, chunk=chunk)
    return ToolResult(ok=True, output=path, data={"path": path})


def file_read(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    name = str(inp.get("name") or inp.get("filename") or "")
    if not name:
        return ToolResult(ok=False, error="missing name")
    text = ctx.workspace.read_artifact(name)
    return ToolResult(ok=True, output=text)


def memory_update(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    content = str(inp.get("content") or "")
    if content:
        ctx.workspace.update_memory(content)
    return ToolResult(ok=True, output="memory updated")


def todo_write(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    session = ctx.session_id or "default"
    name = f"todo_{session}.json"
    data = inp.get("items") or inp.get("todos") or []
    path = ctx.workspace.write_artifact(name, json.dumps(data, ensure_ascii=False, indent=2))
    return ToolResult(ok=True, output=path, data={"path": path})


def docx_render(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    # 占位：真实环境可接 pandoc / python-docx
    return ToolResult(ok=False, error="docx_render not implemented", data=inp)


def similarity_check(inp: dict[str, Any], ctx: ToolContext) -> ToolResult:
    return ToolResult(ok=True, output="0.0", data={"score": 0.0, "note": "stub"})


def _fn(name: str, desc: str, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required or list(props.keys()),
            },
        },
    }


def register_builtin_tools(reg: ToolRegistry) -> None:
    reg.register(
        "file_write",
        file_write,
        _fn(
            "file_write",
            "写入或覆盖 artifacts 下文件；mode=append 时等价于追加开头块",
            {
                "name": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "description": "overwrite | append"},
            },
            ["name", "content"],
        ),
    )
    reg.register(
        "file_append",
        file_append,
        _fn(
            "file_append",
            "向 artifacts 文件追加一段文本，并推送 artifact_delta",
            {"name": {"type": "string"}, "chunk": {"type": "string"}},
            ["name", "chunk"],
        ),
    )
    reg.register(
        "file_read",
        file_read,
        _fn("file_read", "读取 artifacts 文件", {"name": {"type": "string"}}, ["name"]),
    )
    reg.register(
        "memory_update",
        memory_update,
        _fn("memory_update", "覆盖写入 memory.md", {"content": {"type": "string"}}, ["content"]),
    )
    reg.register(
        "todo_write",
        todo_write,
        _fn(
            "todo_write",
            "持久化 todo 列表到 artifacts",
            {"items": {"type": "array"}},
            ["items"],
        ),
    )
    reg.register(
        "docx_render",
        docx_render,
        _fn("docx_render", "渲染 docx（占位）", {"source": {"type": "string"}}, ["source"]),
    )
    reg.register(
        "similarity_check",
        similarity_check,
        _fn("similarity_check", "查重（占位）", {"text": {"type": "string"}}, ["text"]),
    )
