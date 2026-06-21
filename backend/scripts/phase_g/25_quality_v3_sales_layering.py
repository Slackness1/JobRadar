"""Phase G (2026-05-31) — 金融销售岗三分层 reclassify。

背景: quality_label v3 把"机构销售"白名单化后救回大量真销售岗,但副作用是把
"渠道经理 / 财富顾问 / 私人财富 / 理财经理" 这类**零售/代销**销售也一起打成 good,
混进了推荐池的"机构销售·销售支持" sub_cat。

机构销售 ≠ 低质量(SAIF 卖方/资管核心出路),但渠道/零售销售对 SAIF 是 support_role。
v3 prompt 已加"规则四:金融销售岗三分层"(对象=机构→good / 代销渠道→support / 个人→support)。

本脚本用升级后的 v3 重打**池内金融销售类岗位**的 quality_label:
- 真机构销售 → 保持 good (留在推荐池)
- 代销渠道 / 零售财富 → 降级 support_role (自动踢出池,recall SQL 只收 good/intern)

候选 id list 由调用方写到 /tmp/sales_layering_ids.json (见 README)。
幂等: 直接覆盖 quality_label,重跑安全。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/25_quality_v3_sales_layering.py \
    [--workers 8] [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_job_quality_label_v3

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
IDS_FILE = Path("/tmp/sales_layering_ids.json")
PROGRESS_FILE = BACKEND_ROOT / "data" / "_phase_g" / "quality_v3_sales_layering_progress.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sales_layering")


def _process_job(job_id: int) -> tuple[int, str | None, str | None, str | None]:
    """重打一个岗的 quality_label。Returns (id, old_label, new_label, err)。"""
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, None, "not_found")
        old = job.quality_label
        result = enrich_job_quality_label_v3({
            "company": job.company or "",
            "job_title": job.job_title or "",
            "job_duty": job.job_duty or "",
            "job_req": job.job_req or "",
        })
        new = result["quality_label"]
        if new != old:
            job.quality_label = new
            db.commit()
        return (job_id, old, new, None)
    except Exception as exc:  # noqa: BLE001
        return (job_id, None, None, str(exc)[:200])
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not IDS_FILE.exists():
        log.error(f"缺 {IDS_FILE} — 先生成候选 id list")
        return 1
    job_ids = json.loads(IDS_FILE.read_text())["job_ids"]
    if args.limit:
        job_ids = job_ids[: args.limit]
    log.info(f"金融销售类候选: {len(job_ids)}")
    if args.dry_run:
        return 0
    if not job_ids:
        log.info("无候选, 退出")
        return 0

    # 迁移矩阵: (old, new) -> count
    transitions: Counter[tuple[str, str]] = Counter()
    downgraded: list[tuple[int, str]] = []  # (id, new) for good->support
    errors: list[tuple[int, str]] = []
    consecutive_402 = 0

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_process_job, jid): jid for jid in job_ids}
        for i, fut in enumerate(as_completed(futures), 1):
            jid, old, new, err = fut.result()
            if err:
                errors.append((jid, err))
                if "402" in err or "Insufficient Balance" in err:
                    consecutive_402 += 1
                    if consecutive_402 >= 5:
                        log.error("连续 5 个 402, 余额耗尽, 中止")
                        for f in futures:
                            f.cancel()
                        break
                continue
            consecutive_402 = 0
            transitions[(old or "?", new or "?")] += 1
            if old in ("good", "internship_only") and new in ("support_role", "low_signal", "low_pay"):
                downgraded.append((jid, new))
            if i % 25 == 0:
                log.info(f"  {i}/{len(job_ids)} | errors {len(errors)}")

    log.info("\n=== 销售三分层 reclassify summary ===")
    log.info(f"  总处理: {sum(transitions.values())}")
    log.info(f"  errors: {len(errors)}")
    log.info(f"  耗时: {(time.time() - t0)/60:.1f}min")
    log.info(f"  踢出推荐池 (good/intern → support/low): {len(downgraded)}")
    log.info("  迁移矩阵:")
    for (old, new), n in transitions.most_common():
        tag = " ← 踢出池" if (old in ("good", "internship_only") and new not in ("good", "internship_only")) else ""
        log.info(f"    {old:<16} → {new:<16} {n:>3}{tag}")

    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps({
        "ran_at": datetime.utcnow().isoformat(),
        "total": sum(transitions.values()),
        "downgraded_count": len(downgraded),
        "downgraded_ids": [d[0] for d in downgraded],
        "transitions": {f"{o}->{n}": c for (o, n), c in transitions.items()},
        "errors": len(errors),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if consecutive_402 < 5 else 2


if __name__ == "__main__":
    sys.exit(main())
