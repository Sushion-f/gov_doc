"""OpenAI-compatible HTTP 客户端；本模块为唯一直接发起 LLM HTTP 的位置（使用 httpx，不依赖 openai SDK）。"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from typing import Any

import httpx


class ModelClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("ZHIHUI_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("ZHIHUI_LLM_API_KEY", "")
        self.default_model = default_model or os.getenv("ZHIHUI_LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self._post_url = f"{self.base_url}/chat/completions" if self.base_url else ""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        if not self._post_url:
            raise RuntimeError("ZHIHUI_LLM_BASE_URL 未配置")
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self._post_url, headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        on_chunk: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """流式请求；聚合为与 complete 相同形态的 choices[0].message 结构。"""
        if not self._post_url:
            raise RuntimeError("ZHIHUI_LLM_BASE_URL 未配置")
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []

        def _merge_tool_calls(acc: list[dict], delta_tools: list) -> None:
            for dt in delta_tools or []:
                idx = dt.get("index", 0)
                while len(acc) <= idx:
                    acc.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                cur = acc[idx]
                if dt.get("id"):
                    cur["id"] = dt["id"]
                fn = dt.get("function") or {}
                if fn.get("name"):
                    cur["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    cur["function"]["arguments"] = (cur["function"].get("arguments") or "") + fn["arguments"]

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", self._post_url, headers=self._headers(), json=payload) as resp:
                resp.raise_for_status()
                enc = (resp.encoding or "").lower()
                if not enc or enc in ("iso-8859-1", "latin-1"):
                    resp.encoding = "utf-8"
                for line in resp.iter_lines():
                    if not line:
                        continue
                    s = line.strip()
                    if not s.startswith("data:"):
                        continue
                    data_str = s[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    chunks.append(data)
                    if on_chunk:
                        on_chunk(data)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    c = delta.get("content")
                    if isinstance(c, str) and c:
                        text_parts.append(c)
                    rc = delta.get("reasoning_content") or delta.get("reasoning")
                    if isinstance(rc, str) and rc:
                        reasoning_parts.append(rc)
                    _merge_tool_calls(tool_calls, delta.get("tool_calls") or [])

        text = "".join(text_parts).strip()
        reasoning = "".join(reasoning_parts).strip()
        msg: dict[str, Any] = {"role": "assistant", "content": text or None}
        if reasoning:
            msg["reasoning_content"] = reasoning
        if tool_calls:
            msg["tool_calls"] = [t for t in tool_calls if t.get("function", {}).get("name")]
        return {
            "choices": [{"message": msg, "finish_reason": "stop"}],
            "raw_chunks": chunks,
        }
