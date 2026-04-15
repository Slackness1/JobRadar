#!/usr/bin/env python3
"""
Moka招聘平台爬虫 - 针对使用Moka系统的公司（如普华永道）
"""

import hashlib
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

from app.models import Job

# Moka平台的通用配置
PROXY = {'server': 'http://127.0.0.1:7890'}
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36')
MAX_PAGES = 20
DELAY_BETWEEN_REQUESTS = 2


@dataclass
class JobInfo:
    id: str
    company: str
    title: str
    location: str
    department: str
    job_type: str
    url: str
    publish_date: Optional[str] = None
    deadline: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    crawled_at: str = ""

    def __post_init__(self):
        if not self.crawled_at:
            self.crawled_at = datetime.now().isoformat()
        if not self.id:
            self.id = hashlib.md5(f"{self.company}:{self.title}:{self.url}".encode()).hexdigest()[:12]


def create_moka_playwright():
    """创建Playwright浏览器实例"""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True, proxy=PROXY)
    return playwright, browser


def crawl_moka_campus(company_name: str, campus_url: str, playwright, browser) -> List[JobInfo]:
    """
    爬取Moka校招平台岗位

    Args:
        company_name: 公司名称
        campus_url: Moka校招页面URL
        playwright: Playwright实例
        browser: 浏览器实例

    Returns:
        JobInfo列表
    """
    jobs = []

    try:
        print(f"[INFO] 开始爬取 {company_name} 的校招岗位...")
        context = browser.new_context(
            user_agent=UA,
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            viewport={'width': 1440, 'height': 900},
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        print(f"[INFO] 访问 {campus_url}")
        page.goto(campus_url, wait_until="networkidle")

        # 等待页面加载完成
        time.sleep(3)

        # 查找岗位列表
        print(f"[INFO] 查找岗位元素...")

        # 尝试多种可能的岗位选择器
        job_selectors = [
            '.job-item',
            '.job-card',
            '[class*="job"]',
            '[class*="position"]',
            'a[href*="job"]',
            'a[href*="position"]'
        ]

        job_elements = []
        for selector in job_selectors:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"[INFO] 使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                job_elements = elements
                break

        if not job_elements:
            print(f"[WARN] 未找到岗位元素，尝试查找API请求...")

            # 尝试拦截网络请求
            def handle_response(response):
                try:
                    if 'job' in response.url.lower() and response.status == 200:
                        try:
                            data = response.json()
                            print(f"[DEBUG] 捕获API: {response.url}")
                            print(f"[DEBUG] 数据: {str(data)[:200]}")
                        except:
                            pass
                except Exception as e:
                    pass

            page.on('response', handle_response)

            # 重新加载页面
            page.reload(wait_until="networkidle")
            time.sleep(5)

        # 解析岗位信息
        for i, element in enumerate(job_elements[:50], 1):  # 限制最多50个岗位
            try:
                print(f"[DEBUG] 解析第 {i} 个岗位...")

                # 尝试获取岗位信息
                title_element = element.query_selector('a, [class*="title"], [class*="name"], h1, h2, h3, h4')
                if not title_element:
                    continue

                title = title_element.inner_text().strip()
                job_url = title_element.get_attribute('href')

                if not job_url:
                    continue

                # 补全URL
                if job_url.startswith('/'):
                    job_url = f"https://app.mokahr.com{job_url}"
                elif not job_url.startswith('http'):
                    job_url = f"{campus_url}/{job_url}"

                # 查找地点
                location = "未知地点"
                location_selectors = ['[class*="location"]', '[class*="city"]', '[class*="place"]']
                for loc_selector in location_selectors:
                    loc_element = element.query_selector(loc_selector)
                    if loc_element:
                        location = loc_element.inner_text().strip()
                        break

                # 创建岗位信息
                job_info = JobInfo(
                    company=company_name,
                    title=title,
                    location=location,
                    department="未知部门",
                    job_type="campus",
                    url=job_url,
                )

                jobs.append(job_info)
                print(f"[INFO] 找到岗位: {title} - {location}")

            except Exception as e:
                print(f"[WARN] 解析岗位时出错: {str(e)}")
                continue

        page.close()
        context.close()

    except Exception as e:
        print(f"[ERROR] 爬取 {company_name} 时出错: {str(e)}")

    return jobs


def save_jobs_to_db(db: Session, jobs: List[JobInfo]) -> int:
    """
    将岗位保存到数据库

    Args:
        db: 数据库会话
        jobs: 岗位列表

    Returns:
        新增岗位数量
    """
    new_count = 0

    for job_info in jobs:
        try:
            # 检查是否已存在
            existing_job = db.query(Job).filter(Job.id == job_info.id).first()

            if existing_job:
                print(f"[INFO] 岗位已存在: {job_info.title}")
                continue

            # 创建新岗位
            job = Job(
                id=job_info.id,
                company=job_info.company,
                title=job_info.title,
                location=job_info.location,
                department=job_info.department,
                job_stage=job_info.job_type,  # 使用job_stage代替job_type
                url=job_info.url,
                publish_date=job_info.publish_date,
                deadline=job_info.deadline,
                description=job_info.description,
                requirements=job_info.requirements,
                crawled_at=job_info.crawled_at
            )

            db.add(job)
            db.commit()
            new_count += 1
            print(f"[INFO] 新增岗位: {job_info.title}")

        except Exception as e:
            db.rollback()
            print(f"[ERROR] 保存岗位时出错: {str(e)}")
            continue

    return new_count


def crawl_mbb_big4(
    db: Session,
    company_config: Dict[str, Any],
    return_diagnostics: bool = False,
) -> Tuple[int, List[JobInfo] | Dict[str, Any]]:
    """
    爬取四大会计师事务所和MBB咨询公司的岗位

    Args:
        db: 数据库会话
        company_config: 公司配置
        return_diagnostics: 是否返回检测/证据/校验结果

    Returns:
        (新增岗位数量, 岗位列表或诊断结果)
    """
    all_jobs: List[JobInfo] = []
    diagnostics: Dict[str, Any] | None = None

    try:
        playwright, browser = create_moka_playwright()

        try:
            company_name = company_config.get('name', '')
            platform = company_config.get('platform', 'custom')
            campus_url = company_config.get('campus_url', '')
            career_url = company_config.get('career_url', '')

            if platform == 'moka' and campus_url:
                print(f"[INFO] 使用Moka平台爬取 {company_name}")
                result = crawl_moka_campus(
                    company_name,
                    campus_url,
                    playwright,
                    browser,
                    return_diagnostics=return_diagnostics,
                )
                if return_diagnostics:
                    diagnostics = result if isinstance(result, dict) else None
                    jobs = [JobInfo(**item) for item in diagnostics.get('jobs', [])] if diagnostics else []
                else:
                    jobs = result  # type: ignore[assignment]
            else:
                print(f"[INFO] {company_name} 使用自定义平台，暂未实现")
                jobs = []
                if return_diagnostics:
                    diagnostics = {
                        'jobs': [],
                        'detection': {},
                        'evidence': {},
                        'validation': {},
                        'notes': [f'{company_name} custom platform not implemented', career_url],
                    }

            all_jobs.extend(jobs)

        finally:
            browser.close()
            playwright.stop()

        new_count = save_jobs_to_db(db, all_jobs)

        if return_diagnostics and diagnostics is not None:
            diagnostics['new_count'] = new_count
            return new_count, diagnostics

        return new_count, all_jobs

    except Exception as e:
        print(f"[ERROR] 爬取过程出错: {str(e)}")
        return 0, {} if return_diagnostics else []


if __name__ == "__main__":
    from app.database import SessionLocal

    db = SessionLocal()

    test_config = {
        'name': '普华永道',
        'platform': 'moka',
        'campus_url': 'https://app.mokahr.com/campus_apply/pwc/148260',
        'career_url': 'https://www.pwccn.com/careers.html'
    }

    new_count, jobs = crawl_mbb_big4(db, test_config)
    print(f"\\n[INFO] 爬取完成，新增 {new_count} 个岗位")

    db.close()
