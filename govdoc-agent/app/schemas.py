"""
Pydantic 请求/响应模型（AgentLoop API）。

- AgentLoopResponse：统一 JSON 外壳 code/message/data，路由层广泛使用。
- ConversationRunRequest、Workspace*Request 等与前端字段名对齐（snake_case JSON）。
- 所有模型都继承自 BaseModel，使用 Pydantic V2 语法。
"""

from datetime import datetime  # 日期时间类型
from typing import Any, Literal  # 类型注解

from pydantic import BaseModel, Field  # Pydantic 基础类和字段配置


class AgentLoopResponse(BaseModel):
    """统一 API 响应模型。"""
    code: int = 0  # 响应代码，0 表示成功
    message: str = "ok"  # 响应消息
    data: Any = None  # 响应数据


class SkillDescriptor(BaseModel):
    """技能描述符模型。"""
    key: str  # 技能唯一标识
    title: str  # 技能标题
    summary: str  # 技能摘要
    examples: list[str] = Field(default_factory=list)  # 使用示例列表


class TaskPacket(BaseModel):
    """任务数据包模型。"""
    task_id: str  # 任务 ID
    conversation_id: str  # 会话 ID
    parent_task_id: str | None = None  # 父任务 ID（用于子任务）
    objective: str  # 任务目标
    skill_name: str  # 技能名称
    scope: str | None = None  # 任务范围
    repo: str | None = None  # 代码仓库
    branch_policy: str | None = None  # 分支策略
    acceptance_tests: list[str] = Field(default_factory=list)  # 验收测试
    commit_policy: str | None = None  # 提交策略
    team_id: str | None = None  # 团队 ID
    subtask_role: str | None = None  # 子任务角色
    input_payload: dict[str, Any] = Field(default_factory=dict)  # 输入负载
    attachments: list[dict[str, Any]] = Field(default_factory=list)  # 附件列表
    acceptance_criteria: list[str] = Field(default_factory=list)  # 验收标准
    reporting_contract: str  # 报告契约
    escalation_policy: str  # 升级策略
    user_memory_refs: list[str] = Field(default_factory=list)  # 用户记忆引用
    resume_token: str | None = None  # 恢复令牌
    prompt_menu_contract: dict[str, Any] = Field(default_factory=dict)  # 提示菜单契约
    source_state: str | None = None  # 源状态


class TaskEvent(BaseModel):
    """任务事件模型（用于 SSE 事件流）。"""
    id: str  # 事件 ID
    run_id: str  # 运行 ID
    task_id: str  # 任务 ID
    parent_task_id: str | None = None  # 父任务 ID
    seq_no: int  # 事件序号
    event_type: Literal[
        "created",
        "running",
        "tool_call",
        "waiting_user",
        "completed",
        "failed",
    ]  # 事件类型
    status: str  # 状态
    title: str  # 事件标题
    detail: str | None = None  # 事件详情
    detail_html: str | None = None  # 详情 HTML 格式
    payload: dict[str, Any] = Field(default_factory=dict)  # 负载
    prompt_menu: dict[str, Any] = Field(default_factory=dict)  # 提示菜单
    error_detail: str | None = None  # 错误详情
    created_at: datetime  # 创建时间


class WorkspaceArtifactRef(BaseModel):
    """工作区产物引用模型。"""
    id: str  # 产物 ID
    node_id: str | None = None  # 节点 ID
    artifact_type: str  # 产物类型
    title: str  # 产物标题
    summary: str | None = None  # 产物摘要
    content_html: str | None = None  # 内容 HTML
    version_no: int | None = None  # 版本号
    source_run_id: str | None = None  # 来源运行 ID


class SkillAdapterResult(BaseModel):
    """技能适配器结果模型。"""
    normalized_result: dict[str, Any] = Field(default_factory=dict)  # 标准化结果
    render_blocks: list[dict[str, Any]] = Field(default_factory=list)  # 渲染块
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)  # 产物引用
    editor_annotations: list[dict[str, Any]] = Field(default_factory=list)  # 编辑器批注
    retryable: bool = False  # 是否可重试
    source_state: str = "model_success"  # 源状态
    error_detail: str | None = None  # 错误详情
    prompt_menu: dict[str, Any] = Field(default_factory=dict)  # 提示菜单


