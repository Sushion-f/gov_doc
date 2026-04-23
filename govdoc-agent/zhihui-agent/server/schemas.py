"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    type: Literal["chat"] = "chat"
    user_message: str
    user_id: str
    session_id: str | None = None
    skill_ids: list[str] | None = None


class TodoItem(BaseModel):
    id: str
    description: str = ""
    agent_id: str = ""
    agent_name: str = ""
    status: str = "pending"


class TodoList(BaseModel):
    items: list[TodoItem] = Field(default_factory=list)


class ArtifactMeta(BaseModel):
    name: str
    path: str | None = None
    size: int | None = None


class AssetMeta(BaseModel):
    id: str
    ext: str | None = None
    label: str | None = None


class OrchestratorEventSchema(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
