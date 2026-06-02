"""预热 119 家 ground_truth 重点公司的同辈情报缓存 (PR-4)。

抽屉 IntelDrawer 打两套接口、各自现算 LLM:
  1. /api/intel/company-card  → enrichment.enrich()          (公司级, medium)
  2. /api/job-intel/card      → build_job_card() → _company_dims (岗位级, flash)
这两层都要预热,学生点开才真秒开。本脚本对 119 GT 公司各烤这两层:
  - enrichment.enrich(公司名)           → company-card 缓存 (兜底卡走这条)
  - build_job_card(代表岗 id)           → company_dims + job_card 缓存 (live 岗走这条)

无 UGC 的公司:LLM 没料可摘 → 情报为空,但缓存写好后点开仍是"秒回空",不再现场等。
即:预热消除的是"等待",不能凭空造出没有的情报。

用法 (cwd=backend, 建议后台):
    PYTHONPATH=. .venv/bin/python scripts/bake_intel_cache_gt.py [--workers 6] [--refresh]
缓存落 dev 磁盘;进生产需在 prod 同样跑一遍(或把 data/*intel_cache* 一并部署)。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.intel import enrichment  # noqa: E402
from app.services.intel.job_card import build_job_card  # noqa: E402
from app.services.llm_json import flash_json_fn  # noqa: E402
from app.services.phase_g.tier_fit.tier_ladder import _norm_company  # noqa: E402

GT_PATH = Path("data/ground_truth_companies_v1.json")


def gt_companies() -> list[str]:
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))
    names: list[str] = []
    seen: set[str] = set()
    for _sc, lst in (gt.get("ground_truth") or {}).items():
        for e in lst:
            n = (e.get("name") or "").strip()
            if n and n not in seen:
                seen.add(n)
                names.append(n)
    return names


def _rep_job_id(db, company: str) -> int | None:
    norm = _norm_company(company) or company
    row = db.execute(
        text(
            "SELECT id FROM jobs WHERE (company = :e OR company LIKE :l) "
            "AND quality_label IN ('good','internship_only') AND sub_category IS NOT NULL "
            "AND (link_status IS NULL OR link_status != 'dead') LIMIT 1"
        ),
        {"e": norm, "l": f"%{norm}%"},
    ).fetchone()
    return int(row[0]) if row else None


def warm_one(company: str, refresh: bool) -> tuple:
    db = SessionLocal()
    try:
        t0 = time.time()
        card = enrichment.enrich(
            db, company=company, role=None, k=20, use_cache=(not refresh)
        )
        used = card.get("n_insights_used", 0)
        from_cache = card.get("_from_cache", False)
        jid = _rep_job_id(db, company)
        if jid:
            build_job_card(db, jid, use_cache=(not refresh), llm_fn=flash_json_fn)
            job_status = f"job#{jid}"
        else:
            job_status = "no-job"
        return (company, "ok", used, job_status, round(time.time() - t0, 1), from_cache)
    except Exception as e:  # noqa: BLE001
        return (company, "fail", 0, str(e)[:50], round(time.time() - t0, 1), False)
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--refresh", action="store_true", help="强制重烤,不读已有缓存")
    args = p.parse_args()

    names = gt_companies()
    print(f"=== baking intel cache for {len(names)} GT companies "
          f"(company-card + job-card, workers={args.workers}) ===", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(warm_one, c, args.refresh): c for c in names}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            results.append(r)
            tag = "💾" if r[5] else ("🔥" if r[1] == "ok" else "❌")
            print(f"  [{i:>3}/{len(names)}] {tag} {r[0]:<16} used={r[2]:>2} {r[3]:<10} dt={r[4]}s",
                  flush=True)

    ok = sum(1 for r in results if r[1] == "ok")
    empty = sum(1 for r in results if r[1] == "ok" and r[2] == 0)
    fail = sum(1 for r in results if r[1] == "fail")
    print(f"\n=== done: {ok}/{len(names)} ok ({empty} 空-无UGC), {fail} fail ===", flush=True)
    if fail:
        print("failed:", [r[0] for r in results if r[1] == "fail"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
