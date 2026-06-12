"""Thin wrapper around build_resume_llm_client for non-streaming JSON-mode calls.

Cache-friendliness contract: callers MUST put fixed instructions in the system
message and variable data in the user message. DeepSeek caches identical message
prefixes — keeping the system prompt byte-stable across calls maximizes hits.
"""
import json
from typing import Optional
from urllib import request as urllib_request

from app.services.resume_copilot.llm import build_resume_llm_client


def call_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: float = 0.2,
) -> str:
    client = build_resume_llm_client(model=model)
    payload: dict = {
        "model": client.model,
        "stream": False,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
            # OpenCode 中转前置防火墙按 UA 封 Python-urllib(403)— 带浏览器 UA 放行
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=client.timeout_seconds) as r:
        body = json.loads(r.read().decode("utf-8"))
    try:
        from app.services.llm_quota import record_usage_from_response_for_current
        record_usage_from_response_for_current('interview_nowcoder', body)
    except Exception:
        pass
    return body["choices"][0]["message"]["content"]
