"""GT 公司反向索引 + KB block 单测。用 tmp fixture 避免依赖真实数据churn。"""
from __future__ import annotations

import json

from app.services.phase_g.quality_cascade.company_kb import (
    build_company_kb_block,
    load_gt_index,
)

_FIXTURE = {
    "ground_truth": {
        "公募权益研究员": [
            {
                "name": "易方达基金",
                "tier": "一线公募",
                "primary_sub_cats": ["公募权益研究员", "公募指数研究员"],
                "industry_focus": ["消费", "医药"],
            }
        ],
        "量化研究员": [
            {
                "name": "易方达基金",
                "tier": "一线公募",
                "primary_sub_cats": ["量化研究员"],
                "industry_focus": [],
            },
            {"name": "九坤投资", "tier": "头部量化私募", "primary_sub_cats": ["量化研究员"]},
        ],
    }
}


def _write_fixture(tmp_path):
    p = tmp_path / "gt.json"
    p.write_text(json.dumps(_FIXTURE, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_index_merges_subcats_across_entries(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    # 易方达基金在两个 sub_cat 下出现 → 合并典型赛道, 去重
    assert idx["易方达基金"]["tier"] == "一线公募"
    assert set(idx["易方达基金"]["sub_cats"]) == {
        "公募权益研究员",
        "公募指数研究员",
        "量化研究员",
    }


def test_kb_block_for_known_company(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    block = build_company_kb_block("易方达基金 · 消费组", index=idx)
    assert "易方达基金" in block
    assert "一线公募" in block
    assert "公募权益研究员" in block


def test_kb_block_empty_for_unknown_company(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    assert build_company_kb_block("某不知名小公司", index=idx) == ""


def test_kb_block_empty_for_blank(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    assert build_company_kb_block("", index=idx) == ""
