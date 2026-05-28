"""Phase G T11 — Multi-pass C sub_cat enricher unit tests (mocked LLM)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models import Job
from app.services.phase_g.sub_cat_enricher import (
    STRATEGY_TYPES,
    enrich_job_sub_cat,
    pass1_classify_strategy,
    pass2_classify_subcat,
)


def _mock_resp(payload: dict) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = json.dumps(payload)
    return r


def test_strategy_types_7():
    assert len(STRATEGY_TYPES) == 7
    assert "AI 应用_PM_开发" in STRATEGY_TYPES  # 注意空格


@patch("app.services.phase_g.sub_cat_enricher.build_pro_client")
def test_pass1_returns_strategy_known(mock_client_fn):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_resp(
        {"strategy_type": "量化", "confidence": 0.92, "reasoning": "因子 + sharpe"}
    )
    mock_client_fn.return_value = mock_client
    out = pass1_classify_strategy({
        "company": "九坤", "job_title": "量化研究员",
        "job_duty": "中频 alpha", "job_req": "数学硕士",
    })
    assert out["strategy_type"] == "量化"
    assert out["confidence"] == 0.92
    # 验证调用了 Pro client + reasoning_effort=high
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"reasoning_effort": "high"}


@patch("app.services.phase_g.sub_cat_enricher.build_pro_client")
def test_pass1_unknown_strategy_treated_as_null(mock_client_fn):
    """LLM 写了不在 7 大类的 strategy → 兜底 null + confidence 0。"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_resp(
        {"strategy_type": "FAKE_STRATEGY", "confidence": 0.9, "reasoning": "x"}
    )
    mock_client_fn.return_value = mock_client
    out = pass1_classify_strategy({"company": "x", "job_title": "y"})
    assert out["strategy_type"] is None
    assert out["confidence"] == 0


@patch("app.services.phase_g.sub_cat_enricher._gather_subcat_candidates")
@patch("app.services.phase_g.sub_cat_enricher.build_pro_client")
def test_pass2_unknown_sub_cat_clears_to_null(mock_client_fn, mock_gather):
    """Pass 2 LLM 写了不存在的 sub_cat → 兜底 None + conf 0。"""
    mock_gather.return_value = (["量化研究员·中频", "量化研究员·高频"], "candidates text")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_resp(
        {"sub_category": "FAKE_SUB", "confidence": 0.9, "reasoning": "x"}
    )
    mock_client_fn.return_value = mock_client
    out = pass2_classify_subcat(
        {"company": "x", "job_title": "y"}, strategy_type="量化"
    )
    assert out["sub_category"] is None
    assert out["confidence"] == 0


@patch("app.services.phase_g.sub_cat_enricher.pass2_classify_subcat")
@patch("app.services.phase_g.sub_cat_enricher.pass1_classify_strategy")
def test_enrich_full_pipeline(mock_p1, mock_p2):
    mock_p1.return_value = {"strategy_type": "量化", "confidence": 0.92, "reasoning": "x"}
    mock_p2.return_value = {
        "sub_category": "量化研究员·中频",
        "sub_category_secondary": None,
        "industry_focus": ["A股权益"],
        "institution_tier": "头部量化私募",
        "confidence": 0.88,
        "reasoning": "y",
    }
    job = Job(id=1, company="九坤投资", job_title="量化研究员", job_duty="中频", job_req="硕士")
    result = enrich_job_sub_cat(job)
    assert result is not None
    assert result["sub_category"] == "量化研究员·中频"
    assert result["institution_tier"] == "头部量化私募"
    # geo mean of 0.92 * 0.88 ≈ 0.8995
    assert 0.89 < result["sub_cat_confidence"] < 0.91
    # industry_focus 应该是 JSON array str
    assert json.loads(result["industry_focus"]) == ["A股权益"]
    # reasoning 应该拼了 P1 + P2 的 reasoning
    assert "P1[量化" in result["sub_cat_reasoning"]
    assert "P2:" in result["sub_cat_reasoning"]


@patch("app.services.phase_g.sub_cat_enricher.pass1_classify_strategy")
def test_enrich_returns_none_on_off_target(mock_p1):
    """Pass 1 strategy 是 null → None (非 SAIF 目标岗, leave sub_category NULL)。"""
    mock_p1.return_value = {"strategy_type": None, "confidence": 0, "reasoning": "off"}
    job = Job(id=2, company="某央企", job_title="工程师")
    assert enrich_job_sub_cat(job) is None


@patch("app.services.phase_g.sub_cat_enricher.pass1_classify_strategy")
def test_enrich_returns_none_on_low_pass1_confidence(mock_p1):
    """Pass 1 confidence < 0.5 (LLM 自己也不确定) → None。"""
    mock_p1.return_value = {"strategy_type": "量化", "confidence": 0.3, "reasoning": "low"}
    job = Job(id=3, company="某机构", job_title="数据分析")
    assert enrich_job_sub_cat(job) is None


@patch("app.services.phase_g.sub_cat_enricher.pass2_classify_subcat")
@patch("app.services.phase_g.sub_cat_enricher.pass1_classify_strategy")
def test_enrich_returns_none_on_pass2_failure(mock_p1, mock_p2):
    """Pass 2 sub_category None → None (caller 跳过)。"""
    mock_p1.return_value = {"strategy_type": "量化", "confidence": 0.9, "reasoning": "x"}
    mock_p2.return_value = {"sub_category": None, "confidence": 0, "reasoning": "x"}
    job = Job(id=4, company="x", job_title="y")
    assert enrich_job_sub_cat(job) is None
