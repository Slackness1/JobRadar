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
    # 新契约: 4 个 anchor 必须彼此不同, 严禁复制粘贴同一句话(修「三条一样」)
    assert "至少写 3 个" in NARRATIVE_SYSTEM_PROMPT
    assert "严禁把同一句话复制到多个 anchor" in NARRATIVE_SYSTEM_PROMPT


def test_prompt_has_anti_fabrication_rule():
    # 防编造铁律: 无对口经历必须如实说, 绝不杜撰(修深挖给学生安不存在的投研资历)
    assert "不编造" in NARRATIVE_SYSTEM_PROMPT
    assert "暂无直接对口" in NARRATIVE_SYSTEM_PROMPT
    # prompt 不再含可被照抄的具体伪资历示例
    assert "你独立做的 200 亿市值消费股深度报告" not in NARRATIVE_SYSTEM_PROMPT


def test_generate_returns_distinct_anchor_points():
    """KB 存在 + LLM 返结构化 anchors → 解析出彼此不同的 anchor_points + narrative。"""
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
        "app.services.phase_g.recommendation_v2.narrative.build_interactive_client"
    ) as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_resp({
            "anchors": [
                {"key": "A", "text": "你独立做的 200 亿市值消费股深度报告契合本岗"},
                {"key": "B", "text": "一线公募留用差异在'推票面试是核心'"},
                {"key": "C", "text": "本岗硬门槛是 1 段卖方实习, 你已有"},
                {"key": "D", "text": "差距: 缺一次推票模拟, 用易方达内推补"},
            ],
            "narrative": "你独立做的 200 亿市值消费股深度报告对齐本岗硬门槛。",
        })
        mock_client_fn.return_value = mock_client

        out = generate_narrative(_student(), _job(), llm_rerank={"score": 88, "reasoning": "x"})

    assert "200 亿" in out["narrative"]
    assert set(out["anchors_used"]) == {"A", "B", "C", "D"}
    # 核心: 4 条 anchor 文本彼此不同
    texts = [p["text"] for p in out["anchor_points"]]
    assert len(texts) == 4
    assert len(set(texts)) == 4
    assert out["kb_available"] is True
    assert out["data_confidence"] == "medium"


def test_generate_dedupes_identical_anchor_texts():
    """LLM 偷懒把同一句话复制到多个 anchor → 去重, 不再「三条一样」。"""
    fake_kb = {
        "hard_requirements": [], "verbatim_quotes": [], "pitfalls": [],
        "institution_tier_candidates": [], "_data_confidence": "low",
    }
    with patch(
        "app.services.phase_g.recommendation_v2.narrative._gather_kb_payload",
        return_value=fake_kb,
    ), patch(
        "app.services.phase_g.recommendation_v2.narrative.build_interactive_client"
    ) as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_resp({
            "anchors": [
                {"key": "A", "text": "你和这个岗位很匹配"},
                {"key": "B", "text": "你和这个岗位很匹配"},  # 复制
                {"key": "C", "text": "你和这个岗位很匹配"},  # 复制
                {"key": "D", "text": "但你缺低延迟工程经验"},
            ],
            "narrative": "综合理由",
        })
        mock_client_fn.return_value = mock_client
        out = generate_narrative(_student(), _job())
    # 复制的两条被去重, 只剩 2 条不同的
    texts = [p["text"] for p in out["anchor_points"]]
    assert len(texts) == 2
    assert len(set(texts)) == 2


def test_generate_returns_placeholder_when_no_kb():
    with patch(
        "app.services.phase_g.recommendation_v2.narrative._gather_kb_payload",
        return_value=None,
    ):
        out = generate_narrative(_student(), _job(sub_category=""))
    assert "知识库覆盖有限" in out["narrative"]
    assert out["anchors_used"] == []
    assert out["kb_available"] is False


def test_generate_filters_invalid_anchor_keys():
    """LLM 写了 'E' / 'X' 这种无效 anchor key → 过滤掉, 只保留 A/B/C/D。"""
    fake_kb = {
        "hard_requirements": [], "verbatim_quotes": [], "pitfalls": [],
        "institution_tier_candidates": [], "_data_confidence": "low",
    }
    with patch(
        "app.services.phase_g.recommendation_v2.narrative._gather_kb_payload",
        return_value=fake_kb,
    ), patch(
        "app.services.phase_g.recommendation_v2.narrative.build_interactive_client"
    ) as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_resp({
            "anchors": [
                {"key": "a", "text": "锚点甲"},   # 小写归一化
                {"key": "B", "text": "锚点乙"},
                {"key": "E", "text": "无效锚点 E"},  # 无效 key
                {"key": "X", "text": "无效锚点 X"},  # 无效 key
            ],
            "narrative": "...",
        })
        mock_client_fn.return_value = mock_client
        out = generate_narrative(_student(), _job())
    # 只剩 A/B (小写 a 归一化大写, E/X 被过滤)
    assert set(out["anchors_used"]) == {"A", "B"}
