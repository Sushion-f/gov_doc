"""
GovDoc Agent 应用入口。

- 挂载 CORS，允许前端（VITE 开发端口等）携带 Cookie 跨域访问。
- 注册路由：用户/会话/工作区/设置/技能/模型；数据库表结构在启动时 create_all。
- 业务 API 统一前缀见各子模块 router（多为 /api/agentloop/...）。
"""

# 导入 FastAPI 核心模块
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 导入配置和数据库
from .config import settings as app_settings  # 应用配置（从 model.json 和 .env 读取）
from .db import Base, engine  # SQLAlchemy 模型基类和数据库引擎
from . import models  # 导入模型模块以触发模型注册（仅触发，不直接使用）

# 导入路由模块
from .routes import (
    conversations,  # 会话相关路由（/api/agentloop/conversations）
    me,  # 用户信息与健康检查路由（/api/agentloop/me, /api/agentloop/health）
    models as model_routes,  # 模型管理路由（/api/agentloop/models）
    settings,  # 用户设置路由（/api/agentloop/settings）
    skills,  # 技能管理路由（/api/agentloop/skills）
    workspace,  # 工作区管理路由（/api/agentloop/workspace）
)

# 创建 FastAPI 应用实例
app = FastAPI(title="govdoc-agent")

# 配置 CORS 中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,  # 允许的跨域来源（从配置读取）
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有 HTTP 头
)

# 注册路由
app.include_router(me.router)  # 用户信息与健康检查
app.include_router(conversations.router)  # 会话管理（CRUD + 运行 + SSE 事件流）
app.include_router(workspace.router)  # 工作区管理（文档/文件夹操作）
app.include_router(settings.router)  # 用户设置（资料/记忆/词库/模板）
app.include_router(skills.router)  # 技能管理
app.include_router(model_routes.router)  # 模型管理（可用模型列表）

# 初始化数据库表结构（应用启动时执行）
Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def on_startup():
    """应用启动事件处理函数。"""
    # 再次执行数据库表结构创建（确保每次启动时都检查并创建表结构）
    Base.metadata.create_all(bind=engine)
