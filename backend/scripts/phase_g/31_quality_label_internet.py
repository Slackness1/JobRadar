"""给 32 大厂今日入库 tata 岗规则化打 quality(校招=good / 实习=internship_only)。
角色质量过滤交给下游 sub_cat enrich(Pass1 把骑手/HR 路由 null → 不进池)。幂等。"""
from __future__ import annotations
import json, sys, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase_g._internet_quality_rule import quality_for_title

DB = Path(__file__).resolve().parents[2] / "data" / "jobradar.db"
MANIFEST = Path("/home/ubuntu/jobradar-sync/out/fanout_manifest.json")


def main() -> int:
    names = [r["name"] for r in json.loads(MANIFEST.read_text())]
    con = sqlite3.connect(DB); con.execute("PRAGMA busy_timeout=5000"); cur = con.cursor()
    ph = ",".join("?" * len(names))
    rows = cur.execute(
        f"SELECT id, job_title FROM jobs WHERE source='tatawangshen' "
        f"AND date(scraped_at)='2026-06-08' AND company IN ({ph}) "
        f"AND LENGTH(TRIM(COALESCE(job_req,'')||COALESCE(job_duty,'')))>=50 "
        f"AND (quality_label IS NULL OR quality_label='')", names).fetchall()
    g = i = 0
    for jid, title in rows:
        q = quality_for_title(title)
        cur.execute("UPDATE jobs SET quality_label=? WHERE id=?", (q, jid))
        if q == "good": g += 1
        else: i += 1
    con.commit(); con.close()
    print(f"打标 {len(rows)} 岗: good {g} | internship_only {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
