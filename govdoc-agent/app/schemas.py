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
        "message_created",
        "message_delta",
        "message_final",
        "planner_reasoning_delta",
        "planner_plan",
        "agent_invoke",
        "skill_invoke",
        "tool_call",
        "cli_exec",
        "search",
        "context_usage",
        "context_compacted",
        "artifact_created",
        "artifact_updated",
        "waiting_user",
        "completed",
        "error",
        "aborted",
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


# ---------------------------------------------------------------------------
# Assistant Content Block 协议（对齐 Claude Agent SDK 的 content[] block 设计）。
# assistant 消息的权威数据源是 content_blocks_json，由扁平 tool-call loop 驱动。
# ---------------------------------------------------------------------------


class BaseContentBlock(BaseModel):
    """所有 assistant 内容 block 的公共头。子类通过 type 字段判别。"""

    id: str | None = None
    created_at: datetime | None = None


class ThinkingBlock(BaseContentBlock):
    type: Literal["thinking"] = "thinking"
    thinking: str
    signature: str | None = None


class TextBlock(BaseContentBlock):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseContentBlock):
    """模型发起的一次工具调用（dispatch_sub_agent / workspace.* / memory.* 等）。"""

    type: Literal["tool_use"] = "tool_use"
    tool_use_id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    status: Literal["running", "ok", "error"] = "running"


class ToolResultInnerText(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolResultInnerArtifactRef(BaseModel):
    type: Literal["artifact_ref"] = "artifact_ref"
    artifact_id: str
    title: str | None = None
    version: int | None = None
    workspace_node_id: str | None = None


class ToolResultInnerError(BaseModel):
    type: Literal["error"] = "error"
    message: str
    code: str | None = None


class ToolResultBlock(BaseContentBlock):
    """某个 tool_use 的返回值，content 只允许嵌套 text/artifact_ref/error。"""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    is_error: bool = False
    content: list[dict[str, Any]] = Field(default_factory=list)


class ArtifactRefBlock(BaseContentBlock):
    type: Literal["artifact_ref"] = "artifact_ref"
    artifact_id: str
    title: str
    version: int | None = None
    workspace_node_id: str | None = None
    summary: str | None = None


class TodoListItem(BaseModel):
    id: str
    text: str
    status: Literal["pending", "in_progress", "completed", "cancelled"] = "pending"
    priority: Literal["low", "normal", "high"] | None = None


class TodoListBlock(BaseContentBlock):
    type: Literal["todo_list"] = "todo_list"
    items: list[TodoListItem] = Field(default_factory=list)


class WaitingUserBlock(BaseContentBlock):
    type: Literal["waiting_user"] = "waiting_user"
    prompt_menu: dict[str, Any] = Field(default_factory=dict)


class ContextNoticeBlock(BaseContentBlock):
    type: Literal["context_notice"] = "context_notice"
    kind: Literal["compact", "usage"] = "usage"
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    summary: str | None = None


ASSISTANT_CONTENT_BLOCK_TYPES: tuple[str, ...] = (
    "thinking",
    "text",
    "tool_use",
    "tool_result",
    "artifact_ref",
    "todo_list",
    "waiting_user",
    "context_notice",
)


# 注意：Pydantic v2 discriminated union 写法对 schema 输出更干净；
# 这里仅作为内部验证工具，默认只在 build/parse 边界调用。
AssistantContentBlock = (
    ThinkingBlock
    | TextBlock
    | ToolUseBlock
    | ToolResultBlock
    | ArtifactRefBlock
    | TodoListBlock
    | WaitingUserBlock
    | ContextNoticeBlock
)


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


class ArtifactRefPayload(BaseModel):
    id: str | None = None
    artifactType: str | None = None
    title: str | None = None
    summary: str | None = None
    contentHtml: str | None = None
    workspaceNodeId: str | None = None
    relativePath: str | None = None
    versionPath: str | None = None
    sourceSkill: str | None = None
    sourceState: str | None = None
    status: str | None = None
    errorDetail: str | None = None


class OperationContextPayload(BaseModel):
    intentType: str | None = None
    rewriteMode: str | None = None
    baseUserGoal: str | None = None
    latestAssistantSummary: str | None = None
    latestArtifactRefs: list[ArtifactRefPayload] = Field(default_factory=list)


class ConversationRunRequest(BaseModel):
    content: str
    model: str | None = None
    skill: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    operation_context: OperationContextPayload | None = None
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
