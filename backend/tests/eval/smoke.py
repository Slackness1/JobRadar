"""三模型连通性烟雾测试。

跑法（在 backend/ 下）：
    PYTHONPATH=. .venv/bin/python tests/eval/smoke.py

每个模型发一句"用三个字回答 JobRadar 是什么"，打印 OK / FAIL + 内容片段。
不入正式 pytest 套件 —— 这个脚本仅为了验证三把 key 都能 ping 通。
"""
from __future__ import annotations

import json
import os
import sys
from urllib import request, error

# 触发 _load_local_env_file 加载 backend/.env.local
import app.config  # noqa: F401


PROBE_PROMPT = "请用三个字回答：什么是面试？"


def _post(base_url: str, api_key: str, model: str, prompt: str, timeout: int = 120) -> dict:
    payload = {
        "model": model,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _probe(label: str, base_url: str, api_key: str, model: str) -> bool:
    print(f"[{label:<10}] {model:<25}", end=" ", flush=True)
    if not api_key:
        print("SKIP (no api key)")
        return False
    try:
        body = _post(base_url, api_key, model, PROBE_PROMPT)
        content = body["choices"][0]["message"]["content"].strip().replace("\n", " ")
        usage = body.get("usage", {})
        print(f"OK · {content[:40]!r} · in={usage.get('prompt_tokens', '?')} out={usage.get('completion_tokens', '?')}")
        return True
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:200]
        print(f"FAIL · HTTP {exc.code} · {body}")
        return False
    except Exception as exc:
        print(f"FAIL · {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    mimo_key = os.environ.get("MIMO_API_KEY", "")
    mimo_base = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")

    sut_model = os.environ.get("EVAL_SUT_MODEL", "deepseek-v4-pro")
    sim_model = os.environ.get("EVAL_SIMULATOR_MODEL", "deepseek-v4-flash")
    judge_model = os.environ.get("EVAL_JUDGE_MODEL", "mimo-v2.5-pro")

    print(f"DEEPSEEK_BASE_URL = {deepseek_base}")
    print(f"MIMO_BASE_URL     = {mimo_base}")
    print()

    results = [
        _probe("SUT",       deepseek_base, deepseek_key, sut_model),
        _probe("SIMULATOR", deepseek_base, deepseek_key, sim_model),
        _probe("JUDGE",     mimo_base,     mimo_key,     judge_model),
    ]

    print()
    if all(results):
        print("✓ 全 3 模型可达")
        return 0
    print("✗ 至少 1 个模型不可达 — 检查 .env.local")
    return 1


if __name__ == "__main__":
    sys.exit(main())
