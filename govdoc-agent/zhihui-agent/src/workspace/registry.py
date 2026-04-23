"""按 user_id 懒加载 Workspace。"""

from __future__ import annotations

from pathlib import Path

from .workspace import Workspace


class WorkspaceRegistry:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self._cache: dict[str, Workspace] = {}

    def _user_root(self, user_id: str) -> Path:
        root = self.data_root / "workspaces" / user_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get(self, user_id: str) -> Workspace:
        if user_id not in self._cache:
            self._cache[user_id] = Workspace(self._user_root(user_id), user_id)
        return self._cache[user_id]
