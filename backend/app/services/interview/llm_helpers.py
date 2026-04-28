"""Thin wrappers over the resume-copilot LLM client for interview modules.

Two helpers — `chat_json` and `chat_text` — that the scoring / reference /
adaptive / voice-confidence modules all call. They share the byte-stable
system message convention so DeepSeek prompt cache hits across calls.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import request

from app.services.resume_copilot.llm import build_resume_llm_client


class _HTTP(Protocol):
    def post(self, url: str, headers: dict, body: bytes, timeout: int) -> str: ...


class _UrllibHTTP:
    def post(self, url: str, headers: dict, body: bytes, timeout: int) -> str:
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")


@dataclass(slots=True)
class InterviewLLMClient:
    api_key: str
    base_url: str
    model: str
    timeout: int = 30
    http: _HTTP = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.http is None:
            self.http = _UrllibHTTP()

    def _post(self, payload: dict) -> str:
        body = json.dumps(payload).encode("utf-8")
        return self.http.post(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout=self.timeout,
        )

    def _extract_content(self, raw_response: str) -> str:
        try:
            body = json.loads(raw_response)
            return body["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return ""

    def chat_json(self, system: str, user: str, **_kwargs) -> dict:
        """Call LLM with JSON-mode forced. Returns {} on any failure."""
        raw = self._post({
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        })
        content = self._extract_content(raw)
        try:
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {}

    def chat_text(self, system: str, user: str, **_kwargs) -> str:
        """Call LLM expecting a free-form text response. Returns '' on failure."""
        raw = self._post({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        })
        return self._extract_content(raw)


def build_interview_llm_client() -> InterviewLLMClient:
    """Build with default config from the resume-copilot LLM env."""
    base_client = build_resume_llm_client()
    return InterviewLLMClient(
        api_key=base_client.api_key,
        base_url=base_client.base_url,
        model=base_client.model,
        timeout=base_client.timeout_seconds,
    )
