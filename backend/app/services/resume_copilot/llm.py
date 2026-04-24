from dataclasses import dataclass

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


def build_resume_llm_client() -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        base_url=config.RESUME_COPILOT_LLM_BASE_URL,
        api_key=config.RESUME_COPILOT_LLM_API_KEY,
        model=config.RESUME_COPILOT_LLM_MODEL,
        timeout_seconds=config.RESUME_COPILOT_LLM_TIMEOUT_SECONDS,
    )
