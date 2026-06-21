"""字节 (jobs.bytedance.com) 空 JD 详情回填 — 公开 job API,纯 requests,无需签名/代理/渲染。

派单:docs/dispatch-internet-detail-adapters-2026-06-07.md 的 P1。
关键发现(2026-06-07):字节 SPA 渲染时调 GET /api/v1/job/posts/<id>?portal_type=3,**该接口无 _signature、
无代理也直接 200**,正文在 data.job_post_detail.{description, requirement}。所以无需 Playwright 渲染(那条 ~10s/页、
17h 全量),改纯 requests,和腾讯同级速度。

- 目标:source='internet_official' 且 detail_url 含 jobs.bytedance.com/.../position/<id>/detail 且 JD 空。
  description -> job_duty ; requirement -> job_req
- 幂等:只挑空 JD;并发取、单线程写;分块 commit,可断点续。

用法:
  PYTHONPATH=. .venv/bin/python scripts/backfill_bytedance_jd.py [--limit N] [--workers 8] [--dry-run]
"""
from __future__ import annotations
import argparse, re, sqlite3, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

DB = Path(__file__).resolve().parents[1] / "data" / "jobradar.db"
API = "https://jobs.bytedance.com/api/v1/job/posts/{pid}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
PID = re.compile(r"/position/([^/]+)/detail")


def _targets(con, limit):
    q = ("SELECT id, detail_url FROM jobs WHERE source='internet_official' "
         "AND detail_url LIKE '%jobs.bytedance.com%' AND detail_url LIKE '%/detail%' "
         "AND LENGTH(TRIM(COALESCE(job_req,'')||COALESCE(job_duty,'')))<50")
    out = []
    for jid, url in con.execute(q).fetchall():
        m = PID.search(url or "")
        if m:
            out.append((jid, m.group(1)))
    return out[:limit] if limit else out


def _fetch(item):
    jid, pid = item
    try:
        r = requests.get(API.format(pid=pid), params={"portal_type": 3}, headers=UA, timeout=15)
        d = (r.json() or {}).get("data") or {}
        det = d.get("job_post_detail")
        if not isinstance(det, dict):  # 下线/失效
            return (jid, "", "", None)
        return (jid, (det.get("requirement") or "").strip(), (det.get("description") or "").strip(), None)
    except Exception as e:  # noqa: BLE001
        return (jid, None, None, f"{type(e).__name__}:{str(e)[:40]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=5000")
    targets = _targets(con, args.limit)
    print(f"字节空JD待回填: {len(targets)}  (db={DB})")
    if args.dry_run:
        for it in targets[:5]:
            jid, req, duty, err = _fetch(it)
            print(f"  [{jid}] err={err} req={len(req or '')}字 duty={len(duty or '')}字 :: {(duty or req or '')[:55]}")
        return

    filled = empty = errs = 0
    CHUNK = 200
    for s in range(0, len(targets), CHUNK):
        results = list(ThreadPoolExecutor(args.workers).map(_fetch, targets[s:s + CHUNK]))
        writes = []
        for jid, req, duty, err in results:
            if err:
                errs += 1
            elif (req or duty):
                writes.append((req, duty, jid)); filled += 1
            else:
                empty += 1
        if writes:
            con.executemany("UPDATE jobs SET job_req=?, job_duty=? WHERE id=?", writes); con.commit()
        print(f"  {min(s+CHUNK,len(targets))}/{len(targets)}  填{filled} 空{empty} 错{errs}")
        time.sleep(0.3)
    print(f"\n完成: 回填 {filled} | 空(疑下线) {empty} | 错误 {errs}")


if __name__ == "__main__":
    main()
