"""测 DeepSeek dual-schema extractor — mock 掉 OpenAI client。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor
from app.services.taxonomy_discovery.schemas import StrategyType


@pytest.fixture
def extractor(tmp_path) -> DualSchemaExtractor:
    tracker = BudgetTracker(state_file=tmp_path / "b.json", limit_usd=10.0)
    return DualSchemaExtractor(
        api_key="fake_deepseek_key",
        budget_tracker=tracker,
    )


def _mock_llm_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=2000, completion_tokens=800)
    return resp


def test_extract_returns_valid_dual_schema(extractor: DualSchemaExtractor) -> None:
    fake_response = json.dumps({
        "post_id": "abc",
        "url": "https://xhs.com/n/abc",
        "time": "2026-05-01T12:00:00",
        "author": "u1",
        "relevance_score": 0.8,
        "taxonomy": {
            "strategy_signals": [{"canonical": "基本面权益", "verbatim_phrase": "消费组"}],
            "industry_signals": [],
            "institution_signals": [],
            "discovered_sub_categories": ["消费组"],
            "company_role_pairs": [],
            "dimension_distinctions": [],
        },
        "kb": {"insights": []},
        "extraction_confidence": 0.9,
    })
    with patch("app.services.taxonomy_discovery.llm_extractor.OpenAI") as MockClient:
        client_inst = MockClient.return_value
        client_inst.chat.completions.create.return_value = _mock_llm_response(fake_response)
        result = extractor.extract(
            post_id="abc",
            url="https://xhs.com/n/abc",
            time="2026-05-01T12:00:00",
            author="u1",
            content="嘉实基金消费组实习, 主要做白酒研究",
            comments_text=[],
        )
    assert result.taxonomy.strategy_signals[0].canonical == StrategyType.基本面权益
    assert extractor.budget_tracker.spent() > 0  # 抽取扣了钱


def test_extract_handles_malformed_json(extractor: DualSchemaExtractor) -> None:
    """LLM 偶尔回 non-JSON, extractor 必须 graceful 返 low-confidence 空记录。"""
    with patch("app.services.taxonomy_discovery.llm_extractor.OpenAI") as MockClient:
        client_inst = MockClient.return_value
        client_inst.chat.completions.create.return_value = _mock_llm_response("not a json {{{")
        result = extractor.extract(
            post_id="abc",
            url="https://xhs.com/n/abc",
            time="2026-05-01T12:00:00",
            author="u1",
            content="random",
            comments_text=[],
        )
    assert result.relevance_score == 0.0  # malformed → 默认无信号
    assert result.extraction_confidence == 0.0  # 标记 fail
