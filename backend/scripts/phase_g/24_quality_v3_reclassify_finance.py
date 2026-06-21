"""Phase G — quality_label v3 重打分，针对 686 个疑似误判的金融岗位。

从 /tmp/finance_misjudged_ids.json 读 job_id 列表，
用 v3 prompt 重打 quality_label，覆盖写回 DB。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/24_quality_v3_reclassify_finance.py \
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
from pathlib import Path

import app.config  # noqa: F401 — 触发 .env.local 加载

from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_job_quality_label_v3

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_FILE = Path("/tmp/finance_misjudged_ids.json")
PROGRESS_FILE = BACKEND_ROOT / "data" / "_phase_g" / "quality_v3_reclass_progress.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("v3_reclassify")


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("progress 文件损坏，从头开始")
    return {"done": {}, "errors": []}


def _save_progress(progress: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_FILE)


def _process_one(job_id: int, dry_run: bool) -> tuple[int, str | None, str | None, str | None]:
    """单个 job: 读 DB → v3 LLM → 写回。

    Returns (job_id, old_label, new_label, error_msg)
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, None, "not_found")
        old_label = job.quality_label or ""
        result = enrich_job_quality_label_v3({
            "company": job.company or "",
            "job_title": job.job_title or "",
            "job_duty": job.job_duty or "",
            "job_req": job.job_req or "",
        })
        new_label = result["quality_label"]
        reasoning = result.get("reasoning", "")
        if not dry_run and old_label != new_label:
            job.quality_label = new_label
            db.commit()
        return (job_id, old_label, new_label, None)
    except Exception as exc:  # noqa: BLE001
        return (job_id, None, None, str(exc)[:300])
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="v3 quality_label reclassify for 686 finance jobs")
    parser.add_argument("--workers", type=int, default=8, help="并发线程数 (默认 8)")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 个（smoke test 用）")
    parser.add_argument("--dry-run", action="store_true", help="调 LLM 但不写回 DB")
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        log.error(f"输入文件不存在: {INPUT_FILE}")
        return 1

    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    all_ids: list[int] = data.get("job_ids", data) if isinstance(data, dict) else data
    log.info(f"读入 {len(all_ids)} 个 job_id")

    if args.limit:
        all_ids = all_ids[: args.limit]
        log.info(f"--limit {args.limit} → 实际跑 {len(all_ids)} 个")

    progress = _load_progress()
    done: dict[str, dict] = progress.get("done", {})  # {str(job_id): {old, new}}
    errors: list[dict] = progress.get("errors", [])

    todo = [jid for jid in all_ids if str(jid) not in done]
    log.info(f"已完成: {len(done)} / 待跑: {len(todo)}")

    if args.dry_run:
        log.info("--dry-run 模式，调 LLM 后不写 DB")

    if not todo:
        log.info("无待跑任务，退出")
    else:
        t0 = time.time()
        consecutive_402 = 0

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_process_one, jid, args.dry_run): jid for jid in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                jid, old_label, new_label, err = fut.result()
                if err:
                    errors.append({"job_id": jid, "error": err})
                    log.warning(f"job_id={jid} 错误: {err[:80]}")
                    if "402" in err or "Insufficient Balance" in err:
                        consecutive_402 += 1
                        if consecutive_402 >= 5:
                            log.error(f"连续 {consecutive_402} 个 402，余额耗尽，中止！")
                            for f in futures:
                                f.cancel()
                            break
                    else:
                        consecutive_402 = 0
                else:
                    consecutive_402 = 0
                    done[str(jid)] = {"old": old_label, "new": new_label}

                if i % 100 == 0:
                    _save_progress({"done": done, "errors": errors})
                    elapsed = time.time() - t0
                    rate = i / elapsed if elapsed else 0
                    eta = (len(todo) - i) / rate / 60 if rate else 0
                    log.info(
                        f"  进度 {i}/{len(todo)} | rate {rate:.1f}/s | eta {eta:.1f}min | "
                        f"errors {len(errors)}"
                    )

        _save_progress({"done": done, "errors": errors})
        elapsed = time.time() - t0
        log.info(f"跑完，耗时 {elapsed / 60:.1f} min，成功 {len(done)}，错误 {len(errors)}")

    # ===== 输出迁移矩阵 =====
    print("\n" + "=" * 60)
    print("v3 reclassify 结果汇总")
    print("=" * 60)

    # 迁移矩阵
    label_order = ["good", "internship_only", "agency", "low_signal", "spam", "support_role", "low_pay"]
    migration: Counter = Counter()
    for v in done.values():
        old = v.get("old") or "?"
        new = v.get("new") or "?"
        migration[(old, new)] += 1

    # 按旧 label 汇总
    from_labels = sorted({k[0] for k in migration})
    to_labels = sorted({k[1] for k in migration})
    all_lbs = sorted(set(from_labels) | set(to_labels), key=lambda x: label_order.index(x) if x in label_order else 99)

    header = f"{'old \\ new':<20}" + "".join(f"{lb:<15}" for lb in all_lbs)
    print(header)
    print("-" * len(header))
    for old in all_lbs:
        row_vals = [migration.get((old, new), 0) for new in all_lbs]
        if sum(row_vals) == 0:
            continue
        row_str = f"{old:<20}" + "".join(f"{v:<15}" for v in row_vals)
        print(row_str)

    # 汇总 low_signal/support_role → good 的修复
    fixed = [(jid, v) for jid, v in done.items() if v.get("old") in ("low_signal", "support_role") and v.get("new") == "good"]
    print(f"\n修复（low_signal/support_role → good）: {len(fixed)} 个")

    # 仍是 support_role 的
    still_support = [(jid, v) for jid, v in done.items() if v.get("new") == "support_role"]
    print(f"仍判 support_role: {len(still_support)} 个")

    # 仍是 low_signal 的
    still_low = [(jid, v) for jid, v in done.items() if v.get("new") == "low_signal"]
    print(f"仍判 low_signal: {len(still_low)} 个")

    print(f"\n进度文件: {PROGRESS_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
