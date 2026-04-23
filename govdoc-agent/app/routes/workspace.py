"""
用户工作区（云盘）：基于真实文件树的文档/文件夹 CRUD、树、上传、下载、发送到会话。

- 前缀：/api/agentloop/workspace
- 唯一事实源：workspace/files 下的真实文件与文件夹
- .cache 保存解析产物，.versions 保存轻量版本快照
"""

import json
from datetime import datetime
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import V4Conversation, V4WorkspaceAttachmentLink, V4WorkspaceNode
from ..schemas import (
    AgentLoopResponse,
    WorkspaceDocumentCreateRequest,
    WorkspaceDocumentUpdateRequest,
    WorkspaceFolderCreateRequest,
    WorkspaceNodeMoveRequest,
    WorkspaceNodeRenameRequest,
)
from ..storage import (
    build_docx_bytes,
    ensure_unique_workspace_path,
    html_to_plain_text,
    latest_workspace_version,
    move_workspace_path,
    normalize_workspace_path,
    parse_workspace_file,
    resolve_writable_file_path,
    trash_workspace_path,
    workspace_abspath,
    workspace_file_etag,
    workspace_relpath,
    write_workspace_bytes,
    write_workspace_version,
)

router = APIRouter(prefix="/api/agentloop/workspace", tags=["agentloop-workspace"])

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".json", ".csv"}


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


def _list_nodes(db: Session, user_id: str) -> list[V4WorkspaceNode]:
    nodes = db.execute(
        select(V4WorkspaceNode).where(
            V4WorkspaceNode.owner_user_id == user_id,
            V4WorkspaceNode.is_deleted.is_(False),
        )
    ).scalars().all()
    return nodes


def _kind(node: V4WorkspaceNode) -> str:
    return node.kind or ("folder" if node.node_type == "folder" else "document")


def _display_name(node: V4WorkspaceNode) -> str:
    return node.title_override or node.name or Path(node.path or "").name


def _relative_path_for_parent(db: Session, user_id: str, parent_id: str | None) -> str:
    if not parent_id:
        return ""
    parent = _node_or_404(db, parent_id, user_id)
    return normalize_workspace_path(parent.path)


def _join_relative_path(parent_relative_path: str, name: str) -> str:
    safe_name = (name or "").strip().replace("\\", "/").strip("/")
    if not safe_name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    if parent_relative_path:
        return normalize_workspace_path(str(PurePosixPath(parent_relative_path, safe_name)))
    return normalize_workspace_path(safe_name)


def _sync_node_from_path(node: V4WorkspaceNode, relative_path: str, *, kind: str, title: str | None = None) -> None:
    normalized = normalize_workspace_path(relative_path)
    node.path = normalized
    node.relative_path = normalized
    node.kind = kind
    node.node_type = "folder" if kind == "folder" else "document"
    node.name = title or Path(normalized).name or node.name
    node.updated_at = datetime.utcnow()
    if kind == "folder":
        node.size = 0
        node.etag = None
    else:
        absolute_path = workspace_abspath(node.owner_user_id, normalized)
        if absolute_path.exists():
            node.size = absolute_path.stat().st_size
            node.etag = workspace_file_etag(absolute_path)


def _next_version_no(user_id: str, node_id: str) -> int:
    latest = latest_workspace_version(user_id, node_id)
    if not latest:
        return 1
    version = str(latest.get("version") or "v0000")
    try:
        return int(version[1:]) + 1
    except ValueError:
        return 1


def _version_annotations(user_id: str, node_id: str) -> list[dict]:
    latest = latest_workspace_version(user_id, node_id)
    meta = latest.get("meta") if latest else {}
    annotations = meta.get("annotations") if isinstance(meta, dict) else []
    return annotations if isinstance(annotations, list) else []


def _write_document_content(
    *,
    user_id: str,
    node: V4WorkspaceNode,
    target_relative_path: str,
    title: str,
    content_html: str | None,
    content_text: str | None,
) -> tuple[str, dict]:
    requested_path = normalize_workspace_path(target_relative_path)
    writable_path = resolve_writable_file_path(requested_path)
    if writable_path != requested_path:
        writable_path = ensure_unique_workspace_path(user_id, writable_path, is_dir=False)

    ext = Path(writable_path).suffix.lower()
    plain_text = html_to_plain_text(content_html, content_text)
    if ext in TEXT_EXTENSIONS:
        file_bytes = plain_text.encode("utf-8")
    else:
        file_bytes = build_docx_bytes(title, content_html, plain_text)

    write_workspace_bytes(user_id, writable_path, file_bytes)
    parsed = parse_workspace_file(user_id, writable_path, force=True)
    _sync_node_from_path(node, writable_path, kind="document", title=Path(writable_path).name)
    return writable_path, parsed


