"""Phase 3 端到端 — 拿 P1 推荐 items, 跑 platform aggregator, 打印平台卡片列表。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile
from app.services.resume_copilot.platform_aggregator import aggregate_by_company

# Reuse P1 fixture
from scripts.test_p1_recommend import P1_PROFILE, P1_PREFERENCES  # noqa: E402


def main():
    db = SessionLocal()
    try:
        # 不跑 LLM rerank — Phase 1 验证已经证明 rerank 对 P1 不改顺序
        items, _, _ = recommend_jobs_for_profile(
            db, P1_PROFILE, preferences=P1_PREFERENCES, limit=10, ai_top_n=0,
        )
        print(f"raw items: {len(items)} (top 5 公司: {[it.company[:10] for it in items[:5]]})")

        platforms = aggregate_by_company(items, db=db)
        print(f"\n=== aggregated to {len(platforms)} platform cards ===\n")
        for i, p in enumerate(platforms[:15], 1):
            print(
                f"{i:>2}. score={p.platform_score:>3} "
                f"[{p.tier_label or '—':4}/{p.priority_letter or '—'}] "
                f"{p.company[:14]:<14} | "
                f"jobs={p.n_jobs} (校招 {p.n_campus} / 实习 {p.n_internship}) | "
                f"xhs={p.n_xhs_insights:<3} | track={p.matched_track_label[:14]}"
            )
            for j in p.top_jobs:
                marker = "实" if j.is_internship else "校"
                print(f"     · [{marker}] {j.job_title[:50]}  (score={j.final_score})")
            print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
