"""
基于Playwright的券商校园招聘爬虫
直接访问券商官网的校园招聘页面
"""
import hashlib
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import Page, Browser, BrowserContext
from sqlalchemy.orm import Session

from app.models import Job

# 代理服务器配置
PROXY_SERVER = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7890"

# 目标券商校园招聘网站配置
SECURITIES_SITES = {
    # A档券商
    "中金公司": {
        "url": "https://cicc.zhiye.com/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .position-item, .recruitment-item",
            "title": ".title, .position-name, .job-title",
            "location": ".location, .city, .workplace",
            "deadline": ".deadline, .end-date",
            "link": "a",
        }
    },
    "中信证券": {
        "url": "https://www.citics.com/newcn/joinus/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "华泰证券": {
        "url": "https://www.htsc.com.cn/recruitment/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .recruitment-item",
            "title": ".title, .job-title",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "中信建投": {
        "url": "https://www.csc.com.cn/csrc/csrc/joinus/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "国泰君安": {
        "url": "https://gtja.zhiye.com/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "海通证券": {
        "url": "https://www.htsec.com/Recruitment/",
        "company_type": "A档券商",
        "selectors": {
            "job_list": ".job-item, .recruitment-item",
            "title": ".title, .job-title",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    # A-档券商
    "招商证券": {
        "url": "https://www.cmschina.com/careers/",
        "company_type": "A-档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "申万宏源": {
        "url": "https://www.swhyresearch.com/recruitment/",
        "company_type": "A-档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "广发证券": {
        "url": "https://www.gf.com.cn/recruitment/",
        "company_type": "A-档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "中国银河": {
        "url": "https://www.chinastock.com.cn/recruitment/",
        "company_type": "A-档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "国信证券": {
        "url": "https://www.guosen.com.cn/guosen/jsp/portal/",
        "company_type": "A-档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    # B档券商
    "东方证券": {
        "url": "https://www.orientsec.com.cn/careers/",
        "company_type": "B档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "兴业证券": {
        "url": "https://www.xyzq.com.cn/servlet/DispatchServlet",
        "company_type": "B档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "光大证券": {
        "url": "https://www.ebscn.com/main/Recruitment/",
        "company_type": "B档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "中泰证券": {
        "url": "https://www.zts.com.cn/main/Recruitment/",
        "company_type": "B档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "国金证券": {
        "url": "https://www.gjzq.com.cn/main/Recruitment/",
        "company_type": "B档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
    "安信证券": {
        "url": "https://www.essence.com.cn/recruitment/",
        "company_type": "B档券商",
        "selectors": {
            "job_list": ".job-item, .position-item",
            "title": ".title, .position-name",
            "location": ".location, .city",
            "deadline": ".deadline",
            "link": "a",
        }
    },
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


def scrape_securities_site(
    browser: Browser,
    company_name: str,
    site_config: Dict[str, Any],
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """爬取单个券商网站的岗位数据"""
    url = site_config["url"]
    company_type = site_config["company_type"]
    selectors = site_config.get("selectors", {})

    records = []
    visited_urls = set()

    print(f"正在爬取 {company_name} ({url})...")

    for attempt in range(max_retries):
        try:
            # 创建新的页面
            page = browser.new_page()

            # 访问网站
            print(f"  尝试 {attempt + 1}/{max_retries}: 访问 {url}")
            response = page.goto(url, wait_until="networkidle", timeout=30000)

            if response and response.status != 200:
                print(f"  HTTP状态码: {response.status}")
                page.close()
                continue

            # 等待页面加载
            time.sleep(2)

            # 获取页面标题，验证是否成功加载
            title = page.title()
            print(f"  页面标题: {title}")

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
                    if items and len(items) > 5:  # 至少要有几个岗位才算有效
                        job_items = items
                        print(f"  使用选择器 '{selector}' 找到 {len(job_items)} 个岗位")
                        break
                except Exception as e:
                    continue

            if not job_items:
                print(f"  未找到岗位列表，尝试查找所有链接...")
                # 尝试查找所有包含关键词的链接
                all_links = page.locator("a").all()
                for link in all_links[:50]:  # 限制数量
                    try:
                        text = link.inner_text()
                        href = link.get_attribute("href")
                        if href and any(keyword in text.lower() for keyword in ["校园", "实习", "招聘", "岗位", "职位"]):
                            job_items.append(link)
                    except:
                        pass
                print(f"  通过关键词找到 {len(job_items)} 个潜在岗位")

            # 提取岗位信息
            for item in job_items[:100]:  # 限制最大数量
                try:
                    # 提取标题
                    title_element = None
                    title_selectors = selectors.get("title", [".title", ".position-name"])
                    if isinstance(title_selectors, str):
                        title_selectors = [title_selectors]

                    for title_sel in title_selectors:
                        try:
                            title_element = item.locator(title_sel).first
                            if title_element:
                                break
                        except:
                            continue

                    if not title_element:
                        title_text = item.inner_text()
                    else:
                        title_text = title_element.inner_text()

                    if not title_text or len(title_text) < 2:
                        continue

                    # 提取链接
                    link_element = item.locator("a").first
                    detail_url = ""
                    if link_element:
                        href = link_element.get_attribute("href")
                        if href:
                            detail_url = href
                            if not href.startswith("http"):
                                if href.startswith("/"):
                                    detail_url = url + href
                                else:
                                    detail_url = url + "/" + href

                    # 提取地点
                    location = ""
                    location_selectors = selectors.get("location", [".location", ".city"])
                    if isinstance(location_selectors, str):
                        location_selectors = [location_selectors]

                    for loc_sel in location_selectors:
                        try:
                            loc_element = item.locator(loc_sel).first
                            if loc_element:
                                location = loc_element.inner_text()
                                break
                        except:
                            continue

                    # 去重检查
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

            page.close()
            print(f"  成功爬取 {len(records)} 个岗位")
            break

        except Exception as e:
            print(f"  错误: {e}")
            try:
                page.close()
            except:
                pass
            time.sleep(1)

    return records


def run_securities_playwright_crawl(db: Session, existing_jobs: Dict[str, Job]) -> Tuple[int, int]:
    """运行Playwright券商爬虫"""
    from playwright.sync_api import sync_playwright

    total_records = []
    new_count = 0

    with sync_playwright() as p:
        # 启动浏览器（必须使用代理才能访问 HTTPS）
        browser = p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_SERVER}
        )

        try:
            # 爬取每个券商网站
            for company_name, site_config in SECURITIES_SITES.items():
                records = scrape_securities_site(browser, company_name, site_config)
                total_records.extend(records)

            browser.close()

        except Exception as e:
            print(f"浏览器错误: {e}")
            try:
                browser.close()
            except:
                pass

    # 保存数据到数据库
    print(f"\n共获取 {len(total_records)} 条岗位记录")

    for mapped in total_records:
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
            # 更新已有记录
            for field in [
                "company",
                "company_tags",
                "department",
                "job_title",
                "location",
                "job_stage",
                "detail_url",
                "scraped_at",
            ]:
                value = mapped.get(field)
                if value not in (None, ""):
                    setattr(existing, field, value)

    print(f"\n统计: 新增 {new_count} 条岗位，更新 {len(total_records) - new_count} 条岗位")
    return new_count, len(total_records)


if __name__ == "__main__":
    # 测试代码
    from app.database import get_db

    db = next(get_db())
    existing_jobs = {}
    new_count, total_count = run_securities_playwright_crawl(db, existing_jobs)
    db.commit()
    print(f"\n完成！新增 {new_count} 条，共处理 {total_count} 条")
