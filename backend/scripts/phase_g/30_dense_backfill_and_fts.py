"""S1 真实回填:给质量池岗位补 JD embedding + 重建 FTS5 稀疏索引。

幂等、可断点重跑(content_hash 没变就跳过)。只动 dev DB 的 job_embeddings / job_fts
两张实验表,不碰 jobs 业务数据,也不接入任何线上召回链路(flag 默认 OFF)。

    PYTHONPATH=. .venv/bin/python scripts/phase_g/30_dense_backfill_and_fts.py
"""
from __future__ import annotations

import sys
import time

from app.database import SessionLocal
from app.services.phase_g.recommendation_v2 import dense_index as di
from app.services.phase_g.recommendation_v2 import sparse_index as si


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        t0 = time.time()
        _log(f"=== 稠密回填开始 (limit={limit}) ===")

        def on_progress(done: int, total: int) -> None:
            if done % 1000 == 0 or done == total:
                rate = done / max(1e-6, time.time() - t0)
                _log(f"  embed {done}/{total}  ({rate:.1f}/s)")

        stats = di.backfill_embeddings(db, limit=limit, on_progress=on_progress)
        _log(f"稠密回填完成: scanned={stats['scanned']} "
             f"embedded={stats['embedded']} skipped={stats['skipped']}")

        n_cache = di.reload_cache(db)
        _log(f"内存缓存重载: {n_cache} 条向量")

        _log("=== 稀疏 FTS5 重建开始 ===")
        n_fts = si.rebuild_index(db, limit=limit)
        _log(f"稀疏 FTS5 重建完成: {n_fts} 条")

        _log(f"=== 全部完成,用时 {time.time() - t0:.0f}s ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
