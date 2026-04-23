"""会话 JSONL：workspaces/{user_id}/sessions/{session_id}.jsonl"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root

    def _path(self, user_id: str, session_id: str) -> Path:
        d = self._root / "workspaces" / user_id / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{session_id}.jsonl"

    def load(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        p = self._path(user_id, session_id)
        if not p.exists():
            return []
        lines: list[dict[str, Any]] = []
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return lines

    def append(self, user_id: str, session_id: str, user_msg: dict, assistant_msg: dict) -> None:
        p = self._path(user_id, session_id)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(user_msg, ensure_ascii=False) + "\n")
            f.write(json.dumps(assistant_msg, ensure_ascii=False) + "\n")

    def list_sessions(self, user_id: str) -> list[str]:
        d = self._root / "workspaces" / user_id / "sessions"
        if not d.is_dir():
            return []
        return sorted([p.stem for p in d.glob("*.jsonl")])
