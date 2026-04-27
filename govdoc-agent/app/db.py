"""
数据库初始化与会话管理模块。

- create_engine：创建 SQLAlchemy 引擎，支持 SQLite（默认）和 PostgreSQL/MySQL 等
- SessionLocal：数据库会话工厂，用于 FastAPI 的 Depends 依赖注入
- get_db：数据库会话生成器，确保请求结束后正确关闭会话
"""

from sqlalchemy import create_engine, event  # SQLAlchemy 核心组件
from sqlalchemy.orm import declarative_base, sessionmaker  # ORM 基类和会话工厂

from .config import settings  # 应用配置


# SQLAlchemy 引擎关键字参数
engine_kwargs = {"future": True}

# 创建数据库引擎
# create_engine 是 SQLAlchemy 的核心函数，用于创建数据库连接池
engine = create_engine(settings.database_url, **engine_kwargs)

# 创建会话工厂
# autocommit=False：默认关闭自动提交，事务需要手动提交
# autoflush=False：关闭自动刷新，避免意外的数据库操作
# bind=engine：将会话绑定到数据库引擎
# future=True：启用 SQLAlchemy 2.0 兼容模式
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

# 创建 ORM 模型基类
# 所有数据库模型类都需要继承 Base
Base = declarative_base()

def get_db():
    """
    数据库会话生成器（FastAPI 依赖注入）。

    用法：
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...

    确保每个请求都能获得独立的数据库会话，
    请求结束后自动关闭会话，释放连接回连接池。
    """
    db = SessionLocal()  # 创建新会话
    try:
        yield db  # 提供会话给路由处理器
    finally:
        db.close()  # 请求结束后关闭会话
