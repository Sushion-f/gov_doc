"""
GovDoc Agent 应用入口。

- 挂载 CORS，允许前端（VITE 开发端口等）携带 Cookie 跨域访问。
- 注册路由：用户/会话/工作区/设置/技能/模型；数据库表结构在启动时 create_all。
- 业务 API 统一前缀见各子模块 router（多为 /api/agentloop/...）。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings as app_settings
from .db import Base, engine
from . import models  # noqa: F401
from .routes import (
    conversations,
    me,
    models as model_routes,
    settings,
    skills,
    workspace,
)

app = FastAPI(title="govdoc-agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router)
app.include_router(conversations.router)
app.include_router(workspace.router)
app.include_router(settings.router)
app.include_router(skills.router)
app.include_router(model_routes.router)

Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