def _hydrate_node_content(db: Session, current_user, node: V4WorkspaceNode) -> dict | None:
    if _kind(node) == "folder":
        return None
    if not node.path:
        raise HTTPException(status_code=404, detail="工作区文件路径不存在")
    absolute_path = workspace_abspath(current_user.user_id, node.path)
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="工作区文件不存在")
    return parse_workspace_file(current_user.user_id, node.path)


def _document_meta(current_user, node: V4WorkspaceNode, parsed: dict | None) -> dict:
    absolute_path = workspace_abspath(current_user.user_id, node.path) if node.path else None
    suffix = absolute_path.suffix.lower() if absolute_path else ""
    parser = (parsed or {}).get("meta", {}).get("parser")
    is_pdf = suffix == ".pdf" or parser == "pdfplumber"
    editable = not is_pdf
    return {
        "path": node.path,
        "fileType": suffix.lstrip(".") or "document",
        "parser": parser,
        "editable": editable,
        "readOnlyReason": "PDF 只读，保存时会另存为 docx。" if not editable else "",
        "downloadName": _display_name(node),
    }


def _serialize_workspace_item(db: Session, current_user, node: V4WorkspaceNode, include_owner: bool) -> dict:
    parsed = _hydrate_node_content(db, current_user, node) if _kind(node) != "folder" else None
    return {
        "id": node.id,
        "parentId": node.parent_id,
        "type": "folder" if _kind(node) == "folder" else "doc",
        "name": _display_name(node),
        "owner": node.owner_name if include_owner else None,
        "date": node.last_opened_at.strftime("%m月%d日 %H:%M"),
        "summary": node.summary,
        "contentHtml": parsed["content_html"] if parsed else None,
        "annotations": _version_annotations(current_user.user_id, node.id) if parsed else [],
        "canMove": True,
        "canDownload": _kind(node) != "folder",
        "canRename": True,
        "canDelete": True,
        "canSendToConversation": _kind(node) != "folder",
    }


def _update_descendant_paths(db: Session, current_user, old_prefix: str, new_prefix: str, root_node_id: str) -> None:
    if not old_prefix:
        return
    prefix = f"{old_prefix}/"
    for item in _list_nodes(db, current_user.user_id):
        if item.id == root_node_id:
            continue
        if not item.path or not item.path.startswith(prefix):
            continue
        suffix = item.path[len(prefix) :]
        item.path = normalize_workspace_path(str(PurePosixPath(new_prefix, suffix)))
        item.relative_path = item.path
        item.name = Path(item.path).name
        if _kind(item) != "folder":
            absolute_path = workspace_abspath(current_user.user_id, item.path)
            if absolute_path.exists():
                item.size = absolute_path.stat().st_size
                item.etag = workspace_file_etag(absolute_path)
        item.updated_at = datetime.utcnow()


