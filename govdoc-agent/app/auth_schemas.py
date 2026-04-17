from typing import Any

from pydantic import BaseModel, Field


class CurrentUser(BaseModel):
    user_id: str
    account: str
    name: str
    org_name: str | None = None
    org_code: str | None = None
    auth_models: list[dict[str, Any]] = Field(default_factory=list)
    default_model: str | None = None
    legacy_system_url: str
    is_first_login_to_agentloop: bool = False
