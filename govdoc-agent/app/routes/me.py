"""
AgentLoop「当前用户」与健康检查。

- 前缀：/api/agentloop
- GET /health：匿名，负载均衡/探活使用
- GET /me：需登录，返回用户资料、可用模型、偏好 Skill、记忆 Markdown 投影等
"""

from fastapi import APIRouter, Depends
import json
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..model_catalog import effective_auth_models
from ..runtime import _ensure_memory_docs, first_login_to_agent_app, read_profile_docs
from ..schemas import AgentLoopResponse

router = APIRouter(prefix="/api/agentloop", tags=["agentloop-me"])


@router.get("/health", response_model=AgentLoopResponse)
def health():
    return AgentLoopResponse(data={"status": "ok"})


@router.get("/me", response_model=AgentLoopResponse)
def get_me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _ensure_memory_docs(db, current_user)
    current_user.is_first_login_to_agentloop = first_login_to_agent_app(db, current_user.user_id)
    docs = read_profile_docs(current_user, profile)
    db.commit()
    dumped = current_user.model_dump()
    dumped["auth_models"] = effective_auth_models(current_user)
    return AgentLoopResponse(
        data={
            **dumped,
            "preferredSkills": json.loads(profile.preferred_skills_json or "[]"),
            "recommendationSummary": profile.recommendation_summary,
            "identifyMarkdown": docs["identify_markdown"],
            "memoryMarkdown": docs["memory_markdown"],
            "sessionSummaryMarkdown": docs["session_summary_markdown"],
        }
    )
