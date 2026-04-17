"""合并 config/model.json 中的可用模型与鉴权侧 auth_models，供 /me、/settings/profile、/models 使用。"""

from typing import Any

from .config import settings


def effective_auth_models(current_user: Any) -> list[dict[str, Any]]:
    """
    - 若配置了 llm.available_models：优先作为下拉数据源；旧系统返回多条 auth_models 时按 modelName 求交。
    - 若未配置：沿用 current_user.auth_models（与原先 auth 行为一致）。
    """
    configured: list[dict[str, str]] = list(settings.llm_available_models or [])
    auth_list = list(getattr(current_user, "auth_models", None) or [])
    auth_names = {
        str(a.get("modelName", "")).strip()
        for a in auth_list
        if isinstance(a, dict) and a.get("modelName")
    }

    if configured:
        mapped: list[dict[str, Any]] = [
            {"modelName": entry["id"], "modelDisplayName": entry.get("label") or entry["id"]}
            for entry in configured
        ]
        if len(auth_list) > 1:
            filtered = [m for m in mapped if m.get("modelName") in auth_names]
            return filtered if filtered else mapped
        return mapped

    if auth_list:
        return auth_list
    return [
        {
            "modelName": settings.llm_default_model,
            "modelDisplayName": settings.llm_default_model,
        }
    ]
