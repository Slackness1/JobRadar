"""Phase G T17 — narrative 4 anchor 模板测试 (mocked LLM)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.models import Job
from app.services.phase_g.recommendation_v2.narrative import (
    NARRATIVE_SYSTEM_PROMPT,
    generate_narrative,
)


def _mock_resp(payload: dict) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = json.dumps(payload)
    return r


def _student() -> dict:
    return {
        "name": "P_test",
        "background": "海外 Top30 硕士, 卖方 TMT 1 段实习",
        "hidden_highlights": ["独立完成 200 亿市值消费股深度报告", "草根调研"],
    }


def _job(**kw) -> Job:
    base = dict(
        job_id="x", company="易方达基金", job_title="行业研究员",
        sub_category="公募权益研究员", institution_tier="一线公募",
    )
    base.update(kw)
    return Job(**base)


def test_prompt_mentions_4_anchors_explicitly():
    for anchor_label in ["Anchor A", "Anchor B", "Anchor C", "Anchor D"]:
        assert anchor_label in NARRATIVE_SYSTEM_PROMPT
    assert "至少引用 3 个" in NARRATIVE_SYSTEM_PROMPT
    assert "≤200 字" in NARRATIVE_SYSTEM_PROMPT


def test_generate_returns_narrative_with_anchors():
    """KB 存在 + LLM 返合理 narrative → 解析出 narrative + anchors_used。"""
    fake_kb = {
        "hard_requirements": ["海外硕士 + 1 段卖方实习", "200 亿市值标的深度报告"],
        "verbatim_quotes": [{"quote": "推票面试是核心 — 给具体价格和时点"}],
        "pitfalls": ["限薪 + 30% 自购"],
        "institution_tier_candidates": ["一线公募", "二线公募"],
        "_data_confidence": "medium",
    }
    with patch(
        "app.services.phase_g.recommendation_v2.narrative._gather_kb_payload",
        return_value=fake_kb,
    ), patch(
        "app.services.phase_g.recommendation_v2.narrative.build_pro_client"
    ) as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_resp({
            "narrative": "你独立做的 200 亿市值消费股深度报告对齐本岗硬门槛 (公募投研实习+大市值标的)。一线公募有'推票面试是核心'的留用差异, 你的草根调研补足这点。差距: 缺一次推票模拟, 用易方达内推补。",
            "anchors_used": ["A", "B", "C", "D"],
        })
        mock_client_fn.return_value = mock_client

        out = generate_narrative(_student(), _job(), llm_rerank={"score": 88, "reasoning": "x"})

    assert "200 亿" in out["narrative"]
    assert "A" in out["anchors_used"]
    assert "B" in out["anchors_used"]
    assert "C" in out["anchors_used"]
    assert "D" in out["anchors_used"]
    assert out["kb_available"] is True
    assert out["data_confidence"] == "medium"
    # 调用了 Pro client + reasoning_effort=medium + temperature 0.3
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"reasoning_effort": "medium"}
    assert call.kwargs["temperature"] == 0.3


def test_generate_returns_placeholder_when_no_kb():
    with patch(
        "app.services.phase_g.recommendation_v2.narrative._gather_kb_payload",
        return_value=None,
    ):
        out = generate_narrative(_student(), _job(sub_category=""))
    assert "知识库覆盖有限" in out["narrative"]
    assert out["anchors_used"] == []
    assert out["kb_available"] is False


def test_generate_filters_invalid_anchors():
    """LLM 写了 'E' / 'X' 这种无效 anchor → 过滤掉, 只保留 A/B/C/D。"""
    fake_kb = {
        "hard_requirements": [], "verbatim_quotes": [], "pitfalls": [],
        "institution_tier_candidates": [], "_data_confidence": "low",
    }
    with patch(
        "app.services.phase_g.recommendation_v2.narrative._gather_kb_payload",
        return_value=fake_kb,
    ), patch(
        "app.services.phase_g.recommendation_v2.narrative.build_pro_client"
    ) as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_resp({
            "narrative": "...",
            "anchors_used": ["A", "B", "E", "X", "junk", "c"],  # 包含无效 + 小写
        })
        mock_client_fn.return_value = mock_client
        out = generate_narrative(_student(), _job())
    # 应该只剩 A/B/C (小写 c 归一化大写)
    assert set(out["anchors_used"]) == {"A", "B", "C"}
