from __future__ import annotations

import os
import tomllib
from pathlib import Path
from urllib.parse import urlparse

import tomli_w
from platformdirs import user_config_dir, user_data_dir
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str = "openai_compatible"
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3:8b"
    api_key_env: str = "JOBRADAR_LLM_API_KEY"
    timeout_seconds: int = Field(default=60, ge=5, le=300)

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    @property
    def is_local(self) -> bool:
        host = (urlparse(self.base_url).hostname or "").lower()
        return host in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}


class PrivacyConfig(BaseModel):
    telemetry: bool = False
    persist_prompt_bodies: bool = False
    allow_remote_model: bool = False


class JobsConfig(BaseModel):
    max_results: int = Field(default=100, ge=10, le=500)
    stale_after_days: int = Field(default=45, ge=1, le=3650)


class AppConfig(BaseModel):
    data_dir: Path
    model: ModelConfig = Field(default_factory=ModelConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    jobs: JobsConfig = Field(default_factory=JobsConfig)

    @property
    def config_path(self) -> Path:
        return config_path()


def config_dir() -> Path:
    override = os.environ.get("JOBRADAR_CONFIG_HOME", "").strip()
    return Path(override).expanduser() if override else Path(user_config_dir("jobradar"))


def default_data_dir() -> Path:
    override = os.environ.get("JOBRADAR_HOME", "").strip()
    return Path(override).expanduser() if override else Path(user_data_dir("jobradar"))


def config_path() -> Path:
    return config_dir() / "config.toml"


def default_config(data_dir: Path | None = None) -> AppConfig:
    return AppConfig(data_dir=(data_dir or default_data_dir()).expanduser())


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_path()
    if not path.exists():
        return default_config()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    if "data_dir" in raw:
        raw["data_dir"] = Path(raw["data_dir"]).expanduser()
    return AppConfig.model_validate(raw)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    data["data_dir"] = str(config.data_dir)
    temp = path.with_suffix(".tmp")
    temp.write_text(tomli_w.dumps(data), encoding="utf-8")
    temp.replace(path)
    return path
