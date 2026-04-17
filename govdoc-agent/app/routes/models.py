"""
当前用户可用模型列表（与 /me 中 auth_models 数据源一致时可作补充查询）。

- 前缀：/api/agentloop
- GET /models：需登录
"""

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..model_catalog import effective_auth_models
from ..schemas import AgentLoopResponse

router = APIRouter(prefix="/api/agentloop", tags=["agentloop-models"])


@router.get("/models", response_model=AgentLoopResponse)
def list_models(current_user=Depends(get_current_user)):
    return AgentLoopResponse(data=effective_auth_models(current_user))
