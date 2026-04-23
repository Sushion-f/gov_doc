"""WebSocket /ws/chat"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


def create_chat_router(agent_factory: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws/chat")
    async def ws_chat(ws: WebSocket) -> None:
        await ws.accept()
        try:
            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)
                if data.get("type") != "chat":
                    continue
                user_id = str(data.get("user_id") or "anonymous")
                session_id = str(data.get("session_id") or uuid.uuid4())
                msg = str(data.get("user_message") or "")
                agent = agent_factory()

                def handler(ev: dict[str, Any]) -> None:
                    try:
                        asyncio.get_running_loop().create_task(
                            ws.send_text(json.dumps(ev, ensure_ascii=False))
                        )
                    except RuntimeError:
                        pass

                agent.chat(
                    msg,
                    handler,
                    user_id=user_id,
                    session_id=session_id,
                    skill_ids=data.get("skill_ids"),
                )
        except WebSocketDisconnect:
            return

    return router
