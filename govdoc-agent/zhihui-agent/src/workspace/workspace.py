"""单用户工作区：identity / memory / artifacts / assets。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class Workspace:
    def __init__(self, root: Path, user_id: str) -> None:
        self.root = root
        self.user_id = user_id
        self._identity = self.root / "identity.md"
        self._memory = self.root / "memory.md"
        self._artifacts = self.root / "artifacts"
        self._assets = self.root / "assets"
        self._sessions = self.root / "sessions"
        for p in (self._artifacts, self._assets, self._sessions):
            p.mkdir(parents=True, exist_ok=True)
        if not self._identity.exists():
            self._identity.write_text("# 用户身份\n\n（待补充）\n", encoding="utf-8")
        if not self._memory.exists():
            self._memory.write_text("# 记忆\n\n", encoding="utf-8")

    def read_identity(self) -> str:
        return self._identity.read_text(encoding="utf-8") if self._identity.exists() else ""

    def read_memory(self) -> str:
        return self._memory.read_text(encoding="utf-8") if self._memory.exists() else ""

    def update_memory(self, content: str) -> None:
        self._memory.write_text(content, encoding="utf-8")

    def _artifact_path(self, name: str) -> Path:
        safe = name.replace("..", "").lstrip("/")
        return self._artifacts / safe

    def write_artifact(self, name: str, content: str) -> str:
        path = self._artifact_path(name)
        path.write_text(content, encoding="utf-8")
        return str(path.resolve())

    def append_artifact(self, name: str, chunk: str) -> str:
        path = self._artifact_path(name)
        with path.open("a", encoding="utf-8") as f:
            f.write(chunk)
        return str(path.resolve())

    def read_artifact(self, name: str) -> str:
        p = self._artifact_path(name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def list_artifacts(self) -> list[str]:
        return sorted([p.name for p in self._artifacts.iterdir() if p.is_file()])

    def save_asset(self, buffer: bytes, meta: dict[str, Any]) -> str:
        aid = str(uuid.uuid4())
        ext = meta.get("ext") or "bin"
        path = self._assets / f"{aid}.{ext}"
        path.write_bytes(buffer)
        meta_path = self._assets / f"{aid}.meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return aid

    def list_assets(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self._assets.glob("*.meta.json")):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
                m["id"] = p.name.replace(".meta.json", "")
                out.append(m)
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def get_asset(self, asset_id: str) -> tuple[Path | None, dict[str, Any]]:
        metas = list(self._assets.glob(f"{asset_id}.meta.json"))
        if not metas:
            return None, {}
        meta = json.loads(metas[0].read_text(encoding="utf-8"))
        for p in self._assets.iterdir():
            if p.name.startswith(asset_id + ".") and not p.name.endswith(".meta.json"):
                return p, meta
        return None, meta
