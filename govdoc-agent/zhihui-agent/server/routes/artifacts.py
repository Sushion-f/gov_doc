"""artifacts CRUD（按 user_id 隔离）。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse


def create_artifacts_router(data_root: Path) -> APIRouter:
    from workspace.registry import WorkspaceRegistry

    reg = WorkspaceRegistry(data_root)
    router = APIRouter(prefix="/artifacts", tags=["artifacts"])

    @router.get("")
    def list_artifacts(user_id: Annotated[str, Query()]):
        ws = reg.get(user_id)
        return {"items": [{"name": n} for n in ws.list_artifacts()]}

    @router.get("/{name}")
    def get_artifact(name: str, user_id: Annotated[str, Query()]):
        ws = reg.get(user_id)
        text = ws.read_artifact(name)
        if not text and name not in ws.list_artifacts():
            raise HTTPException(404, "not found")
        return PlainTextResponse(text)

    @router.put("/{name}")
    async def put_artifact(name: str, user_id: Annotated[str, Query()], body: UploadFile | None = None):
        ws = reg.get(user_id)
        raw = (await body.read()) if body else b""
        ws.write_artifact(name, raw.decode("utf-8", errors="replace"))
        return {"ok": True}

    @router.delete("/{name}")
    def delete_artifact(name: str, user_id: Annotated[str, Query()]):
        p = reg.get(user_id)._artifact_path(name)  # noqa: SLF001
        if p.exists():
            p.unlink()
        return {"ok": True}

    return router
