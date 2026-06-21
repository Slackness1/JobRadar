"""塔塔网申 VIP 抓取器(tata-fetch.mjs)输出 → jobs 表导入。

新 fetcher 字段: _id, job_title, responsibility(职责), raw_position_require(要求),
address_str, major_str, publish_date, expire_date, industry, position_web_url(官网链接,TATA_LINKS=1),
main_company_name(feed 才有)。

- job_id = tata_<_id>(与库内现有 tatawangshen 一致 → upsert 去重 + 给老空JD补全)。
- upsert: 新岗 INSERT;已存在只刷 JD/detail_url/location/major/publish/deadline/scraped_at,
  **不动 quality_label / sub_category**(已 enrich 的不回退)。
- company: feed 用 main_company_name;company 模式文件用 --company 传入。

用法:
  PYTHONPATH=. .venv/bin/python scripts/tata_import_vip.py <out/xxx.json> [--company "公司全名"] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "jobradar.db"
CONFIG_ID = "687d079c70ccc5e36315f4ba"  # 与库内现有 tatawangshen 一致


def _join(v):
    return " / ".join(str(x) for x in v if x) if isinstance(v, list) else str(v or "")


def _date(s):
    s = str(s or "").strip()
    if not s or s == "null":
        return None
    return s.replace(" ", "T") if "T" not in s else s


def _rows(path, company_override):
    recs = json.loads(Path(path).read_text("utf-8"))
    out = []
    for r in recs:
        vid = r.get("_id") or r.get("id")
        if not vid:
            continue
        company = company_override or r.get("main_company_name") or r.get("company_alias") or ""
        out.append({
            "job_id": f"tata_{vid}",
            "company": company,
            "job_title": r.get("job_title") or "",
            "job_duty": r.get("responsibility") or "",
            "job_req": r.get("raw_position_require") or "",
            "location": _join(r.get("address_str")),
            "major_req": _join(r.get("major_str")),
            "detail_url": r.get("position_web_url") or r.get("official_url") or "",
            "publish_date": _date(r.get("publish_date")),
            "deadline": _date(r.get("expire_date")),
            "industry": _join(r.get("industry")),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--company", default=None, help="company 模式文件的公司全名(feed 不用传)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=5000")
    cur = con.cursor()

    rows = []
    for f in args.files:
        rows.extend(_rows(f, args.company))
    print(f"待导入 {len(rows)} 条 (db={DB}, dry_run={args.dry_run})")

    ins = upd = skip = 0
    for r in rows:
        exists = cur.execute("SELECT 1 FROM jobs WHERE job_id=?", (r["job_id"],)).fetchone()
        if not r["company"]:
            skip += 1; continue
        if args.dry_run:
            (upd if exists else ins).__class__  # no-op
            if exists: upd += 1
            else: ins += 1
            continue
        if exists:
            cur.execute(
                "UPDATE jobs SET job_duty=?, job_req=?, detail_url=?, location=?, major_req=?, "
                "publish_date=COALESCE(?,publish_date), deadline=COALESCE(?,deadline), scraped_at=? WHERE job_id=?",
                (r["job_duty"], r["job_req"], r["detail_url"], r["location"], r["major_req"],
                 r["publish_date"], r["deadline"], now, r["job_id"]))
            upd += 1
        else:
            cur.execute(
                "INSERT INTO jobs (job_id, source, company, company_type_industry, job_title, location, "
                "major_req, job_req, job_duty, source_config_id, publish_date, deadline, detail_url, "
                "scraped_at, created_at, track_predicted, quality_label) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'','')",
                (r["job_id"], "tatawangshen", r["company"], r["industry"], r["job_title"], r["location"],
                 r["major_req"], r["job_req"], r["job_duty"], CONFIG_ID, r["publish_date"], r["deadline"],
                 r["detail_url"], now, now))
            ins += 1
    con.commit()
    print(f"完成: 新增 {ins} | 更新 {upd} | 跳过(无公司名) {skip}")


if __name__ == "__main__":
    main()
