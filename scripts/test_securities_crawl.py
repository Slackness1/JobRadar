"""
测试 Playwright 爬虫 - 只爬取一个券商
"""
import hashlib
import os
import time
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import Job

# 代理服务器配置
PROXY_SERVER = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7890"

# 测试配置 - 只爬取中金公司
TEST_COMPANY = {
    "name": "中金公司",
    "url": "https://cicc.zhiye.com/",
    "company_type": "A档券商",
}

def _safe_text(element) -> str:
    """安全提取文本内容"""
    if element is None:
        return ""
    return str(element).strip()

def _build_job_id(company: str, title: str, url: str) -> str:
    """构建唯一的岗位ID"""
    raw = f"securities_playwright|{company}|{title}|{url}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]

def _infer_stage(title: str) -> str:
    """推断岗位阶段（校园招聘/实习）"""
    if "实习" in title:
        return "internship"
    return "campus"

def scrape_single_site(company_name: str, site_config: Dict[str, Any], max_retries: int = 3) -> List[Dict[str, Any]]:
    """爬取单个券商网站的岗位数据"""
    from playwright.sync_api import sync_playwright

    url = site_config["url"]
    company_type = site_config["company_type"]
    selectors = site_config.get("selectors", {})

    records = []
    visited_urls = set()

    print(f"\n正在测试爬取 {company_name} ({url})...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_SERVER} if PROXY_SERVER else None
        )

        for attempt in range(max_retries):
            page = None
            try:
                page = browser.new_page()
                print(f"  尝试访问 {url}")
                response = page.goto(url, wait_until="networkidle", timeout=30000)

                if response and response.status != 200:
                    print(f"  HTTP状态码: {response.status}")
                    continue

                print(f"  页面标题: {page.title()}")

                # 等待页面加载
                time.sleep(3)

                # 尝试查找岗位列表
                job_list_selectors = [
                    selectors.get("job_list"),
                    ".job-item",
                    ".position-item",
                    ".recruitment-item",
                    "[class*='job']",
                    "[class*='position']",
                    "li",
                ]

                job_items = []
                for selector in job_list_selectors:
                    if not selector:
                        continue
                    try:
                        items = page.locator(selector).all()
                        if items and len(items) > 5:
                            job_items = items
                            print(f"  使用选择器 '{selector}' 找到 {len(job_items)} 个岗位")
                            break
                    except Exception as e:
                        continue

                if not job_items:
                    print(f"  未找到岗位列表，尝试查找所有链接...")
                    all_links = page.locator("a").all()
                    for link in all_links[:50]:
                        try:
                            text = link.inner_text()
                            href = link.get_attribute("href")
                            if href and any(keyword in text.lower() for keyword in ["校园", "实习", "招聘", "岗位", "职位"]):
                                job_items.append(link)
                        except:
                            pass
                    print(f"  通过关键词找到 {len(job_items)} 个潜在岗位")

                # 提取岗位信息
                for item in job_items[:100]:
                    try:
                        title_text = _safe_text(item.inner_text())
                        if not title_text or len(title_text) < 2:
                            continue

                        detail_url = url

                        location = ""
                        location_selectors = [".location", ".city"]
                        for loc_sel in location_selectors:
                            try:
                                loc_element = item.locator(loc_sel).first
                                if loc_element:
                                    location = _safe_text(loc_element.inner_text())
                                    break
                            except:
                                continue

                        job_id = _build_job_id(company_name, title_text, detail_url)
                        if job_id in visited_urls:
                            continue
                        visited_urls.add(job_id)

                        records.append({
                            "job_id": job_id,
                            "source": "securities_playwright",
                            "company": company_name,
                            "company_type_industry": "券商",
                            "company_tags": company_type,
                            "department": company_name,
                            "job_title": title_text,
                            "location": location,
                            "major_req": "",
                            "job_req": "",
                            "job_duty": "",
                            "application_status": "待申请",
                            "job_stage": _infer_stage(title_text),
                            "source_config_id": f"securities:{company_name}",
                            "publish_date": datetime.now(),
                            "deadline": None,
                            "detail_url": detail_url,
                            "scraped_at": datetime.now(),
                        })

                    except Exception as e:
                        continue

                print(f"  成功爬取 {len(records)} 个岗位")
                # 成功爬取后跳出外层的 for-retries 循环
                break

            except Exception as e:
                print(f"  错误: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if page:
                    try:
                        page.close()
                    except:
                        pass

        browser.close()

    return records

if __name__ == "__main__":
    from app.database import get_db

    db = next(get_db())
    existing_jobs = {}
    new_count = 0

    records = scrape_single_site(TEST_COMPANY["name"], TEST_COMPANY)

    print(f"\n共获取 {len(records)} 条岗位记录")

    for mapped in records:
        job_id = mapped.get("job_id")
        if not job_id:
            continue

        existing = existing_jobs.get(job_id)
        if existing is None:
            job = Job(**mapped)
            db.add(job)
            existing_jobs[job_id] = job
            new_count += 1
            print(f"新增岗位: {mapped.get('company')} - {mapped.get('job_title')}")
        else:
            print(f"  已存在: {mapped.get('company')} - {mapped.get('job_title')}")

    db.commit()
    print(f"\n完成！新增 {new_count} 条，共处理 {len(records)} 条")
