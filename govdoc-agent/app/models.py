import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class V4Conversation(Base):
    __tablename__ = "v4_conversation"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), default="新对话")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    running_context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    running_context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4ConversationMessage(Base):
    __tablename__ = "v4_conversation_message"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(32))
    skill_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    annotations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4ConversationRun(Base):
    __tablename__ = "v4_conversation_run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    objective: Mapped[str] = mapped_column(Text)
    requested_skill: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created")
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    input_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assistant_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4TaskEvent(Base):
    __tablename__ = "v4_task_event"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    seq_no: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4ConversationArtifact(Base):
    __tablename__ = "v4_conversation_artifact"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workspace_node_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4WorkspaceNode(Base):
    __tablename__ = "v4_workspace_node"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    parent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    owner_user_id: Mapped[str] = mapped_column(String(255), index=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    node_type: Mapped[str] = mapped_column(String(32))
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4WorkspaceVersion(Base):
    __tablename__ = "v4_workspace_version"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    node_id: Mapped[str] = mapped_column(String(64), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_rel_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    annotations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4WorkspaceAttachmentLink(Base):
    __tablename__ = "v4_workspace_attachment_link"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    node_id: Mapped[str] = mapped_column(String(64), index=True)
    attachment_role: Mapped[str] = mapped_column(String(64), default="workspace")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4CompressionSnapshot(Base):
    __tablename__ = "v4_compression_snapshot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    summary: Mapped[str] = mapped_column(Text)
    summary_markdown: Mapped[str] = mapped_column(Text)
    source_message_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stats_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4UserProfile(Base):
    __tablename__ = "v4_user_profile"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    default_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    preferred_skills_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identity_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    memory_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identify_md_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    memory_md_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_session_summary_md_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4DictionaryEntry(Base):
    __tablename__ = "v4_dictionary_entry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    dict_type: Mapped[str] = mapped_column(String(32), index=True)
    word: Mapped[str] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class V4TemplateItem(Base):
    __tablename__ = "v4_template_item"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
