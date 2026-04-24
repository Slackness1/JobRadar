#!/usr/bin/env python3
"""将 legacy bank crawler 的 CSV 数据同步到 JobRadar SQLite(jobs)。"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.database import SessionLocal
from app.models import Job

BASE_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = BASE_DIR / "app" / "services" / "data" / "jobs.csv"


def parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y%m%d%H%M%S",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    # 兜底: ISO
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00").replace("+00:00", ""))
    except Exception:
        return None


def make_job_id(company: str, title: str, url: str) -> str:
    raw = f"{company}:{title}:{url}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def normalize_company(company: str) -> str:
    c = (company or "").strip()
    c = c.replace("（", "(").replace("）", ")")

    alias = {
        "中国平安银行（上海分行）": "平安银行",
        "中国平安银行(上海分行)": "平安银行",
        "广东华兴银行股份有限公司": "广东华兴银行",
        "浙江民泰商业银行": "民泰银行",
    }
    if c in alias:
        return alias[c]

    if "银行" in c:
        # 去掉括号内分行/支行信息
        c = re.sub(r"\((?:[^)]*?(?:分行|支行)[^)]*?)\)", "", c)
        m = re.match(r"^(.*?银行).*(?:分行|支行).*$", c)
        if m:
            c = m.group(1)
        c = c.replace("股份有限公司", "").strip()
    return c


def is_social_post(title: str, url: str) -> bool:
    t = (title or "").strip()
    u = (url or "").lower()
    social_keywords = ["社招", "社会招聘", "社会人才", "成熟人才", "社聘", "高层次人才"]
    if any(k in t for k in social_keywords):
        return True
    if "social" in u or "socialjob" in u:
        return True
    return False


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    db = SessionLocal()
    try:
        existing = {j.job_id: j for j in db.query(Job).all() if j.job_id}

        inserted = 0
        updated = 0
        scanned = 0
        skipped = 0

        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                scanned += 1
                company = normalize_company((row.get("company") or "").strip())
                title = (row.get("title") or "").strip()
                url = (row.get("url") or "").strip()
                stage = ((row.get("job_type") or "campus").strip() or "campus").lower()

                # 只同步校招 + 可访问详情链接 + 银行公司
                if not company or not title or not url:
                    skipped += 1
                    continue
                if stage != "campus":
                    skipped += 1
                    continue
                if "银行" not in company:
                    skipped += 1
                    continue
                if company == "中国平安":
                    skipped += 1
                    continue
                if is_social_post(title, url):
                    skipped += 1
                    continue

                job_id = (row.get("id") or "").strip() or make_job_id(company, title, url)
                mapped = {
                    "job_id": job_id,
                    "source": "bank-legacy-csv",
                    "company": company,
                    "department": (row.get("department") or "").strip(),
                    "job_title": title,
                    "location": (row.get("location") or "").strip() or "未知",
                    "major_req": (row.get("requirements") or "").strip(),
                    "job_req": (row.get("requirements") or "").strip(),
                    "job_duty": (row.get("description") or "").strip(),
                    "job_stage": stage,
                    "source_config_id": "legacy-bank-crawler",
                    "detail_url": url,
                    "publish_date": parse_dt(row.get("publish_date") or ""),
                    "deadline": parse_dt(row.get("deadline") or ""),
                    "scraped_at": parse_dt(row.get("crawled_at") or "") or datetime.utcnow(),
                }

                old = existing.get(job_id)
                if old is None:
                    db.add(Job(**mapped))
                    inserted += 1
                    continue

                changed = False
                # 填充空值 + 校招口径同步
                for field in [
                    "company",
                    "department",
                    "job_title",
                    "location",
                    "major_req",
                    "job_req",
                    "job_duty",
                    "detail_url",
                    "source_config_id",
                ]:
                    nv = mapped.get(field)
                    ov = getattr(old, field, None)
                    if (ov is None or ov == "") and nv:
                        setattr(old, field, nv)
                        changed = True

                # job_stage 以 CSV 为准（当前全是 campus）
                if mapped["job_stage"] and old.job_stage != mapped["job_stage"]:
                    old.job_stage = mapped["job_stage"]
                    changed = True

                for field in ["publish_date", "deadline"]:
                    nv = mapped.get(field)
                    ov = getattr(old, field, None)
                    if ov is None and nv is not None:
                        setattr(old, field, nv)
                        changed = True

                # 抓取时间更新为较新值
                if mapped["scraped_at"] and (old.scraped_at is None or mapped["scraped_at"] > old.scraped_at):
                    old.scraped_at = mapped["scraped_at"]
                    changed = True

                if changed:
                    updated += 1

        db.commit()
        total_db = db.query(Job).count()
        print(
            f"SYNC_DONE scanned={scanned} inserted={inserted} updated={updated} skipped={skipped} total_jobs={total_db} csv={CSV_PATH}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
