"""轻量信息完整性检测（单次 complete）。"""

from __future__ import annotations

import json
from typing import Any

from model.client import ModelClient


def check_completeness(client: ModelClient, user_message: str) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": "判断用户输入是否包含完成任务所需的关键信息。只输出 JSON："
            '{"is_complete":true|false,"question":"若缺信息则给出一句追问"}',
        },
        {"role": "user", "content": user_message},
    ]
    try:
        data = client.complete(messages, temperature=0)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        text = msg.get("content") or ""
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        pass
    return {"is_complete": True, "question": ""}