class CompressionSnapshot(BaseModel):
    """压缩快照模型。"""
    id: str  # 快照 ID
    summary: str  # 摘要
    summary_markdown: str  # Markdown 格式摘要
    stats: dict[str, Any] = Field(default_factory=dict)  # 统计信息
    created_at: datetime  # 创建时间


class UserIdentityProfile(BaseModel):
    """用户身份画像模型。"""
    default_model: str | None = None  # 默认模型
    preferred_skills: list[str] = Field(default_factory=list)  # 偏好技能
    recommendation_summary: str | None = None  # 推荐摘要
    identity: dict[str, Any] = Field(default_factory=dict)  # 身份信息
    memory: dict[str, Any] = Field(default_factory=dict)  # 记忆信息
    identify_markdown: str = ""  # 身份 Markdown
    memory_markdown: str = ""  # 记忆 Markdown
    session_summary_markdown: str = ""  # 会话摘要 Markdown


class ConversationCreateRequest(BaseModel):
    """创建对话请求模型。"""
    title: str | None = None  # 对话标题


class ConversationRenameRequest(BaseModel):
    """重命名对话请求模型。"""
    title: str | None = None  # 新标题
    pinned: bool | None = None  # 是否置顶


class ConversationRunRequest(BaseModel):
    """运行对话请求模型。"""
    content: str  # 消息内容
    model: str | None = None  # 模型名称
    skill: str | None = None  # 技能名称
    attachments: list[dict[str, Any]] = Field(default_factory=list)  # 附件列表
    resume_from_waiting: bool = False  # 是否从等待状态恢复
    selected_option: str | None = None  # 选择的选项
    prompt_menu_input: str | None = None  # 提示菜单输入


class WorkspaceFolderCreateRequest(BaseModel):
    """创建工作区文件夹请求模型。"""
    name: str  # 文件夹名称
    parent_id: str | None = None  # 父文件夹 ID


class WorkspaceDocumentCreateRequest(BaseModel):
    """创建工作区文档请求模型。"""
    name: str  # 文档名称
    parent_id: str | None = None  # 父文件夹 ID
    content_html: str | None = None  # 内容 HTML
    content_text: str | None = None  # 内容文本
    source: str | None = "manual"  # 来源：manual/conversation


class WorkspaceDocumentUpdateRequest(BaseModel):
    """更新工作区文档请求模型。"""
    title: str | None = None  # 文档标题
    content_html: str | None = None  # 内容 HTML
    content_text: str | None = None  # 内容文本
    annotations: list[dict[str, Any]] = Field(default_factory=list)  # 批注列表


class WorkspaceNodeRenameRequest(BaseModel):
    """重命名工作区节点请求模型。"""
    name: str  # 新名称


class WorkspaceNodeMoveRequest(BaseModel):
    """移动工作区节点请求模型。"""
    parent_id: str | None = None  # 新的父文件夹 ID


class SettingsProfileUpdateRequest(BaseModel):
    """更新设置配置文件请求模型。"""
    default_model: str | None = None  # 默认模型
    preferred_skills: list[str] = Field(default_factory=list)  # 偏好技能
    recommendation_summary: str | None = None  # 推荐摘要


class MemoryUpdateRequest(BaseModel):
    """更新记忆请求模型。"""
    identity: dict[str, Any] = Field(default_factory=dict)  # 身份信息
    memory: dict[str, Any] = Field(default_factory=dict)  # 记忆信息
    identify_markdown: str | None = None  # 身份 Markdown
    memory_markdown: str | None = None  # 记忆 Markdown


class DictionaryEntryCreateRequest(BaseModel):
    """创建词库条目请求模型。"""
    dict_type: Literal["whiteList", "blackList"]  # 词库类型
    word: str  # 词汇
    notes: str | None = None  # 备注