@router.get("", response_model=AgentLoopResponse)
def list_workspace(view: str = "recent", current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = _list_nodes(db, current_user.user_id)
    if view == "mine":
        items = [item for item in items if item.source != "conversation"]
    elif view == "ai":
        items = [item for item in items if item.source == "conversation"]
    items.sort(key=lambda item: (item.last_opened_at, item.updated_at), reverse=True)
    include_owner = view == "recent"
    return AgentLoopResponse(
        data=[_serialize_workspace_item(db, current_user, item, include_owner) for item in items]
    )


@router.get("/tree", response_model=AgentLoopResponse)
def get_tree(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    nodes = _list_nodes(db, current_user.user_id)
    return AgentLoopResponse(
        data=[
            {
                "id": node.id,
                "name": _display_name(node),
                "nodeType": "folder" if _kind(node) == "folder" else "document",
                "parentId": node.parent_id,
            }
            for node in nodes
        ]
    )


@router.post("/folders", response_model=AgentLoopResponse)
def create_folder(payload: WorkspaceFolderCreateRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    parent_relative_path = _relative_path_for_parent(db, current_user.user_id, payload.parent_id)
    desired_path = _join_relative_path(parent_relative_path, payload.name)
    relative_path = ensure_unique_workspace_path(current_user.user_id, desired_path, is_dir=True)
    workspace_abspath(current_user.user_id, relative_path).mkdir(parents=True, exist_ok=True)

    node = V4WorkspaceNode(
        parent_id=payload.parent_id,
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        source="manual",
        name=Path(relative_path).name,
        summary="手动创建的文件夹",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_opened_at=datetime.utcnow(),
        is_deleted=False,
        node_type="folder",
    )
    _sync_node_from_path(node, relative_path, kind="folder", title=Path(relative_path).name)
    db.add(node)
    db.commit()
    db.refresh(node)
    return AgentLoopResponse(data={"id": node.id, "name": node.name})


@router.post("/documents", response_model=AgentLoopResponse)
def create_document(payload: WorkspaceDocumentCreateRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    parent_relative_path = _relative_path_for_parent(db, current_user.user_id, payload.parent_id)
    desired_path = _join_relative_path(parent_relative_path, payload.name)
    relative_path = ensure_unique_workspace_path(current_user.user_id, desired_path, is_dir=False)

    node = V4WorkspaceNode(
        parent_id=payload.parent_id,
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        source=payload.source,
        name=Path(relative_path).name,
        summary="新建文档",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_opened_at=datetime.utcnow(),
        is_deleted=False,
        node_type="document",
    )
    parsed_path, parsed = _write_document_content(
        user_id=current_user.user_id,
        node=node,
        target_relative_path=relative_path,
        title=payload.name,
        content_html=payload.content_html or "<p></p>",
        content_text=payload.content_text or "",
    )
    db.add(node)
    db.flush()
    write_workspace_version(
        current_user.user_id,
        node.id,
        1,
        title=Path(parsed_path).name,
        content_html=parsed["content_html"],
        content_text=parsed["content_text"],
        annotations=[],
        file_relative_path=parsed_path,
        extra_meta={"source": payload.source or "manual"},
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
    conversation = V4Conversation(user_id=current_user.user_id, title=_display_name(node)[:24] or "新对话")
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
    if _kind(node) == "folder":
        raise HTTPException(status_code=400, detail="文件夹不支持下载")
    parsed = _hydrate_node_content(db, current_user, node)
    absolute_path = workspace_abspath(current_user.user_id, node.path)
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(Path(absolute_path), filename=_display_name(node), media_type=None)


@router.post("/uploads", response_model=AgentLoopResponse)
async def upload_document(file: UploadFile = File(...), current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    raw = await file.read()
    name = (file.filename or "上传文件").strip() or "上传文件"
    # 魔数校验：扩展名声明为 docx/pdf 等二进制文档，但内容是 HTML/登录/反爬页时直接拒收，
    # 避免把一张 Cloudflare 挑战页以 .docx 存进工作区再被"解析"成乱码。
    from ..file_parser import _detect_corrupted_reason  # 内部工具，避免循环导入

    corruption_reason = _detect_corrupted_reason(name, raw)
    if corruption_reason:
        raise HTTPException(status_code=400, detail=f"上传被拒绝：{corruption_reason}")
    relative_path = ensure_unique_workspace_path(current_user.user_id, normalize_workspace_path(name), is_dir=False)
    write_workspace_bytes(current_user.user_id, relative_path, raw)
    parsed = parse_workspace_file(current_user.user_id, relative_path, force=True)

    node = V4WorkspaceNode(
        owner_user_id=current_user.user_id,
        owner_name=current_user.name,
        source="upload",
        name=Path(relative_path).name,
        summary="上传文件",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_opened_at=datetime.utcnow(),
        is_deleted=False,
        node_type="document",
    )
    _sync_node_from_path(node, relative_path, kind="document", title=Path(relative_path).name)
    db.add(node)
    db.flush()
    write_workspace_version(
        current_user.user_id,
        node.id,
        1,
        title=Path(relative_path).name,
        content_html=parsed["content_html"],
        content_text=parsed["content_text"],
        annotations=[],
        file_relative_path=relative_path,
        extra_meta={"source": "upload", "parser": parsed["meta"].get("parser")},
    )
    db.commit()
    meta = _document_meta(current_user, node, parsed)
    return AgentLoopResponse(
        data={
            "id": node.id,
            "name": node.name,
            "fileType": meta.get("fileType"),
            "editable": meta.get("editable"),
            "summary": node.summary,
        }
    )


@router.get("/documents/{node_id}", response_model=AgentLoopResponse)
def get_document(node_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    if _kind(node) == "folder":
        raise HTTPException(status_code=400, detail="文件夹不可编辑")
    parsed = _hydrate_node_content(db, current_user, node)
    node.last_opened_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(
        data={
            "id": node.id,
            "title": _display_name(node),
            "contentHtml": parsed["content_html"],
            "contentText": parsed["content_text"],
            "annotations": _version_annotations(current_user.user_id, node.id),
            "updatedAt": node.updated_at.isoformat(),
            "meta": _document_meta(current_user, node, parsed),
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
    if _kind(node) == "folder":
        raise HTTPException(status_code=400, detail="文件夹不可编辑")

    title = (payload.title or _display_name(node)).strip() or _display_name(node)
    parent_relative_path = _relative_path_for_parent(db, current_user.user_id, node.parent_id)
    target_relative_path = _join_relative_path(parent_relative_path, title)
    target_relative_path = ensure_unique_workspace_path(
        current_user.user_id,
        target_relative_path,
        is_dir=False,
        exclude_relative_path=node.path,
    )
    if node.path and node.path != target_relative_path:
        move_workspace_path(current_user.user_id, node.path, target_relative_path)

    actual_relative_path, parsed = _write_document_content(
        user_id=current_user.user_id,
        node=node,
        target_relative_path=target_relative_path,
        title=title,
        content_html=payload.content_html,
        content_text=payload.content_text,
    )
    node.last_opened_at = node.updated_at
    version_no = _next_version_no(current_user.user_id, node.id)
    write_workspace_version(
        current_user.user_id,
        node.id,
        version_no,
        title=Path(actual_relative_path).name,
        content_html=parsed["content_html"],
        content_text=parsed["content_text"],
        annotations=payload.annotations,
        file_relative_path=actual_relative_path,
        extra_meta={"savedFrom": "workspace.put_document"},
    )
    db.commit()
    return AgentLoopResponse(
        data={
            "id": node.id,
            "title": node.name,
            "versionNo": version_no,
            "meta": _document_meta(current_user, node, parsed),
        }
    )


@router.put("/nodes/{node_id}", response_model=AgentLoopResponse)
def rename_node(node_id: str, payload: WorkspaceNodeRenameRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    parent_relative_path = _relative_path_for_parent(db, current_user.user_id, node.parent_id)
    desired_path = _join_relative_path(parent_relative_path, payload.name)
    relative_path = ensure_unique_workspace_path(
        current_user.user_id,
        desired_path,
        is_dir=_kind(node) == "folder",
        exclude_relative_path=node.path,
    )
    old_path = normalize_workspace_path(node.path)
    if old_path and old_path != relative_path:
        move_workspace_path(current_user.user_id, old_path, relative_path)
        _update_descendant_paths(db, current_user, old_path, relative_path, node.id)
    _sync_node_from_path(node, relative_path, kind=_kind(node), title=Path(relative_path).name)
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "name": node.name})


@router.put("/nodes/{node_id}/move", response_model=AgentLoopResponse)
def move_node(node_id: str, payload: WorkspaceNodeMoveRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    target_parent_relative_path = _relative_path_for_parent(db, current_user.user_id, payload.parent_id)
    desired_path = _join_relative_path(target_parent_relative_path, _display_name(node))
    relative_path = ensure_unique_workspace_path(
        current_user.user_id,
        desired_path,
        is_dir=_kind(node) == "folder",
        exclude_relative_path=node.path,
    )
    old_path = normalize_workspace_path(node.path)
    if old_path and old_path != relative_path:
        move_workspace_path(current_user.user_id, old_path, relative_path)
        _update_descendant_paths(db, current_user, old_path, relative_path, node.id)
    node.parent_id = payload.parent_id
    _sync_node_from_path(node, relative_path, kind=_kind(node), title=Path(relative_path).name)
    db.commit()
    return AgentLoopResponse(data={"id": node.id, "parentId": node.parent_id})


@router.delete("/nodes/{node_id}", response_model=AgentLoopResponse)
def delete_node(node_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    node = _node_or_404(db, node_id, current_user.user_id)
    root_path = normalize_workspace_path(node.path)
    descendants = []
    if root_path:
        prefix = f"{root_path}/"
        descendants = [
            item
            for item in _list_nodes(db, current_user.user_id)
            if item.id != node.id and item.path and item.path.startswith(prefix)
        ]
    trash_workspace_path(current_user.user_id, root_path)
    node.is_deleted = True
    node.updated_at = datetime.utcnow()
    for item in descendants:
        item.is_deleted = True
        item.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data=True)
