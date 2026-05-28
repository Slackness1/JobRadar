"""Phase G T9 — Schema + prompt structure tests for quality_label v2.

Live LLM 调用 (test_real_llm_golden_samples) 标 @pytest.mark.slow, 默认跳。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.crawler_llm_enrich import (
    QUALITY_LABEL_PROMPT_V2,
    QUALITY_LABELS_V2,
    enrich_job_quality_label_v2,
)


def _mock_choice(label: str, reasoning: str = "test reason") -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps(
        {"quality_label": label, "reasoning": reasoning}
    )
    return resp


def _make_job(title: str, duty: str = "", req: str = "", company: str = "Test Co") -> dict:
    return {"company": company, "job_title": title, "job_duty": duty, "job_req": req}


def test_prompt_includes_all_7_labels():
    for label in QUALITY_LABELS_V2:
        assert label in QUALITY_LABEL_PROMPT_V2, f"label {label} 没在 prompt 里"


def test_prompt_mentions_boundary_cases():
    for case in ["客户经理", "实习", "应届"]:
        assert case in QUALITY_LABEL_PROMPT_V2, f"边界 case {case} 没在 prompt 里"


def test_qualilty_labels_v2_count():
    assert len(QUALITY_LABELS_V2) == 7
    assert "support_role" in QUALITY_LABELS_V2
    assert "low_pay" in QUALITY_LABELS_V2
    assert "internship_only" in QUALITY_LABELS_V2


@patch("app.services.crawler_llm_enrich.build_pro_client")
def test_enrich_returns_parsed_label(mock_client):
    instance = mock_client.return_value
    instance.chat.completions.create.return_value = _mock_choice("good", "投研对口")
    result = enrich_job_quality_label_v2(
        _make_job("量化研究员", duty="开发因子模型", req="数学硕士")
    )
    assert result["quality_label"] == "good"
    assert result["reasoning"] == "投研对口"
    # 验证调用了 Pro client + reasoning_effort=medium
    call = instance.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"reasoning_effort": "medium"}
    assert call.kwargs["temperature"] == 0.1
    assert call.kwargs["response_format"] == {"type": "json_object"}


@patch("app.services.crawler_llm_enrich.build_pro_client")
def test_enrich_falls_back_on_unknown_label(mock_client):
    """LLM 偶尔写 invalid label, 必须兜底落 low_signal 不能 raise。"""
    instance = mock_client.return_value
    instance.chat.completions.create.return_value = _mock_choice("not_a_real_label", "x")
    result = enrich_job_quality_label_v2(_make_job("奇怪岗位"))
    assert result["quality_label"] == "low_signal"


@patch("app.services.crawler_llm_enrich.build_pro_client")
def test_enrich_truncates_long_jd(mock_client):
    """job_duty/job_req 长度截断到 1500 防 token 爆炸。"""
    instance = mock_client.return_value
    instance.chat.completions.create.return_value = _mock_choice("good")
    long_duty = "x" * 5000
    enrich_job_quality_label_v2(_make_job("量化", duty=long_duty))
    call = instance.chat.completions.create.call_args
    user_msg = call.kwargs["messages"][-1]["content"]
    # truncated portion should not appear past 1500
    assert "x" * 1500 in user_msg
    assert "x" * 1600 not in user_msg


@pytest.mark.slow
@pytest.mark.skipif(
    not __import__("os").environ.get("DEEPSEEK_API_KEY"),
    reason="needs DEEPSEEK_API_KEY for real LLM call",
)
def test_real_llm_golden_samples():
    """5 个人工标好的样本, 跑真实 LLM 看 7 等级判定。`pytest -m slow` 触发。"""
    samples = [
        (
            _make_job(
                "量化研究员",
                duty="开发中频 alpha 因子, 维护因子库, 跟踪策略表现",
                req="数学/物理/CS 硕士, 熟悉 Python + 多因子",
            ),
            "good",
        ),
        (
            _make_job(
                "银行客户经理",
                duty="销售理财产品, 维护客户关系, 完成销售指标",
                req="本科即可, 有销售经验优先",
            ),
            "support_role",
        ),
        (
            _make_job(
                "暑期实习生 (TMT 卖方研究)",
                duty="协助行业研究员撰写月报, 收集行业数据",
                req="在读硕士, 实习时长 3 个月以上",
            ),
            "internship_only",
        ),
        (
            _make_job(
                "运营助理",
                duty="处理日常运营事务",
                req="大专以上",
                company="某公司",
            ),
            "low_signal",
        ),
    ]
    for job, expected in samples:
        out = enrich_job_quality_label_v2(job)
        assert out["quality_label"] == expected, (
            f"Job {job['job_title']}: expected {expected}, got {out}"
        )
