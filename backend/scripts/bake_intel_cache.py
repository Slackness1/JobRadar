"""Phase 5b (2026-05-25) — 预烤 Top N XHS-覆盖公司的同辈情报卡到磁盘缓存。

为什么:学生进「平台」tab 展开公司卡时,RecommendCardIntelSection 首次会调
GET /api/intel/company-card?company=xxx → enrichment.enrich() → 6~8s LLM。
预烤一次后写入 data/intel_cache/<sha>.json (TTL 30 天),后续命中即时返。

用法 (prod / dev 都行):
    PYTHONPATH=. .venv/bin/python scripts/bake_intel_cache.py            # top 30
    PYTHONPATH=. .venv/bin/python scripts/bake_intel_cache.py --top 50   # top 50
    PYTHONPATH=. .venv/bin/python scripts/bake_intel_cache.py --refresh  # 强制重烤
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.intel import enrichment
from app.services.xhs.retrieve import _ensure_cache


def top_companies_by_xhs(db, top_n: int) -> list[tuple[str, int]]:
    """从 XHS in-memory cache 里数 company_target → 出现次数,取 top_n。"""
    cache = _ensure_cache(db)
    insights = cache["insights"]
    c: Counter[str] = Counter()
    for ins in insights:
        for tag in ins.company_target:
            c[tag] += 1
    return c.most_common(top_n)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=30, help="top N companies (default 30)")
    parser.add_argument("--refresh", action="store_true", help="强制重烤,不读已有缓存")
    parser.add_argument("--min-insights", type=int, default=3,
                        help="低于这个 XHS 数的公司不烤 (LLM 摘不出有用东西)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        top = top_companies_by_xhs(db, args.top)
        print(f"=== baking intel cache for top {len(top)} companies (min_insights={args.min_insights}) ===\n")
        ok = skipped = failed = 0
        for i, (co, n_xhs) in enumerate(top, 1):
            if n_xhs < args.min_insights:
                print(f"  [{i:>2}/{len(top)}] {co} (xhs={n_xhs}) — skipped (below min)")
                skipped += 1
                continue
            t0 = time.time()
            try:
                card = enrichment.enrich(
                    db, company=co, role=None, k=20, use_cache=(not args.refresh),
                )
                dt = time.time() - t0
                used = card.get("n_insights_used", 0)
                cached = card.get("_from_cache", False)
                status = "💾 cached" if cached else "🔥 baked "
                print(f"  [{i:>2}/{len(top)}] {status} {co:<14} xhs={n_xhs:>3} used={used:>2} dt={dt:.1f}s")
                ok += 1
            except Exception as e:
                dt = time.time() - t0
                print(f"  [{i:>2}/{len(top)}] ❌ {co}: {e} (dt={dt:.1f}s)")
                failed += 1
        print(f"\n=== done: {ok} ok, {skipped} skipped, {failed} failed ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
