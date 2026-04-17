"""
用户设置：个人资料、记忆、词库、模板文件。

- 前缀：/api/agentloop/settings
- profile/memory 与 runtime 侧「记忆投影」、Markdown 文件联动
- dictionaries：白名单/黑名单词条
- templates：multipart 上传模板文件，落盘 + 元数据表
"""

from datetime import datetime
import json

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..model_catalog import effective_auth_models
from ..models import V4DictionaryEntry, V4TemplateItem
from ..runtime import (
    _default_memory_state,
    _ensure_memory_docs,
    _extract_manual_notes_from_memory_markdown,
    _normalize_memory_state,
    _sync_profile_memory_projection,
    _sync_session_summary_projection,
    read_profile_docs,
)
from ..schemas import (
    AgentLoopResponse,
    DictionaryEntryCreateRequest,
    MemoryUpdateRequest,
    SettingsProfileUpdateRequest,
)
from ..storage import clear_user_memory_subdir, write_memory_doc, write_template_file

router = APIRouter(prefix="/api/agentloop/settings", tags=["agentloop-settings"])


@router.get("/profile", response_model=AgentLoopResponse)
def get_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _ensure_memory_docs(db, current_user)
    docs = read_profile_docs(current_user, profile)
    db.commit()
    return AgentLoopResponse(
        data={
            "defaultModel": profile.default_model or current_user.default_model,
            "preferredSkills": json.loads(profile.preferred_skills_json or "[]"),
            "recommendationSummary": profile.recommendation_summary,
            "authModels": effective_auth_models(current_user),
            "identifyMarkdown": docs["identify_markdown"],
            "memoryMarkdown": docs["memory_markdown"],
            "sessionSummaryMarkdown": docs["session_summary_markdown"],
        }
    )


@router.put("/profile", response_model=AgentLoopResponse)
def update_profile(payload: SettingsProfileUpdateRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _ensure_memory_docs(db, current_user)
    profile.default_model = payload.default_model or profile.default_model
    profile.preferred_skills_json = json.dumps(payload.preferred_skills, ensure_ascii=False)
    profile.recommendation_summary = payload.recommendation_summary
    profile.updated_at = datetime.utcnow()
    _sync_profile_memory_projection(db, current_user, profile)
    db.commit()
    return AgentLoopResponse(data=True)


@router.get("/memory", response_model=AgentLoopResponse)
def get_memory(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _ensure_memory_docs(db, current_user)
    docs = read_profile_docs(current_user, profile)
    db.commit()
    return AgentLoopResponse(
        data={
            "identity": json.loads(profile.identity_json or "{}"),
            "memory": json.loads(profile.memory_json or "{}"),
            "identifyMarkdown": docs["identify_markdown"],
            "memoryMarkdown": docs["memory_markdown"],
            "sessionSummaryMarkdown": docs["session_summary_markdown"],
        }
    )


@router.put("/memory", response_model=AgentLoopResponse)
def update_memory(payload: MemoryUpdateRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _ensure_memory_docs(db, current_user)
    profile.identity_json = json.dumps(payload.identity, ensure_ascii=False)
    memory_state = _normalize_memory_state(payload.memory)
    if payload.memory_markdown is not None:
        memory_state["manualNotes"] = _extract_manual_notes_from_memory_markdown(payload.memory_markdown)
    profile.memory_json = json.dumps(memory_state, ensure_ascii=False)
    identify_md = payload.identify_markdown or "# identify\n\n"
    profile.identify_md_path = write_memory_doc(current_user.user_id, "identify.md", identify_md)
    _sync_profile_memory_projection(db, current_user, profile)
    db.commit()
    return AgentLoopResponse(data=True)


@router.delete("/memory", response_model=AgentLoopResponse)
def clear_memory(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _ensure_memory_docs(db, current_user)
    profile.identity_json = json.dumps({}, ensure_ascii=False)
    profile.memory_json = json.dumps(_default_memory_state(), ensure_ascii=False)
    profile.recommendation_summary = None
    clear_user_memory_subdir(current_user.user_id, "topics")
    clear_user_memory_subdir(current_user.user_id, "sessions")
    _sync_profile_memory_projection(db, current_user, profile)
    _sync_session_summary_projection(db, current_user, profile)
    db.commit()
    return AgentLoopResponse(data=True)


@router.get("/dictionaries", response_model=AgentLoopResponse)
def get_dictionaries(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.execute(
        select(V4DictionaryEntry).where(
            V4DictionaryEntry.user_id == current_user.user_id,
            V4DictionaryEntry.is_deleted.is_(False),
        )
    ).scalars().all()
    return AgentLoopResponse(
        data={
            "whiteList": [
                {"id": item.id, "word": item.word, "status": 1, "notes": item.notes}
                for item in items
                if item.dict_type == "whiteList"
            ],
            "blackList": [
                {"id": item.id, "word": item.word, "status": 1, "notes": item.notes}
                for item in items
                if item.dict_type == "blackList"
            ],
        }
    )


@router.put("/dictionaries", response_model=AgentLoopResponse)
def create_dictionary_entry(
    payload: DictionaryEntryCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = V4DictionaryEntry(
        user_id=current_user.user_id,
        dict_type=payload.dict_type,
        word=payload.word,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return AgentLoopResponse(data={"id": item.id, "word": item.word})


@router.delete("/dictionaries/{entry_id}", response_model=AgentLoopResponse)
def delete_dictionary_entry(
    entry_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.execute(
        select(V4DictionaryEntry).where(
            V4DictionaryEntry.id == entry_id,
            V4DictionaryEntry.user_id == current_user.user_id,
            V4DictionaryEntry.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if item is None:
        return AgentLoopResponse(data=True)
    item.is_deleted = True
    item.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data=True)


@router.get("/templates", response_model=AgentLoopResponse)
def get_templates(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.execute(
        select(V4TemplateItem).where(
            V4TemplateItem.user_id == current_user.user_id,
            V4TemplateItem.is_deleted.is_(False),
        )
    ).scalars().all()
    return AgentLoopResponse(
        data=[
            {
                "id": item.id,
                "title": item.title,
                "documentType": item.document_type,
                "fileName": item.file_name,
            }
            for item in items
        ]
    )


@router.post("/templates", response_model=AgentLoopResponse)
async def create_template(
    title: str,
    document_type: str | None = None,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    relative_path = write_template_file(current_user.user_id, file.filename or f"{title}.bin", content)
    item = V4TemplateItem(
        user_id=current_user.user_id,
        title=title,
        document_type=document_type,
        file_name=file.filename,
        relative_path=relative_path,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return AgentLoopResponse(data={"id": item.id, "title": item.title})


@router.delete("/templates/{template_id}", response_model=AgentLoopResponse)
def delete_template(
    template_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.execute(
        select(V4TemplateItem).where(
            V4TemplateItem.id == template_id,
            V4TemplateItem.user_id == current_user.user_id,
            V4TemplateItem.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if item is None:
        return AgentLoopResponse(data=True)
    item.is_deleted = True
    item.updated_at = datetime.utcnow()
    db.commit()
    return AgentLoopResponse(data=True)
