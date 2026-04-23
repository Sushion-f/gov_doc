"""
GovDoc Agent 应用入口。

- 挂载 CORS，允许前端（VITE 开发端口等）携带 Cookie 跨域访问。
- 注册路由：用户/会话/工作区/设置/技能/模型；数据库表结构在启动时 create_all。
- 业务 API 统一前缀见各子模块 router（多为 /api/agentloop/...）。
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings as app_settings
from .db import Base, engine, ensure_conversation_schema, ensure_workspace_schema
from .debug_log import log_stage, mask_cookie
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


@app.middleware("http")
async def log_agentloop_http_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        if request.url.path.startswith("/api/agentloop"):
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log_stage(
                "api.http.error",
                {
                    "method": request.method,
                    "path": request.url.path,
                    "query": dict(request.query_params),
                    "statusCode": 500,
                    "durationMs": duration_ms,
                    "origin": request.headers.get("origin"),
                    "referer": request.headers.get("referer"),
                    "cookiePreview": mask_cookie(request.headers.get("cookie")),
                    "error": str(exc),
                },
                enabled=app_settings.debug_runtime_logs,
                max_chars=app_settings.debug_log_max_chars,
                max_string_chars=app_settings.debug_log_max_string_chars,
            )
        raise
    if request.url.path.startswith("/api/agentloop"):
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_stage(
            "api.http.request",
            {
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "statusCode": response.status_code,
                "durationMs": duration_ms,
                "origin": request.headers.get("origin"),
                "referer": request.headers.get("referer"),
                "cookiePreview": mask_cookie(request.headers.get("cookie")),
            },
            enabled=app_settings.debug_runtime_logs,
            max_chars=app_settings.debug_log_max_chars,
            max_string_chars=app_settings.debug_log_max_string_chars,
        )
    return response

app.include_router(me.router)
app.include_router(conversations.router)
app.include_router(workspace.router)
app.include_router(settings.router)
app.include_router(skills.router)
app.include_router(model_routes.router)

Base.metadata.create_all(bind=engine)
ensure_conversation_schema()
ensure_workspace_schema()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_conversation_schema()
    ensure_workspace_schema()
