"""
用户工作区（云盘）：文档/文件夹 CRUD、树、上传、下载、发送到会话。

- 前缀：/api/agentloop/workspace
- 列表视图 query：view=recent|mine|ai，用于筛选来源
- 文档版本通过 V4WorkspaceVersion 追加；下载返回最新版本 HTML 文件
"""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import V4Conversation, V4WorkspaceAttachmentLink, V4WorkspaceNode, V4WorkspaceVersion
from ..schemas import (
    AgentLoopResponse,
    WorkspaceDocumentCreateRequest,
    WorkspaceDocumentUpdateRequest,
    WorkspaceFolderCreateRequest,
    WorkspaceNodeMoveRequest,
    WorkspaceNodeRenameRequest,
)
from ..file_parser import parse_uploaded_file
from ..storage import user_root, write_workspace_version

router = APIRouter(prefix="/api/agentloop/workspace", tags=["agentloop-workspace"])


def _node_or_404(db: Session, node_id: str, user_id: str) -> V4WorkspaceNode:
    node = db.execute(
        select(V4WorkspaceNode).where(
            V4WorkspaceNode.id == node_id,
            V4WorkspaceNode.owner_user_id == user_id,
            V4WorkspaceNode.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="节点不存在")
    return node


def _latest_versions(db: Session, node_ids: list[str]):
    if not node_ids:
        return {}
    versions = db.execute(
        select(V4WorkspaceVersion)
        .where(V4WorkspaceVersion.node_id.in_(node_ids))
        .order_by(V4WorkspaceVersion.created_at.desc())
    ).scalars().all()
    result = {}
    for version in versions:
        result.setdefault(version.node_id, version)
    return result


@router.get("", response_model=AgentLoopResponse)
def list_workspace(view: str = "recent", current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(V4WorkspaceNode).where(
        V4WorkspaceNode.owner_user_id == current_user.user_id,
        V4WorkspaceNode.is_deleted.is_(False),
    )
    if view == "mine":
        query = query.where(V4WorkspaceNode.source != "conversation")
    elif view == "ai":
        query = query.where(V4WorkspaceNode.source == "conversation")
    items = db.execute(
        query.order_by(V4WorkspaceNode.last_opened_at.desc(), V4WorkspaceNode.updated_at.desc())
    ).scalars().all()
    versions = _latest_versions(db, [item.id for item in items])
    include_owner = view == "recent"
    return AgentLoopResponse(
        data=[
            {
                "id": item.id,
                "parentId": item.parent_id,
                "type": "folder" if item.node_type == "folder" else "doc",
                "name": item.name,
                "owner": item.owner_name if include_owner else None,
                "date": item.last_opened_at.strftime("%m月%d日 %H:%M"),
                "summary": item.summary,
                "contentHtml": versions.get(item.id).content_html if versions.get(item.id) else None,
                "annotations": json.loads(versions.get(item.id).annotations_json or "[]")
                if versions.get(item.id)
                else [],
                "canMove": True,
                "canDownload": True,
                "canRename": True,
                "canDelete": True,
                "canSendToConversation": item.node_type != "folder",
            }
            for item in items
        ]
    )


@router.get("/tree", response_model=AgentLoopResponse)
def get_tree(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    nodes = db.execute(
        select(V4WorkspaceNode).where(
            V4WorkspaceNode.owner_user_id == current_user.user_id,
            V4WorkspaceNode.is_deleted.is_(False),
        )
    ).scalars().all()
    return AgentLoopResponse(
        data=[
            {
                "id": node.id,
                "name": node.name,
                "nodeType": node.node_type,
                "parentId": node.parent_id,
            }
            for node in nodes
        ]
    )


@router.post("/folders", response_model=AgentLoopResponse)
def create_folder(payload: WorkspaceFolderCreateRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = V4WorkspaceNode(
        parent_id=payload.parent_id,
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        node_type="folder",
        source="manual",
        name=payload.name,
        summary="手动创建的文件夹",
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return AgentLoopResponse(data={"id": node.id, "name": node.name})


@router.post("/documents", response_model=AgentLoopResponse)
def create_document(payload: WorkspaceDocumentCreateRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = V4WorkspaceNode(
        parent_id=payload.parent_id,
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        node_type="document",
        source=payload.source,
        name=payload.name,
        summary="新建文档",
    )
    db.add(node)
    db.flush()
    rel_path = write_workspace_version(
        current_user.user_id,
        node.id,
        1,
        payload.name,
        payload.content_html or "<p></p>",
        payload.content_text or "",
        [],
    )
    node.relative_path = rel_path
    db.add(
        V4WorkspaceVersion(
            node_id=node.id,
            version_no=1,
            title=payload.name,
            content_html=payload.content_html or "<p></p>",
            content_text=payload.content_text or "",
            file_rel_path=rel_path,
            annotations_json="[]",
        )
    )
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "name": node.name})


@router.post("/nodes/{node_id}/send-to-conversation", response_model=AgentLoopResponse)
def send_to_conversation(
    node_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    node = _node_or_404(db, node_id, current_user.user_id)
    conversation = V4Conversation(user_id=current_user.user_id, title=node.name[:24] or "新对话")
    db.add(conversation)
    db.flush()
    db.add(
        V4WorkspaceAttachmentLink(
            conversation_id=conversation.id,
            node_id=node.id,
            attachment_role="workspace",
        )
    )
    db.commit()
    return AgentLoopResponse(
        data={
            "conversationId": conversation.id,
            "conversationTitle": conversation.title,
        }
    )


@router.get("/download/{node_id}")
def download_node(node_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    version = db.execute(
        select(V4WorkspaceVersion)
        .where(V4WorkspaceVersion.node_id == node_id)
        .order_by(V4WorkspaceVersion.version_no.desc())
    ).scalars().first()
    if version is None or not version.file_rel_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = user_root(current_user.user_id) / version.file_rel_path / "content.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(Path(file_path), filename=f"{node.name}.html")


@router.post("/uploads", response_model=AgentLoopResponse)
async def upload_document(file: UploadFile = File(...), current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    raw = await file.read()
    name = file.filename or "上传文件"
    text, content_html = parse_uploaded_file(name, raw)
    node = V4WorkspaceNode(
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        node_type="document",
        source="upload",
        name=name,
        summary="上传文件",
    )
    db.add(node)
    db.flush()
    rel_path = write_workspace_version(
        current_user.user_id,
        node.id,
        1,
        name,
        content_html,
        text[:10000],
        [],
    )
    node.relative_path = rel_path
    db.add(
        V4WorkspaceVersion(
            node_id=node.id,
            version_no=1,
            title=name,
            content_html=content_html,
            content_text=text[:10000],
            file_rel_path=rel_path,
            annotations_json="[]",
        )
    )
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "name": node.name})


@router.get("/documents/{node_id}", response_model=AgentLoopResponse)
def get_document(node_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    version = db.execute(
        select(V4WorkspaceVersion)
        .where(V4WorkspaceVersion.node_id == node_id)
        .order_by(V4WorkspaceVersion.version_no.desc())
    ).scalars().first()
    node.last_opened_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(
        data={
            "id": node.id,
            "title": node.name,
            "contentHtml": version.content_html if version else "<p></p>",
            "contentText": version.content_text if version else "",
            "annotations": json.loads(version.annotations_json or "[]") if version else [],
            "updatedAt": node.updated_at.isoformat(),
        }
    )


@router.put("/documents/{node_id}", response_model=AgentLoopResponse)
def save_document(
    node_id: str,
    payload: WorkspaceDocumentUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    node = _node_or_404(db, node_id, current_user.user_id)
    latest = db.execute(
        select(V4WorkspaceVersion)
        .where(V4WorkspaceVersion.node_id == node_id)
        .order_by(V4WorkspaceVersion.version_no.desc())
    ).scalars().first()
    version_no = 1 if latest is None else latest.version_no + 1
    node.name = payload.title or node.name
    node.updated_at = datetime.utcnow()
    node.last_opened_at = node.updated_at
    rel_path = write_workspace_version(
        current_user.user_id,
        node.id,
        version_no,
        node.name,
        payload.content_html or (latest.content_html if latest else "<p></p>"),
        payload.content_text or (latest.content_text if latest else ""),
        payload.annotations,
    )
    node.relative_path = rel_path
    db.add(
        V4WorkspaceVersion(
            node_id=node.id,
            version_no=version_no,
            title=node.name,
            content_html=payload.content_html or (latest.content_html if latest else "<p></p>"),
            content_text=payload.content_text or (latest.content_text if latest else ""),
            file_rel_path=rel_path,
            annotations_json=json.dumps(payload.annotations, ensure_ascii=False),
        )
    )
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "title": node.name, "versionNo": version_no})


@router.put("/nodes/{node_id}", response_model=AgentLoopResponse)
def rename_node(node_id: str, payload: WorkspaceNodeRenameRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    node.name = payload.name
    node.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "name": node.name})


@router.put("/nodes/{node_id}/move", response_model=AgentLoopResponse)
def move_node(node_id: str, payload: WorkspaceNodeMoveRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    node.parent_id = payload.parent_id
    node.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "parentId": node.parent_id})


@router.delete("/nodes/{node_id}", response_model=AgentLoopResponse)
def delete_node(node_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    node.is_deleted = True
    node.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data=True)
