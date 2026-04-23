"""
Skill 描述列表 + SKILL.md 上传接口。

- 前缀：/api/agentloop
- GET  /skills：匿名可访问，供首屏渲染 Quick Skill
- GET  /skills/custom：列出当前用户可见的可上传覆盖
- GET  /skills/custom/{name}：读取某个 skill 的原始 SKILL.md 内容
- POST /skills/custom：上传/覆盖单个 SKILL.md（multipart 或 JSON）
- DELETE /skills/custom/{name}：删除覆盖文件，回落到内置 prompt
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..auth import get_current_user
from ..schemas import AgentLoopResponse
from ..skills import skill_descriptors
from ..skills_registry import (
    delete_skill_overlay,
    list_overlays,
    read_skill_markdown,
    save_skill_markdown,
)

router = APIRouter(prefix="/api/agentloop", tags=["agentloop-skills"])


@router.get("/skills", response_model=AgentLoopResponse)
def get_skills():
    return AgentLoopResponse(data=skill_descriptors())


def _overlay_to_dict(overlay) -> dict:
    return {
        "name": overlay.name,
        "display": overlay.display_name or overlay.name,
        "description": overlay.description,
        "tools": overlay.tools or [],
        "temperature": overlay.temperature,
        "model": overlay.model_hint,
        "updatedAt": overlay.mtime,
        "sourcePath": str(overlay.source_path or ""),
    }


@router.get("/skills/custom", response_model=AgentLoopResponse)
def list_custom_skills(current_user=Depends(get_current_user)):
    items = [_overlay_to_dict(overlay) for overlay in list_overlays()]
    return AgentLoopResponse(data={"items": items})


@router.get("/skills/custom/{name}", response_model=AgentLoopResponse)
def read_custom_skill(name: str, current_user=Depends(get_current_user)):
    content = read_skill_markdown(name)
    if content is None:
        raise HTTPException(status_code=404, detail=f"skill '{name}' 没有自定义 SKILL.md")
    return AgentLoopResponse(data={"name": name, "markdown": content})


@router.post("/skills/custom", response_model=AgentLoopResponse)
async def upload_custom_skill(
    current_user=Depends(get_current_user),
    name: str | None = Form(default=None),
    markdown: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    """优先使用上传文件内容；否则读取 markdown 字段。"""
    content = ""
    resolved_name = (name or "").strip().lower()
    if file is not None:
        raw_bytes = await file.read()
        content = raw_bytes.decode("utf-8", errors="replace")
        if not resolved_name:
            stem = (file.filename or "").rsplit(".", 1)[0]
            resolved_name = stem.strip().lower()
    elif markdown is not None:
        content = markdown
    if not content.strip():
        raise HTTPException(status_code=400, detail="SKILL.md 内容为空")
    if not resolved_name:
        raise HTTPException(status_code=400, detail="必须提供 name 或通过文件名推断")
    try:
        path = save_skill_markdown(resolved_name, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentLoopResponse(
        data={
            "name": resolved_name,
            "path": str(path),
            "bytes": len(content.encode("utf-8")),
        }
    )


@router.delete("/skills/custom/{name}", response_model=AgentLoopResponse)
def delete_custom_skill(name: str, current_user=Depends(get_current_user)):
    ok = delete_skill_overlay(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"skill '{name}' 无自定义覆盖或无法删除")
    return AgentLoopResponse(data={"name": name, "deleted": True})
