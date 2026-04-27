"""
鉴权与当前用户解析（get_current_user）。

优先级：
1) 联调 Header：X-Legacy-User-Id / X-Legacy-Account / X-Legacy-Name 同时存在时视为已登录。
2) Cookie：配置 LEGACY_AUTH_BASE_URL 时，请求旧系统 /report-agent/v3/auth/me。
3) 开发 Mock：ENABLE_DEV_AUTH_MOCK=true 且无有效用户时，返回固定 Mock 用户。

失败时抛出 HTTP 401，前端应引导登录或开启 Mock。
"""

from dataclasses import dataclass  # 数据类装饰器

import requests  # HTTP 请求库
from fastapi import Depends, Header, HTTPException, Request  # FastAPI 依赖注入和异常

from .config import settings  # 应用配置
from .auth_schemas import CurrentUser  # 当前用户模型


@dataclass
class LegacyUser:
    """旧系统用户信息数据类。"""
    user_id: str  # 用户 ID
    account: str  # 账号
    name: str  # 姓名
    org_name: str | None  # 组织名称
    org_code: str | None  # 组织代码
    auth_models: list[dict]  # 授权模型列表
    default_model: str | None  # 默认模型


def _mock_user() -> LegacyUser:
    """生成 Mock 用户（开发环境使用）。"""
    return LegacyUser(
        user_id="66666666666666666666666666666666",  # Mock 用户 ID
        account="liwenjing",  # Mock 账号
        name="李文静",  # Mock 姓名
        org_name="党组秘书处",  # Mock 组织名称
        org_code="DANGZU-001",  # Mock 组织代码
        auth_models=[
            {
                "modelName": settings.llm_default_model,  # 默认模型名称
                "modelDisplayName": settings.llm_default_model,  # 默认模型显示名称
            },
        ],
        default_model=settings.llm_default_model,  # 默认模型
    )


def _fetch_legacy_user(cookie_header: str | None) -> LegacyUser | None:
    """从旧系统获取用户信息。"""
    if not settings.legacy_auth_base_url:  # 未配置旧系统认证 URL
        return None

    try:
        response = requests.get(
            f"{settings.legacy_auth_base_url}/report-agent/v3/auth/me",  # 旧系统认证接口
            headers={"Cookie": cookie_header or ""},  # 传递 Cookie
            timeout=5,  # 5秒超时
        )
        if response.status_code == 401:  # 未登录
            return None
        response.raise_for_status()  # 检查其他 HTTP 错误
        payload = response.json().get("data") or {}  # 获取响应数据
        return LegacyUser(
            user_id=payload.get("userId"),  # 用户 ID
            account=payload.get("account"),  # 账号
            name=payload.get("name"),  # 姓名
            org_name=payload.get("orgName"),  # 组织名称
            org_code=payload.get("orgCode"),  # 组织代码
            auth_models=payload.get("authModels") or [],  # 授权模型列表
            default_model=payload.get("defaultModel"),  # 默认模型
        )
    except requests.RequestException:  # 网络请求异常
        return None


def get_current_user(
    request: Request,  # FastAPI 请求对象
    x_legacy_user_id: str | None = Header(default=None),  # 联调 Header：用户 ID
    x_legacy_account: str | None = Header(default=None),  # 联调 Header：账号
    x_legacy_name: str | None = Header(default=None),  # 联调 Header：姓名
    x_legacy_org_name: str | None = Header(default=None),  # 联调 Header：组织名称
    x_legacy_org_code: str | None = Header(default=None),  # 联调 Header：组织代码
) -> CurrentUser:
    """获取当前用户信息（FastAPI 依赖注入）。"""
    # 1. 优先使用联调 Header
    if x_legacy_user_id and x_legacy_account and x_legacy_name:
        return CurrentUser(
            user_id=x_legacy_user_id,  # 用户 ID
            account=x_legacy_account,  # 账号
            name=x_legacy_name,  # 姓名
            org_name=x_legacy_org_name,  # 组织名称
            org_code=x_legacy_org_code,  # 组织代码
            auth_models=[
                {
                    "modelName": settings.llm_default_model,  # 默认模型名称
                    "modelDisplayName": settings.llm_default_model,  # 默认模型显示名称
                }
            ],
            default_model=settings.llm_default_model,  # 默认模型
            legacy_system_url=settings.legacy_system_url,  # 旧系统 URL
        )

    # 2. 尝试从 Cookie 获取旧系统用户信息
    cookie_header = request.headers.get("cookie")  # 获取 Cookie Header
    legacy_user = _fetch_legacy_user(cookie_header)  # 从旧系统获取用户信息
    if legacy_user is None and settings.enable_dev_auth_mock:  # 未获取到用户且启用 Mock
        legacy_user = _mock_user()  # 使用 Mock 用户

    if legacy_user is None:  # 仍未获取到用户
        raise HTTPException(status_code=401, detail="未登录")  # 抛出 401 异常

    # 处理授权模型和默认模型
    auth_models = legacy_user.auth_models or [
        {
            "modelName": settings.llm_default_model,  # 默认模型名称
            "modelDisplayName": settings.llm_default_model,  # 默认模型显示名称
        }
    ]
    default_model = legacy_user.default_model or settings.llm_default_model  # 默认模型

    # 返回当前用户对象
    return CurrentUser(
        user_id=legacy_user.user_id,  # 用户 ID
        account=legacy_user.account,  # 账号
        name=legacy_user.name,  # 姓名
        org_name=legacy_user.org_name,  # 组织名称
        org_code=legacy_user.org_code,  # 组织代码
        auth_models=auth_models,  # 授权模型列表
        default_model=default_model,  # 默认模型
        legacy_system_url=settings.legacy_system_url,  # 旧系统 URL
    )
