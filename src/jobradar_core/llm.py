from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from jobradar_core.config import AppConfig


class LLMError(RuntimeError):
    pass


class LLMPort(Protocol):
    async def complete_json(self, *, system: str, user: str) -> dict: ...


class OpenAICompatibleLLM:
    def __init__(self, config: AppConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self._client = client

    @property
    def available(self) -> bool:
        model = self.config.model
        if not model.base_url or not model.model:
            return False
        if model.is_local:
            return True
        return self.config.privacy.allow_remote_model and bool(model.api_key)

    async def complete_json(self, *, system: str, user: str) -> dict:
        if not self.available:
            raise LLMError("模型不可用：本地 endpoint 未配置，或远程模型尚未在 privacy 中授权")
        model = self.config.model
        endpoint = f"{model.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"
        payload = {
            "model": model.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=model.timeout_seconds,
            trust_env=not model.is_local,
        )
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"模型请求失败：{exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型响应缺少 choices[0].message.content") from exc
        return parse_json_object(str(content))


def parse_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1)
        text = re.sub(r"\s*```$", "", text, count=1)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise LLMError("模型没有返回 JSON 对象") from None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"模型 JSON 解析失败：{exc}") from exc
    if not isinstance(value, dict):
        raise LLMError("模型响应必须是 JSON 对象")
    return value
