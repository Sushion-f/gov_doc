"""
Skill 描述列表（前端展示入口与示例句）。

- 前缀：/api/agentloop
- GET /skills：匿名可访问，供首屏渲染 Quick Skill
"""

from fastapi import APIRouter

from ..schemas import AgentLoopResponse
from ..skills import skill_descriptors

router = APIRouter(prefix="/api/agentloop", tags=["agentloop-skills"])


@router.get("/skills", response_model=AgentLoopResponse)
def get_skills():
    return AgentLoopResponse(data=skill_descriptors())
