from dataclasses import dataclass
from typing import Optional

from app import config


@dataclass(slots=True)
class OpenAICompatibleLLMClient:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url}/chat/completions"


# 官方 DeepSeek 直连只认这两个模型名;中转的 deepseek-v4-flash/pro 在官方不存在。
_OFFICIAL_MODELS = {"deepseek-chat", "deepseek-reasoner"}


def _to_official_model(model: Optional[str]) -> str:
    """把调用方传入的模型名映射到交互专线(官方)可用的名字。

    - 交互专线未独立配置(INTERACTIVE 回落 RESUME_COPILOT)→ 不映射,保持旧行为。
    - 已是官方名(改写/打分显式传 deepseek-reasoner)→ 原样。
    - 中转名(deepseek-v4-flash/pro)或空 → 回落默认快档 deepseek-chat。
    """
    m = (model or "").strip()
    if config.INTERACTIVE_LLM_BASE_URL == config.RESUME_COPILOT_LLM_BASE_URL:
        return m or config.RESUME_COPILOT_LLM_MODEL
    if m in _OFFICIAL_MODELS:
        return m
    return config.INTERACTIVE_LLM_MODEL


def build_resume_llm_client(*, model: Optional[str] = None) -> OpenAICompatibleLLMClient:
    # 2026-06-15:学生交互链路走"低延迟专线"(INTERACTIVE_LLM_* = 官方直连);
    # 未配置专线时回落 RESUME_COPILOT_*,字节等价旧版。
    return OpenAICompatibleLLMClient(
        base_url=config.INTERACTIVE_LLM_BASE_URL,
        api_key=config.INTERACTIVE_LLM_API_KEY,
        model=_to_official_model(model),
        timeout_seconds=config.INTERACTIVE_LLM_TIMEOUT_SECONDS,
    )
