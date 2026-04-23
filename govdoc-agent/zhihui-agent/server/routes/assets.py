"""素材上传与下载。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse


def create_assets_router(data_root: Path) -> APIRouter:
    from workspace.registry import WorkspaceRegistry

    reg = WorkspaceRegistry(data_root)
    router = APIRouter(prefix="/assets", tags=["assets"])

    @router.post("/upload")
    async def upload(user_id: Annotated[str, Query()], file: UploadFile = File(...)):
        ws = reg.get(user_id)
        buf = await file.read()
        aid = ws.save_asset(
            buf,
            {"ext": (file.filename or "bin").rsplit(".", 1)[-1][:8], "label": file.filename},
        )
        return {"id": aid}

    @router.get("")
    def list_assets(user_id: Annotated[str, Query()]):
        ws = reg.get(user_id)
        return {"items": ws.list_assets()}

    @router.get("/{asset_id}")
    def download(asset_id: str, user_id: Annotated[str, Query()]):
        ws = reg.get(user_id)
        path, meta = ws.get_asset(asset_id)
        if path is None or not path.exists():
            raise HTTPException(404, "not found")
        return FileResponse(path, filename=meta.get("label") or path.name)

    return router
