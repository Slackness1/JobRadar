"""为 4 个非 AI v2 新 sub_cat 生成 input bundle (给 Opus subagent 重做 KB 用):
- 机构销售·销售支持 (卖方研究)
- 债券承做DCM·ABS/REITs (固定收益)
- 基金产品运营·中后台 (多资产_FOF_衍生品)
- 金融科技·量化平台 (量化)

每个 bundle 含:
- taxonomy_v2_1.json 对应 entry (boundary / typical_companies / industry_focus_candidates / institution_tier_candidates)
- 从全 809 taxonomy_xhs_posts 用关键词挖出相关 XHS 帖 (作为 verbatim 来源)
- ground_truth 公司清单 (从 ground_truth_companies_v1.json 抽该 strategy 下的公司)

输出: data/_phase_g/synthesis_bundles_v2/{slug}.bundle.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import TaxonomyXhsPost

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TAXONOMY_V2 = BACKEND_ROOT / "data" / "_phase_g" / "taxonomy_v2_1.json"
GROUND_TRUTH = BACKEND_ROOT / "data" / "ground_truth_companies_v1.json"
OUTPUT_DIR = BACKEND_ROOT / "data" / "_phase_g" / "synthesis_bundles_v2"

# 4 个 新 sub_cat 的关键词 (从 taxonomy_v2_1 boundary 提取, 用于挖相关 XHS 帖)
NEW_SUBCAT_KEYWORDS: dict[str, list[str]] = {
    "机构销售·销售支持": [
        "机构销售", "销售助理", "客户经理", "客户组", "公募客户", "保险客户",
        "股销", "股票销售", "Rates Sales", "Credit Sales", "Sales Assistant",
        "Client Coverage", "客户服务", "销售材料", "路演支持", "投资者覆盖",
        "交易对手覆盖", "QFII销售", "渠道经理",
    ],
    "债券承做DCM·ABS/REITs": [
        "DCM", "债权资本市场", "债券承做", "债券承销", "债券发行", "发行执行",
        "ABS", "资产证券化", "REITs", "类REITs", "募集说明书", "申报材料",
        "尽调底稿", "评级沟通", "簿记建档", "发行上市", "存续管理",
    ],
    "基金产品运营·中后台": [
        "基金运营", "产品助理", "产品支持", "产品团队", "产品基础设施",
        "估值清算", "TA", "登记", "份额", "申赎", "运营报表", "产品材料",
        "产品生命周期", "存续管理", "基金会计", "产品经理", "数据维护",
    ],
    "金融科技·量化平台": [
        "金融科技", "数字金融", "客户研究", "量化平台", "金融工程工具",
        "ESG量化", "风险模型", "投研平台", "机构客户分析", "数据产品",
        "数据中台", "AIOps", "数字化平台",
    ],
}


def _new_subcat_meta() -> dict:
    """从 taxonomy_v2_1.json 拉 4 个新 sub_cat 的元信息。"""
    tax = json.loads(TAXONOMY_V2.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for entry in tax["new_sub_cats"]:
        name = entry["name"]
        if name in NEW_SUBCAT_KEYWORDS:
            out[name] = entry
    return out


def _mine_xhs_posts_by_keywords(keywords: list[str], max_posts: int = 30) -> list[dict]:
    """从全 809 taxonomy_xhs_posts 用关键词挖相关帖。

    评分: 命中关键词数 * relevance_score。取 top N。
    """
    db = SessionLocal()
    try:
        rows = db.query(TaxonomyXhsPost).all()
        scored: list[tuple[float, dict]] = []
        for r in rows:
            content = (r.raw_content or "")
            try:
                verb = json.loads(r.verbatim_signals or "[]")
            except json.JSONDecodeError:
                verb = []
            haystack = content + " " + " ".join(str(v) for v in verb)
            hit_count = sum(1 for kw in keywords if kw in haystack)
            if hit_count == 0:
                continue
            score = hit_count * (r.relevance_score or 0.5)
            try:
                mentions = json.loads(r.company_mentions or "[]")
            except json.JSONDecodeError:
                mentions = []
            scored.append((score, {
                "source_url": r.source_url,
                "origin_sub_cat": r.sub_cat,
                "content": content[:1500],
                "verbatim_signals": verb[:5],
                "company_mentions": mentions[:8],
                "relevance_score": r.relevance_score or 0,
                "hit_count": hit_count,
            }))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:max_posts]]
    finally:
        db.close()


def _ground_truth_companies_for_strategy(strategy: str) -> list[dict]:
    """从 ground_truth 拉该 strategy 下所有 sub_cat 的公司, 给 Opus subagent 当 typical_companies 候选。"""
    gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    # SUBCAT_TO_STRATEGY 映射 — 直接从 knowledge_synthesis import
    from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY
    relevant_subs = [sc for sc, st in SUBCAT_TO_STRATEGY.items() if st == strategy]
    out: dict[str, dict] = {}  # dedup by name
    for sc in relevant_subs:
        for c in gt.get("ground_truth", {}).get(sc, []):
            name = c.get("name", "")
            if name and name not in out:
                out[name] = c
    return list(out.values())


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    meta_map = _new_subcat_meta()
    print(f"taxonomy_v2_1 里 4 个非 AI 新 sub_cat: {list(meta_map.keys())}")
    print()

    for sub_cat, meta in meta_map.items():
        keywords = NEW_SUBCAT_KEYWORDS[sub_cat]
        posts = _mine_xhs_posts_by_keywords(keywords, max_posts=40)
        strategy = meta["strategy_type"]
        gt_pool = _ground_truth_companies_for_strategy(strategy)

        # 简洁 slug
        slug = {
            "机构销售·销售支持": "institutional_sales_support",
            "债券承做DCM·ABS/REITs": "dcm_abs_reits_underwriting",
            "基金产品运营·中后台": "fund_product_ops_middle_back",
            "金融科技·量化平台": "fintech_quant_platform",
        }[sub_cat]

        bundle = {
            "sub_cat": sub_cat,
            "sub_cat_slug": slug,
            "strategy_type": strategy,
            "boundary": meta["boundary"],
            "typical_companies_seed": meta["typical_companies"],
            "industry_focus_candidates": meta["industry_focus_candidates"],
            "institution_tier_candidates": meta["institution_tier_candidates"],
            "rationale": meta["rationale"],
            "ground_truth_pool_in_strategy": gt_pool[:30],
            "mined_xhs_posts": posts,
            "post_count": len(posts),
            "company_mention_dedup_count": len({
                m for p in posts for m in (p.get("company_mentions") or [])
            }),
        }
        out_file = OUTPUT_DIR / f"{slug}.bundle.json"
        out_file.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"  ✓ {sub_cat} → {out_file.name}"
            f" | {len(posts)} XHS 帖 (mined by keyword) | {len(gt_pool)} ground_truth 公司池"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
