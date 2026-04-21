"""
SQLAlchemy 数据库表模型定义。

所有模型类都继承自 db.Base，使用 SQLAlchemy 2.0 的 Mapped 类型注解。
每个模型对应数据库中的一张表，主要包括对话、工作区、用户配置等相关表。
"""

import uuid  # 用于生成 UUID 字符串
from datetime import datetime  # 日期时间类型
from typing import Optional  # 可选类型注解

from sqlalchemy import Boolean, DateTime, Integer, String, Text  # SQLAlchemy 列类型
from sqlalchemy.orm import Mapped, mapped_column  # SQLAlchemy 2.0 列映射

from .db import Base  # ORM 模型基类


def uuid_str() -> str:
    """生成 UUID 字符串，用于主键。"""
    return str(uuid.uuid4())


class V4Conversation(Base):
    """对话会话表。存储用户与 Agent 的一次完整对话会话。"""
    __tablename__ = "v4_conversation"  # 表名

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 会话 ID（主键）
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID（建立索引加速查询）
    title: Mapped[str] = mapped_column(String(255), default="新对话")  # 会话标题
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否置顶
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已删除（软删除）
    running_context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 运行上下文摘要
    running_context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 运行上下文 JSON
    last_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 最近一次运行的 ID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 更新时间
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 最后消息时间


class V4ConversationMessage(Base):
    """对话消息表。存储对话中的每条消息，包括用户消息和助手回复。"""
    __tablename__ = "v4_conversation_message"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 消息 ID（主键）
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属会话 ID
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 所属运行 ID
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    role: Mapped[str] = mapped_column(String(32))  # 角色：user/assistant/system
    skill_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 关联的技能名称
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 使用的模型名称
    content: Mapped[str] = mapped_column(Text)  # 消息内容（纯文本）
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 消息内容（HTML 格式）
    annotations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 批注 JSON
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 元数据 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间


class V4ConversationRun(Base):
    """对话运行记录表。每次用户发送消息并触发 Agent 执行，记录为一条 Run。"""
    __tablename__ = "v4_conversation_run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 运行 ID（主键）
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属会话 ID
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    task_id: Mapped[str] = mapped_column(String(64), index=True)  # 任务 ID
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 父任务 ID（用于子任务）
    objective: Mapped[str] = mapped_column(Text)  # 任务目标描述
    requested_skill: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 请求的技能
    status: Mapped[str] = mapped_column(String(32), default="created")  # 状态：created/running/completed/failed
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 使用的模型
    input_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 输入负载 JSON
    context_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 上下文快照 JSON
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 结果摘要
    assistant_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 助手消息 ID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 更新时间


class V4TaskEvent(Base):
    """任务事件表。用于 SSE 事件流推送，实时通知前端任务状态变化。"""
    __tablename__ = "v4_task_event"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 事件 ID（主键）
    run_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属运行 ID
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属会话 ID
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    task_id: Mapped[str] = mapped_column(String(64), index=True)  # 任务 ID
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 父任务 ID
    seq_no: Mapped[int] = mapped_column(Integer)  # 事件序号（递增，用于排序）
    event_type: Mapped[str] = mapped_column(String(64))  # 事件类型：created/running/tool_call/waiting_user/completed/failed
    status: Mapped[str] = mapped_column(String(32))  # 状态
    title: Mapped[str] = mapped_column(String(255))  # 事件标题
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 事件详情
    detail_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 详情 HTML 格式
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 负载 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间


class V4ConversationArtifact(Base):
    """会话产物表。存储 Agent 生成的内容产物（如文档、报告等）。"""
    __tablename__ = "v4_conversation_artifact"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 产物 ID（主键）
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属会话 ID
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 所属运行 ID
    message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 关联消息 ID
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    artifact_type: Mapped[str] = mapped_column(String(64))  # 产物类型
    title: Mapped[str] = mapped_column(String(255))  # 产物标题
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 产物摘要
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 产物内容 HTML
    workspace_node_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 工作区节点 ID
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 元数据 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间


class V4WorkspaceNode(Base):
    """工作区节点表（云盘）。存储文档和文件夹的元数据。"""
    __tablename__ = "v4_workspace_node"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 节点 ID（主键）
    parent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 父文件夹 ID
    owner_user_id: Mapped[str] = mapped_column(String(255), index=True)  # 所有者用户 ID
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # 所有者名称
    node_type: Mapped[str] = mapped_column(String(32))  # 节点类型：folder/document
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 来源：manual/conversation
    name: Mapped[str] = mapped_column(String(255))  # 节点名称
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 摘要/描述
    relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 相对路径
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已删除
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 更新时间
    last_opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 最后打开时间


class V4WorkspaceVersion(Base):
    """工作区文档版本表。每次保存文档都会创建新版本。"""
    __tablename__ = "v4_workspace_version"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 版本 ID（主键）
    node_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属节点 ID
    version_no: Mapped[int] = mapped_column(Integer, default=1)  # 版本号
    title: Mapped[str] = mapped_column(String(255))  # 文档标题
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 内容纯文本
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 内容 HTML
    file_rel_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 文件相对路径
    annotations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 批注 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间


class V4WorkspaceAttachmentLink(Base):
    """工作区附件关联表。建立附件与对话/消息的关联关系。"""
    __tablename__ = "v4_workspace_attachment_link"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 关联 ID（主键）
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 关联会话 ID
    message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # 关联消息 ID
    node_id: Mapped[str] = mapped_column(String(64), index=True)  # 工作区节点 ID
    attachment_role: Mapped[str] = mapped_column(String(64), default="workspace")  # 附件角色
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间


class V4CompressionSnapshot(Base):
    """上下文压缩快照表。保存压缩后的对话摘要，用于长对话的记忆压缩。"""
    __tablename__ = "v4_compression_snapshot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 快照 ID（主键）
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属会话 ID
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    summary: Mapped[str] = mapped_column(Text)  # 摘要文本
    summary_markdown: Mapped[str] = mapped_column(Text)  # Markdown 格式摘要
    source_message_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 来源消息 ID JSON
    stats_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 统计信息 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间


class V4UserProfile(Base):
    """用户画像表。存储用户的偏好设置、记忆和身份信息。"""
    __tablename__ = "v4_user_profile"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 画像 ID（主键）
    user_id: Mapped[str] = mapped_column(String(255), index=True, unique=True)  # 用户 ID（唯一索引）
    default_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 默认模型
    preferred_skills_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 偏好技能 JSON
    recommendation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 推荐摘要
    identity_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 身份信息 JSON
    memory_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 记忆信息 JSON
    identify_md_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 身份 Markdown 文件路径
    memory_md_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 记忆 Markdown 文件路径
    last_session_summary_md_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # 最近会话摘要 Markdown 文件路径
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 更新时间


class V4DictionaryEntry(Base):
    """词库条目表。存储用户的自定义词汇（白名单/黑名单）。"""
    __tablename__ = "v4_dictionary_entry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 条目 ID（主键）
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    dict_type: Mapped[str] = mapped_column(String(32), index=True)  # 词库类型：whiteList/blackList
    word: Mapped[str] = mapped_column(String(255))  # 词汇
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 备注
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已删除
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 更新时间


class V4TemplateItem(Base):
    """模板文件表。存储用户上传的模板文件。"""
    __tablename__ = "v4_template_item"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)  # 模板 ID（主键）
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # 用户 ID
    title: Mapped[str] = mapped_column(String(255))  # 模板标题
    document_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 文档类型
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # 文件名
    relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 相对路径
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已删除
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 更新时间
