#!/usr/bin/env python3
"""简化版券商爬虫测试"""
import hashlib
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models import Job

# 代理服务器配置
PROXY_SERVER = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7890"

# 测试目标（只测试 2 个 A 档）
SECURITIES_SITES = {
    "中金公司": {
        "url": "https://cicc.zhiye.com/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
        }
    },
    "中信证券": {
        "url": "https://www.citics.com/newcn/joinus/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
        }
    },
}

def _safe_text(element) -> str:
    if element is None:
        return ""
    return str(element).strip()

def _build_job_id(company: str, title: str, url: str) -> str:
    raw = f"securities_playwright|{company}|{title}|{url}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]

def scrape_one_site(
    browser,
    company_name: str,
    site_config: Dict[str, Any],
    max_retries: int = 2
) -> List[Dict[str, Any]]:
    """爬取单个券商网站"""
    url = site_config["url"]
    company_type = site_config["company_type"]
    selectors = site_config.get("selectors", {})

    records = []

    print(f"\n{'='*60}")
    print(f"爬取 {company_name} ({url})")
    print(f"{'='*60}")

    for attempt in range(max_retries):
        try:
            page = browser.new_page()
            print(f"\n[尝试 {attempt+1}/{max_retries}] 访问 {url}")
            response = page.goto(url, wait_until="networkidle", timeout=30000)

            if response and response.status != 200:
                print(f"  ❌ HTTP 状态码: {response.status}")
                page.close()
                continue

            print(f"  ✓ HTTP {response.status} - {page.title()}")
            time.sleep(2)

            # 尝试查找岗位列表
            job_items = []
            job_list_sel = selectors.get("job_list", ".job-item")
            try:
                items = page.locator(job_list_sel).all()
                if items:
                    job_items = items
                    print(f"  ✓ 找到 {len(items)} 个岗位（选择器: {job_list_sel}）")
                else:
                    print(f"  ⚠ 未找到 {job_list_sel}，尝试其他选择器...")
            except Exception as e:
                print(f"  ⚠ 查找岗位列表失败: {e}")

            if not job_items:
                # 尝试通过链接过滤
                all_links = page.locator("a").all()
                for link in all_links[:20]:
                    try:
                        text = link.inner_text()
                        href = link.get_attribute("href")
                        if href and any(kw in text for kw in ["校园", "实习", "招聘"]):
                            job_items.append(link)
                    except:
                        pass
                print(f"  ⚠ 通过关键词找到 {len(job_items)} 个潜在岗位")

            # 提取岗位
            count = 0
            for item in job_items[:50]:
                try:
                    title = item.inner_text()
                    if not title or len(title) < 3:
                        continue

                    link = item.locator("a").first
                    detail_url = link.get_attribute("href") if link else ""

                    records.append({
                        "job_id": _build_job_id(company_name, title, detail_url),
                        "source": "securities_playwright",
                        "company": company_name,
                        "company_type_industry": "券商",
                        "company_tags": company_type,
                        "department": company_name,
                        "job_title": title,
                        "location": "",
                        "major_req": "",
                        "job_req": "",
                        "job_duty": "",
                        "application_status": "待申请",
                        "job_stage": "campus",
                        "source_config_id": f"securities:{company_name}",
                        "publish_date": datetime.now(),
                        "deadline": None,
                        "detail_url": detail_url,
                        "scraped_at": datetime.now(),
                    })
                    count += 1
                except Exception as e:
                    continue

            print(f"  ✓ 成功提取 {count} 个岗位")
            page.close()
            return records

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            try:
                page.close()
            except:
                pass
            if attempt < max_retries - 1:
                time.sleep(1)

    return records

def main():
    from app.database import get_db

    db = next(get_db())
    existing_jobs = {}

    print(f"\n代理配置: {PROXY_SERVER}")
    print(f"测试目标: {list(SECURITIES_SITES.keys())}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_SERVER}
        )

        total_records = []

        try:
            for company_name, site_config in SECURITIES_SITES.items():
                records = scrape_one_site(browser, company_name, site_config)
                total_records.extend(records)

        except Exception as e:
            print(f"\n❌ 整体错误: {e}")
        finally:
            browser.close()

    print(f"\n{'='*60}")
    print(f"共获取 {len(total_records)} 条岗位记录")
    print(f"{'='*60}")

    # 尝试入库
    new_count = 0
    for job in total_records:
        job_id = job.get("job_id")
        if not job_id:
            continue

        existing = existing_jobs.get(job_id)
        if existing is None:
            job = Job(**job)
            db.add(job)
            existing_jobs[job_id] = job
            new_count += 1
            print(f"  新增: {job.get('company')} - {job.get('job_title')[:50]}")
        else:
            print(f"  更新: {job.get('company')} - {job.get('job_title')[:50]}")

    db.commit()
    print(f"\n✓ 入库完成: 新增 {new_count} 条")

if __name__ == "__main__":
    main()
