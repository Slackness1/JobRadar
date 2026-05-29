"""One-off: 跑 ground_truth 补缺的两个快赢 — 中银证券 (stc_cms_decodo) + 高盛 (goldman_graphql)。"""
import os
import sys

import app.config  # noqa: F401  loads .env.local into os.environ

# Decodo helper 读 DECODO_AUTHORIZATION;由 WEB_SCRAPING_API_KEY 拼 Basic 头
ws = os.environ.get("WEB_SCRAPING_API_KEY")
if ws and not os.environ.get("DECODO_AUTHORIZATION"):
    os.environ["DECODO_AUTHORIZATION"] = f"Basic {ws}"

from app.database import SessionLocal
from app.models import Job


def main():
    db = SessionLocal()
    try:
        existing = {j.job_id: j for j in db.query(Job).all() if j.job_id}

        print("=== 中银证券 (securities stc_cms_decodo) ===")
        from app.services.securities_crawler import run_configured_securities_crawl
        new_c, total_c, per = run_configured_securities_crawl(
            db, existing, target_names=["中银证券"]
        )
        print(f"  中银证券: fetched={total_c} new={new_c} per={per}")

        print("\n=== 高盛 (foreign_ibs goldman_graphql) ===")
        from app.services.foreign_ibs_tier_crawler import crawl_foreign_ibs
        g_new, g_fetched, g_per = crawl_foreign_ibs(
            db, existing_jobs=existing, target_names=["Goldman Sachs"]
        )
        print(f"  高盛: fetched={g_fetched} new={g_new} per={g_per}")

        db.commit()
        print("\n[committed]")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
