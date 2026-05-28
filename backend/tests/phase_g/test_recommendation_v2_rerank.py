"""Phase G T16 — LLM rerank with 知识库 测试 (mocked LLM)。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models import Job
from app.services.phase_g.recommendation_v2.rerank import (
    RERANK_SYSTEM_PROMPT,
    rerank_one,
    rerank_top_n,
)


def _mock_resp(payload: dict) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = json.dumps(payload)
    return r


def _student(**kwargs) -> dict:
    base = {
        "name": "P_test",
        "background": "海外 Top30 硕士, 卖方 TMT 1 段实习",
        "hidden_highlights": ["独立完成 200 亿市值标的深度报告", "草根调研"],
        "preferred_sub_cats": ["公募权益研究员"],
    }
    base.update(kwargs)
    return base


def _job(**kwargs) -> Job:
    base = dict(
        job_id="j1", company="易方达基金", job_title="行业研究员",
        sub_category="公募权益研究员", institution_tier="一线公募",
        industry_focus='["消费"]', job_duty="覆盖消费股", job_req="硕士 + 实习",
    )
    base.update(kwargs)
    return Job(**base)


def test_prompt_mentions_judging_principles():
    for kw in ["hard_requirements", "hidden_highlights", "pitfalls", "data_confidence"]:
        assert kw in RERANK_SYSTEM_PROMPT
    # 禁止模板话
    assert "禁止" in RERANK_SYSTEM_PROMPT


def test_rerank_one_falls_back_when_kb_missing():
    """无 KB row (空 sub_category 或 KB 表 0 row) → score=50 + 提示, 不调 LLM。"""
    with patch(
        "app.services.phase_g.recommendation_v2.rerank._gather_kb_row",
        return_value=None,
    ):
        out = rerank_one(_student(), _job(sub_category=""))
    assert out["score"] == 50
    assert "知识库未覆盖" in out["reasoning"]
    assert out["kb_available"] is False


@patch("app.services.phase_g.recommendation_v2.rerank.build_pro_client")
@patch("app.services.phase_g.recommendation_v2.rerank._gather_kb_row")
def test_rerank_one_with_kb_calls_llm(mock_kb, mock_client_fn):
    mock_kb.return_value = {
        "hard_requirements": ["海外硕士 + 1 段卖方实习"],
        "soft_signals": ["草根调研"],
        "pitfalls": ["限薪 / 自购"],
        "verbatim_quotes": [{"quote": "推票面试是核心"}],
        "_data_confidence": "medium",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_resp({
        "score": 88, "reasoning": "你的卖方 TMT 实习 + 深度报告与硬门槛对齐, 一线公募 fit"
    })
    mock_client_fn.return_value = mock_client

    out = rerank_one(_student(), _job())
    assert out["score"] == 88
    assert "卖方" in out["reasoning"]
    assert out["kb_available"] is True
    assert out["data_confidence"] == "medium"
    # 验证调用了 Pro client + reasoning_effort=high
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"reasoning_effort": "high"}
    assert call.kwargs["temperature"] == 0.2


@patch("app.services.phase_g.recommendation_v2.rerank.build_pro_client")
@patch("app.services.phase_g.recommendation_v2.rerank._gather_kb_row")
def test_rerank_one_clips_score_to_range(mock_kb, mock_client_fn):
    """LLM 写 >100 或 <0 自动 clip 到 [0, 100]。"""
    mock_kb.return_value = {"hard_requirements": [], "_data_confidence": "medium"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_resp(
        {"score": 150, "reasoning": "x"}
    )
    mock_client_fn.return_value = mock_client
    out = rerank_one(_student(), _job())
    assert out["score"] == 100


@patch("app.services.phase_g.recommendation_v2.rerank.rerank_one")
def test_rerank_top_n_only_calls_llm_for_top_n(mock_rerank):
    mock_rerank.side_effect = lambda profile, job: {
        "score": 90, "reasoning": "ok", "kb_available": True, "data_confidence": "high",
    }
    ranked = [(_job(job_id=f"j{i}"), 0.8 - i * 0.05) for i in range(10)]
    out = rerank_top_n(_student(), ranked, n=3)
    # 只前 3 调 rerank_one
    assert mock_rerank.call_count == 3
    # 前 3 final_score = 0.7*0.9 + 0.3*base = 0.63 + 0.3*base
    top3 = [o for o in out if o["llm_score"] is not None]
    assert len(top3) == 3
    others = [o for o in out if o["llm_score"] is None]
    assert len(others) == 7
    # 全部排序按 final_score desc
    for i in range(len(out) - 1):
        assert out[i]["final_score"] >= out[i + 1]["final_score"]


@patch("app.services.phase_g.recommendation_v2.rerank.rerank_one")
def test_rerank_top_n_swallows_exception(mock_rerank):
    """rerank_one 抛错 → 兜底 score=50, final_score 仍可算, 不破坏 batch。"""
    def raising(_p, job):
        if job.job_id == "j1":
            raise RuntimeError("simulated LLM fail")
        return {"score": 80, "reasoning": "ok", "kb_available": True, "data_confidence": "high"}
    mock_rerank.side_effect = raising
    ranked = [(_job(job_id="j0"), 0.8), (_job(job_id="j1"), 0.7), (_job(job_id="j2"), 0.6)]
    out = rerank_top_n(_student(), ranked, n=3)
    fail_entry = next(o for o in out if o["job"].job_id == "j1")
    assert fail_entry["llm_score"] == 50
    assert "rerank 失败" in fail_entry["llm_reasoning"]
