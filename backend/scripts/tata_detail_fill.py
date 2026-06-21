"""给 tatawangshen 岗补 JD 正文 + 官网链接(detail + position/click)。

适用: feed 发现流导入的 stub(无 JD)、老 65k 里空 JD 的存量。
- job_id = tata_<vacancyId> → 取出 vacancyId
- POST /api/recruit/vacancy/vacancy/{id} {} → responsibility / raw_position_require
- POST /api/recruit/position/click {_id,scene:"total"} → data.position_web_url
- 更新 job_req/job_duty/detail_url;不动 quality/sub_category。

用法:
  PYTHONPATH=. .venv/bin/python scripts/tata_detail_fill.py [--where today|empty] [--limit N] [--workers 6]
"""
from __future__ import annotations
import argparse, json, sqlite3, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "jobradar.db"
TOKEN_FILE = Path("/home/ubuntu/jobradar-sync/tata-token.json")
HOST = "https://www.tatawangshen.com"
_T = json.loads(TOKEN_FILE.read_text())
HDR = {"Content-Type": "application/json", "TATA-X-OPEN-ID": _T["openId"],
       "Authorization": _T.get("bearer") or ("Bearer " + _T["token"])}


def _post(path, body):
    req = urllib.request.Request(HOST + path, data=json.dumps(body).encode(), headers=HDR, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def _fetch(job):
    jid, job_id = job
    vid = job_id[5:] if job_id.startswith("tata_") else job_id
    try:
        d = (_post(f"/api/recruit/vacancy/vacancy/{vid}", {}) or {}).get("data") or {}
        if not isinstance(d, dict):
            return (jid, None, None, None, "offline")
        duty = (d.get("responsibility") or "").strip()
        req = (d.get("raw_position_require") or "").strip()
        url = ""
        try:
            url = ((_post("/api/recruit/position/click", {"_id": vid, "scene": "total"}) or {}).get("data") or {}).get("position_web_url") or ""
        except Exception:
            pass
        return (jid, req, duty, url, None)
    except Exception as e:  # noqa: BLE001
        return (jid, None, None, None, f"{type(e).__name__}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--where", choices=["today", "empty"], default="today")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=5000")
    cur = con.cursor()
    cond = ("date(scraped_at)>='2026-06-07'" if args.where == "today" else "1=1")
    q = (f"SELECT id, job_id FROM jobs WHERE source='tatawangshen' AND {cond} "
         "AND LENGTH(TRIM(COALESCE(job_req,'')||COALESCE(job_duty,'')))<50")
    targets = cur.execute(q).fetchall()
    if args.limit:
        targets = targets[:args.limit]
    print(f"待补 detail 的 tatawangshen 岗: {len(targets)}")

    filled = offline = errs = 0
    CHUNK = 100
    for s in range(0, len(targets), CHUNK):
        res = list(ThreadPoolExecutor(args.workers).map(_fetch, targets[s:s + CHUNK]))
        writes = []
        for jid, req, duty, url, err in res:
            if err == "offline":
                offline += 1
            elif err:
                errs += 1
            elif (req or duty):
                writes.append((req, duty, url or "", jid)); filled += 1
            else:
                offline += 1
        for req, duty, url, jid in writes:
            if url:
                cur.execute("UPDATE jobs SET job_req=?, job_duty=?, detail_url=? WHERE id=?", (req, duty, url, jid))
            else:
                cur.execute("UPDATE jobs SET job_req=?, job_duty=? WHERE id=?", (req, duty, jid))
        con.commit()
        print(f"  {min(s+CHUNK,len(targets))}/{len(targets)}  填{filled} 下线{offline} 错{errs}")
    print(f"\n完成: 补全 {filled} | 下线 {offline} | 错误 {errs}")


if __name__ == "__main__":
    main()
