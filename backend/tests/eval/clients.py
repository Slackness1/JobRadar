"""Eval-side LLM 客户端封装。

3 角色用 3 个 client (跨厂商防 self-judge bias):
  SUT       deepseek-v4-pro   重任务,production 用什么测什么
  Simulator deepseek-v4-flash 轻量多轮 role-play
  Judge     可选 mimo / qwen / deepseek (默认 mimo),通过 EVAL_JUDGE_PROVIDER 切换

所有 client 走 OpenAI-compatible chat completions。Retry:
  - 5xx / connection error → 重试 3 次,2s/4s/8s backoff
  - 429 (rate limit) → 重试 5 次,5s/10s/20s/40s/60s backoff (限流是临时态)
  - 其他 4xx → 不重试 (key/model/payload 问题,重试也没用)
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib import error, request

# 触发 backend/.env.local 加载
import app.config  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMClient:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 120
    label: str = "llm"

    @property
    def chat_completions_url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        response_format: Optional[dict] = None,
        max_retries: int = 3,
    ) -> str:
        """阻塞调一次 chat completions,返回 content 字符串。

        失败时按 retry 策略重试。所有 retry 都失败时抛原始异常。
        """
        if not self.api_key:
            raise RuntimeError(f"[{self.label}] api_key 未配置 (检查 .env.local)")

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        # 429 享 5 次重试 (限流临时态),其他 5xx 享 3 次 (网络问题)
        rate_limit_max_retries = 5
        last_exc: Optional[Exception] = None
        for attempt in range(max(max_retries, rate_limit_max_retries) + 1):
            try:
                req = request.Request(
                    self.chat_completions_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
            except error.HTTPError as exc:
                # 429 是限流(临时态)— 拉长 backoff 多重试
                if exc.code == 429:
                    if attempt >= rate_limit_max_retries:
                        raise
                    last_exc = exc
                    backoff = min(5 * (2 ** attempt), 60)  # 5/10/20/40/60
                    logger.warning(
                        "[%s] HTTP 429 rate-limited on attempt %d, sleeping %ds",
                        self.label, attempt + 1, backoff,
                    )
                    time.sleep(backoff)
                    continue
                # 其他 4xx 不重试 — key/model/payload 问题
                if exc.code < 500 or attempt >= max_retries:
                    raise
                last_exc = exc
            except (error.URLError, TimeoutError) as exc:
                if attempt >= max_retries:
                    raise
                last_exc = exc
            backoff = 2 ** (attempt + 1)
            logger.warning(
                "[%s] %s on attempt %d, retrying in %ds",
                self.label, type(last_exc).__name__, attempt + 1, backoff,
            )
            time.sleep(backoff)

        raise RuntimeError(f"unreachable: last_exc={last_exc}")


def build_sut_client() -> LLMClient:
    return LLMClient(
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model=os.environ.get("EVAL_SUT_MODEL", "deepseek-v4-pro"),
        timeout_seconds=180,
        label="SUT",
    )


def build_simulator_client() -> LLMClient:
    return LLMClient(
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model=os.environ.get("EVAL_SIMULATOR_MODEL", "deepseek-v4-flash"),
        timeout_seconds=120,
        label="SIMULATOR",
    )


def build_judge_client() -> LLMClient:
    """Judge client。

    Provider switchable via EVAL_JUDGE_PROVIDER env:
      mimo (default) | qwen | glm | deepseek

    - mimo: 默认,跨厂商独立 judge,但限流偏紧 (after-fix baseline 35% 429 rate)
    - qwen: dashscope qwen-max,独立 + 限流宽,推荐 SAIF 试点
    - glm: 智谱 glm-4.6,独立 + 推理强,跟 qwen 互为备份
    - deepseek: 与 SUT 同厂商,有 self-judge bias (~10-20% 偏高);仅应急用
    """
    provider = os.environ.get("EVAL_JUDGE_PROVIDER", "mimo").lower()
    if provider == "qwen":
        return LLMClient(
            base_url=os.environ.get(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
            model=os.environ.get("EVAL_JUDGE_MODEL", "qwen-max-latest"),
            timeout_seconds=180,
            label="JUDGE",
        )
    if provider == "glm":
        return LLMClient(
            base_url=os.environ.get(
                "ZHIPU_BASE_URL",
                "https://open.bigmodel.cn/api/paas/v4",
            ),
            api_key=os.environ.get("ZHIPU_API_KEY", ""),
            model=os.environ.get("EVAL_JUDGE_MODEL", "glm-4.6"),
            timeout_seconds=180,
            label="JUDGE",
        )
    if provider == "deepseek":
        return LLMClient(
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            model=os.environ.get("EVAL_JUDGE_MODEL", "deepseek-v4-pro"),
            timeout_seconds=180,
            label="JUDGE",
        )
    return LLMClient(
        base_url=os.environ.get("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1"),
        api_key=os.environ.get("MIMO_API_KEY", ""),
        model=os.environ.get("EVAL_JUDGE_MODEL", "mimo-v2.5-pro"),
        timeout_seconds=180,
        label="JUDGE",
    )
