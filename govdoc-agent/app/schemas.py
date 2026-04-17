"""
Pydantic 请求/响应模型（AgentLoop API）。

- AgentLoopResponse：统一 JSON 外壳 code/message/data，路由层广泛使用。
- ConversationRunRequest、Workspace*Request 等与前端字段名对齐（snake_case JSON）。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentLoopResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None


class SkillDescriptor(BaseModel):
    key: str
    title: str
    summary: str
    examples: list[str] = Field(default_factory=list)


class TaskPacket(BaseModel):
    task_id: str
    conversation_id: str
    parent_task_id: str | None = None
    objective: str
    skill_name: str
    scope: str | None = None
    repo: str | None = None
    branch_policy: str | None = None
    acceptance_tests: list[str] = Field(default_factory=list)
    commit_policy: str | None = None
    team_id: str | None = None
    subtask_role: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    reporting_contract: str
    escalation_policy: str
    user_memory_refs: list[str] = Field(default_factory=list)
    resume_token: str | None = None
    prompt_menu_contract: dict[str, Any] = Field(default_factory=dict)
    source_state: str | None = None


class TaskEvent(BaseModel):
    id: str
    run_id: str
    task_id: str
    parent_task_id: str | None = None
    seq_no: int
    event_type: Literal[
        "created",
        "running",
        "tool_call",
        "waiting_user",
        "completed",
        "failed",
    ]
    status: str
    title: str
    detail: str | None = None
    detail_html: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    prompt_menu: dict[str, Any] = Field(default_factory=dict)
    error_detail: str | None = None
    created_at: datetime


class WorkspaceArtifactRef(BaseModel):
    id: str
    node_id: str | None = None
    artifact_type: str
    title: str
    summary: str | None = None
    content_html: str | None = None
    version_no: int | None = None
    source_run_id: str | None = None


class SkillAdapterResult(BaseModel):
    normalized_result: dict[str, Any] = Field(default_factory=dict)
    render_blocks: list[dict[str, Any]] = Field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    editor_annotations: list[dict[str, Any]] = Field(default_factory=list)
    retryable: bool = False
    source_state: str = "model_success"
    error_detail: str | None = None
    prompt_menu: dict[str, Any] = Field(default_factory=dict)


class CompressionSnapshot(BaseModel):
    id: str
    summary: str
    summary_markdown: str
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class UserIdentityProfile(BaseModel):
    default_model: str | None = None
    preferred_skills: list[str] = Field(default_factory=list)
    recommendation_summary: str | None = None
    identity: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    identify_markdown: str = ""
    memory_markdown: str = ""
    session_summary_markdown: str = ""


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationRenameRequest(BaseModel):
    title: str | None = None
    pinned: bool | None = None


class ConversationRunRequest(BaseModel):
    content: str
    model: str | None = None
    skill: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    resume_from_waiting: bool = False
    selected_option: str | None = None
    prompt_menu_input: str | None = None


class WorkspaceFolderCreateRequest(BaseModel):
    name: str
    parent_id: str | None = None


class WorkspaceDocumentCreateRequest(BaseModel):
    name: str
    parent_id: str | None = None
    content_html: str | None = None
    content_text: str | None = None
    source: str | None = "manual"


class WorkspaceDocumentUpdateRequest(BaseModel):
    title: str | None = None
    content_html: str | None = None
    content_text: str | None = None
    annotations: list[dict[str, Any]] = Field(default_factory=list)


class WorkspaceNodeRenameRequest(BaseModel):
    name: str


class WorkspaceNodeMoveRequest(BaseModel):
    parent_id: str | None = None


class SettingsProfileUpdateRequest(BaseModel):
    default_model: str | None = None
    preferred_skills: list[str] = Field(default_factory=list)
    recommendation_summary: str | None = None


class MemoryUpdateRequest(BaseModel):
    identity: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    identify_markdown: str | None = None
    memory_markdown: str | None = None


class DictionaryEntryCreateRequest(BaseModel):
    dict_type: Literal["whiteList", "blackList"]
    word: str
    notes: str | None = None

