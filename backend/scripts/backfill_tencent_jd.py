"""腾讯 (careers.tencent.com) 空 JD 详情回填 — 公开 ByPostId API,纯 requests,不需 Decodo。

派单:docs/dispatch-internet-detail-adapters-2026-06-07.md 的 P0。
- 目标:source='internet_official' 且 detail_url 含 careers.tencent.com 且 job_req+job_duty 基本空 的岗。
- 取数:GET careers.tencent.com/tencentcareer/api/post/ByPostId?postId=<id>&language=zh-cn
        -> Data.Responsibility -> job_duty ; Data.Requirement -> job_req
- 幂等:只挑空 JD 的;已填的不会再选中,中断重跑安全。
- 并发取、单线程写(避开 SQLite 并发);分块 commit,可断点续。

用法:
  PYTHONPATH=. .venv/bin/python scripts/backfill_tencent_jd.py [--limit N] [--workers 8] [--dry-run]
"""
from __future__ import annotations
import argparse, re, sqlite3, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

DB = Path(__file__).resolve().parents[1] / "data" / "jobradar.db"
API = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
POSTID = re.compile(r"postId=(\d+)")


def _targets(con: sqlite3.Connection, limit: int | None):
    q = ("SELECT id, detail_url FROM jobs WHERE source='internet_official' "
         "AND detail_url LIKE '%careers.tencent.com%' "
         "AND LENGTH(TRIM(COALESCE(job_req,'')||COALESCE(job_duty,'')))<50")
    rows = con.execute(q).fetchall()
    out = []
    for jid, url in rows:
        m = POSTID.search(url or "")
        if m:
            out.append((jid, m.group(1)))
    return out[:limit] if limit else out


def _fetch(item):
    jid, post_id = item
    try:
        r = requests.get(API, params={"postId": post_id, "language": "zh-cn"}, headers=UA, timeout=15)
        d = (r.json() or {}).get("Data")
        if not isinstance(d, dict):  # 失效/下线 postId -> Data 为 "" 空串
            return (jid, "", "", None)
        duty = (d.get("Responsibility") or "").strip()
        req = (d.get("Requirement") or "").strip()
        return (jid, req, duty, None)
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
    print(f"腾讯空JD待回填: {len(targets)}  (db={DB})")
    if args.dry_run:
        for jid, pid in targets[:5]:
            jid_, req, duty, err = _fetch((jid, pid))
            print(f"  [{jid}] err={err} req={len(req or '')}字 duty={len(duty or '')}字 :: {(duty or req or '')[:60]}")
        return

    filled = empty = errs = 0
    CHUNK = 200
    for s in range(0, len(targets), CHUNK):
        chunk = targets[s:s + CHUNK]
        results = list(ThreadPoolExecutor(args.workers).map(_fetch, chunk))
        writes = []
        for jid, req, duty, err in results:
            if err:
                errs += 1
            elif (req or duty):
                writes.append((req, duty, jid)); filled += 1
            else:
                empty += 1  # API 返回但无正文(岗位可能已下线)
        if writes:
            con.executemany("UPDATE jobs SET job_req=?, job_duty=? WHERE id=?", writes)
            con.commit()
        print(f"  {min(s+CHUNK,len(targets))}/{len(targets)}  填{filled} 空{empty} 错{errs}")
        time.sleep(0.3)
    print(f"\n完成: 回填 {filled} | API空(疑下线) {empty} | 错误 {errs}")


if __name__ == "__main__":
    main()
