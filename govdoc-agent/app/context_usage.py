"""Context usage tracker: 记录每个会话最近一次 LLM 真实 token 用量。

优先级：API 实测（usage.prompt_tokens）> tiktoken 预估 > 字符数粗估。
前端 context_usage 事件通过 ``source`` 字段区分显示"实测 / 预估"。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class ConversationUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_name: str = ""
    updated_at: float = field(default_factory=time.time)

    def asdict(self) -> dict:
        return {
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "totalTokens": self.total_tokens,
            "model": self.model_name,
            "updatedAt": self.updated_at,
        }


class _UsageStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_conversation: dict[str, ConversationUsage] = {}

    def record(
        self,
        conversation_id: str | None,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        model_name: str = "",
    ) -> None:
        if not conversation_id:
            return
        with self._lock:
            current = self._by_conversation.get(conversation_id) or ConversationUsage()
            if prompt_tokens:
                current.prompt_tokens = int(prompt_tokens)
            if completion_tokens:
                current.completion_tokens = int(completion_tokens)
            if total_tokens:
                current.total_tokens = int(total_tokens)
            elif prompt_tokens or completion_tokens:
                current.total_tokens = current.prompt_tokens + current.completion_tokens
            if model_name:
                current.model_name = str(model_name)
            current.updated_at = time.time()
            self._by_conversation[conversation_id] = current

    def get(self, conversation_id: str | None) -> ConversationUsage | None:
        if not conversation_id:
            return None
        with self._lock:
            return self._by_conversation.get(conversation_id)

    def clear(self, conversation_id: str | None) -> None:
        if not conversation_id:
            return
        with self._lock:
            self._by_conversation.pop(conversation_id, None)


_STORE = _UsageStore()


def record_usage(conversation_id: str | None, usage: dict | None, *, model_name: str = "") -> None:
    if not isinstance(usage, dict):
        return
    _STORE.record(
        conversation_id,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        model_name=model_name,
    )


def get_usage(conversation_id: str | None) -> ConversationUsage | None:
    return _STORE.get(conversation_id)


def clear_usage(conversation_id: str | None) -> None:
    _STORE.clear(conversation_id)
