"""P1 (公募投研 SAIF MF) 推荐端到端验证 — Phase 1+2 改完跑 top 10。

构造固定 profile (避开 LLM 生成),跑 recommend_jobs_for_profile, 打印:
  - top 10 final_score / 公司 / 岗位 / matched_track_label / priority_letter
  - bucket 统计 (subset / transferable / ambiguous / mismatch / low_quality)
  - 跨大类 mismatch (互联网/外企/营销/算法) 命中数 — Phase 1 核心目标:压到 0
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.schemas_resume_copilot import (
    ResumeEducationItem,
    ResumeInternshipItem,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeProjectItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile


P1_PROFILE = ResumeProfilePayload(
    basic_info={"name": "林思远", "email": "lsy@saif.edu.cn"},
    candidate_summary=(
        "上海交大 SAIF 金融硕士，主攻公募行研方向。本科复旦经济，"
        "GPA 3.8。在中信证券宏观研究 + 易方达基金消费研究部实习，"
        "CFA Level II，跟踪覆盖 6 只食品饮料股票，撰写 8 篇深度报告，"
        "其中 2 篇被分析师采纳推送内部投委会。"
    ),
    education=[
        ResumeEducationItem(
            school="上海交大高金 SAIF",
            degree="金融硕士",
            major="金融学",
            start_date="2025-09",
            end_date="2027-06",
        ),
        ResumeEducationItem(
            school="复旦大学",
            degree="本科",
            major="经济学",
            start_date="2021-09",
            end_date="2025-06",
        ),
    ],
    internships=[
        ResumeInternshipItem(
            company="易方达基金",
            role="消费组行研实习生",
            start_date="2025-06",
            end_date="2025-08",
            bullets=[
                "跟踪 6 只食品饮料股票，建立 DCF + 相对估值模型",
                "撰写 8 篇深度公司研究报告，2 篇被基金经理推上投委会",
                "搭建白酒板块景气度跟踪表，月频更新分析师内部使用",
            ],
        ),
        ResumeInternshipItem(
            company="中信证券",
            role="宏观研究助理",
            start_date="2024-12",
            end_date="2025-05",
            bullets=[
                "协助首席分析师完成 5 期月度宏观周报",
                "拉通 30 个国家宏观指标数据库，月频更新",
                "参与 2 次买方路演 + 1 次行业沙龙",
            ],
        ),
    ],
    projects=[
        ResumeProjectItem(
            name="A股行业景气度量化模型",
            role="项目负责人",
            tech_stack=["Python", "Wind", "SQL"],
            bullets=[
                "用 30 个 alpha 因子构建食品饮料板块景气度回归模型，IR 1.5",
                "回测 2018-2024，年化超额收益 12%，最大回撤 8%",
            ],
        ),
    ],
    skills=ResumeSkillsPayload(
        technical=["DCF 估值", "财务建模", "Python", "SQL", "Wind 数据库", "Bloomberg"],
        tools=["Excel", "Wind", "Bloomberg", "Choice", "PowerBI"],
        languages=["中文", "英语"],
    ),
    languages=["中文 (母语)", "英语 (CET-6, IELTS 7.0)"],
    awards=["CFA Level II 通过", "复旦经院专业排名 5%"],
    inferred_roles=["行业研究员", "投研实习生", "研究助理"],
    inferred_tracks=["二级买方·基本面"],
)


P1_PREFERENCES = ResumePreferencePayload(
    preferred_tracks=["二级买方·基本面"],
    preferred_locations=["上海"],
    preferred_company_types=["金融机构"],
    preferred_roles=["投研实习生"],
    all_skipped=False,
)


def classify(item) -> str:
    """Bucket per risks-marker."""
    risks = list(item.risks or [])
    if any("赛道不符" in r for r in risks):
        return "mismatch"
    if any("低质量" in r for r in risks):
        return "low_quality"
    if any("可迁移" in r for r in risks):
        return "transferable"
    if any("信号不足" in r for r in risks):
        return "ambiguous"
    return "subset"


def main():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("P1 (林思远 / 公募投研) 推荐 — Phase 1+2 改完版本")
        print("=" * 80)
        print(f"preferred_tracks: {P1_PREFERENCES.preferred_tracks}")
        print(f"inferred_tracks:  {P1_PROFILE.inferred_tracks}")
        print()

        # 跑 rule_score only (no LLM rerank — 先看底层逻辑)
        print("--- A. rule_score only (ai_top_n=0) ---")
        items_rule, _, _ = recommend_jobs_for_profile(
            db, P1_PROFILE, preferences=P1_PREFERENCES, limit=10, ai_top_n=0,
        )
        breakdown_rule = Counter(classify(it) for it in items_rule)
        for i, it in enumerate(items_rule, 1):
            bucket = classify(it)
            stage = "[实习]" if it.is_internship else "[校招]"
            print(
                f"  {i:>2}. final={it.final_score:>3} {stage} "
                f"[{bucket:11}/{it.priority_letter}] "
                f"{it.company[:18]:<18} | {it.job_title[:30]:<30} | "
                f"track={it.matched_track_label[:14]}"
            )
        print(f"\n  bucket: {dict(breakdown_rule)}")
        print(f"  跨大类 mismatch: {breakdown_rule.get('mismatch', 0)} (目标 0)")

        # 跑 LLM rerank (pro + high — 体验生产路径)
        print("\n--- B. LLM rerank (pro + reasoning=high, ai_top_n=10) ---")
        import time
        t0 = time.time()
        items_ai, used_ai, fallback = recommend_jobs_for_profile(
            db, P1_PROFILE, preferences=P1_PREFERENCES, limit=10, ai_top_n=10,
        )
        dt = time.time() - t0
        print(f"  rerank: used_ai={used_ai} fallback={fallback or '(none)'} dt={dt:.1f}s")
        breakdown_ai = Counter(classify(it) for it in items_ai)
        for i, it in enumerate(items_ai, 1):
            bucket = classify(it)
            stage = "[实习]" if it.is_internship else "[校招]"
            print(
                f"  {i:>2}. final={it.final_score:>3} {stage} "
                f"[{bucket:11}/{it.priority_letter}] "
                f"{it.company[:18]:<18} | {it.job_title[:30]:<30} | "
                f"track={it.matched_track_label[:14]}"
            )
        print(f"\n  bucket: {dict(breakdown_ai)}")
        print(f"  跨大类 mismatch: {breakdown_ai.get('mismatch', 0)} (目标 0)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
