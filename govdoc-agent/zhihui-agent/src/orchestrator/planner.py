"""任务分解（单次 complete）→ TodoList。"""

from __future__ import annotations

import json
from typing import Any

from model.client import ModelClient


def decompose_to_todos(client: ModelClient, user_message: str) -> list[dict[str, Any]]:
    messages = [
        {
            "role": "system",
            "content": "将用户需求拆成 3～8 个可执行步骤。只输出 JSON 数组，每项包含 "
            'id, description, agent_id, agent_name, status（pending） 字段。',
        },
        {"role": "user", "content": user_message},
    ]
    try:
        data = client.complete(messages, temperature=0.2)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        text = msg.get("content") or ""
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            arr = json.loads(text[start : end + 1])
            if isinstance(arr, list):
                return arr
    except Exception:
        pass
    return [
        {
            "id": "step_1",
            "description": user_message[:200],
            "agent_id": "writing",
            "agent_name": "写作",
            "status": "pending",
        }
    ]
