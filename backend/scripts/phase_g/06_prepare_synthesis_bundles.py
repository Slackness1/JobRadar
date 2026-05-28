"""T6 prep: 给剩 24 个 sub_cat 各自生成 self-contained 输入 bundle 文件,
方便 batch subagent 并行跑——每个 subagent 只读 1 个 bundle 写 1 个 synth_*.json。

输出: backend/data/_phase_g/synthesis_bundles/{slug}.json
schema:
  - sub_cat, strategy_type, sub_cat_slug
  - posts (list of {source_url, content, company_mentions, verbatim_signals, relevance_score, extracted})
  - saif_records (list)
  - ground_truth (list)
  - data_basis (post_count / company_mention_count / saif_alumni_count)
  - expected_data_confidence
  - user_message (pre-built prompt ready to feed Opus)
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import app.config  # noqa: F401

from app.services.phase_g.knowledge_synthesis import (
    SUBCAT_TO_STRATEGY,
    build_synthesis_user_message,
    compute_data_basis,
    expected_data_confidence,
    gather_ground_truth_for_subcat,
    gather_posts_for_subcat,
    gather_saif_alumni_for_subcat,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE_DIR = BACKEND_ROOT / "data" / "_phase_g" / "synthesis_bundles"
SYNTH_DIR = BACKEND_ROOT / "data" / "_phase_g" / "synthesis"

# 已 T5 完成的 5 个 sub_cat (按 synth file 实际名)
DONE_SUBCATS = {
    "AI PM",
    "PE投后VC行研",
    "公募权益研究员",
    "卖方研究员·TMT",
    "量化研究员·中频",
}

# sub_cat → slug 显式映射 (中文无 ascii 表达, 不能机械 slugify)
SLUG_MAP: dict[str, str] = {
    "公募权益研究员": "public_equity_researcher",
    "行业研究员·消费": "industry_researcher_consumer",
    "行业研究员·TMT-医药-周期": "industry_researcher_tmt_pharma_cyclical",
    "公募指数研究员": "public_index_researcher",
    "公募基金中后台": "public_fund_middle_back_office",
    "量化研究员·中频": "quant_researcher_mid_freq",
    "量化研究员·高频": "quant_researcher_high_freq",
    "量化开发QD": "quant_developer_qd",
    "AI 量化工程师": "ai_quant_engineer",
    "量化因子工程师": "quant_factor_engineer",
    "信用研究员": "credit_researcher",
    "固收交易员": "fixed_income_trader",
    "固收+多资产": "fixed_income_plus_multi_asset",
    "利率宏观策略": "rates_macro_strategy",
    "卖方研究员·TMT": "sell_side_researcher_tmt",
    "卖方研究员·消费医药周期": "sell_side_researcher_consumer_pharma_cyclical",
    "卖方研究员·宏观策略": "sell_side_researcher_macro_strategy",
    "买方 Quant": "buy_side_quant",
    "投行 IBD": "investment_banking_ibd",
    "资管FOF": "asset_management_fof",
    "自营FOF": "proprietary_fof",
    "财富管理FOF": "wealth_management_fof",
    "结构化产品衍生品": "structured_products_derivatives",
    "PE投后VC行研": "pe_post_inv_vc_industry_research",
    "LLM算法post-train": "llm_algorithm_posttrain",
    "Agent工程师": "agent_engineer",
    "多模态推理优化": "multimodal_inference_optimization",
    "AI PM": "ai_product_manager",
    "AI算法业务": "ai_algorithm_business",
}


def _safe_filename(s: str) -> str:
    """sub_cat 中文 → 安全文件名 (保留中文, 去 / \\ : 等)"""
    return "".join(c if c.isalnum() or c in "·-+_" else "_" for c in s)


def main() -> int:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)

    all_subcats = list(SUBCAT_TO_STRATEGY.keys())
    remaining = [s for s in all_subcats if s not in DONE_SUBCATS]
    print(f"总 sub_cat: {len(all_subcats)}")
    print(f"已完成 (T5 pilot): {len(DONE_SUBCATS)}")
    print(f"待 T6 处理: {len(remaining)}")
    print()

    written = 0
    skipped_low_data = []
    for sub_cat in remaining:
        strategy = SUBCAT_TO_STRATEGY[sub_cat]
        slug = SLUG_MAP.get(sub_cat) or f"unknown_{_safe_filename(sub_cat)}"
        posts = gather_posts_for_subcat(sub_cat)
        saif = gather_saif_alumni_for_subcat(sub_cat)
        gt = gather_ground_truth_for_subcat(sub_cat)
        basis = compute_data_basis(posts, saif)
        conf = expected_data_confidence(basis)
        user_msg = build_synthesis_user_message(sub_cat, strategy, posts, saif, gt)

        bundle = {
            "sub_cat": sub_cat,
            "sub_cat_slug": slug,
            "strategy_type": strategy,
            "data_basis": basis,
            "expected_data_confidence": conf,
            "posts_count": len(posts),
            "saif_records_count": len(saif),
            "ground_truth_count": len(gt),
            "posts": posts,
            "saif_records": saif,
            "ground_truth": gt,
            "user_message": user_msg,
        }
        out_file = BUNDLE_DIR / f"{_safe_filename(sub_cat)}.bundle.json"
        out_file.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        written += 1
        if conf == "low":
            skipped_low_data.append((sub_cat, basis))
        print(
            f"  ✓ {sub_cat} ({strategy}) | posts={len(posts)} saif={len(saif)} gt={len(gt)} | conf={conf}"
        )

    print()
    print(f"写出 {written} 份 bundle 到 {BUNDLE_DIR}")
    if skipped_low_data:
        print()
        print(f"⚠️  low data ({len(skipped_low_data)} sub_cat) 仍按 low conf 跑,无需跳过:")
        for sc, b in skipped_low_data:
            print(
                f"  - {sc}: post={b['post_count']} co_mention={b['company_mention_count']} saif={b['saif_alumni_count']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
