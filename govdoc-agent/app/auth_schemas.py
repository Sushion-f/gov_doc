"""
认证相关的数据模型。

主要包含 CurrentUser 模型，用于表示当前登录用户的信息。
"""

from typing import Any  # 类型注解

from pydantic import BaseModel, Field  # Pydantic 基础类和字段配置


class CurrentUser(BaseModel):
    """当前用户模型。"""
    user_id: str  # 用户 ID
    account: str  # 账号
    name: str  # 姓名
    org_name: str | None = None  # 组织名称
    org_code: str | None = None  # 组织代码
    auth_models: list[dict[str, Any]] = Field(default_factory=list)  # 授权模型列表
    default_model: str | None = None  # 默认模型
    legacy_system_url: str  # 旧系统 URL
    is_first_login_to_agentloop: bool = False  # 是否首次登录 AgentLoop
