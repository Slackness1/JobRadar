from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobradar_core.config import AppConfig, default_config, save_config


class FakeLLM:
    async def complete_json(self, *, system: str, user: str) -> dict:
        assert "不得编造" in system
        payload = json.loads(user)
        block = payload["resume_evidence"][0]
        return {
            "summary": "已有后端与 Agent 项目证据，建议把动作和交付结果前置。",
            "strengths": ["具备 Python 和 Agent 项目经验"],
            "gaps": ["尚未体现 WebSocket"],
            "patches": [
                {
                    "target_block_id": block["block_id"],
                    "before": block["text"],
                    "after": f"负责交付：{block['text']}",
                    "intent": "wording",
                    "evidence_refs": [block["source_ref"]],
                    "rationale": "把动作和交付对象前置，不增加新事实。",
                }
            ],
        }


@pytest.fixture
def app_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    monkeypatch.setenv("JOBRADAR_HOME", str(data_dir))
    monkeypatch.setenv("JOBRADAR_CONFIG_HOME", str(config_dir))
    config = default_config(data_dir)
    save_config(config)
    return config


@pytest.fixture
def resume_file(tmp_path: Path) -> Path:
    path = tmp_path / "resume.md"
    path.write_text(
        """# 周同学

## 项目经历
使用 Python 构建求职 Agent，负责岗位召回、工具调用和简历优化。
设计 SQLite 数据模型和可追溯的运行记录。
""",
        encoding="utf-8",
    )
    return path
