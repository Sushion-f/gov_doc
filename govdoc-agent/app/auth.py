"""
鉴权与当前用户解析（get_current_user）。

优先级：
1) 联调 Header：X-Legacy-User-Id / X-Legacy-Account / X-Legacy-Name 同时存在时视为已登录。
2) Cookie：配置 LEGACY_AUTH_BASE_URL 时，请求旧系统 /report-agent/v3/auth/me。
3) 开发 Mock：ENABLE_DEV_AUTH_MOCK=true 且无有效用户时，返回固定 Mock 用户。

失败时抛出 HTTP 401，前端应引导登录或开启 Mock。
"""

from dataclasses import dataclass

import requests
from fastapi import Depends, Header, HTTPException, Request

from .config import settings
from .auth_schemas import CurrentUser


@dataclass
class LegacyUser:
    user_id: str
    account: str
    name: str
    org_name: str | None
    org_code: str | None
    auth_models: list[dict]
    default_model: str | None


def _mock_user() -> LegacyUser:
    return LegacyUser(
        user_id="66666666666666666666666666666666",
        account="liwenjing",
        name="李文静",
        org_name="党组秘书处",
        org_code="DANGZU-001",
        auth_models=[
            {
                "modelName": settings.llm_default_model,
                "modelDisplayName": settings.llm_default_model,
            },
        ],
        default_model=settings.llm_default_model,
    )


def _fetch_legacy_user(cookie_header: str | None) -> LegacyUser | None:
    if not settings.legacy_auth_base_url:
        return None

    try:
        response = requests.get(
            f"{settings.legacy_auth_base_url}/report-agent/v3/auth/me",
            headers={"Cookie": cookie_header or ""},
            timeout=5,
        )
        if response.status_code == 401:
            return None
        response.raise_for_status()
        payload = response.json().get("data") or {}
        return LegacyUser(
            user_id=payload.get("userId"),
            account=payload.get("account"),
            name=payload.get("name"),
            org_name=payload.get("orgName"),
            org_code=payload.get("orgCode"),
            auth_models=payload.get("authModels") or [],
            default_model=payload.get("defaultModel"),
        )
    except requests.RequestException:
        return None


def get_current_user(
    request: Request,
    x_legacy_user_id: str | None = Header(default=None),
    x_legacy_account: str | None = Header(default=None),
    x_legacy_name: str | None = Header(default=None),
    x_legacy_org_name: str | None = Header(default=None),
    x_legacy_org_code: str | None = Header(default=None),
) -> CurrentUser:
    if x_legacy_user_id and x_legacy_account and x_legacy_name:
        return CurrentUser(
            user_id=x_legacy_user_id,
            account=x_legacy_account,
            name=x_legacy_name,
            org_name=x_legacy_org_name,
            org_code=x_legacy_org_code,
            auth_models=[
                {
                    "modelName": settings.llm_default_model,
                    "modelDisplayName": settings.llm_default_model,
                }
            ],
            default_model=settings.llm_default_model,
            legacy_system_url=settings.legacy_system_url,
        )

    cookie_header = request.headers.get("cookie")
    legacy_user = _fetch_legacy_user(cookie_header)
    if legacy_user is None and settings.enable_dev_auth_mock:
        legacy_user = _mock_user()

    if legacy_user is None:
        raise HTTPException(status_code=401, detail="未登录")

    auth_models = legacy_user.auth_models or [
        {
            "modelName": settings.llm_default_model,
            "modelDisplayName": settings.llm_default_model,
        }
    ]
    default_model = legacy_user.default_model or settings.llm_default_model

    return CurrentUser(
        user_id=legacy_user.user_id,
        account=legacy_user.account,
        name=legacy_user.name,
        org_name=legacy_user.org_name,
        org_code=legacy_user.org_code,
        auth_models=auth_models,
        default_model=default_model,
        legacy_system_url=settings.legacy_system_url,
    )
