#!/usr/bin/env python3
"""
Job Crawler - 招聘信息爬虫 (Playwright 浏览器版)
"""

import csv
import json
import yaml
import hashlib
import logging
import re
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse, parse_qs

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('job-crawler')

PROXY = {'server': 'http://127.0.0.1:7890'}
REQUEST_PROXIES = {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36')
MAX_PAGES = 20
MAX_EMPTY_PAGES = 2


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


STEALTH_SCRIPT = r"""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'});
window.chrome = window.chrome || {runtime: {}};
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""


def make_browser(playwright):
    browser = playwright.chromium.launch(headless=True, proxy=PROXY)
    return browser


def new_page(browser):
    context = browser.new_context(
        user_agent=UA,
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
        viewport={'width': 1440, 'height': 900},
    )
    context.add_init_script(STEALTH_SCRIPT)
    page = context.new_page()
    page.set_default_timeout(30000)
    page._captured_json = []

    def on_response(resp):
        ctype = (resp.headers or {}).get('content-type', '')
        url = resp.url
        # 放宽条件：捕获 chinahr.com 的所有响应，以及所有 JSON 响应
        if 'json' not in ctype.lower() and 'chinahr' not in url and 'applyjob' not in url and 'api' not in url and 'position' not in url and 'job' not in url:
            return
        try:
            data = resp.json()
            # 记录所有捕获的响应（仅调试）
            # import logging
            # logger.debug(f'捕获响应: {url[:100]}...')
            page._captured_json.append({'url': url, 'data': data})
        except Exception:
            pass

    page.on('response', on_response)
    return context, page


def wait_and_get(page, selector, timeout=10000):
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return page.query_selector_all(selector)
    except Exception:
        return []


def abs_url(base: str, href: Optional[str]) -> str:
    href = href or ''
    if not href:
        return ''
    return urljoin(base, href)


def norm_text(value: Any) -> str:
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def looks_like_job(item: Dict[str, Any]) -> bool:
    keys = set(item.keys())
    title_keys = {'title', 'name', 'jobname', 'positionname', 'recruitpostname', 'postname'}
    url_keys = {'url', 'posturl', 'positionurl', 'detailurl', 'link'}
    id_keys = {'id', 'postid', 'jobid', 'recruitpostid'}
    return bool(keys & title_keys) and bool(keys & (url_keys | id_keys))


def build_job_from_item(company: str, job_type: str, item: Dict[str, Any], base_url: str) -> Optional[JobInfo]:
    lowered = {str(k).lower(): v for k, v in item.items()}
    title = norm_text(
        lowered.get('title') or lowered.get('name') or lowered.get('jobname') or
        lowered.get('positionname') or lowered.get('recruitpostname') or lowered.get('postname')
    )
    if not title:
        return None
    location = norm_text(
        lowered.get('location') or lowered.get('locationname') or lowered.get('city') or
        lowered.get('city_name') or lowered.get('workcity') or lowered.get('worklocation') or
        lowered.get('worklocationname') or lowered.get('address') or '未知'
    )
    department = norm_text(
        lowered.get('department') or lowered.get('departmentname') or lowered.get('productname') or
        lowered.get('category_name') or lowered.get('categoryname') or lowered.get('bgname') or
        lowered.get('postcodename') or lowered.get('jobname') or ''
    )
    raw_url = (
        lowered.get('url') or lowered.get('posturl') or lowered.get('positionurl') or
        lowered.get('detailurl') or lowered.get('link') or ''
    )
    pid = lowered.get('postid') or lowered.get('id') or lowered.get('jobid') or lowered.get('recruitpostid')
    if not raw_url and pid:
        raw_url = str(pid)
    url = str(raw_url)
    if company == '腾讯' and pid:
        url = f'https://careers.tencent.com/jobdesc.html?postId={pid}'
    elif company == '字节跳动' and pid:
        url = f'https://jobs.bytedance.com/campus/position/{pid}/detail'
    elif company == '哔哩哔哩' and pid:
        url = f'https://jobs.bilibili.com/campus/positions?positionId={pid}'
    elif company == '拼多多' and pid:
        url = f'https://careers.pddglobalhr.com/campus/grad?jobId={pid}'
    elif url and not url.startswith('http'):
        url = abs_url(base_url, url)
    return JobInfo(
        id='', company=company, title=title, location=location or '未知', department=department,
        job_type=job_type, url=url, publish_date=norm_text(
            lowered.get('publishtime') or lowered.get('publish_date') or lowered.get('createtime') or
            lowered.get('create_time') or lowered.get('updated_at') or lowered.get('pushtime') or
            lowered.get('releasetime') or ''
        ),
        description=norm_text(lowered.get('description') or lowered.get('positiondescription') or lowered.get('jobduty') or ''),
        requirements=norm_text(lowered.get('requirement') or lowered.get('jobrequire') or '')
    )


def iter_job_dicts(data: Any):
    if isinstance(data, dict):
        if looks_like_job(data):
            yield data
        for value in data.values():
            yield from iter_job_dicts(value)
    elif isinstance(data, list):
        for item in data:
            yield from iter_job_dicts(item)


def collect_jobs_from_responses(page, company: str, job_type: str, base_url: str, url_keywords: Optional[List[str]] = None) -> List[JobInfo]:
    seen: Set[str] = set()
    jobs: List[JobInfo] = []
    for entry in getattr(page, '_captured_json', []):
        resp_url = entry['url']
        if url_keywords and not any(k in resp_url for k in url_keywords):
            continue
        for item in iter_job_dicts(entry['data']):
            job = build_job_from_item(company, job_type, item, base_url)
            if not job:
                continue
            if job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(job)
    return jobs


def extract_jobs_dom(page, company: str, target: Dict[str, Any], selectors: List[str], base_url: str) -> List[JobInfo]:
    combined = []
    for selector in selectors:
        try:
            combined.extend(page.query_selector_all(selector))
        except Exception:
            pass
    jobs = []
    seen: Set[str] = set()
    for item in combined:
        try:
            t = item.query_selector('[class*="title" i], [class*="name" i], h3, h4, td:first-child, a')
            l = item.query_selector('[class*="location" i], [class*="city" i], [class*="work" i], td:nth-child(2), td:nth-child(3)')
            d = item.query_selector('[class*="department" i], [class*="dept" i], [class*="category" i]')
            a = item.query_selector('a')
            href = a.get_attribute('href') if a else ''
            href = href or ''
            title = norm_text(t.inner_text() if t else '')
            if len(title) < 2:
                continue
            job = JobInfo(
                id='', company=company, title=title, location=norm_text(l.inner_text() if l else '') or '未知',
                department=norm_text(d.inner_text() if d else ''), job_type=target.get('type', 'campus'),
                url=abs_url(base_url, href)
            )
            if job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(job)
        except Exception:
            continue
    return jobs


def scroll_until_stable(page, rounds: int = 6, pause: float = 1.5):
    last_height = -1
    stable = 0
    for _ in range(rounds):
        try:
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        except Exception:
            break
        time.sleep(pause)
        try:
            height = page.evaluate('document.body.scrollHeight')
        except Exception:
            break
        if height == last_height:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        last_height = height


def goto_and_wait(page, url: str, timeout: int = 30000, extra_sleep: float = 2):
    page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    try:
        page.wait_for_load_state('networkidle', timeout=timeout)
    except Exception:
        pass
    if extra_sleep:
        time.sleep(extra_sleep)


def click_next_page(page) -> bool:
    selectors = [
        'text=下一页', 'text=下页', 'text=Next',
        '[aria-label="next"]', '[class*="next" i]', '.ant-pagination-next', '.pagination-next'
    ]
    for selector in selectors:
        try:
            btn = page.query_selector(selector)
            if not btn:
                continue
            cls = (btn.get_attribute('class') or '').lower()
            disabled = btn.get_attribute('disabled') is not None or 'disabled' in cls
            if disabled:
                continue
            btn.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


def crawl_with_pagination(page, target: Dict[str, Any], company: str, base_url: str,
                          selectors: List[str], scroll: bool = False,
                          timeout: int = 30000, extra_sleep: float = 2,
                          response_keywords: Optional[List[str]] = None,
                          max_pages: Optional[int] = None) -> List[JobInfo]:
    all_jobs: List[JobInfo] = []
    seen_ids: Set[str] = set()
    empty_rounds = 0
    current_url = target['url']
    skip_goto = False

    page_limit = max_pages or int(target.get('max_pages') or MAX_PAGES)

    for page_no in range(1, page_limit + 1):
        logger.info(f'{company} - 第 {page_no}/{page_limit} 页')
        if not skip_goto:
            goto_and_wait(page, current_url, timeout=timeout, extra_sleep=extra_sleep)
        else:
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                pass
            time.sleep(extra_sleep)
        skip_goto = False
        if scroll:
            scroll_until_stable(page)

        page_jobs = collect_jobs_from_responses(page, company, target.get('type', 'campus'), base_url, response_keywords)
        if not page_jobs:
            page_jobs = extract_jobs_dom(page, company, target, selectors, base_url)

        fresh = [j for j in page_jobs if j.id not in seen_ids]
        for job in fresh:
            seen_ids.add(job.id)
        all_jobs.extend(fresh)

        if not fresh:
            empty_rounds += 1
            if empty_rounds >= MAX_EMPTY_PAGES:
                logger.info(f'{company}: 连续 {MAX_EMPTY_PAGES} 页空结果，终止')
                break
        else:
            empty_rounds = 0

        url_before_click = page.url
        next_clicked = click_next_page(page)
        if next_clicked:
            time.sleep(2)
            if page.url == url_before_click:
                skip_goto = True
            else:
                current_url = page.url
            continue

        parsed = urlparse(target['url'])
        query = parse_qs(parsed.query)
        if 'current' in query:
            next_page = page_no + 1
            current_url = re.sub(r'([?&]current=)\d+', rf'\g<1>{next_page}', current_url or target['url'])
            if current_url == (page.url or target['url']):
                current_url = re.sub(r'([?&]current=)\d+', rf'\g<1>{next_page}', target['url'])
            continue
        break

    return all_jobs


def crawl_bytedance(page, target) -> List[JobInfo]:
    """字节跳动：
    - 初始 goto 加载页面，等待第一次 /api/v1/search/job/posts 响应获取 total_count
    - 之后通过点击分页器的「下一页」按钮（~1s/page）逐页采集
    - 所有 JSON 响应由 on_response 拦截收集，无需解析 DOM
    - API 请求携带 _signature（页面 JS 自动附加），无法从外部 requests 直接调用
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    total_count = [0]

    def _ingest_post_item(item: Dict[str, Any]) -> Optional[JobInfo]:
        pid = str(item.get('id') or '').strip()
        title = norm_text(item.get('title') or item.get('sub_title') or '')
        if not title or not pid:
            return None
        if pid in seen:
            return None
        seen.add(pid)
        city_info = item.get('city_info') or {}
        city_list = item.get('city_list') or []
        if city_list:
            location = norm_text('/'.join(c.get('name', '') for c in city_list if c.get('name'))) or '未知'
        else:
            location = norm_text(city_info.get('name') or city_info.get('i18n_name') or '') or '未知'
        category = item.get('job_category') or {}
        department = norm_text(category.get('name') or category.get('i18n_name') or '')
        job_func = item.get('job_function') or {}
        if not department:
            department = norm_text(job_func.get('name') or job_func.get('i18n_name') or '')
        recruit = item.get('recruit_type') or {}
        job_type = norm_text(recruit.get('name') or recruit.get('i18n_name') or target.get('type', 'campus'))
        publish_time = norm_text(str(item.get('publish_time') or ''))
        return JobInfo(
            id='', company='字节跳动', title=title, location=location,
            department=department, job_type=job_type,
            url=f'https://jobs.bytedance.com/campus/position/{pid}/detail',
            publish_date=publish_time,
        )

    # Intercept API responses directly (more reliable than scanning _captured_json)
    fresh_posts: List[JobInfo] = []

    def on_post_response(resp):
        url = resp.url
        ct = (resp.headers or {}).get('content-type', '')
        if 'search/job/posts' not in url or 'json' not in ct.lower():
            return
        try:
            data = resp.json()
        except Exception:
            return
        if not isinstance(data, dict) or data.get('code') != 0:
            return
        cnt = (data.get('data') or {}).get('count')
        if cnt:
            total_count[0] = int(cnt)
        posts = (data.get('data') or {}).get('job_post_list') or []
        for item in posts:
            job = _ingest_post_item(item)
            if job:
                fresh_posts.append(job)

    page.on('response', on_post_response)

    max_page_limit = int(target.get('max_pages') or MAX_PAGES)

    # Initial load
    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=4)
    except Exception as e:
        logger.warning(f'字节跳动初始页面加载失败: {e}')
        return jobs

    # Drain fresh_posts
    jobs.extend(fresh_posts)
    fresh_posts.clear()

    if total_count[0]:
        pages_needed = min(max_page_limit, (total_count[0] + 9) // 10)
    else:
        pages_needed = max_page_limit

    logger.info(f'字节跳动: total_count={total_count[0]}, pages_needed={pages_needed}, so_far={len(jobs)}')

    # Paginate via next-button clicks (~1s/page).
    # After BYTEDANCE_SESSION_RESET_INTERVAL pages the SPA stops returning new data in the
    # same browser context, so we do a hard goto to the target page number every N pages to
    # reset the session and let the response interceptor pick up fresh API results.
    BYTEDANCE_SESSION_RESET_INTERVAL = 150
    # Bumped from MAX_EMPTY_PAGES=2 to 6 — even with deterministic
    # wait_for_response, async response handler ordering can still produce
    # transient empty reads. 6 buys ~6s of slack before declaring exhaustion.
    BYTEDANCE_MAX_EMPTY_PAGES = 6
    empty_rounds = 0
    for pg in range(2, pages_needed + 1):
        before = len(jobs)

        # Periodic hard-reset: navigate directly to the current page number so the SPA
        # re-issues a fresh API request rather than serving stale cached state.
        if pg > 2 and (pg - 1) % BYTEDANCE_SESSION_RESET_INTERVAL == 0:
            logger.info(f'字节跳动: 会话重置 goto 第 {pg} 页 (每 {BYTEDANCE_SESSION_RESET_INTERVAL} 页重置一次)')
            try:
                goto_and_wait(page, f'https://jobs.bytedance.com/campus/position?current={pg}', timeout=30000, extra_sleep=3)
                jobs.extend(fresh_posts)
                fresh_posts.clear()
                added = len(jobs) - before
                if added == 0:
                    empty_rounds += 1
                    if empty_rounds >= BYTEDANCE_MAX_EMPTY_PAGES:
                        logger.info(f'字节跳动: 会话重置后仍空，终止于第 {pg} 页')
                        break
                else:
                    empty_rounds = 0
                continue
            except Exception as e:
                logger.warning(f'字节跳动会话重置失败于第 {pg} 页: {e}，继续尝试点击')

        try:
            next_btn = page.locator('.atsx-pagination-next:not(.atsx-pagination-disabled)').first
            if next_btn.count() == 0:
                logger.info(f'字节跳动: 第 {pg} 页找不到下一页按钮，终止')
                break
            next_btn.click(timeout=5000)
            # 异步竞争修复 (2026-05-08)：原本用 time.sleep(1.0) 等 API 响应；
            # 但 on_post_response 是 async 触发，sleep 完 fresh_posts 仍可能空
            # → added=0 假阳性 → MAX_EMPTY_PAGES=2 提前 kill。
            # 改成 deterministically wait_for_response 让 fresh_posts 必有数据
            # 再读，然后 sleep 0.3 缓冲。subagent 实测：原版 38/600 页就 break
            # (~349 jobs)；upstream 实际 7834 条。
            try:
                page.wait_for_response(
                    lambda r: 'search/job/posts' in r.url,
                    timeout=8000,
                )
                page.wait_for_timeout(300)  # tiny buffer for callback to fully drain
            except Exception:
                time.sleep(1.0)  # fallback if no API response captured
        except Exception as e:
            logger.warning(f'字节跳动第 {pg} 页点击失败: {e}，尝试 goto fallback')
            try:
                goto_and_wait(page, f'https://jobs.bytedance.com/campus/position?current={pg}', timeout=30000, extra_sleep=2)
            except Exception as e2:
                logger.warning(f'字节跳动第 {pg} 页 goto fallback 失败: {e2}')
                break

        jobs.extend(fresh_posts)
        fresh_posts.clear()
        added = len(jobs) - before

        if pg % 100 == 0 or added == 0:
            logger.info(f'字节跳动第 {pg}/{pages_needed} 页: +{added} (total={len(jobs)})')

        if added == 0:
            empty_rounds += 1
            if empty_rounds >= BYTEDANCE_MAX_EMPTY_PAGES:
                logger.info(f'字节跳动: 连续 {BYTEDANCE_MAX_EMPTY_PAGES} 页空结果，终止于第 {pg} 页')
                break
        else:
            empty_rounds = 0

    logger.info(f'字节跳动: 最终采集 {len(jobs)} 条岗位')
    return jobs


def crawl_tencent(page, target) -> List[JobInfo]:
    jobs = []
    seen = set()
    page_size = 100
    # Derive total pages from first response; cap at 50 pages (5000 jobs)
    max_page_limit = max(int(target.get('max_pages') or MAX_PAGES), 50)
    total_count = 0
    for idx in range(1, max_page_limit + 1):
        try:
            resp = requests.get(
                'https://careers.tencent.com/tencentcareer/api/post/Query',
                params={'pageIndex': idx, 'pageSize': page_size, 'language': 'zh-cn', 'area': 'cn'},
                headers={'User-Agent': UA, 'Accept': 'application/json', 'Referer': 'https://careers.tencent.com/'},
                proxies=REQUEST_PROXIES, timeout=30
            )
            data = resp.json()
            if idx == 1:
                total_count = int(((data or {}).get('Data') or {}).get('Count') or 0)
                if total_count:
                    pages_total = (total_count + page_size - 1) // page_size
                    max_page_limit = min(max_page_limit, pages_total)
                    logger.info(f'腾讯: total={total_count}, pages={max_page_limit}')
            posts = (((data or {}).get('Data') or {}).get('Posts') or [])
            if not posts:
                break
            page_added = 0
            for item in posts:
                job = build_job_from_item('腾讯', target.get('type', 'campus'), item, 'https://careers.tencent.com/')
                if job and job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
                    page_added += 1
            logger.info(f'腾讯 REST API 第 {idx} 页: {page_added} 条')
            if page_added == 0:
                break
        except Exception as e:
            logger.warning(f'腾讯 REST API 第 {idx} 页失败: {e}')
            break
    return jobs


def crawl_meituan(page, target) -> List[JobInfo]:
    """美团：直接调用 /api/official/job/getJobList REST 接口（无需浏览器会话）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    page_size = 20
    max_page_limit = int(target.get('max_pages') or MAX_PAGES)
    total_count = 0
    headers = {
        'User-Agent': UA,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Referer': 'https://zhaopin.meituan.com/web/campus',
    }
    page_no = 1
    while page_no <= max_page_limit:
        payload = {
            'page': {'pageNo': page_no, 'pageSize': page_size},
            'jobShareType': '1',
            'keywords': '',
            'cityList': [],
            'department': [],
            'jfJgList': [],
            'jobType': [],
            'typeCode': [],
            'specialCode': [],
        }
        try:
            resp = requests.post(
                'https://zhaopin.meituan.com/api/official/job/getJobList',
                json=payload,
                headers=headers,
                proxies=REQUEST_PROXIES,
                timeout=30,
            )
            data = resp.json() or {}
        except Exception as e:
            logger.warning(f'美团 API 第 {page_no} 页失败: {e}')
            break
        dd = data.get('data') or {}
        if page_no == 1:
            pg_info = dd.get('page') or {}
            total_count = int(pg_info.get('totalCount') or 0)
            if total_count:
                pages_total = (total_count + page_size - 1) // page_size
                max_page_limit = min(max(max_page_limit, pages_total), 300)
                logger.info(f'美团: total={total_count}, pages_needed={max_page_limit}')
        items = dd.get('list') or []
        if not items:
            break
        page_added = 0
        for item in items:
            title = norm_text(item.get('name') or item.get('jobName') or '')
            if not title:
                continue
            job_union_id = str(item.get('jobUnionId') or item.get('id') or '').strip()
            project_id = str(item.get('projectId') or '').strip()
            url = f'https://zhaopin.meituan.com/web/position/detail?jobId={job_union_id}' if job_union_id else target['url']
            cities = item.get('cityList') or []
            location = norm_text('/'.join(c.get('name', '') for c in cities if c.get('name'))) or '未知'
            dept = norm_text(item.get('department') or item.get('jobFamily') or item.get('jobFamilyGroup') or '')
            job_type_info = item.get('jobType') or {}
            jt_name = norm_text(job_type_info.get('name') or '') if isinstance(job_type_info, dict) else ''
            publish_date = norm_text(item.get('firstPostTime') or item.get('refreshTime') or '')
            deadline = norm_text(item.get('expiredTime') or '')
            job = JobInfo(
                id='', company='美团', title=title, location=location,
                department=dept, job_type=jt_name or target.get('type', 'campus'),
                url=url, publish_date=publish_date, deadline=deadline,
                description=norm_text(item.get('jobDuty') or item.get('desc') or ''),
                requirements=norm_text(item.get('jobRequirement') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'美团 API 第 {page_no} 页: {page_added} 条 / total={total_count}')
        if page_added == 0:
            break
        page_no += 1
    return jobs


def crawl_ctrip(page, target) -> List[JobInfo]:
    """携程: hash-routed SPA. Job links render as `#/campus/job-detail/MJ-xxx`
    after JS hydration; pagination is via numbered buttons inside the SPA.
    Strategy: load page, wait for hydration, scroll/click-next until job count
    plateaus, then read all job-detail anchors from DOM."""
    from playwright.sync_api import TimeoutError as PWTimeoutError

    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    url = target.get('url') or 'https://job.ctrip.com/#/campus/jobList'
    base = 'https://job.ctrip.com'

    try:
        goto_and_wait(page, url, timeout=45000, extra_sleep=4)
    except Exception as e:
        logger.warning(f'携程页面加载失败: {e}')
        return jobs

    try:
        page.wait_for_selector('a[href*="job-detail"]', timeout=20000)
    except PWTimeoutError:
        logger.warning('携程: 首屏未渲染 job-detail 链接')
        return jobs

    # Try clicking next-page buttons / scroll, collecting after each
    max_pages = int(target.get('max_pages') or MAX_PAGES)
    prev = 0
    stagnant = 0

    def _harvest():
        try:
            anchors = page.locator('a[href*="job-detail"]').all()
        except Exception:
            return 0
        added = 0
        for a in anchors:
            try:
                href = a.get_attribute('href') or ''
                if 'job-detail' not in href:
                    continue
                jid_m = re.search(r'job-detail/([A-Za-z0-9]+)', href)
                if not jid_m:
                    continue
                jid = jid_m.group(1)
                if jid in seen:
                    continue
                full_url = href if href.startswith('http') else urljoin(base, href.lstrip('#'))
                # Build a stable URL form
                full_url = f'https://job.ctrip.com/#/campus/job-detail/{jid}'
                text = (a.inner_text(timeout=400) or '').strip()
                lines = [norm_text(x) for x in text.split('\n') if x.strip()]
                # First line typically is the title; "查看职位" buttons are separate anchors
                title = ''
                meta = ''
                for line in lines:
                    if line == '查看职位':
                        continue
                    if not title:
                        title = line
                    else:
                        meta = (meta + ' ' + line).strip() if meta else line
                if not title or title == '查看职位':
                    continue
                location = ''
                m_loc = re.search(r'(北京|上海|深圳|广州|杭州|成都|南京|苏州|西安|武汉|香港|新加坡|东京)', meta)
                if m_loc:
                    location = m_loc.group(1)
                seen.add(jid)
                jobs.append(JobInfo(
                    id='', company='携程', title=title,
                    location=location or '未知', department='',
                    job_type=target.get('type', 'campus'),
                    url=full_url, description=meta,
                ))
                added += 1
            except Exception as exc:
                logger.debug(f'携程 anchor 跳过: {exc}')
        return added

    _harvest()
    logger.info(f'携程 第 1 页: {len(jobs)} 条')

    for pg in range(2, max_pages + 1):
        # Try clicking the SPA pagination "next" button
        clicked = False
        for sel in ['.ant-pagination-next:not(.ant-pagination-disabled)',
                    'button:has-text("下一页")',
                    '[class*="next"]:not([class*="disabled"])']:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click(timeout=3000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            try:
                page.mouse.wheel(0, 4000)
            except Exception:
                pass
        try:
            page.wait_for_timeout(1500)
        except Exception:
            break

        before = len(jobs)
        _harvest()
        added = len(jobs) - before
        logger.info(f'携程 第 {pg} 页: +{added} (total={len(jobs)})')
        if added == 0:
            stagnant += 1
            if stagnant >= 2:
                break
        else:
            stagnant = 0
        prev = len(jobs)

    logger.info(f'携程: 抓取 {len(jobs)} 条')
    return jobs


def crawl_xiaohongshu(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '小红书', 'https://job.xiaohongshu.com',
        selectors=[
            'a[href*="/campus/position/"]', 'a[href*="/social/position/"]',
            '[class*="position-item"]', '[class*="job-item"]',
        ],
        scroll=True, timeout=30000, extra_sleep=3,
        response_keywords=['job', 'position', 'api']
    )


def _crawl_campus_talent_alibaba(page, target) -> List[JobInfo]:
    """campus-talent.alibaba.com：用 Playwright 获取 XSRF-TOKEN，然后直调 /position/search API。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    page_size = 20
    max_page_limit = int(target.get('max_pages') or MAX_PAGES)

    # Load the page to get XSRF-TOKEN cookie
    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=3)
    except Exception as e:
        logger.warning(f'阿里巴巴(campus-talent) 页面加载失败: {e}')
        return jobs

    # Extract CSRF token from cookies
    csrf_token = None
    try:
        context = page.context
        cookies = context.cookies()
        for c in cookies:
            if c.get('name') == 'XSRF-TOKEN':
                csrf_token = c.get('value')
                break
    except Exception as e:
        logger.warning(f'阿里巴巴(campus-talent) 获取 CSRF token 失败: {e}')

    if not csrf_token:
        logger.warning('阿里巴巴(campus-talent): 无法获取 CSRF token，跳过 REST API 路径')
        return jobs

    # Extract batchId from URL
    import re as _re
    batch_id_match = _re.search(r'batchId=(\d+)', target['url'])
    batch_id = int(batch_id_match.group(1)) if batch_id_match else 100000540002

    # Get cookies string for requests
    cookies = page.context.cookies()
    cookie_str = '; '.join(f'{c["name"]}={c["value"]}' for c in cookies if c.get("name") and c.get("value"))

    headers = {
        'User-Agent': UA,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Referer': target['url'],
        'Cookie': cookie_str,
        'X-XSRF-TOKEN': csrf_token,
    }

    total_count = 0
    page_index = 1
    while page_index <= max_page_limit:
        payload = {
            'batchId': batch_id,
            'pageIndex': page_index,
            'pageSize': page_size,
            'channel': 'campus_group_official_site',
            'language': 'zh',
        }
        try:
            resp = requests.post(
                f'https://campus-talent.alibaba.com/position/search?_csrf={csrf_token}',
                json=payload,
                headers=headers,
                proxies=REQUEST_PROXIES,
                timeout=30,
            )
            data = resp.json() or {}
        except Exception as e:
            logger.warning(f'阿里巴巴(campus-talent) API 第 {page_index} 页失败: {e}')
            break

        if not data.get('success'):
            logger.warning(f'阿里巴巴(campus-talent) API 返回失败: {data.get("errorMsg")}')
            break

        content = data.get('content') or {}
        if page_index == 1:
            total_count = int(content.get('totalCount') or 0)
            if total_count:
                pages_total = (total_count + page_size - 1) // page_size
                max_page_limit = min(max(max_page_limit, pages_total), 200)
                logger.info(f'阿里巴巴(campus-talent): total={total_count}, pages={max_page_limit}')

        items = content.get('datas') or []
        if not items:
            break

        page_added = 0
        for item in items:
            pid = str(item.get('id') or '').strip()
            title = norm_text(item.get('name') or item.get('title') or '')
            if not title or not pid:
                continue
            if pid in seen:
                continue
            seen.add(pid)
            pos_url = item.get('positionUrl') or f'https://campus-talent.alibaba.com/campus/position/detail?id={pid}'
            locs = item.get('workLocations') or []
            location = norm_text('/'.join(str(l) for l in locs if l)) or '未知'
            cats = item.get('categories') or []
            department = norm_text('/'.join(str(c) for c in cats if c)) or ''
            publish_time = norm_text(str(item.get('publishTime') or ''))
            grad_time = item.get('graduationTime') or {}
            deadline = ''
            if isinstance(grad_time, dict) and (grad_time.get('from') or grad_time.get('to')):
                deadline = f"{norm_text(str(grad_time.get('from') or ''))}-{norm_text(str(grad_time.get('to') or ''))}".strip('-')
            job = JobInfo(
                id='', company='阿里巴巴', title=title, location=location,
                department=department, job_type=target.get('type', 'campus'),
                url=pos_url, publish_date=publish_time, deadline=deadline,
            )
            jobs.append(job)
            page_added += 1

        logger.info(f'阿里巴巴(campus-talent) 第 {page_index} 页: {page_added} 条 / total={total_count}')
        if page_added == 0:
            break
        page_index += 1

    return jobs


def crawl_alibaba(page, target) -> List[JobInfo]:
    """阿里巴巴：campus-talent.alibaba.com 走 CSRF+REST API；
    talent.alibaba.com 和 talent-holding.alibaba.com 走 Playwright 分页。
    """
    url = target['url']
    if 'campus-talent.alibaba.com' in url:
        return _crawl_campus_talent_alibaba(page, target)
    base = 'https://talent.alibaba.com' if 'talent.alibaba.com' in url else 'https://talent-holding.alibaba.com'
    return crawl_with_pagination(
        page, target, '阿里巴巴', base,
        selectors=['[class*="position-item"]', '[class*="job-card"]', '[class*="list-item"]', 'a[href*="position"]'],
        timeout=30000, extra_sleep=3,
        response_keywords=['position', 'job', 'api']
    )


def crawl_baidu(page, target) -> List[JobInfo]:
    """百度: Playwright Chromium gets a 200 + blank body (some bot fingerprint
    issue), but plain requests with a Windows-Chrome UA returns a fully SSR'd
    HTML page. Bypass Playwright entirely and parse SSR HTML for `post-item__`
    cards. Pagination via `?current=N` (1-based)."""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    base_url = (target.get('url') or 'https://talent.baidu.com/jobs/list?search=').strip()
    max_page_limit = int(target.get('max_pages') or MAX_PAGES)

    headers = {'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9'}
    proxies = REQUEST_PROXIES or None

    title_re = re.compile(r'<div class="post-title-content__[A-Za-z0-9_-]+">\s*<span>([^<]+)</span>')
    meta_re = re.compile(r'<span class="post-subtitle-item__[A-Za-z0-9_-]+"[^>]*>([^<]*)</span>')
    desc_re = re.compile(r'<div class="post-description__[A-Za-z0-9_-]+">(.*?)</div>', re.DOTALL)
    card_re = re.compile(r'<div class="post-item__[A-Za-z0-9_-]+">(.*?)(?=<div class="post-item__|$)', re.DOTALL)

    for page_no in range(1, max_page_limit + 1):
        url = base_url
        sep = '&' if '?' in url else '?'
        if 'current=' in url:
            url = re.sub(r'([?&]current=)\d+', rf'\g<1>{page_no}', url)
        else:
            url = f'{url}{sep}current={page_no}'

        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        except Exception as e:
            logger.warning(f'百度 第 {page_no} 页请求失败: {e}')
            break
        if resp.status_code != 200 or not resp.text:
            logger.info(f'百度 第 {page_no} 页 HTTP {resp.status_code}, 终止')
            break

        cards = card_re.findall(resp.text)
        if not cards:
            logger.info(f'百度 第 {page_no} 页未找到 post-item 卡片，终止')
            break

        before = len(jobs)
        for card_html in cards:
            tm = title_re.search(card_html)
            if not tm:
                continue
            title = norm_text(tm.group(1))
            metas = [norm_text(x) for x in meta_re.findall(card_html)]
            location = metas[0] if metas else '未知'
            dept = metas[2] if len(metas) > 2 else (metas[1] if len(metas) > 1 else '')
            desc_match = desc_re.search(card_html)
            desc = norm_text(re.sub(r'<[^>]+>', ' ', desc_match.group(1))) if desc_match else ''
            job = JobInfo(
                id='', company='百度', title=title, location=location,
                department=dept, job_type=target.get('type', 'campus'),
                url=url, description=desc,
            )
            if job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(job)

        added = len(jobs) - before
        logger.info(f'百度 第 {page_no} 页: +{added} (total={len(jobs)})')
        if added == 0:
            break
    logger.info(f'百度: 抓取 {len(jobs)} 条')
    return jobs


def crawl_jd(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '京东', 'https://campus.jd.com',
        selectors=['[class*="job-item"]', '[class*="position-item"]', 'li[class*="item"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'api']
    )


def crawl_bilibili(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '哔哩哔哩', 'https://jobs.bilibili.com',
        selectors=['.bili-item-card', '[class*="bili-item-card"]', 'bili-position-card', '[class*="position-item"]', '[class*="job-item"]', 'a[href*="positions"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=3,
        response_keywords=['position', 'job', 'api']
    )


def crawl_huawei(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '华为', 'https://career.huawei.com',
        selectors=['[class*="position"]', '[class*="job"]', 'table tbody tr', 'a[href*="position"]'],
        timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'api']
    )


def crawl_didi(page, target) -> List[JobInfo]:
    """滴滴 (MokaHR-hosted SPA): wire response is encrypted (data+necromancer
    blob), so we let the browser decrypt and read the rendered DOM. Scroll
    to drive infinite-scroll pagination.

    History: this DOM-scrape was first added in commit 86bef1b (1 → 31 jobs),
    then accidentally overwritten in 9ebbaad (when fixing 携程) and reverted
    to a generic crawl_with_pagination shim that only catches "隐私协议" link
    (1 row). Restored 2026-05-08 as part of Phase 2.
    """
    from playwright.sync_api import TimeoutError as PWTimeoutError
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    url = target.get('url') or 'https://campus.didiglobal.com/campus_apply/didiglobal/96064#/jobs'
    base = 'https://campus.didiglobal.com'

    try:
        goto_and_wait(page, url, timeout=45000, extra_sleep=4)
    except Exception as e:
        logger.warning(f'滴滴页面加载失败: {e}')
        return jobs

    try:
        page.wait_for_selector('a[href*="#/job/"], [class*="JobItem"], [class*="ItemContent"]',
                               timeout=20000)
    except PWTimeoutError:
        logger.warning('滴滴: 首屏未渲染 job 卡片')

    total_hint = 0
    try:
        text = page.locator('body').inner_text(timeout=2000)
        m = re.search(r'共\s*(\d{1,4})\s*个', text or '')
        if m:
            total_hint = int(m.group(1))
            logger.info(f'滴滴: 页面 total={total_hint}')
    except Exception:
        pass

    max_scrolls = int(target.get('max_pages') or MAX_PAGES) * 2
    prev_count = 0
    stagnant = 0
    for _ in range(max_scrolls):
        try:
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(900)
            try:
                btn = page.locator('button:has-text("加载更多"), button:has-text("更多")').first
                if btn.is_visible(timeout=300):
                    btn.click(timeout=1000)
                    page.wait_for_timeout(900)
            except Exception:
                pass
        except Exception:
            break

        cur = len(page.locator('a[href*="#/job/"]').all())
        if cur <= prev_count:
            stagnant += 1
            if stagnant >= 3:
                break
        else:
            stagnant = 0
            prev_count = cur
        if total_hint and cur >= total_hint:
            break

    try:
        anchors = page.locator('a[href*="#/job/"]').all()
    except Exception:
        anchors = []

    for a in anchors:
        try:
            href = a.get_attribute('href') or ''
            if not href or '#/job/' not in href:
                continue
            jid = href.split('#/job/')[-1].rstrip('/').split('?')[0]
            full_url = f'https://campus.didiglobal.com/campus_apply/didiglobal/96064#/job/{jid}'
            if not jid or jid in seen:
                continue
            text = (a.inner_text(timeout=500) or '').strip()
            if not text:
                continue
            lines = [norm_text(x) for x in text.split('\n') if x.strip()]
            # 滴滴 2026-05 起在卡片首行加了"急"等 badge（1-2 字纯中文短 tag），
            # 跳过这些 tag 行直到拿到真正的岗位标题。
            BADGE_TAGS = {'急', '热', '新', '荐', '紧急', '热招', '推荐', '新发布'}
            while lines and lines[0] in BADGE_TAGS:
                lines.pop(0)
            title = lines[0] if lines else ''
            meta = ' · '.join(lines[1:]) if len(lines) > 1 else ''
            if not title:
                continue
            location = ''
            dept = ''
            jtype = target.get('type', 'campus')
            for token in re.split(r'[·•|\s]+', meta):
                if not token:
                    continue
                if any(k in token for k in ('实习', '全职', '校招', '社招')):
                    jtype = token
                elif re.search(r'(北京|上海|深圳|广州|杭州|成都|南京|苏州|西安|武汉)', token):
                    location = location or token
                else:
                    dept = dept or token
            seen.add(jid)
            jobs.append(JobInfo(
                id='', company='滴滴', title=title,
                location=location or '未知',
                department=dept, job_type=jtype,
                url=full_url, description=meta,
            ))
        except Exception as exc:
            logger.debug(f'滴滴 DOM 解析跳过: {exc}')

    logger.info(f'滴滴: 抓取 {len(jobs)} 条 (total_hint={total_hint})')
    return jobs


def crawl_pingan(page, target) -> List[JobInfo]:
    """平安集团：zztj-recruit-talent-webserver REST。

    Phase 7（2026-05-10）逆向 SPA chunk_freshStudent~chunk_internStudent~chunk_position：
        Step 1 (拿 wecruitId):
          POST /zztj-recruit-talent-webserver/rctt/candidate/officialWebsite/selectGroupOfficial
          body = {websiteType:'3', published:'Y'}
          返回 {data: '<wecruitId 32位 hex>'}
        Step 2 (查岗位):
          POST /zztj-recruit-talent-webserver/rctt/candidate/position/campus/positionSearch/queryPositionPage
          body = {wecruitId, PageNum, pageSize, positionType:'1', wecruitPlatform:true,
                  businessUnitId:'', keyWord:'', positionCategoryId:'',
                  workCity:'', interviewCity:''}
          返回 {data: {list, pageNo, pageSize, totalCount, totalPage}}
    positionType=1 全职校招（实测 totalCount=738），positionType=2 实习（数十条）。
    businessUnitName 含 平安银行/平安证券/平安寿险/平安产险/平安科技/平安基金/平安租赁/陆控/平安普惠。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    base = 'https://campus.pingan.com/zztj-recruit-talent-webserver/rctt'
    headers = {
        'User-Agent': UA,
        'Origin': 'https://campus.pingan.com',
        'Referer': 'https://campus.pingan.com/',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    # Step 1: wecruitId
    try:
        r = requests.post(
            f'{base}/candidate/officialWebsite/selectGroupOfficial',
            json={'websiteType': '3', 'published': 'Y'},
            headers=headers, proxies=REQUEST_PROXIES, timeout=15, verify=False,
        )
        wj = r.json() or {}
    except Exception as exc:
        logger.warning(f'平安集团 selectGroupOfficial 失败: {exc}')
        return jobs

    if str(wj.get('responseCode') or '') != '10001':
        logger.info(f'平安集团 selectGroupOfficial 非 10001: {wj}')
        return jobs
    wecruit_id = wj.get('data') or ''
    if not wecruit_id:
        logger.info('平安集团 selectGroupOfficial 未返回 wecruitId')
        return jobs

    PAGE_SIZE = 50
    max_pages_cfg = int(target.get('max_pages') or 20) if isinstance(target, dict) else 20
    list_url = f'{base}/candidate/position/campus/positionSearch/queryPositionPage'

    def fetch_page(position_type: str, page_num: int) -> Optional[dict]:
        body = {
            'PageNum': page_num,
            'pageSize': PAGE_SIZE,
            'wecruitId': wecruit_id,
            'positionType': position_type,
            'wecruitPlatform': True,
            'businessUnitId': '',
            'keyWord': '',
            'positionCategoryId': '',
            'workCity': '',
            'interviewCity': '',
        }
        try:
            resp = requests.post(
                list_url, json=body, headers=headers,
                proxies=REQUEST_PROXIES, timeout=20, verify=False,
            )
            data = resp.json() or {}
        except Exception as exc:
            logger.warning(f'平安集团 queryPositionPage type={position_type} p{page_num} 失败: {exc}')
            return None
        if str(data.get('responseCode') or '') != '10001':
            logger.info(f'平安集团 queryPositionPage 非 10001: {data.get("responseCode")} {data.get("responseMsg")}')
            return None
        return data.get('data') or {}

    for ptype, label in [('1', 'campus'), ('2', 'intern')]:
        first = fetch_page(ptype, 1)
        if not first:
            continue
        total = int(first.get('totalCount') or 0)
        rows = list(first.get('list') or [])
        if total > PAGE_SIZE and len(rows) < total:
            pages = min(max_pages_cfg, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            for pn in range(2, pages + 1):
                time.sleep(0.3)
                d = fetch_page(ptype, pn)
                if not d:
                    break
                extra = list(d.get('list') or [])
                if not extra:
                    break
                rows.extend(extra)

        for item in rows:
            pid = norm_text(item.get('idPosition') or item.get('positionCode') or '')
            title = norm_text(item.get('positionName') or '')
            if not pid or not title:
                continue
            if pid in seen:
                continue
            seen.add(pid)
            biz = norm_text(item.get('businessUnitName') or '')
            dept = norm_text(item.get('deptShowName') or item.get('deptName') or biz)
            loc = norm_text(item.get('workCity') or item.get('interviewCity') or '') or '未知'
            publish_date = norm_text(item.get('publishDate') or item.get('createdDate') or '')
            duty = norm_text(item.get('duty') or '')
            qualif = norm_text(item.get('qualification') or '')
            url = f'https://campus.pingan.com/position/positionDetail?id={pid}&type={ptype}'
            company_label = biz if biz else '平安集团'
            jobs.append(JobInfo(
                id='', company=company_label, title=title, location=loc,
                department=dept, job_type=label, url=url,
                publish_date=publish_date, deadline='',
                description=duty, requirements=qualif,
            ))

    if jobs:
        logger.info(f'平安集团 zztj API: {len(jobs)} 条（含银行/证券/寿险/产险/科技等子公司）')
    else:
        logger.info('平安集团当前无开放校招岗位')
    return jobs


def crawl_pdd(page, target) -> List[JobInfo]:
    """拼多多：先用 Playwright 加载页面获取 session cookie，再直调
    /api/careers/api/recruit/position/list REST 接口分页。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    page_size = 20
    max_page_limit = int(target.get('max_pages') or MAX_PAGES)

    # Load the page to establish session
    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=3)
    except Exception as e:
        logger.warning(f'拼多多页面加载失败: {e}')
        return jobs

    # Extract cookies for requests
    try:
        cookies = page.context.cookies()
        cookie_str = '; '.join(f'{c["name"]}={c["value"]}' for c in cookies if c.get("name") and c.get("value"))
    except Exception:
        cookie_str = ''

    headers = {
        'User-Agent': UA,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Referer': target['url'],
        'Cookie': cookie_str,
    }

    total_count = 0
    pg = 1
    while pg <= max_page_limit:
        payload = {'page': pg, 'pageSize': page_size, 't': None}
        try:
            resp = requests.post(
                'https://careers.pddglobalhr.com/api/careers/api/recruit/position/list',
                json=payload,
                headers=headers,
                proxies=REQUEST_PROXIES,
                timeout=30,
            )
            data = resp.json() or {}
        except Exception as e:
            logger.warning(f'拼多多 API 第 {pg} 页失败: {e}')
            break

        if not data.get('success'):
            logger.warning(f'拼多多 API 返回失败: {data.get("errorMsg")}')
            break

        result = data.get('result') or {}
        if pg == 1:
            total_count = int(result.get('total') or 0)
            if total_count:
                pages_total = (total_count + page_size - 1) // page_size
                max_page_limit = min(max(max_page_limit, pages_total), 200)
                logger.info(f'拼多多: total={total_count}, pages={max_page_limit}')

        items = result.get('list') or []
        if not items:
            break

        page_added = 0
        for item in items:
            pid = str(item.get('id') or '').strip()
            title = norm_text(item.get('name') or item.get('jobName') or '')
            if not title or not pid:
                continue
            if pid in seen:
                continue
            seen.add(pid)
            location = norm_text(item.get('workLocationName') or item.get('workLocation') or '') or '未知'
            dept = norm_text(item.get('jobName') or item.get('job') or '')
            recruit_type = norm_text(item.get('recruitTypeName') or target.get('type', 'campus'))
            url = f'https://careers.pddglobalhr.com/campus/grad?jobId={pid}'
            job = JobInfo(
                id='', company='拼多多', title=title, location=location,
                department=dept, job_type=recruit_type,
                url=url,
                publish_date=norm_text(str(item.get('releaseTime') or '')),
                description=norm_text(item.get('jobDuty') or ''),
            )
            jobs.append(job)
            page_added += 1

        logger.info(f'拼多多 API 第 {pg} 页: {page_added} 条 / total={total_count}')
        if page_added == 0:
            break
        pg += 1

    return jobs


def crawl_cmb(page, target) -> List[JobInfo]:
    """招商银行（career.cmbchina.com）：直调 /api/campusRecruitmentWebsite REST。

    SPA webpack chunk 188 中暴露:
        POST /api/campusRecruitmentWebsite/job/getList
        body = {orgIdList:[], keywords:"", locationIdList:[],
                pageIndex:N, pageSize:50, recruitmentTypeId:GUID}
    返回 {body:{total, data:[{publishGID, jobDisplay, branchCodeName,
                              locationName, expiredOn}, ...]}}.

    Phase 7（2026-05-10）探查：3 个 recruitmentTypeId 中 96574F8D=7（春招宁波）、
    DF94FD6D=130（春招全行 + 招银理财）、48E013CF=0。pageSize 服务端无硬性 cap，
    单页 50 拿全 130。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    RECRUITMENT_TYPE_IDS = [
        '48E013CF-A9DE-4FA4-9CEE-4967B162CAEF',
        '96574F8D-C7ED-4772-AE7C-BAC896D190C1',
        'DF94FD6D-26D3-4A19-9E69-577C4BA1DE82',
    ]
    PAGE_SIZE = 50
    api_url = 'https://career.cmbchina.com/api/campusRecruitmentWebsite/job/getList'
    headers = {
        'User-Agent': UA,
        'Origin': 'https://career.cmbchina.com',
        'Referer': 'https://career.cmbchina.com/',
        'Content-Type': 'application/json;charset=UTF-8',
        'X-B3-BusinessId': 'LZ4101CMBRecruitmentPCFront',
        'Accept': 'application/json',
    }

    def fetch_page(rtype: str, page_idx: int) -> Optional[dict]:
        body = {
            'orgIdList': [],
            'keywords': '',
            'locationIdList': [],
            'pageIndex': page_idx,
            'pageSize': PAGE_SIZE,
            'recruitmentTypeId': rtype,
        }
        try:
            resp = requests.post(
                api_url, json=body, headers=headers,
                proxies=REQUEST_PROXIES, timeout=20, verify=False,
            )
            data = resp.json() or {}
        except Exception as exc:
            logger.warning(f'招商银行 getList rtype={rtype} p{page_idx} 失败: {exc}')
            return None
        if str(data.get('returnCode') or '') != 'SUC0000':
            logger.info(f'招商银行 rtype={rtype} 返回非 SUC0000: {data.get("returnCode")} {data.get("errorMsg")}')
            return None
        return (data.get('body') or {})

    max_pages_cfg = int(target.get('max_pages') or 5) if isinstance(target, dict) else 5

    for rtype in RECRUITMENT_TYPE_IDS:
        first = fetch_page(rtype, 1)
        if first is None:
            continue
        total = int(first.get('total') or 0)
        if total <= 0:
            continue
        rows = list(first.get('data') or [])
        if total > PAGE_SIZE:
            pages = min(max_pages_cfg, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            for pn in range(2, pages + 1):
                more = fetch_page(rtype, pn)
                if not more:
                    break
                page_rows = list(more.get('data') or [])
                if not page_rows:
                    break
                rows.extend(page_rows)

        for item in rows:
            pid = norm_text(item.get('publishGID') or '')
            title = norm_text(item.get('jobDisplay') or '')
            if not pid or not title:
                continue
            if pid in seen:
                continue
            seen.add(pid)
            org = norm_text(item.get('branchCodeName') or '')
            loc = norm_text(item.get('locationName') or '') or '未知'
            deadline = norm_text(item.get('expiredOn') or '')
            url = (
                f'https://career.cmbchina.com/positionDetail/school?publishId={pid}'
                f'&recruitmentTypeID={rtype}'
            )
            company_label = '招商银行'
            if '理财' in (title + org):
                company_label = '招银理财'
            jobs.append(JobInfo(
                id='', company=company_label, title=title, location=loc,
                department=org, job_type='campus', url=url,
                publish_date='', deadline=deadline,
                description='', requirements='',
            ))

    if jobs:
        logger.info(f'招商银行 API: {len(jobs)} 条（含招银理财）')
    else:
        logger.info('招商银行当前无开放校招岗位（3 个 recruitmentTypeId 总计 0）')
    return jobs


def crawl_spdb(page, target) -> List[JobInfo]:
    """浦发银行：走官网校园招聘 JSON 接口，避免首页导航项误采集。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    api = 'https://job.spdb.com.cn/socialJobJsonList'
    page_no = 1
    page_limit = 50

    while page_no <= page_limit:
        try:
            payload = {
                'jobKey': '',
                'jobTime': '',
                'pageNo': page_no,
                'deptDescr': '',
                'address': '',
                'recuitType': '12',  # 校园招聘
                'positionName': '',
                'descName': '',
                'descType': '',
                'deptLevel': '',
                'flagFlush': 'dept',
            }
            resp = requests.post(
                api,
                data=payload,
                headers={'User-Agent': UA, 'Referer': 'https://job.spdb.com.cn/campusJob'},
                timeout=30,
            )
            data = resp.json() if resp.ok else {}
        except Exception as e:
            logger.warning(f'浦发银行 API 第 {page_no} 页失败: {e}')
            break

        rows = data.get('rows') or []
        if not rows:
            break

        total = int(data.get('totalRowCount') or 0)
        rows_display = int(data.get('rowsDisplayed') or 10)
        if total > 0 and rows_display > 0:
            page_limit = min(max(page_limit, (total + rows_display - 1) // rows_display), 80)

        page_added = 0
        for item in rows:
            if str(item.get('recuitType') or '') != '12':
                continue
            title = norm_text(item.get('positionName'))
            if not title:
                continue

            oid = norm_text(item.get('openningJobId'))
            url = f'https://job.spdb.com.cn/campusJob?openningJobId={oid}' if oid else 'https://job.spdb.com.cn/campusJob'
            job = JobInfo(
                id='',
                company='浦发银行',
                title=title,
                location=norm_text(item.get('address') or item.get('prmLocArea') or '未知') or '未知',
                department=norm_text(item.get('deptDescr') or ''),
                job_type='campus',
                url=url,
                publish_date=norm_text(item.get('desiredStartDt') or ''),
                deadline=norm_text(item.get('closeDt') or ''),
                description=norm_text(item.get('posnDescr') or ''),
                requirements=norm_text(item.get('hpsDegreeRql') or ''),
            )
            if job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(job)
            page_added += 1

        logger.info(f'浦发银行 API 第 {page_no} 页: {page_added} 条 / total={total}')
        if page_added == 0:
            break
        page_no += 1

    return jobs


def crawl_nbcb(page, target) -> List[JobInfo]:
    """宁波银行：通过页面上下文 fetch 校招接口（规避 requests 的 TLS 兼容问题）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=2)
        data = page.evaluate(
            """
            async () => {
              const resp = await fetch('/api/position/schoolByPage/list', {
                method: 'POST',
                credentials: 'include',
                headers: {'content-type': 'application/json'},
                body: JSON.stringify({pageNum: 1, pageSize: 500})
              });
              return await resp.json();
            }
            """
        )
    except Exception as e:
        logger.warning(f'宁波银行校招接口请求失败: {e}')
        return jobs

    rows = (((data or {}).get('data') or {}).get('list') or [])
    for item in rows:
        title = norm_text(item.get('posName') or item.get('positionName') or '')
        if not title:
            continue
        rid = norm_text(item.get('id') or item.get('posHid') or '')
        url = f"https://zhaopin.nbcb.com.cn/#/campus-recruitment?jobId={rid}" if rid else target['url']
        location = norm_text(item.get('compName') or item.get('workCity') or item.get('workLocation') or '未知') or '未知'
        job = JobInfo(
            id='',
            company='宁波银行',
            title=title,
            location=location,
            department=norm_text(item.get('deptName') or ''),
            job_type='campus',
            url=url,
            publish_date=norm_text(item.get('startTime') or ''),
            deadline=norm_text(item.get('endTime') or ''),
            description=norm_text(item.get('posDuty') or ''),
            requirements=norm_text(item.get('posRequiRement') or ''),
        )
        if job.id in seen:
            continue
        seen.add(job.id)
        jobs.append(job)

    logger.info(f'宁波银行 API: {len(jobs)} 条')
    return jobs


def crawl_jsbc(page, target) -> List[JobInfo]:
    jobs = crawl_with_pagination(
        page, target, '江苏银行', 'https://hr.jsbchina.cn',
        selectors=['[class*="position"]', '[class*="job"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'campus', 'recruit', 'api']
    )
    if not jobs:
        logger.info('江苏银行当前可能未开放校招职位或页面受保护，暂未抓到岗位')
    return jobs


def crawl_njcb(page, target) -> List[JobInfo]:
    """南京银行：仅抓校招结果页，过滤宣传类非岗位内容。"""
    seed_urls = [
        'https://job.njcb.com.cn/#/campus/result?search=%E6%9C%AC%E7%A7%91&outflag=1',
        'https://job.njcb.com.cn/#/campus/result?search=%E7%A0%94%E7%A9%B6%E7%94%9F&outflag=1',
    ]

    ban_words = ['BANNER', '视频', '简介', '文明单位', '课堂', '团委', '为什么选择南京银行']
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    for url in seed_urls:
        local_target = dict(target)
        local_target['url'] = url
        batch = crawl_with_pagination(
            page, local_target, '南京银行', 'https://job.njcb.com.cn',
            selectors=['table tbody tr', '[class*="position"]', '[class*="job"]', '[class*="list-item"]', 'li[class*="item"]'],
            scroll=True, timeout=30000, extra_sleep=2,
            response_keywords=['school', 'position', 'job', 'campus', 'recruit', 'api']
        )

        for job in batch:
            title = norm_text(job.title)
            if not title:
                continue
            if any(w.lower() in title.lower() for w in ban_words):
                continue
            if job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(job)

    if not jobs:
        logger.info('南京银行当前未稳定抓到校招岗位（网络/反爬或未开招）')
    return jobs


def crawl_suzhou_bank(page, target) -> List[JobInfo]:
    """苏州银行（北森）：校园招聘 API。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    base = 'https://suzhoubank.zhiye.com'
    portal_id = 'bc5aa0fe-f971-4b0d-a48e-50136bfdab11'
    max_pages = int(target.get('max_pages') or MAX_PAGES)

    for page_index in range(max_pages):
        try:
            resp = requests.post(
                f'{base}/api/Jobad/GetJobAdPageList',
                json={
                    'PageIndex': page_index,
                    'PageSize': 20,
                    'Category': ['2'],
                    'KeyWords': '',
                    'SpecialType': 0,
                    'PortalId': portal_id,
                    'DisplayFields': ['Category', 'Kind', 'LocId', 'Org', 'PostDate'],
                },
                headers={'User-Agent': UA, 'Referer': f'{base}/campus', 'Accept': 'application/json, text/plain, */*'},
                timeout=30,
            )
            data = (resp.json() or {}).get('Data') or []
        except Exception as e:
            logger.warning(f'苏州银行 API 第 {page_index + 1} 页失败: {e}')
            break

        if not data:
            break

        page_added = 0
        for item in data:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            jid = norm_text(item.get('Id') or item.get('JobAdId'))
            loc_list = item.get('LocNames') or []
            loc = ','.join(norm_text(x) for x in loc_list if norm_text(x)) if isinstance(loc_list, list) else norm_text(loc_list)
            job = JobInfo(
                id='', company='苏州银行', title=title,
                location=loc or '未知',
                department=norm_text(item.get('Org') or ''),
                job_type='campus',
                url=f'{base}/job/{jid}' if jid else target['url'],
                publish_date=norm_text(item.get('PostDate') or ''),
                deadline=norm_text(item.get('EndTime') or ''),
                description=norm_text(item.get('Duty') or ''),
                requirements=norm_text(item.get('Require') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1

        logger.info(f'苏州银行 API 第 {page_index + 1} 页: {page_added} 条')

    return jobs


def crawl_bosc(page, target) -> List[JobInfo]:
    """上海银行（北森）：校园招聘 API。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    base = 'https://bosc.zhiye.com'
    portal_id = '04dd30cc-229d-43ed-a3fd-7b94c9f2543f'
    max_pages = int(target.get('max_pages') or MAX_PAGES)

    for page_index in range(max_pages):
        try:
            resp = requests.post(
                f'{base}/api/Jobad/GetJobAdPageList',
                json={
                    'PageIndex': page_index,
                    'PageSize': 20,
                    'Category': ['2'],
                    'KeyWords': '',
                    'SpecialType': 0,
                    'PortalId': portal_id,
                    'DisplayFields': ['Category', 'Kind', 'LocId', 'Org', 'PostDate'],
                },
                headers={'User-Agent': UA, 'Referer': f'{base}/campus', 'Accept': 'application/json, text/plain, */*'},
                timeout=30,
            )
            data = (resp.json() or {}).get('Data') or []
        except Exception as e:
            logger.warning(f'上海银行 API 第 {page_index + 1} 页失败: {e}')
            break

        if not data:
            break

        page_added = 0
        for item in data:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            jid = norm_text(item.get('Id') or item.get('JobAdId'))
            loc_list = item.get('LocNames') or []
            loc = ','.join(norm_text(x) for x in loc_list if norm_text(x)) if isinstance(loc_list, list) else norm_text(loc_list)
            job = JobInfo(
                id='', company='上海银行', title=title,
                location=loc or '未知',
                department=norm_text(item.get('Org') or ''),
                job_type='campus',
                url=f'{base}/job/{jid}' if jid else target['url'],
                publish_date=norm_text(item.get('PostDate') or ''),
                deadline=norm_text(item.get('EndTime') or ''),
                description=norm_text(item.get('Duty') or ''),
                requirements=norm_text(item.get('Require') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1

        logger.info(f'上海银行 API 第 {page_index + 1} 页: {page_added} 条')

    return jobs


def crawl_hzbank(page, target) -> List[JobInfo]:
    """杭州银行：校园招聘接口（positionType=01）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    max_pages = int(target.get('max_pages') or MAX_PAGES)

    for page_index in range(max_pages):
        try:
            resp = requests.get(
                'https://myjob.hzbank.com.cn/hzzp-apply/employInfo/queryEmployInfosList',
                params={
                    'page': page_index,
                    'positionName': '',
                    'positionType': '01',
                    'size': 20,
                    'organNo': '',
                    'workSpace': '',
                    'day': '',
                },
                headers={'User-Agent': UA, 'Referer': 'https://myjob.hzbank.com.cn/hzzp-apply-web/static/index.html#/employ/school'},
                timeout=30,
            )
            result = (resp.json() or {}).get('result') or {}
            rows = result.get('content') or []
        except Exception as e:
            logger.warning(f'杭州银行 API 第 {page_index + 1} 页失败: {e}')
            break

        if not rows:
            break

        page_added = 0
        for item in rows:
            title = norm_text(item.get('positionName'))
            if not title:
                continue
            jid = norm_text(item.get('id'))
            job = JobInfo(
                id='', company='杭州银行', title=title,
                location=norm_text(item.get('workSpace') or '未知') or '未知',
                department=norm_text(item.get('organizationName') or ''),
                job_type='campus',
                url=f'https://myjob.hzbank.com.cn/hzzp-apply-web/static/index.html#/employ/school?id={jid}' if jid else target['url'],
                publish_date=norm_text(item.get('startTime') or ''),
                deadline=norm_text(item.get('endTime') or ''),
                description=norm_text(item.get('jobDesc') or ''),
                requirements=norm_text(item.get('jobRequire') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1

        logger.info(f'杭州银行 API 第 {page_index + 1} 页: {page_added} 条')

    return jobs


def crawl_feishu_nio(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, 'NIO蔚来', 'https://nio.jobs.feishu.cn',
        selectors=['[class*="position-item"]', '[class*="job-item"]', '[class*="list-item"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=3,
        response_keywords=['position', 'job', 'posts', 'api']
    )


def crawl_163(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    nav = requests.get(
        'https://campus.163.com/api/campuspc/project/navigation/list',
        params={'timeStamp': int(time.time() * 1000)},
        headers={'User-Agent': UA, 'Referer': 'https://campus.163.com/app/index', 'Accept': 'application/json, text/plain, */*'},
        proxies=REQUEST_PROXIES, timeout=30,
    ).json()
    project_id = None
    for item in ((nav or {}).get('data') or []):
        if item.get('title') == '应届生':
            for child in (item.get('children') or []):
                link = child.get('link') or ''
                m = re.search(r'id=(\d+)', link)
                if m and 'campus.163.com' in link:
                    project_id = int(m.group(1))
                    break
        if project_id:
            break
    if not project_id:
        return jobs
    current_page = 1
    total_pages = 1
    while current_page <= total_pages and current_page <= MAX_PAGES:
        resp = requests.get(
            'https://campus.163.com/api/campuspc/position/getJobList',
            params={'pageSize': 20, 'currentPage': current_page, 'projectId': project_id, 'timeStamp': int(time.time() * 1000)},
            headers={'User-Agent': UA, 'Referer': f'https://campus.163.com/app/job/position?id={project_id}', 'Accept': 'application/json, text/plain, */*'},
            proxies=REQUEST_PROXIES, timeout=30,
        )
        data = resp.json().get('data') or {}
        total_pages = int(data.get('pages') or 1)
        page_added = 0
        for item in (data.get('list') or []):
            job = JobInfo(
                id='', company='网易', title=norm_text(item.get('positionName')), location=norm_text(item.get('workPlaceName')) or '未知',
                department='', job_type=target.get('type', 'campus'),
                url=f'https://campus.163.com/app/job/position/detail?id={item.get("id")}&projectId={project_id}',
                description=norm_text(item.get('positionDescription')), requirements=norm_text(item.get('positionRequirement')),
                publish_date=norm_text(item.get('updateTime') or ''),
            )
            if job.title and job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'网易 API 第 {current_page} 页: {page_added} 条')
        if page_added == 0:
            break
        current_page += 1
    return jobs


def crawl_360_campus(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    current_page = 0
    while current_page < MAX_PAGES:
        payload = {
            'PageIndex': current_page,
            'PageSize': 20,
            'KeyWords': '',
            'SpecialType': 0,
            'PortalId': '',
            'DisplayFields': ['Category', 'Kind', 'LocId', 'ClassificationOne', 'WorkWeChatQrCode'],
        }
        resp = requests.post(
            'https://360campus.zhiye.com/api/Jobad/GetJobAdPageList',
            json=payload,
            headers={'User-Agent': UA, 'Referer': 'https://360campus.zhiye.com/jobs', 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json, text/plain, */*'},
            proxies=REQUEST_PROXIES, timeout=30,
        )
        data = resp.json()
        rows = data.get('Data') or []
        page_added = 0
        for item in rows:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            job = JobInfo(
                id='', company='360', title=title, location=norm_text(','.join(item.get('LocNames') or [])) or '未知',
                department=norm_text(item.get('ClassificationOne') or item.get('Category') or ''),
                job_type=target.get('type', 'campus'),
                url=f'https://360campus.zhiye.com/jobs/detail/{item.get("Id")}',
                description=norm_text(item.get('Duty') or ''), requirements=norm_text(item.get('Require') or ''),
                publish_date=norm_text(item.get('PostDate') or ''), deadline=norm_text(item.get('EndTime') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'360 API 第 {current_page + 1} 页: {page_added} 条')
        if not rows or page_added == 0:
            break
        current_page += 1
    return jobs


def _crawl_antgroup_one_type(
    target, headers: Dict[str, str], ctoken: str,
    recruit_types: List[str], type_label: str,
    seen: Set[str],
) -> List[JobInfo]:
    """蚂蚁集团：按指定 recruitType 列表抓取一轮。"""
    jobs: List[JobInfo] = []
    page_size = 20
    current_page = 1
    total_pages = 1
    max_pages = MAX_PAGES * 5  # generous cap (500 items max)
    while current_page <= total_pages and current_page <= max_pages:
        try:
            resp = requests.post(
                'https://hrcareersweb.antgroup.com/api/campus/position/search',
                params={'ctoken': ctoken},
                headers=headers,
                proxies=REQUEST_PROXIES,
                timeout=30,
                json={
                    'channel': 'campus_group_official_site',
                    'language': 'zh',
                    'regions': '',
                    'subCategories': '',
                    'bgCode': '',
                    'pageIndex': current_page,
                    'pageSize': page_size,
                    'recruitType': recruit_types,
                    'batchIds': [],
                },
            )
            data = resp.json()
        except Exception as e:
            logger.warning(f'蚂蚁集团({type_label}) 第 {current_page} 页失败: {e}')
            break
        if not data.get('success', True) and data.get('errorCode'):
            logger.warning(f'蚂蚁集团({type_label}) API 错误: {data.get("errorMsg")}')
            break
        rows = data.get('content') or []
        total_count = int(data.get('totalCount') or 0)
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page_added = 0
        for item in rows:
            title = norm_text(item.get('name'))
            if not title:
                continue
            pid = item.get('id')
            url = f'https://talent.antgroup.com/campus-position?positionId={pid}' if pid else target['url']
            grad = item.get('graduationTime') or {}
            deadline = ''
            if grad.get('from') or grad.get('to'):
                deadline = f"{norm_text(str(grad.get('from') or ''))} ~ {norm_text(str(grad.get('to') or ''))}".strip(' ~')
            # Derive job_type from item's recruitType field
            item_recruit = item.get('recruitType') or {}
            item_jtype = norm_text(item_recruit.get('name') or '') if isinstance(item_recruit, dict) else norm_text(str(item_recruit))
            job = JobInfo(
                id='', company='蚂蚁集团', title=title,
                location=norm_text('/'.join(str(x) for x in (item.get('workLocations') or []) if x)) or '未知',
                department=norm_text('/'.join(str(x) for x in (item.get('categories') or []) if x)) or norm_text(item.get('category') or ''),
                job_type=item_jtype or target.get('type', 'campus'), url=url,
                publish_date=norm_text(str(item.get('publishTime') or '')),
                deadline=deadline,
                description=norm_text(item.get('requirement') or ''),
                requirements=norm_text(item.get('requirement') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'蚂蚁集团({type_label}) 第 {current_page} 页: {page_added} 条 / total={total_count}')
        if not rows:
            break
        current_page += 1
    return jobs


def crawl_antgroup(page, target) -> List[JobInfo]:
    """蚂蚁集团：分别抓取校招（campus_graduates）和实习（campus_interns）两种岗位类型，
    再合并去重。之前只用空 recruitType 会只返回部分结果（约 300 条），遗漏了 600+ 实习岗位。
    """
    seen: Set[str] = set()
    headers = {
        'User-Agent': UA,
        'Accept': 'application/json',
        'Referer': 'https://talent.antgroup.com/',
        'Content-Type': 'application/json;charset=UTF-8',
        'front-user-id': f'{hashlib.md5(str(time.time()).encode()).hexdigest()}30',
    }
    ctoken = f'bigfish_ctoken_{hashlib.md5(str(time.time()).encode()).hexdigest()[:10]}'

    jobs: List[JobInfo] = []
    for recruit_types, label in [
        (['campus_graduates'], 'graduates'),
        (['campus_interns'], 'interns'),
    ]:
        batch = _crawl_antgroup_one_type(target, headers, ctoken, recruit_types, label, seen)
        logger.info(f'蚂蚁集团({label}): {len(batch)} 条')
        jobs.extend(batch)

    return jobs


def crawl_kuaishou(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    headers = {
        'User-Agent': UA,
        'Referer': 'https://campus.kuaishou.cn/',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
    }
    current_page = 1
    total_pages = 1
    while current_page <= total_pages and current_page <= MAX_PAGES:
        resp = requests.post(
            'https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple',
            headers=headers,
            proxies=REQUEST_PROXIES,
            timeout=30,
            json={'pageSize': 50, 'pageNum': current_page},
        )
        data = resp.json().get('result') or {}
        rows = data.get('list') or []
        total_pages = int(data.get('pages') or 1)
        page_added = 0
        for item in rows:
            title = norm_text(item.get('name'))
            if not title:
                continue
            pid = item.get('id')
            job = JobInfo(
                id='', company='快手', title=title,
                location=norm_text('/'.join([x.get('name') for x in (item.get('workLocationDicts') or []) if x.get('name')])) or '未知',
                department=norm_text(item.get('positionCategoryCode') or item.get('departmentName') or ''),
                job_type='campus',
                url=f'https://campus.kuaishou.cn/#/campus/job-info/{pid}',
                publish_date=norm_text(item.get('releaseTime') or ''),
                description=norm_text(item.get('description') or ''),
                requirements=norm_text(item.get('positionDemand') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'快手 API 第 {current_page} 页: {page_added} 条 / total={data.get("total")}')
        if not rows:
            break
        current_page += 1
    return jobs


def crawl_leihuo(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '网易雷火', 'https://leihuo.163.com',
        selectors=['[class*="position"]', '[class*="job"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'campus', 'recruit', 'api']
    )


def crawl_boss_campus(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, 'BOSS直聘', 'https://www.zhipin.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_dewu(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '得物', 'https://campus.dewu.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_mihoyo(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '米哈游', 'https://jobs.mihoyo.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="position"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_zhihu_campus(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '知乎', 'https://app.mokahr.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_weibo_campus(page, target) -> List[JobInfo]:
    """微博校招：当前环境下官网直连不稳定，优先用新浪校园招聘 Moka 官方页兜底。"""
    fallback = dict(target)
    fallback['url'] = 'https://app.mokahr.com/campus-recruitment/sina/43536#/jobs?page=1&anchorName=jobsList&project%5B0%5D=100098744'
    return crawl_with_pagination(
        page, fallback, '微博', 'https://app.mokahr.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_beike_campus(page, target) -> List[JobInfo]:
    """贝壳校招：直连官方 API（避免 Playwright 网络波动）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    max_pages = int(target.get('max_pages') or MAX_PAGES)
    base = 'https://campus.ke.com'

    for idx in range(max_pages):
        payload = {
            'PageIndex': idx,
            'PageSize': 20,
            'KeyWords': '',
            'SpecialType': 0,
            'PortalId': '',
            'DisplayFields': ['Category', 'Kind', 'LocId', 'ClassificationOne'],
        }
        try:
            resp = requests.post(
                f'{base}/api/Jobad/GetJobAdPageList',
                json=payload,
                headers={'User-Agent': UA, 'Referer': 'https://campus.ke.com/campus/jobs', 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json, text/plain, */*'},
                timeout=30,
            )
            rows = (resp.json() or {}).get('Data') or []
        except Exception as e:
            logger.warning(f'贝壳 API 第 {idx + 1} 页失败: {e}')
            break

        page_added = 0
        for item in rows:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            jid = item.get('Id')
            loc = norm_text(','.join(item.get('LocNames') or [])) or '未知'
            job = JobInfo(
                id='', company='贝壳找房', title=title, location=loc,
                department=norm_text(item.get('ClassificationOne') or item.get('Category') or ''),
                job_type='campus',
                url=f'{base}/campus/job/{jid}' if jid else target['url'],
                description=norm_text(item.get('Duty') or ''), requirements=norm_text(item.get('Require') or ''),
                publish_date=norm_text(item.get('PostDate') or ''), deadline=norm_text(item.get('EndTime') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'贝壳 API 第 {idx + 1} 页: {page_added} 条')
        if not rows or page_added == 0:
            break

    return jobs


def crawl_tongcheng_campus(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '同程旅行', 'https://campus.ly.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_aiqiyi_campus(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '爱奇艺', 'https://join.iqiyi.com',
        selectors=['[class*="job"]', '[class*="position"]', '[class*="card"]', '[class*="list-item"]', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'campus', 'api']
    )


def crawl_shein(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    headers = {
        'User-Agent': UA,
        'Referer': 'https://careers.shein.com/Professionals',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
    }
    shein_max_pages = int(target.get('max_pages') or MAX_PAGES)
    max_retries = 2

    def post_json(url: str, payload: Dict[str, Any], label: str):
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    proxies=REQUEST_PROXIES,
                    timeout=30,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json() or {}
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    logger.warning(f'{label} 异常，第 {attempt + 1} 次重试: {e}')
                    time.sleep(1.5 * (attempt + 1))
                else:
                    logger.warning(f'{label} 异常，跳过: {e}')
        raise last_exc

    cat_data = post_json(
        'https://careers.shein.com/api/v1/open/grw/front/jobCategoryList',
        {'jobTypeId': 'SOCIAL', 'langCode': 'EN'},
        'SHEIN 分类接口'
    )
    categories = ((cat_data.get('info') or cat_data.get('data') or {}).get('jobCategoryList') or []) if isinstance(cat_data.get('info') or cat_data.get('data'), dict) else (cat_data.get('info') or cat_data.get('data') or [])
    for cat in categories:
        cat_id = norm_text(cat.get('jobCategoryId') or cat.get('id'))
        if not cat_id:
            continue
        current = 1
        total = 1
        while current <= total and current <= shein_max_pages:
            payload = {
                'current': current,
                'size': 10,
                'cityName': '',
                'jobCategoryIds': [cat_id],
                'countryIds': [],
                'cityIds': [],
                'jobTypeIds': ['SOCIAL'],
                'jobIds': [],
                'key': '',
                'langCode': 'EN',
            }
            try:
                raw = post_json(
                    'https://careers.shein.com/api/v1/open/grw/front/jobPage',
                    payload,
                    f'SHEIN API {cat_id} 第 {current} 页'
                )
            except Exception:
                break
            data = raw.get('info') or raw.get('data') or {}
            rows = data.get('records') or data.get('list') or []
            total_count = int(data.get('total') or 0)
            total = int(data.get('pages') or data.get('totalPage') or ((total_count + 9) // 10) or 1)
            page_added = 0
            for item in rows:
                title = norm_text(item.get('jobTitle') or item.get('jobName') or item.get('name'))
                if not title:
                    continue
                pid = item.get('jobId') or item.get('id')
                city = norm_text(item.get('cityName') or item.get('workCityName') or item.get('cityNames') or '')
                country = norm_text(item.get('countryName') or '')
                location = ' / '.join([x for x in [country, city] if x]) or '未知'
                category_name = norm_text(item.get('jobCategoryName') or cat.get('jobCategoryName') or cat.get('name') or '')
                url = f'https://careers.shein.com/All-Jobs?jobCategoryId={cat_id}&jobTypeId=SOCIAL'
                if pid:
                    url += f'&jobId={pid}'
                job = JobInfo(
                    id='', company='SHEIN', title=title, location=location,
                    department=category_name, job_type='social', url=url,
                    publish_date=norm_text(item.get('publishTime') or item.get('releaseTime') or item.get('releaseDate') or ''),
                    deadline=norm_text(item.get('deadline') or ''),
                    description=norm_text(item.get('jobDescription') or item.get('description') or ''),
                    requirements=norm_text(item.get('jobRequirement') or ''),
                )
                if job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
                    page_added += 1
            logger.info(f'SHEIN API {cat_id} 第 {current} 页: {page_added} 条 / total_pages={total}')
            if not rows:
                break
            current += 1
    return jobs


def crawl_cmbc(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    current_page = 1
    total_pages = 1
    while current_page <= total_pages and current_page <= MAX_PAGES:
        resp = requests.post(
            f'https://career.cmbc.com.cn/portal/rest/careerrecruitment/search.view?random={int(time.time() * 1000)}',
            headers={
                'User-Agent': UA,
                'Referer': 'https://career.cmbc.com.cn/',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/plain, */*',
            },
            proxies=REQUEST_PROXIES, timeout=30,
            data={'searchRecruitmentIds': 'social', 'view': 'careerRecruitmentList', 'pageNo': current_page, 'pageSize': 20},
        )
        data = (resp.json() or {}).get('data') or {}
        rows = data.get('items') or []
        total_pages = int(data.get('pageCount') or 1)
        page_added = 0
        for item in rows:
            title = norm_text(item.get('careerRecruitment_career_name'))
            if not title:
                continue
            pid = item.get('id')
            location = norm_text(item.get('careerRecruitment_regions_name')) or '未知'
            job = JobInfo(
                id='', company='民生银行', title=title, location=location,
                department=norm_text(item.get('careerRecruitment_career_jobFamily_name') or ''),
                job_type='social',
                url=f'https://career.cmbc.com.cn/#/app/detail?id={pid}' if pid else target['url'],
                publish_date=norm_text(item.get('careerRecruitment_career_publishDate') or ''),
                deadline=norm_text(item.get('careerRecruitment_career_expirationDate') or ''),
                description=norm_text(item.get('careerRecruitment_career_enterprise_name') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'民生银行 API 第 {current_page} 页: {page_added} 条 / total_pages={total_pages}')
        if not rows:
            break
        current_page += 1
    return jobs


def crawl_cib(page, target) -> List[JobInfo]:
    """兴业银行：通过页面真实请求抓取校园招聘（recruitType=CR）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=2)
        try:
            page.get_by_text('校园招聘', exact=False).first.click(timeout=3000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f'兴业银行页面打开失败: {e}')
        return jobs

    max_pages = int(target.get('max_pages') or MAX_PAGES)

    def harvest_from_captured() -> int:
        total_count = 0
        for rec in getattr(page, '_captured_json', []):
            if 'recruitposition/portalPage' not in (rec.get('url') or ''):
                continue
            payload = rec.get('data') or {}
            data = payload.get('data') or {}
            rows = data.get('list') or payload.get('items') or payload.get('records') or []
            if isinstance(rows, dict):
                rows = rows.get('list') or rows.get('items') or rows.get('records') or []
            if not rows:
                continue
            total_count = max(total_count, int(data.get('total') or payload.get('total') or len(rows)))
            for item in rows:
                title = norm_text(item.get('positionName') or item.get('recruitPositionName') or item.get('name') or '')
                if not title:
                    continue
                pid = item.get('positionId') or item.get('id') or ''
                url = f"https://job.cib.com.cn/portal/#/positionDetails?id={pid}" if pid else target['url']
                location = norm_text(item.get('positionAddr') or item.get('workLocation') or item.get('cityName') or '') or '未知'
                org = norm_text(item.get('businessUnitDesc') or item.get('firstBusinessUnitDesc') or item.get('departmentDesc') or '')
                publish_date = norm_text(item.get('publishTime') or item.get('createTime') or '')
                deadline = norm_text(item.get('expiryDate') or '')
                job = JobInfo(
                    id='', company='兴业银行', title=title, location=location,
                    department=org, job_type='campus', url=url,
                    publish_date=publish_date, deadline=deadline,
                    description=norm_text(item.get('jobDuty') or ''),
                    requirements=norm_text(item.get('positionRequirment') or item.get('educationRequirment') or ''),
                )
                if job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
        return total_count

    total_count = harvest_from_captured()
    page_size = 10
    target_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else max_pages
    target_pages = min(target_pages, max_pages)

    for idx in range(1, target_pages):
        try:
            next_btn = page.locator('.ant-pagination-next')
            if next_btn.count() == 0:
                break
            classes = next_btn.get_attribute('class') or ''
            if 'ant-pagination-disabled' in classes:
                break
            next_btn.click(timeout=3000)
            page.wait_for_timeout(2000)
            harvest_from_captured()
        except Exception:
            break

    logger.info(f'兴业银行校招岗位: {len(jobs)} 条')
    return jobs


def crawl_citic(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    current_page = 1
    page_size = 15
    total_count = 1
    max_pages = int(target.get('max_pages') or MAX_PAGES)
    headers = {
        'User-Agent': UA,
        'Referer': 'https://job.citicbank.com/CustStyle/zpmhys/clubRecruit.html',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
    }
    while current_page <= max_pages and (current_page == 1 or (current_page - 1) * page_size < total_count):
        resp = requests.post(
            'https://job.citicbank.com/recruitportal/portal/recruitQuery',
            headers=headers, proxies=REQUEST_PROXIES, timeout=30,
            json={'RELEASENAME': '', 'recruitmentType': '01', 'workAddr': [], 'deptCode': [], 'page': current_page, 'userId': None},
        )
        data = resp.json() or {}
        total_count = int(data.get('pageCount') or 0)
        rows = (((data.get('tableData') or {}).get('rows')) or [])
        page_added = 0
        for row in rows:
            item = row.get('itemMap') or {}
            title = norm_text(item.get('POSTNAME'))
            if not title:
                continue
            pid = item.get('ID')
            job = JobInfo(
                id='', company='中信银行', title=title,
                location=norm_text(item.get('WORKADDR')) or '未知',
                department=norm_text(item.get('RELEASENAME')),
                job_type='social',
                url=f'https://job.citicbank.com/recruitportal/job/detail?id={pid}' if pid else target['url'],
                publish_date=norm_text(item.get('FBZWDATE') or ''),
                description=norm_text(item.get('CONTENT') or ''),
                requirements=norm_text(item.get('RESUMEREQUIRE') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'中信银行 API 第 {current_page} 页: {page_added} 条 / total={total_count}')
        if not rows:
            break
        current_page += 1
    return jobs


def crawl_hxb(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    current_page = 1
    page_size = 15
    total_pages = 1
    suite = 'SU645b0d18bef57c0907e9fbc8'
    max_pages = int(target.get('max_pages') or MAX_PAGES)
    headers = {
        'User-Agent': UA,
        'Referer': f'https://wecruit.hotjob.cn/{suite}/pb/social.html',
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest',
    }
    while current_page <= total_pages and current_page <= max_pages:
        resp = requests.post(
            f'https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{suite}',
            headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
            proxies=REQUEST_PROXIES, timeout=30,
            params={'iSaJAx': 'isAjax', 'request_locale': 'zh_CN', 't': int(time.time() * 1000)},
            data={'isFrompb': 'true', 'recruitType': '2', 'pageSize': str(page_size), 'currentPage': str(current_page)},
        )
        data = (resp.json() or {}).get('data') or {}
        page_form = data.get('pageForm') or {}
        rows = page_form.get('pageData') or []
        total_pages = int(page_form.get('totalPage') or 1)
        page_added = 0
        for item in rows:
            title = norm_text(item.get('postName'))
            if not title:
                continue
            pid = item.get('postId')
            desc = ' '.join(x for x in [norm_text(item.get('subject')), norm_text(item.get('educationStr')), norm_text(item.get('workYears'))] if x)
            job = JobInfo(
                id='', company='华夏银行', title=title,
                location=norm_text(item.get('workPlaceStr')) or '未知',
                department=norm_text(item.get('postTypeName') or item.get('company') or ''),
                job_type='social',
                url=f'https://wecruit.hotjob.cn/{suite}/pb/social.html#/post?postId={pid}' if pid else target['url'],
                publish_date=norm_text(item.get('publishDate') or item.get('publishFirstDate') or ''),
                deadline=norm_text(item.get('endDate') or ''),
                description=desc,
                requirements=norm_text(item.get('subject') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'华夏银行 API 第 {current_page} 页: {page_added} 条 / total_pages={total_pages}')
        if not rows:
            break
        current_page += 1
    return jobs


def crawl_czbank(page, target) -> List[JobInfo]:
    """浙商银行：先抓校招（zpType=1），空则回退社招（zpType=2 / postType=SH）。

    Phase 8 (2026-05-10) 探查更新：
      - getPost.mvc API GBK 编码（既有 fn 走 .json()，requests 走系统默认 UTF-8 解码
        在很多公告文本里会失败；改用 .content.decode('gbk') + json.loads）。
      - postTotalRow 字段长期返回 None，仅 postTotalPage 可信。
      - zpType=1（校招/管培/实习）当前空（季节空档）。zpType=2 = 社招（postType=SH）
        18 pages × 6（默认 pageSize=6） → 服务端 pageSize=50 实测 OK。
      - 既有 fn 写死 zpType=1 → 长期 fetched=0；改成 校招优先 + 社招回退（job_type=
        social），公司列按 title 含 '理财' 二次贴标 浙银理财。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    base_url = 'https://zp.czbank.com.cn/zpweb/planController/getPost.mvc'
    headers = {
        'User-Agent': UA,
        'Referer': 'https://zp.czbank.com.cn/zpweb/planController/gotoIndex.mvc?pageType=2',
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest',
    }
    PAGE_SIZE = 50  # 服务端实测无 cap
    max_pages_cfg = int(target.get('max_pages') or 20) if isinstance(target, dict) else 20

    def fetch(zp_type: str, pn: int):
        start = (pn - 1) * PAGE_SIZE
        end = pn * PAGE_SIZE
        try:
            resp = requests.get(
                base_url, headers=headers, proxies=REQUEST_PROXIES, timeout=30,
                params={
                    'pageType': '2', 'zpType': zp_type,
                    'start': start, 'end': end,
                    'depid': '', 'educ': '', 'orgId': '', 'postName': '',
                    'workYear': '', 'location': '',
                },
            )
            text = resp.content.decode('gbk', errors='replace')
            import json as _json
            return _json.loads(text)
        except Exception as exc:
            logger.warning(f'浙商银行 zpType={zp_type} p{pn} 失败: {exc}')
            return None

    plans = [('1', 'campus'), ('2', 'social')]
    for zp_type, label in plans:
        first = fetch(zp_type, 1)
        if not first:
            continue
        body = (first.get('body') or [{}])[0]
        rows = list(body.get('dataList') or [])
        total_pages = int(body.get('postTotalPage') or 1)
        if not rows:
            logger.info(f'浙商银行 zpType={zp_type}（{label}）当前 0 页')
            continue
        if total_pages > 1:
            for pn in range(2, min(total_pages, max_pages_cfg) + 1):
                time.sleep(0.3)
                more = fetch(zp_type, pn)
                if not more:
                    break
                bm = (more.get('body') or [{}])[0]
                extra = list(bm.get('dataList') or [])
                if not extra:
                    break
                rows.extend(extra)

        page_added = 0
        for item in rows:
            title = norm_text(item.get('name'))
            if not title:
                continue
            pid = item.get('postId')
            if pid in seen:
                continue
            seen.add(pid)
            desc = '\n'.join(x for x in [
                norm_text(item.get('baseCond')), norm_text(item.get('postCond'))
            ] if x)
            req = ' / '.join(x for x in [
                norm_text(item.get('eduCond')), norm_text(item.get('majorCond')),
                norm_text(item.get('workYear') or item.get('workYears')),
            ] if x)
            org = norm_text(
                item.get('needDept') or item.get('needOrg') or item.get('mgrOrg') or ''
            )
            company = '浙银理财' if '理财' in (title + org) else '浙商银行'
            job = JobInfo(
                id='', company=company, title=title,
                location=norm_text(item.get('locationName') or item.get('location')) or '未知',
                department=org,
                job_type=label,
                url=(
                    f'https://zp.czbank.com.cn/zpweb/zpPostController/jobDetailPage.mvc?postId={pid}'
                    if pid else target['url']
                ),
                publish_date=norm_text(item.get('createTime') or item.get('zpStartDate') or ''),
                deadline=norm_text(item.get('zpEndDate') or item.get('applyEndDate') or ''),
                description=desc, requirements=req,
            )
            jobs.append(job)
            page_added += 1
        logger.info(
            f'浙商银行 {label} (zpType={zp_type}): fetched {len(rows)} 条 / '
            f'totalPages={total_pages} added={page_added}'
        )
        # 校招命中即可，不必再走社招；校招空才走社招回退
        if jobs and zp_type == '1':
            break

    if not jobs:
        logger.info('浙商银行当前无开放岗位（校招/社招均空）')
    return jobs


def crawl_zhiye_campus(page, target) -> List[JobInfo]:
    """通用 zhiye 校招接口抓取（如 虎扑/光大/中交集团/中铁十二局医院 等）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    parsed = urlparse(target['url'])
    base = f"{parsed.scheme}://{parsed.netloc}"
    # MAX_PAGES=20 + PageSize=20 = 400 hard cap，对很多 zhiye host 来说太低：
    # ccccltd.zhiye.com 真上游 2612, genertec.zhiye.com 1374 — Phase 3 audit
    # 发现 5 家国央企 fetched=400 整都是这个 cap 触发的。改为默认 100 页
    # （= 2000 items），覆盖 genertec 100%、ccccltd 76%。+3min cron 时间。
    max_pages = int(target.get('max_pages') or 100)

    for current_page in range(max_pages):
        payload = {
            'PageIndex': current_page,
            'PageSize': 20,
            'KeyWords': '',
            'SpecialType': 0,
            'PortalId': '',
            'DisplayFields': ['Category', 'Kind', 'LocId', 'ClassificationOne'],
        }
        try:
            resp = requests.post(
                f'{base}/api/Jobad/GetJobAdPageList',
                json=payload,
                headers={'User-Agent': UA, 'Referer': target['url'], 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json, text/plain, */*'},
                proxies=REQUEST_PROXIES, timeout=30,
            )
            rows = (resp.json() or {}).get('Data') or []
        except Exception as e:
            logger.warning(f"{target['name']} API 第 {current_page + 1} 页失败: {e}")
            break

        page_added = 0
        for item in rows:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            jid = item.get('Id')
            loc = norm_text(','.join(item.get('LocNames') or [])) or '未知'
            job = JobInfo(
                id='', company=target['name'], title=title, location=loc,
                department=norm_text(item.get('ClassificationOne') or item.get('Category') or ''),
                job_type=target.get('type', 'campus'),
                url=f'{base}/jobs/detail/{jid}' if jid else target['url'],
                description=norm_text(item.get('Duty') or ''), requirements=norm_text(item.get('Require') or ''),
                publish_date=norm_text(item.get('PostDate') or ''), deadline=norm_text(item.get('EndTime') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f"{target['name']} API 第 {current_page + 1} 页: {page_added} 条")
        if not rows or page_added == 0:
            break
    return jobs


def crawl_zhiye_table_campus(page, target) -> List[JobInfo]:
    """zhiye.com 表格 / UL 列表变体（北森 BeiSen 老模板）通用爬虫。

    适用于走 DOM 渲染（不返回 GetJobAdPageList JSON）的 zhiye 站点，例如
    cssc.zhiye.com / cnnc.zhiye.com / hr.cnnc.com.cn (重定向到 cnnc.zhiye.com)。

    支持两种 DOM 变体（同一 BeiSen 模板的不同皮肤）：
      A. <table class="tabletitle"><tbody><tr>...</tr></tbody></table>
         例：cnnc.zhiye.com — 4 列：职位名称 / 成员单位 / 招聘人数 / 发布时间
      B. <div class="job-list"><ul><li>...</li></ul></div>
         例：cssc.zhiye.com — 5 行（li.innerText 换行分隔）：
            职位名称 / 成员单位 / 专业类别 / 工作地点 / 发布时间

    锚点 a[jobadid] 永远存在，跨变体可作 anchor。我们走父链找到行容器（TR/LI），
    再用 children innerText（TR 模板）或 li.innerText 按换行切分（UL 模板）抽列。

    分页：底部 `<a class="next" href="...?PageIndex=N">下一页</a>`，直接 page.goto 翻页，
    避免点击触发 SPA 路由问题。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    parsed = urlparse(target['url'])
    base = f"{parsed.scheme}://{parsed.netloc}"
    company = target['name']
    max_pages = int(target.get('max_pages') or 20)
    job_type = target.get('type', 'campus')

    current_url = target['url']
    for page_idx in range(1, max_pages + 1):
        try:
            page.goto(current_url, wait_until='domcontentloaded', timeout=45000)
        except Exception as e:
            logger.warning(f'{company} 第 {page_idx} 页 goto 失败: {e}')
            break

        # 等待数据渲染：要么 table tbody tr，要么 ul li 内 a[jobadid]
        try:
            page.wait_for_function(
                "document.querySelectorAll('a[jobadid]').length > 0",
                timeout=20000,
            )
        except Exception:
            logger.warning(f'{company} 第 {page_idx} 页未检测到 a[jobadid]，停止翻页')
            break
        page.wait_for_timeout(800)

        rows_data = page.evaluate("""() => {
          const out = [];
          const seenRowKey = new Set();
          const anchors = Array.from(document.querySelectorAll('a[jobadid]'));
          for (const a of anchors) {
            const jid = a.getAttribute('jobadid') || '';
            if (!jid) continue;
            // 找行容器：先看是不是 a 自己就是标题（CNNC: a 在 td.joblsttitle 内）
            // 否则向上找 LI（CSSC: a.apply 在 div.info > li 内）
            let row = null;
            let cur = a;
            for (let i = 0; i < 8 && cur; i++) {
              if (cur.tagName === 'TR' || cur.tagName === 'LI') { row = cur; break; }
              cur = cur.parentElement;
            }
            if (!row) continue;
            const key = row.tagName + ':' + jid;
            if (seenRowKey.has(key)) continue;
            seenRowKey.add(key);

            let cols = [];
            let detailHref = '';
            let titleText = '';
            // 优先取真正的标题锚点（href 指向详情，不是 javascript:void(0)）
            const realTitleAnchor = row.querySelector('a[jobadid][href]:not([href^="javascript"])');
            if (realTitleAnchor) {
              titleText = (realTitleAnchor.innerText || '').replace(/\\s+/g, ' ').trim();
              detailHref = realTitleAnchor.getAttribute('href') || '';
            }

            if (row.tagName === 'TR') {
              cols = Array.from(row.children).map(c => (c.innerText || '').replace(/\\s+/g, ' ').trim());
              if (!titleText && cols.length) titleText = cols[0];
            } else {
              // LI 变体：用 innerText 按换行切分（LI 内的 a.apply 是「立即申请」按钮，不是标题）
              const raw = (row.innerText || '').split(/\\n+/).map(s => s.trim()).filter(Boolean);
              cols = raw.filter(s => !/^立即申请$|^工作职责|^任职要求|^岗位要求|^点击查看/.test(s));
              // li 第一行 = 标题（含 J 编号），后续 = 成员单位/专业类别/工作地点/发布时间
              if (!titleText && cols.length) titleText = cols[0];
            }
            out.push({jobadid: jid, title: titleText, href: detailHref, cols});
          }
          return out;
        }""")

        page_added = 0
        for r in rows_data:
            jid = r.get('jobadid') or ''
            cols = [norm_text(c) for c in (r.get('cols') or [])]
            title = norm_text(r.get('title')) or (cols[0] if cols else '')
            if not title or title == '立即申请':
                # 标题取不到时跳过
                continue
            # 列映射（启发式）
            #   5 列 = title / 成员单位 / 专业类别 / 工作地点 / 发布时间  (CSSC 系)
            #   4 列 = title / 成员单位 / 人数 / 发布时间                  (CNNC 系)
            department = ''
            location = '未知'
            publish_date = ''
            if len(cols) >= 5:
                department = cols[1]
                location = cols[3] or '未知'
                publish_date = cols[4]
            elif len(cols) >= 4:
                department = cols[1]
                publish_date = cols[3]
                # CNNC 列没有 location，从标题里抓括号（跳过 J 编号、届数、数字等无效内容）
                for m in re.finditer(r'[（(]([^（()）]{1,15})[）)]', title):
                    candidate = m.group(1).strip()
                    if re.fullmatch(r'J\d+', candidate, re.IGNORECASE):
                        continue
                    if re.fullmatch(r'\d{4}届', candidate):
                        continue
                    if re.fullmatch(r'\d+', candidate):
                        continue
                    location = candidate
                    break
            elif len(cols) >= 2:
                department = cols[1]

            href = r.get('href') or ''
            if href:
                detail_url = urljoin(base + '/', href)
            else:
                detail_url = f'{base}/campusxq?jobId={jid}&class=2'

            job = JobInfo(
                id='', company=company, title=title, location=location or '未知',
                department=department, job_type=job_type,
                url=detail_url, publish_date=publish_date,
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1

        logger.info(f'{company} 第 {page_idx} 页（DOM 表格/UL）: {page_added} 条')
        if page_added == 0:
            break

        # 翻页：BeiSen 模板 `上一页`/`下一页` 都用 class="next"，必须按文本区分
        # 末页时下一页变 <span> 或带 disabled，没有 href，循环自动结束
        try:
            next_href = page.evaluate("""() => {
              const all = Array.from(document.querySelectorAll('a'));
              const cands = all.filter(e => (e.innerText || '').trim() === '下一页'
                                            && !(e.className || '').includes('disabled')
                                            && (e.getAttribute('href') || '').includes('PageIndex='));
              return cands.length ? cands[0].getAttribute('href') : null;
            }""")
        except Exception:
            next_href = None
        if not next_href:
            break
        current_url = urljoin(base + '/', next_href)

    return jobs


# CNNC 子公司 → mobile API c2 ID 映射
# 用途：class B (hr.cnnc.com.cn) 和 class C (cnnc.zhiye.com)
# 没有 c2 in URL，但所有 jobs 在 cnnc.m.zhiye.com 上有数据。按 company name 查表得 c2。
# c2 ID 来源：cnnc.m.zhiye.com/JobAd/_GetSearchItems jobclasses['对外显示招聘单位']
CNNC_COMPANY_C2_MAP: Dict[str, str] = {
    # class B (hr.cnnc.com.cn) — 5+ subsidiaries
    '中核运维': '1_454',
    '中核运维技术': '1_454',
    '中核大唐庄河核电': '1_559',
    '中核浙能': '1_28',
    '中核苏能': '1_12',
    '中核龙安': '1_451',
    '中核龙安有限公司': '1_451',
    '三门核电': '1_9',
    '中核二四': '1_103',
    '中国核电': '',  # 集团本部 jc=2 全量（fallback）
    # class C (cnnc.zhiye.com)
    '中核海洋': '1_26',
    '中核光电': '1_465',
    '中核光电科技(上海)有限公司': '1_465',
    '中核光电科技（上海）有限公司': '1_465',
    '中辐院，中国辐射防护研究院': '1_169',
    '中国辐射防护研究院': '1_169',
    '中国原子能科学研究院': '1_122',
    # class A 备用（URL 已有 c2 时不会用到此 map）
    '中核二三': '1_106',
    '中核二二': '1_104',
    '中核华泰': '1_101',
    '中核四0四有限公司': '1_121',
    '中核四0四': '1_121',
    '中核五公司': '1_102',
    '中核铀业': '1_457',
    '中核（上海）供应链管理有限公司': '',  # jc=2 全量
    '中国中原': '1_162',
    '中国聚变能源有限公司': '1_680',
    '中国聚变': '1_680',
}


def crawl_cnnc_mobile_api(page, target) -> List[JobInfo]:
    """中核（CNNC）子公司专用爬虫 — 直接调用 cnnc.m.zhiye.com 移动端 JSON API。

    背景：CNNC 旗下三组域名走同一套北森后台（TenantId=605932），但前端模板差异
      - cnnc.m.zhiye.com (移动端)：URL 上带 c2=1_xxx 子公司筛选
      - hr.cnnc.com.cn (桌面)：WAF 412 challenge，curl/Chromium/requests 全部被挡
      - cnnc.zhiye.com (桌面)：landing page 仅 CMS 内容，无 jobadid DOM
    Playwright/Chromium 对所有三组域名都 ERR_EMPTY_RESPONSE（TLS 指纹被挡）。
    但 requests + iPhone UA 可以稳定访问 cnnc.m.zhiye.com 的 JSON API：
      GET /JobAd/_SearchJobAd?pi=N&ps=20&jc=2&c1=-1&c2=<id>&ky=&c=-1&in=1
      → {DataResult:[{JobAdId, JobAdName, LocIdName, Department, ToPostDate, Duty, ...}],
         RowCount: <total>, PageCount, ...}

    所以本函数：
      1. 从 URL 解析 c2 参数（class A 直接拿到）
      2. 否则按 target['name'] 查 CNNC_COMPANY_C2_MAP（class B/C）
      3. 直接 requests 拉 mobile API；忽略 Playwright `page` 参数
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    company = target['name']
    job_type = target.get('type', 'campus')
    target_url = target.get('url', '')

    # 解析 c2：先从 URL query string 找
    c2 = ''
    try:
        parsed = urlparse(target_url)
        qs = parse_qs(parsed.query or '')
        c2_vals = qs.get('c2') or []
        if c2_vals:
            c2 = c2_vals[0].strip()
    except Exception:
        pass
    # URL 没有 c2 → 按公司名查表
    if not c2 or c2 in ('-1', ''):
        c2 = CNNC_COMPANY_C2_MAP.get(company, '')
    if not c2:
        # 最后兜底用 -1（jc=2 全量），把整个 CNNC 校招岗位都拉下来
        # 通常只在公司名未在 map 中时触发；返回数据后由 fetched/match 阶段去重
        c2 = '-1'

    api_base = 'https://cnnc.m.zhiye.com/JobAd/_SearchJobAd'
    iphone_ua = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
                 'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1')
    headers = {
        'User-Agent': iphone_ua,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': f'https://cnnc.m.zhiye.com/joblist.html?jc=2&c2={c2}',
        'X-Requested-With': 'XMLHttpRequest',
    }
    max_pages = int(target.get('max_pages') or 30)  # 30 * 20 = 600 上限够 99% 子公司

    for pi in range(1, max_pages + 1):
        api_url = f'{api_base}?pi={pi}&ps=20&jc=2&c1=-1&c2={c2}&ky=&c=-1&in=1'
        try:
            resp = requests.get(api_url, headers=headers, proxies=REQUEST_PROXIES, timeout=30)
            data = resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.warning(f'{company} CNNC mobile API 第 {pi} 页失败: {e}')
            break
        rows = data.get('DataResult') or []
        page_added = 0
        for item in rows:
            jid = str(item.get('JobAdId') or '').strip()
            title = norm_text(item.get('JobAdName'))
            if not title or not jid:
                continue
            location = norm_text(item.get('LocIdName')) or '未知'
            department = norm_text(item.get('Department') or item.get('OrgName') or '')
            publish = norm_text(item.get('ToPostDate') or '')
            deadline = norm_text(item.get('ToEndDate') or '')
            description = norm_text(item.get('Duty') or '')
            detail_url = f'https://cnnc.m.zhiye.com/cmpdetail.html?jobid={jid}&jc={item.get("CategoryId") or 2}'
            job = JobInfo(
                id='', company=company, title=title, location=location,
                department=department, job_type=job_type,
                url=detail_url, description=description,
                publish_date=publish, deadline=deadline,
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'{company} CNNC mobile API 第 {pi} 页 (c2={c2}): {page_added} 条 (RowCount={data.get("RowCount")})')
        if not rows or page_added == 0:
            break
    return jobs


def crawl_cebbank(page, target) -> List[JobInfo]:
    """光大银行：北森系统，校园招聘 API。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    base = 'https://cebbank.zhiye.com'
    portal_id = 'cebbank_portal_id_2024'
    max_pages = int(target.get('max_pages') or MAX_PAGES)

    for current_page in range(max_pages):
        payload = {
            'PageIndex': current_page,
            'PageSize': 20,
            'Category': ['2'],
            'KeyWords': '',
            'SpecialType': 0,
            'PortalId': portal_id,
            'DisplayFields': ['Category', 'Kind', 'LocId', 'Org', 'PostDate'],
        }
        try:
            resp = requests.post(
                f'{base}/api/Jobad/GetJobAdPageList',
                json=payload,
                headers={'User-Agent': UA, 'Referer': f'{base}/campus', 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json, text/plain, */*'},
                timeout=30,
            )
            rows = (resp.json() or {}).get('Data') or []
        except Exception as e:
            logger.warning(f'光大银行 API 第 {current_page + 1} 页失败: {e}')
            break

        if not rows:
            break

        page_added = 0
        for item in rows:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            jid = norm_text(item.get('Id') or item.get('JobAdId'))
            loc = norm_text(','.join(item.get('LocNames') or [])) or '未知'
            job = JobInfo(
                id='', company='光大银行', title=title, location=loc,
                department=norm_text(item.get('Org') or ''),
                job_type='campus',
                url=f'{base}/job/{jid}' if jid else target['url'],
                description=norm_text(item.get('Duty') or ''), requirements=norm_text(item.get('Require') or ''),
                publish_date=norm_text(item.get('PostDate') or ''), deadline=norm_text(item.get('EndTime') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1

        logger.info(f'光大银行 API 第 {current_page + 1} 页: {page_added} 条')
        if not rows or page_added == 0:
            break

    if not jobs:
        logger.info('光大银行当前未获取到校招岗位（可能未开招）')
    return jobs


def crawl_icbc(page, target) -> List[JobInfo]:
    """工商银行：qryAnnounList REST。

    Phase 7（2026-05-10）发现服务端 pageSize 实际无 hard cap：pageSize=50 单次
    返回 total=41 returned=41。改用 stdlib requests + verify=False 直连，省去
    Playwright in-page fetch 路径（旧实现因 OpenSSL renegotiation 走 page.evaluate）。
    保留 4 个 projectType 遍历：R00301 校招 / R00302 社招 / R00303 实习 / R00304 乡村振兴。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    api_url = 'https://job.icbc.com.cn/icbc/trmo/announ/qryAnnounList'
    PROJECT_TYPES = [
        ('R00301', 'campus'),
        ('R00302', 'social'),
        ('R00303', 'intern'),
        ('R00304', 'campus'),
    ]
    PAGE_SIZE = 50
    MAX_PAGES = 20

    headers = {
        'User-Agent': UA,
        'Origin': 'https://job.icbc.com.cn',
        'Referer': 'https://job.icbc.com.cn/pc/index.html',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    def fetch_one(ptype: str, pn: int) -> Optional[dict]:
        body = {'public': {'call_app': 'F-TRM'},
                'private': {'page': pn, 'pageSize': PAGE_SIZE, 'projectType': ptype}}
        try:
            r = requests.post(
                api_url, json=body, headers=headers,
                proxies=REQUEST_PROXIES, timeout=20, verify=False,
            )
            return r.json() or {}
        except Exception as exc:
            logger.warning(f'工商银行 qryAnnounList {ptype} p{pn} 失败: {exc}')
            return None

    api_rows: List[dict] = []
    for ptype, _label in PROJECT_TYPES:
        first = fetch_one(ptype, 1)
        if not first or str(first.get('retCode') or '') != '0':
            logger.info(f'工商银行 {ptype} 异常: {first!r}'[:200])
            continue
        data = first.get('data') or {}
        total = int(data.get('total') or 0)
        rows = list(data.get('dataList') or [])
        for r in rows:
            r['projectType'] = ptype
        api_rows.extend(rows)
        if len(rows) >= total or total <= PAGE_SIZE:
            continue
        pages = min(MAX_PAGES, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        for pn in range(2, pages + 1):
            time.sleep(0.4)
            more = fetch_one(ptype, pn)
            if not more:
                break
            d = more.get('data') or {}
            extra = list(d.get('dataList') or [])
            for rec in extra:
                rec['projectType'] = ptype
            api_rows.extend(extra)
            if len(extra) < PAGE_SIZE:
                break

    for item in api_rows:
        title = norm_text(item.get('title') or item.get('positionName') or '')
        if not title:
            continue
        announ_id = norm_text(item.get('announId') or '')
        pid = announ_id or item.get('positionId') or item.get('id') or ''
        if announ_id:
            url = f"https://job.icbc.com.cn/pc/index.html#/main/news/announ/detail?announId={announ_id}"
        elif pid:
            url = f"https://job.icbc.com.cn/campus/detail?id={pid}"
        else:
            url = target['url'] if isinstance(target, dict) else 'https://job.icbc.com.cn/'
        location = norm_text(item.get('struName') or item.get('workLocation') or item.get('city') or '') or '未知'
        org = norm_text(item.get('struName') or item.get('department') or '')
        publish_date = norm_text(item.get('publishTime') or item.get('createTime') or '')
        deadline = norm_text(item.get('deadline') or item.get('endTime') or item.get('soldOutTime') or '')
        ptype = item.get('projectType') or ''
        job_type = 'social' if ptype == 'R00302' else ('intern' if ptype == 'R00303' else 'campus')
        company_label = '工银理财' if '工银理财' in title else '工商银行'
        job = JobInfo(
            id='', company=company_label, title=title, location=location,
            department=org, job_type=job_type, url=url,
            publish_date=publish_date, deadline=deadline,
            description=norm_text(item.get('jobDescription') or item.get('description') or item.get('content') or ''),
            requirements=norm_text(item.get('jobRequirement') or item.get('requirement') or ''),
        )
        if job.id not in seen:
            seen.add(job.id)
            jobs.append(job)

    if jobs:
        logger.info(f'工商银行招聘公告: {len(jobs)} 条（4 类 projectType 合计）')
    else:
        logger.info('工商银行当前未获取到招聘公告')
    return jobs


def crawl_psbc(page, target) -> List[JobInfo]:
    """邮储银行：抓主域 https://www.psbc.com/cn/gyyc/rczp/{xyzp,shzp}/ 公告列表。

    Phase 8 (2026-05-10) 重写：
      - 既有 fn 走 psbc.zhaopin.com 通道，403 forbidden（zhaopin 反爬已升级）；
        psbc 不开放任何 list API，只剩主域官网 announcement 模式。
      - 主域校园招聘 9 条公告（多 stale，最新 2023-06）；社会招聘 10 条（latest
        2025-11）。announcement-style 同 ICBC / 渤海，每条公告作 1 个 JobInfo。
      - 链接形如 ./202511/t20251107_375690.html，相对 子页面 url 拼接。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    BASE = 'https://www.psbc.com'
    PAGES = [
        ('校园招聘', f'{BASE}/cn/gyyc/rczp/xyzp/', 'campus'),
        ('社会招聘', f'{BASE}/cn/gyyc/rczp/shzp/', 'social'),
    ]
    headers = {
        'User-Agent': UA,
        'Referer': f'{BASE}/cn/index.html',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    item_re = re.compile(
        r'<a[^>]+href="((?:\.{1,2}/)+[^"]+t\d+_\d+\.html)"[^>]*>([^<]+)</a>'
    )
    date_path_re = re.compile(r'/(20\d{2})(\d{2})/t(20\d{2})(\d{2})(\d{2})_')

    for label, url, job_type in PAGES:
        try:
            r = requests.get(url, headers=headers, proxies=REQUEST_PROXIES, timeout=20, verify=False)
            text = r.content.decode('utf-8', errors='replace')
        except Exception as exc:
            logger.warning(f'邮储银行 {label} 列表抓取失败: {exc}')
            continue

        page_added = 0
        for m in item_re.finditer(text):
            href = m.group(1).strip()
            title = norm_text(m.group(2))
            if not title or title in ('校园招聘', '社会招聘', '人才招聘'):
                continue
            full_url = urljoin(url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            pubd = ''
            pm = date_path_re.search(full_url)
            if pm:
                pubd = f'{pm.group(3)}-{pm.group(4)}-{pm.group(5)}'

            job = JobInfo(
                id='', company='邮储银行', title=title,
                location='全国' if '总行' in title else '未知',
                department='', job_type=job_type, url=full_url,
                publish_date=pubd, deadline='',
                description='', requirements='',
            )
            jobs.append(job)
            page_added += 1
        logger.info(f'邮储银行 {label}: 收 {page_added} 条公告')

    if jobs:
        logger.info(f'邮储银行招聘公告: {len(jobs)} 条（announcement-style 校招+社招）')
    else:
        logger.info('邮储银行当前未获取到招聘公告')

    return jobs


def crawl_cgb(page, target) -> List[JobInfo]:
    """广发银行：经 chinalife.zhiye.com /custom/gfcampus（中国人寿 Beisen 多租户）。

    Phase 8 (2026-05-10) 探查：
      - 主站 www.cgbchina.com.cn /Channel/11581868（人才招聘）跳转
        chinalife.zhiye.com/custom/gfcampus?hideMenu=1（即广发借中国人寿的 Beisen
        租户发布岗位）。
      - GetJobAdPageList API 不区分租户（所有 chinalife-Beisen tenants 共用），需
        KeyWords="广发" + 客户端 Org 过滤（contains "广发"）。
      - 实测 113 条 社招岗位，pageSize=50 时 3 页（pidx=0,1,2）即收完；pidx=3 起 0 条。
      - 全为 社招（Category="社会招聘"），公司列 = 广发银行。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    api_url = 'https://chinalife.zhiye.com/api/Jobad/GetJobAdPageList'
    headers = {
        'User-Agent': UA,
        'Origin': 'https://chinalife.zhiye.com',
        'Referer': 'https://chinalife.zhiye.com/custom/gfcampus',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
    }
    PAGE_SIZE = 50
    max_pages_cfg = int(target.get('max_pages') or 10) if isinstance(target, dict) else 10

    def fetch(pidx: int):
        body = {
            'PageIndex': pidx, 'PageSize': PAGE_SIZE,
            'KeyWords': '广发', 'SpecialType': 0, 'PortalId': '',
            'Category': [],
            'DisplayFields': ['Category', 'Kind', 'LocId', 'Org', 'PostDate'],
        }
        try:
            r = requests.post(
                api_url, json=body, headers=headers,
                proxies=REQUEST_PROXIES, timeout=20, verify=False,
            )
            return list((r.json() or {}).get('Data') or [])
        except Exception as exc:
            logger.warning(f'广发银行 GetJobAdPageList p{pidx} 失败: {exc}')
            return []

    for pidx in range(max_pages_cfg):
        rows = fetch(pidx)
        if not rows:
            break
        cgb_rows = [r for r in rows if '广发' in (r.get('Org') or '')]
        if not cgb_rows and pidx > 1:
            break
        for item in cgb_rows:
            title = norm_text(item.get('JobAdName'))
            if not title:
                continue
            jid = norm_text(item.get('Id') or item.get('JobAdId'))
            if jid in seen:
                continue
            seen.add(jid)
            org = norm_text(item.get('Org') or '')
            loc = norm_text(','.join(item.get('LocNames') or [])) or '未知'
            cat = norm_text(item.get('Category') or '')
            jt = 'campus' if any(k in cat + title for k in ['校园', '管培', '实习']) else 'social'
            url = (
                f'https://chinalife.zhiye.com/job/{jid}'
                if jid else 'https://chinalife.zhiye.com/custom/gfcampus'
            )
            jobs.append(JobInfo(
                id='', company='广发银行', title=title, location=loc,
                department=org, job_type=jt, url=url,
                publish_date=norm_text(item.get('PostDate') or ''),
                deadline=norm_text(item.get('EndTime') or ''),
                description=norm_text(item.get('Duty') or ''),
                requirements=norm_text(item.get('Require') or ''),
            ))
        logger.info(
            f'广发银行 chinalife 第 {pidx + 1} 页: 收 {len(cgb_rows)}/{len(rows)} 广发条'
        )

    if jobs:
        logger.info(f'广发银行 chinalife API: {len(jobs)} 条（KeyWords=广发 + Org 过滤）')
    else:
        logger.info('广发银行当前未获取到开放岗位')
    return jobs


def crawl_cbhb(page, target) -> List[JobInfo]:
    """渤海银行：抓主域 https://www.cbhb.com.cn/cbhbank/jrwm/zpxx/index.shtml 公告列表。

    Phase 8 (2026-05-10) 探查：
      - 主域 announcement-list 单页 10 条公告（latest 2026-04-02 武汉社招）；
        index_2.shtml 等续页 404，全公告挤在单页。
      - announcement-style 同 ICBC / 邮储 / 工商；每条公告作 1 个 JobInfo。
      - 公司列 = 渤海银行；按 title 含 '渤银理财' 二次贴标。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    BASE = 'https://www.cbhb.com.cn'
    LIST_URL = f'{BASE}/cbhbank/jrwm/zpxx/index.shtml'
    headers = {
        'User-Agent': UA,
        'Referer': f'{BASE}/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    try:
        r = requests.get(
            LIST_URL, headers=headers, proxies=REQUEST_PROXIES,
            timeout=20, verify=False,
        )
        text = r.content.decode('utf-8', errors='replace')
    except Exception as exc:
        logger.warning(f'渤海银行 公告列表抓取失败: {exc}')
        return jobs

    item_re = re.compile(
        r'<a[^>]+href="(/cbhbank/(\d{4})-(\d{2})/(\d{2})/article_\d+\.shtml)"[^>]*>([^<]+)</a>'
    )
    for m in item_re.finditer(text):
        href, yy, mm, dd, title = m.groups()
        title = norm_text(title)
        if not title or title in ('招聘信息', '人才招聘'):
            continue
        full_url = BASE + href
        if full_url in seen:
            continue
        seen.add(full_url)

        if any(k in title for k in ['校园', '管培', '应届', '实习', '校招']):
            jt = 'campus'
        else:
            jt = 'social'
        company = '渤银理财' if '渤银理财' in title else '渤海银行'

        jobs.append(JobInfo(
            id='', company=company, title=title,
            location='未知',
            department='', job_type=jt, url=full_url,
            publish_date=f'{yy}-{mm}-{dd}', deadline='',
            description='', requirements='',
        ))

    if jobs:
        logger.info(f'渤海银行 公告: {len(jobs)} 条（announcement-style 单页）')
    else:
        logger.info('渤海银行 当前未获取到公告')
    return jobs


def crawl_boc(page, target) -> List[JobInfo]:
    """中国银行：校园招聘，通过浏览器捕获 API 响应或直接解析 DOM。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=5)
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f'中国银行页面打开失败: {e}')
        return jobs

    # 尝试从页面嵌入的数据中获取岗位信息
    try:
        page_data = page.evaluate("""
            () => {
                return window.chinahr_cmp_json_data || {};
            }
        """)
        if page_data:
            logger.info(f'中国银行页面数据 keys: {list(page_data.keys())}')
            # 检查是否有 springjobs 或 jobs 数据
            springjobs = page_data.get('springjobs', {})
            jobs_data = page_data.get('jobs', {})
            if springjobs:
                token = springjobs.get('token')
                first_id = springjobs.get('firstId')
                logger.info(f'中国银行 springjobs 数据: token={token}, firstId={first_id}')
            if jobs_data:
                token = jobs_data.get('token')
                first_id = jobs_data.get('firstId')
                logger.info(f'中国银行 jobs 数据: token={token}, firstId={first_id}')

            # 尝试从公告中提取岗位类型信息
            try:
                gonggao = page_data.get('gonggao', [])
                if gonggao and isinstance(gonggao, list):
                    for tab in gonggao:
                        if isinstance(tab, dict):
                            tabs = tab.get('tabs', [])
                            for t in tabs:
                                if isinstance(t, dict):
                                    content = t.get('content', [])
                                    if content and isinstance(content, list):
                                        logger.info(f'中国银行: 从公告中提取到 {len(content)} 条内容片段')
                                        # 尝试从内容中提取岗位类型
                                        for item in content:
                                            if isinstance(item, str) and '岗位' in item:
                                                lines = item.split('。')
                                                for line in lines:
                                                    line = line.strip()
                                                    if '岗位' in line and len(line) < 100:
                                                        # 提取岗位类型作为示例岗位
                                                        job = JobInfo(
                                                            id='',
                                                            company='中国银行',
                                                            title=line,
                                                            location='全国多地',
                                                            department='详见官网',
                                                            job_type='campus',
                                                            url=target['url'],
                                                            publish_date='2026-03',
                                                            deadline='2026-03-30',
                                                            description='请查看官网公告详情',
                                                            requirements='',
                                                        )
                                                        if job.id not in seen:
                                                            seen.add(job.id)
                                                            jobs.append(job)
            except Exception as e2:
                logger.debug(f'从公告提取岗位类型失败: {e2}')
    except Exception as e:
        logger.info(f'获取页面数据失败: {e}')

    # 尝试从 Vue 状态中获取岗位数据
    try:
        all_vue_keys = page.evaluate("""
            () => {
                const app = document.querySelector('#app');
                if (app && app.__vue__) {
                    return Object.keys(app.__vue__.$data || {}).slice(0, 20);
                }
                return [];
            }
        """)
        if all_vue_keys:
            logger.info(f'中国银行 Vue 数据键: {all_vue_keys}')
    except Exception as e:
        logger.debug(f'获取 Vue 状态失败: {e}')

    # 尝试点击左侧机构列表并获取岗位数据
    try:
        # 使用更通用的选择器查找可点击的机构元素
        org_selectors = [
            'div[class*="menu"] > div, div[class*="sidebar"] > div',
            'ul[class*="menu"] > li, ul[class*="list"] > li',
            '.menu-item, .list-item, .org-item',
            '[class*="branch"], [class*="institution"], [class*="org"]',
        ]

        for selector in org_selectors:
            try:
                org_items = page.locator(selector).all()
                if org_items and len(org_items) > 1:  # 至少有2个元素才可能是机构列表
                    logger.info(f'中国银行: 通过选择器 "{selector}" 找到 {len(org_items)} 个元素')
                    for idx, item in enumerate(org_items[:8]):  # 最多点击前8个
                        try:
                            text = item.text_content() or ''
                            if text and len(text.strip()) > 1:
                                logger.info(f'中国银行: 点击元素 {idx+1}: {text[:40]}')
                                item.click(timeout=3000)
                                page.wait_for_timeout(3000)

                                # 点击后尝试从 Vue 状态中获取岗位数据
                                try:
                                    job_data = page.evaluate("""
                                        () => {
                                            const app = document.querySelector('#app');
                                            if (app && app.__vue__) {
                                                const data = app.__vue__.$data;
                                                // 尝试查找岗位列表数据
                                                const possibleKeys = ['positionList', 'jobList', 'jobs', 'positions', 'jobData', 'positionData', 'list', 'data'];
                                                const result = {};
                                                possibleKeys.forEach(key => {
                                                    if (data[key] && Array.isArray(data[key])) {
                                                        result[key] = data[key].slice(0, 5);  // 只返回前5个
                                                    }
                                                });
                                                return result;
                                            }
                                            return {};
                                        }
                                    """)
                                    if job_data:
                                        logger.info(f'中国银行: 点击后找到的岗位数据键: {list(job_data.keys())}')
                                        # 尝试解析岗位数据
                                        for key, items in job_data.items():
                                            if isinstance(items, list) and items:
                                                logger.info(f'中国银行: 从 {key} 找到 {len(items)} 个岗位示例')
                                                for item in items:
                                                    if not isinstance(item, dict):
                                                        continue
                                                    title = norm_text(item.get('positionName') or item.get('jobName') or item.get('title') or item.get('name') or '')
                                                    if title:
                                                        pid = item.get('positionId') or item.get('id') or item.get('jobId') or ''
                                                        url = f"https://campus.chinahr.com/pages/boc-2026-Spring/#/position?id={pid}" if pid else target['url']
                                                        location = norm_text(item.get('workLocation') or item.get('city') or item.get('location') or '') or '未知'
                                                        org = norm_text(item.get('department') or item.get('deptName') or '')
                                                        publish_date = norm_text(item.get('publishTime') or item.get('createTime') or '')
                                                        description = norm_text(item.get('jobDescription') or item.get('description') or '')
                                                        requirements = norm_text(item.get('jobRequirement') or item.get('requirement') or '')

                                                        job = JobInfo(
                                                            id=pid,
                                                            company='中国银行',
                                                            title=title,
                                                            location=location,
                                                            department=org,
                                                            job_type='campus',
                                                            url=url,
                                                            publish_date=publish_date,
                                                            description=description,
                                                            requirements=requirements,
                                                        )
                                                        if job.id not in seen:
                                                            seen.add(job.id)
                                                            jobs.append(job)
                                except Exception as e2:
                                    logger.debug(f'点击后获取 Vue 状态失败: {e2}')
                        except Exception as e:
                            logger.debug(f'点击失败: {e}')
                    if jobs:  # 如果已经获取到岗位，就不再点击更多机构
                        break
            except Exception as e:
                logger.debug(f'选择器 {selector} 失败: {e}')
    except Exception as e:
        logger.debug(f'点击机构失败: {e}')

    # 尝试从 DOM 中解析岗位列表
    try:
        # 查找岗位列表的常见选择器
        job_selectors = [
            'div[class*="job-list"] .job-item, div[class*="job-list"] > div',
            'div[class*="position-list"] .position-item, div[class*="position-list"] > div',
            'li[class*="job"], li[class*="position"]',
            'tr[class*="job"], tr[class*="position"]',
            '.job-card, .position-card',
        ]

        for selector in job_selectors:
            try:
                job_elements = page.locator(selector).count()
                if job_elements > 0:
                    logger.info(f'中国银行: 通过选择器 "{selector}" 找到 {job_elements} 个岗位元素')
                    elements = page.locator(selector).all()
                    for elem in elements[:50]:  # 最多解析50个元素
                        try:
                            text = elem.text_content()
                            if text and len(text.strip()) > 2:
                                # 尝试解析岗位信息
                                lines = [line.strip() for line in text.split('\n') if line.strip()]
                                if lines:
                                    title = lines[0]
                                    location = lines[1] if len(lines) > 1 else ''
                                    org = lines[2] if len(lines) > 2 else ''

                                    job = JobInfo(
                                        id='',
                                        company='中国银行',
                                        title=title,
                                        location=location or '未知',
                                        department=org,
                                        job_type='campus',
                                        url=target['url'],
                                        publish_date='',
                                        deadline='',
                                        description='',
                                        requirements='',
                                    )
                                    if job.id not in seen:
                                        seen.add(job.id)
                                        jobs.append(job)
                        except Exception:
                            continue
                    if jobs:
                        break
            except Exception:
                continue
    except Exception as e:
        logger.debug(f'DOM 解析失败: {e}')

    # 尝试从捕获的 API 响应中解析
    def harvest_from_captured() -> int:
        total_count = 0
        for rec in getattr(page, '_captured_json', []):
            url = rec.get('url', '')
            # 记录所有捕获的 API 响应
            logger.info(f'中国银行捕获到响应: {url[:100]}')

            # 检查是否是岗位相关的 API
            if not any(k in url for k in ['job', 'position', 'campus', 'recruit', 'chinahr', 'applyjob']):
                continue

            payload = rec.get('data') or {}
            data = payload.get('data') or payload
            rows = data.get('list') or data.get('items') or data.get('records') or data.get('positions') or []

            # 处理嵌套的 list/items
            if isinstance(rows, dict):
                rows = rows.get('list') or rows.get('items') or rows.get('records') or rows.get('positions') or []

            if not rows:
                continue

            logger.info(f'中国银行: 从 {url[:80]}... 解析到 {len(rows)} 条数据')

            total_count = max(total_count, int(data.get('total') or payload.get('total') or len(rows)))
            for item in rows:
                title = norm_text(item.get('positionName') or item.get('jobName') or item.get('title') or item.get('name') or item.get('position_title') or '')
                if not title:
                    continue

                pid = item.get('positionId') or item.get('id') or item.get('jobId') or item.get('position_id') or ''
                url = f"https://campus.chinahr.com/pages/boc-2026-Spring/#/position?id={pid}" if pid else target['url']

                location = norm_text(item.get('workLocation') or item.get('city') or item.get('location') or item.get('work_city') or '') or '未知'
                org = norm_text(item.get('department') or item.get('deptName') or item.get('orgName') or item.get('organization') or '')
                publish_date = norm_text(item.get('publishTime') or item.get('createTime') or item.get('release_time') or '')
                description = norm_text(item.get('jobDescription') or item.get('description') or item.get('job_desc') or '')
                requirements = norm_text(item.get('jobRequirement') or item.get('requirement') or item.get('require') or '')

                job = JobInfo(
                    id=pid,
                    company='中国银行',
                    title=title,
                    location=location,
                    department=org,
                    job_type='campus',
                    url=url,
                    publish_date=publish_date,
                    description=description,
                    requirements=requirements,
                )
                if job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
        return total_count

    total_count = harvest_from_captured()

    if jobs:
        logger.info(f'中国银行校招岗位: {len(jobs)} 条')
    else:
        logger.info('中国银行当前未获取到校招岗位（可能未开招或需要更多交互）')

    return jobs


def crawl_ccb(page, target) -> List[JobInfo]:
    """建设银行 (CCB)：通过 plan_index 建立 session，再 in-page fetch 翻
    `/tran/WCCMainPlatV5?TXCODE=NHR104` 全量。

    planType: XY=校园招聘, SX=实习生招聘, SH=社会招聘（本爬虫只取 XY+SX）。
    上游 2026 春季招聘 XY 类目实测 TOTAL_REC=4491, TOTAL_PAGE=90 (PAGE_SIZE=50)。
    服务端响应是文本前缀的 JSON：`\\n\\n{...}`，strip 后 json.loads。
    """
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    PLAN_TYPES = [('XY', 'campus'), ('SX', 'intern')]
    PAGE_SIZE = 50
    max_pages = int(target.get('max_pages') or MAX_PAGES)

    try:
        # 先访问 plan_index 建立 session/cookie
        goto_and_wait(
            page,
            f"https://job3.ccb.com/cn/job/plan_index.html?planType=XY",
            timeout=30000, extra_sleep=3,
        )
        page.wait_for_timeout(2000)
    except Exception as e:
        logger.warning(f'建设银行 plan_index 打开失败: {e}')
        return jobs

    def fetch_page(plan_type: str, page_num: int) -> dict:
        url = (
            "/tran/WCCMainPlatV5"
            "?CCB_IBSVersion=V5&isAjaxRequest=true&SERVLET_NAME=WCCMainPlatV5"
            f"&TXCODE=NHR104&keyWord=&planType={plan_type}"
            f"&orgId=&planPostId=&planId="
            f"&PAGE_JUMP={page_num}&REC_IN_PAGE={PAGE_SIZE}"
            f"&_={int(time.time() * 1000)}"
        )
        try:
            text = page.evaluate(
                f"""async () => {{
                  const r = await fetch({json.dumps(url)}, {{
                    method: 'GET',
                    credentials: 'include',
                    headers: {{'X-Requested-With': 'XMLHttpRequest'}}
                  }});
                  return await r.text();
                }}"""
            )
        except Exception as exc:
            logger.warning(f'建设银行 NHR104 {plan_type} p{page_num} 失败: {exc}')
            return {}
        try:
            return json.loads((text or '').strip()) or {}
        except Exception as exc:
            logger.warning(f'建设银行 NHR104 解析失败 ({plan_type} p{page_num}): {exc}; raw[:200]={text[:200]!r}')
            return {}

    for plan_type, label in PLAN_TYPES:
        first = fetch_page(plan_type, 1)
        if first.get('SUCCESS') != 'true':
            logger.info(f'建设银行 {plan_type}: SUCCESS={first.get("SUCCESS")} busMsg={first.get("busMsg")}')
            continue
        total_rec = int(first.get('TOTAL_REC', 0) or 0)
        total_page = int(first.get('TOTAL_PAGE', 0) or 0)
        if total_rec == 0:
            logger.info(f'建设银行 {plan_type}: 上游空档 total=0')
            continue
        logger.info(f'建设银行 {plan_type}: total_rec={total_rec} total_page={total_page}')

        rows_iter = list(first.get('planPostList') or [])
        # 限制：cron 一次最多 max_pages 页，避免单类拉太慢
        cap = min(max_pages, total_page)
        for pn in range(2, cap + 1):
            page.wait_for_timeout(300)
            r = fetch_page(plan_type, pn)
            if r.get('SUCCESS') != 'true':
                logger.info(f'建设银行 {plan_type} p{pn} 异常停: SUCCESS={r.get("SUCCESS")}')
                break
            more = list(r.get('planPostList') or [])
            if not more:
                break
            rows_iter.extend(more)

        for item in rows_iter:
            title = norm_text(item.get('planPostName') or '')
            if not title:
                continue
            plan_id = norm_text(item.get('planId') or '')
            plan_post = norm_text(item.get('planPost') or '')
            # CCB API 返回 (planPost × org × secondOrg) 笛卡尔积：4491 = 5 岗位类型 ×
            # ~900 (分行 × 支行)。必须把 orgId + secondOrgId 全带进 URL，否则
            # md5 dedup 把全部多分行同岗 collapse 成 5 条。验证：单页 50 行用
            # (planPost, orgId, secondOrgId) tuple 是 50/50 unique。
            org_id = norm_text(item.get('orgId') or '')
            second_org_id = norm_text(item.get('secondOrgId') or '')
            url = (
                f"https://job3.ccb.com/cn/job/post_detail.html"
                f"?planId={plan_id}&planPost={plan_post}&planType={plan_type}"
                f"&orgId={org_id}&secondOrgId={second_org_id}"
            ) if plan_id and plan_post else target['url']
            location = norm_text(item.get('workPlace') or '') or '未知'
            org = norm_text(item.get('secondOName') or item.get('orgName') or '')
            publish_date = norm_text(item.get('postDate') or '')
            deadline = norm_text(item.get('endDate') or '')
            job = JobInfo(
                id='', company='建设银行', title=title, location=location,
                department=org, job_type=label, url=url,
                publish_date=publish_date, deadline=deadline,
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)

    if jobs:
        logger.info(f'建设银行: {len(jobs)} 条 (含校招/实习)')
    else:
        logger.info('建设银行当前未获取到岗位（上游可能空档或页面结构变化）')
    return jobs


def crawl_srcb(page, target) -> List[JobInfo]:
    """上海农商银行：通过浏览器访问并捕获 API 响应。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=3)
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f'上海农商银行页面打开失败: {e}')
        return jobs

    def harvest_from_captured() -> int:
        total_count = 0
        for rec in getattr(page, '_captured_json', []):
            if not any(k in rec.get('url', '') for k in ['job', 'position', 'campus', 'recruit', 'api']):
                continue
            payload = rec.get('data') or {}
            data = payload.get('data') or payload
            rows = data.get('list') or data.get('items') or data.get('records') or []
            if isinstance(rows, dict):
                rows = rows.get('list') or rows.get('items') or []
            if not rows:
                continue
            total_count = max(total_count, int(data.get('total') or payload.get('total') or len(rows)))
            for item in rows:
                title = norm_text(item.get('positionName') or item.get('jobName') or item.get('title') or '')
                if not title:
                    continue
                pid = item.get('positionId') or item.get('id') or item.get('jobId') or ''
                url = f"https://www.srcb.com/job?id={pid}" if pid else target['url']
                location = norm_text(item.get('workLocation') or item.get('city') or item.get('location') or '') or '未知'
                org = norm_text(item.get('department') or item.get('deptName') or '')
                publish_date = norm_text(item.get('publishTime') or item.get('createTime') or '')
                job = JobInfo(
                    id='', company='上海农商银行', title=title, location=location,
                    department=org, job_type='campus', url=url,
                    publish_date=publish_date,
                    description=norm_text(item.get('jobDescription') or item.get('description') or ''),
                    requirements=norm_text(item.get('jobRequirement') or item.get('requirement') or ''),
                )
                if job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
        return total_count

    total_count = harvest_from_captured()

    if jobs:
        logger.info(f'上海农商银行校招岗位: {len(jobs)} 条')
    else:
        logger.info('上海农商银行当前未获取到校招岗位（可能未开招）')

    return jobs


def crawl_generic_bank_site(page, target) -> List[JobInfo]:
    """国有行等通用兜底抓取：先抓响应 JSON，再兜底 DOM。"""
    company = target.get('name', '银行')
    return crawl_with_pagination(
        page, target, company, target.get('url', ''),
        selectors=['[class*="job"]', '[class*="position"]', '[class*="post"]', '[class*="list"]', 'tr', 'li', 'a[href*="job"]', 'a[href*="position"]'],
        scroll=True, timeout=45000, extra_sleep=3,
        response_keywords=['job', 'position', 'post', 'campus', 'recruit', 'api'],
        max_pages=int(target.get('max_pages') or 10)
    )


# 国家烟草专卖局 (www.tobacco.gov.cn / bj.tobacco.gov.cn) 系列 — Phase 5 故障
# 集中点 #2 修复（2026-05-09）。
# 8 家烟草子公司在 Playwright Chromium 走全部 ERR_EMPTY_RESPONSE/Timeout 90s，
# 但 curl/requests 直连 0.13-0.18s 200 OK。Server fingerprint 检测 headless
# Chromium 在 TCP 层就 drop。改用 requests + stdlib re 直接解 SSR HTML。
_TOBACCO_ARTICLE_PATH_RE = re.compile(r"/gjyc/zpxx/\d{6}/[a-f0-9]+\.shtml")
_TOBACCO_LIST_ANCHOR_RE = re.compile(
    r'<a[^>]+href="(?P<href>[^"]*?/gjyc/zpxx/\d{6}/[a-f0-9]+\.shtml)"[^>]*?(?:title="(?P<title>[^"]*)")?[^>]*>(?P<body>.*?)</a>',
    re.S,
)
_TOBACCO_TAG_STRIP_RE = re.compile(r"<[^>]+>")
_TOBACCO_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_TOBACCO_SOURCE_SPAN_RE = re.compile(r'<span class="source">(.*?)</span>', re.S)
_TOBACCO_DATE_RE = re.compile(r"时间：\s*([\d\-]{8,10})")


def _tobacco_strip_tags(html_fragment: str) -> str:
    return _TOBACCO_TAG_STRIP_RE.sub("", html_fragment).strip()


def crawl_tobacco_gov_cn(page, target) -> List[JobInfo]:
    """国家烟草专卖局 SSR HTML 抓取（绕开 Chromium fingerprint 拦截）。"""
    url = (target.get("url") or "").strip()
    company = (target.get("name") or "").strip() or "国家烟草专卖局"
    job_type = (target.get("type") or "campus").strip()
    if not url:
        return []
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    try:
        resp = requests.get(url, headers=headers, timeout=12, proxies=REQUEST_PROXIES or None, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
        html = resp.text
    except Exception:
        # 真死站点（bj.tobacco.gov.cn 等）— re-raise 让 company_crawl_log 12s
        # fail-fast 而不是 90s Playwright timeout
        raise

    base = "http://www.tobacco.gov.cn"
    jobs: List[JobInfo] = []

    if _TOBACCO_ARTICLE_PATH_RE.search(url):
        # 单 article 页 — 1 JobInfo
        h1 = _TOBACCO_H1_RE.search(html)
        if not h1:
            return []
        title = _tobacco_strip_tags(h1.group(1))
        if not title:
            return []
        src_match = _TOBACCO_SOURCE_SPAN_RE.search(html)
        department = _tobacco_strip_tags(src_match.group(1)) if src_match else company
        date_match = _TOBACCO_DATE_RE.search(html)
        publish_date = date_match.group(1) if date_match else ''
        return [JobInfo(
            id='', company=company, title=title, location='未知', department=department,
            job_type=job_type, url=url, publish_date=publish_date,
        )]

    # list 页 — 20 JobInfo
    seen: Set[str] = set()
    for m in _TOBACCO_LIST_ANCHOR_RE.finditer(html):
        href = m.group("href")
        title = (m.group("title") or "").strip() or _tobacco_strip_tags(m.group("body") or "")
        if not href or not title:
            continue
        full_url = href if href.startswith("http") else (base + href)
        if full_url in seen:
            continue
        seen.add(full_url)
        jobs.append(JobInfo(
            id='', company=company, title=title, location='未知', department=company,
            job_type=job_type, url=full_url,
        ))
    logger.info(f'国烟[{company}]: {len(jobs)} 条')
    return jobs


# 51job 校招页 (campus.51job.com/<slug>) — Phase 5 故障集中点 #3 修复
# (2026-05-09)。亿滋（campus.51job.com/2026mdlz）等校招页面是 SPA，岗位
# 数据来自静态 JS 文件 js/data.js（var jobData=[...])，DOM selector 抓
# 不到。直接 requests 拉 data.js 用 regex 解。
_DATAJS_DEPT_BLOCK_RE = re.compile(
    r"\{\s*(?:img\s*:[^,]*,)?\s*name\s*:\s*\"([^\"]+)\"(.*?)\}\s*,?\s*(?=\{|\];)",
    re.DOTALL,
)
_DATAJS_LOCATION_RE = re.compile(r"location\s*:\s*\"([^\"]*)\"")
_DATAJS_APPLY_ITEM_RE = re.compile(
    r"\{\s*(?:title\s*:\s*['\"]([^'\"]*)['\"]\s*,?\s*)?"
    r"(?:content\s*:\s*['\"](?:[^'\"\\]|\\.)*['\"]\s*,?\s*)?"
    r"city\s*:\s*\"([^\"]*)\"\s*,\s*"
    r"url\s*:\s*\"([^\"]*apply\.aspx[^\"]*)\"",
    re.DOTALL,
)
_DATAJS_FALLBACK_APPLY_RE = re.compile(
    r"\"(https?://[^\"]*apply\.aspx\?[^\"]*jobid=(\d+)[^\"]*)\"",
    re.IGNORECASE,
)


def _51job_campus_root(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    while parts and "." in parts[-1]:
        parts.pop()
    new_path = "/" + "/".join(parts) if parts else "/"
    return f"{parsed.scheme}://{parsed.netloc}{new_path}"


def _51job_extract_jobid(url: str) -> str:
    try:
        q = parse_qs(urlparse(url).query)
        return (q.get("jobid") or q.get("jobId") or [""])[0]
    except Exception:
        return ""


def crawl_51job_campus_data_js(page, target) -> List[JobInfo]:
    """51job 校招专属页（campus.51job.com/<slug>）：抓 js/data.js + 解析。"""
    company = target.get("name", "")
    target_url = target.get("url", "")
    job_type = target.get("type", "campus")
    if not target_url:
        return []
    base = _51job_campus_root(target_url)
    if not base.endswith("/"):
        base += "/"
    candidates = [base + "js/data.js", base + "data.js", base + "js/jobData.js"]

    text = ""
    for url in candidates:
        try:
            resp = requests.get(url, headers={"User-Agent": UA, "Referer": base}, timeout=20)
            if resp.status_code == 200 and ("jobData" in resp.text or "applyLinks" in resp.text or "apply.aspx" in resp.text):
                text = resp.text
                logger.info(f"51job-campus[{company}]: data.js hit at {url} ({len(text)} bytes)")
                break
        except Exception as exc:
            logger.debug(f"51job-campus[{company}]: probe {url} failed: {exc}")

    if not text:
        try:
            resp = requests.get(base + "page.html", headers={"User-Agent": UA}, timeout=20)
            if resp.status_code == 200 and "apply.aspx" in resp.text:
                text = resp.text
        except Exception:
            pass

    if not text:
        logger.warning(f"51job-campus[{company}]: no data.js found under {base}")
        return []

    jobs: List[JobInfo] = []
    seen_ids: Set[str] = set()

    # 结构化 path：按 department 块走
    for dept_match in _DATAJS_DEPT_BLOCK_RE.finditer(text):
        dept_name = dept_match.group(1).strip()
        body = dept_match.group(2)
        loc_match = _DATAJS_LOCATION_RE.search(body)
        dept_location = loc_match.group(1).strip() if loc_match else ""
        for apply_match in _DATAJS_APPLY_ITEM_RE.finditer(body):
            sub_title = (apply_match.group(1) or "").strip()
            city = (apply_match.group(2) or "").strip()
            url = (apply_match.group(3) or "").strip()
            jobid = _51job_extract_jobid(url)
            if not jobid or jobid in seen_ids:
                continue
            seen_ids.add(jobid)
            title_parts = [dept_name]
            if sub_title:
                title_parts.append(sub_title)
            if city:
                title_parts.append(city)
            jobs.append(JobInfo(
                id=jobid, company=company, title=" - ".join(title_parts),
                location=city or dept_location or "未知",
                department=dept_name, job_type=job_type, url=url,
            ))

    # Fallback: 任何 apply.aspx 链接，用近邻 city/name 上下文兜底 title
    for fb in _DATAJS_FALLBACK_APPLY_RE.finditer(text):
        url = fb.group(1)
        jobid = fb.group(2)
        if jobid in seen_ids:
            continue
        seen_ids.add(jobid)
        start = max(0, fb.start() - 240)
        ctx = text[start:fb.start()]
        city_match = re.findall(r"city\s*:\s*\"([^\"]+)\"", ctx)
        name_match = re.findall(r"name\s*:\s*\"([^\"]+)\"", text[:fb.start()])
        city = city_match[-1].strip() if city_match else ""
        dept = name_match[-1].strip() if name_match else company
        title = " - ".join(p for p in [dept, city] if p) or f"{company} 岗位 {jobid}"
        jobs.append(JobInfo(
            id=jobid, company=company, title=title,
            location=city or "未知", department=dept, job_type=job_type, url=url,
        ))

    logger.info(f"51job-campus[{company}]: {len(jobs)} 条")
    return jobs


SITE_MAP = {
    'bytedance': crawl_bytedance,
    'meituan': crawl_meituan,
    'ctrip': crawl_ctrip,
    'xiaohongshu': crawl_xiaohongshu,
    'alibaba': crawl_alibaba,
    'talent-holding': crawl_alibaba,
    'baidu': crawl_baidu,
    'campus.jd': crawl_jd,
    'bilibili': crawl_bilibili,
    'huawei': crawl_huawei,
    'didiglobal': crawl_didi,
    'pingan': crawl_pingan,
    'pddglobalhr': crawl_pdd,
    'cmbchina': crawl_cmb,
    'job.spdb.com.cn': crawl_spdb,
    'zhaopin.nbcb.com.cn': crawl_nbcb,
    'hr.jsbchina.cn': crawl_jsbc,
    'zhaopin.njcb.com.cn': crawl_njcb,
    'job.njcb.com.cn': crawl_njcb,
    'zhaopin.suzhoubank.com': crawl_suzhou_bank,
    'suzhoubank.zhiye.com': crawl_suzhou_bank,
    'bosc.zhiye.com': crawl_bosc,
    'myjob.hzbank.com.cn': crawl_hzbank,
    'feishu': crawl_feishu_nio,
    'nio.jobs': crawl_feishu_nio,
    'tencent': crawl_tencent,
    'qq.com': crawl_tencent,
    'campus.163.com': crawl_163,
    'leihuo.163.com': crawl_leihuo,
    'hr.360.cn': crawl_360_campus,
    '360.cn/campus': crawl_360_campus,
    '360campus.zhiye.com': crawl_360_campus,
    'hupu.zhiye.com': crawl_zhiye_campus,
    'cebbank.zhiye.com': crawl_cebbank,
    'shrcb.zhiye.com': crawl_zhiye_campus,
    # 北森老模板 zhiye 站点：DOM 表格 / UL 渲染（不返回 JSON API）
    'cssc.zhiye.com': crawl_zhiye_table_campus,
    # CNNC 三组域名共用同一后台（TenantId=605932），但 hr.cnnc.com.cn 走 WAF 412
    # challenge，cnnc.zhiye.com 是 CMS landing page 没 jobadid DOM。统一改走
    # cnnc.m.zhiye.com 的 mobile JSON API（curl/requests + iPhone UA 通），
    # 按 c2 参数 / 公司名查表区分子公司。详见 crawl_cnnc_mobile_api。
    'cnnc.m.zhiye.com': crawl_cnnc_mobile_api,
    'cnnc.zhiye.com': crawl_cnnc_mobile_api,
    'hr.cnnc.com.cn': crawl_cnnc_mobile_api,
    'job.bankcomm.com': crawl_generic_bank_site,
    'job.icbc.com.cn': crawl_icbc,
    'career.abchina.com': crawl_generic_bank_site,
    'campus.bankofchina.com': crawl_boc,
    'campus.chinahr.com/pages/boc-2026-Spring': crawl_boc,
    'campus.chinahr.com/pages/boc-2026-spring': crawl_boc,
    'www.boc.cn': crawl_boc,
    'job.ccb.com': crawl_generic_bank_site,
    'job2.ccb.com': crawl_generic_bank_site,
    'psbc.zhaopin.com': crawl_psbc,
    'www.psbc.com': crawl_psbc,
    'cmbnt.cmbchina.com': crawl_generic_bank_site,
    'www.ccbft.com.cn': crawl_generic_bank_site,
    'www.srcb.com': crawl_srcb,
    'srcb.com': crawl_srcb,
    'talent.antgroup.com': crawl_antgroup,
    'campus.kuaishou.cn': crawl_kuaishou,
    'app.mokahr.com/campus_apply/zhihu': crawl_zhihu_campus,
    'app.mokahr.com/campus_apply/sohu': crawl_zhihu_campus,
    'app.mokahr.com/campus_apply': crawl_zhihu_campus,
    'app.mokahr.com/campus-recruitment': crawl_zhihu_campus,
    'app.mokahr.com/campus-recruitment/wps': crawl_zhihu_campus,
    'app.mokahr.com/campus-recruitment/sina': crawl_zhihu_campus,
    'hr.sohu.com': crawl_zhihu_campus,
    'job.weibo.com': crawl_weibo_campus,
    'careers.ke.com': crawl_beike_campus,
    'campus.ke.com': crawl_beike_campus,
    'campus.ly.com': crawl_tongcheng_campus,
    'mhr.ly.com': crawl_tongcheng_campus,
    'join.iqiyi.com': crawl_aiqiyi_campus,
    'careers.iqiyi.com': crawl_aiqiyi_campus,
    'careers.hellobike.com': crawl_tongcheng_campus,
    'hire.freshippo.com': crawl_alibaba,
    'lilithgames.jobs.feishu.cn': crawl_feishu_nio,
    'soulapp.jobs.feishu.cn': crawl_feishu_nio,
    'zhipin.com/campus': crawl_boss_campus,
    'campus.dewu.com': crawl_dewu,
    'jobs.mihoyo.com': crawl_mihoyo,
    'careers.shein.com': crawl_shein,
    'career.cmbc.com.cn': crawl_cmbc,
    'job.cib.com.cn': crawl_cib,
    'job.citicbank.com': crawl_citic,
    'hxb.hotjob.cn': crawl_hxb,
    'wecruit.hotjob.cn': crawl_hxb,
    'zp.czbank.com.cn': crawl_czbank,
    # Phase 5 集中问题修复 (2026-05-09)：
    'tobacco.gov.cn': crawl_tobacco_gov_cn,        # 国家烟草专卖局 SSR HTML（绕开 Chromium 拦截）
    'campus.51job.com': crawl_51job_campus_data_js,  # 51job 校招页 data.js 解析（亿滋 + 类似 51job 模板）
}


class JobCrawler:
    def __init__(self, config_path: Path = None, include_sites: Optional[List[str]] = None,
                 exclude_sites: Optional[List[str]] = None, max_pages: Optional[int] = None,
                 per_site_max_pages: Optional[Dict[str, int]] = None):
        self.base = Path(__file__).parent.parent
        cfg_path = Path(config_path) if config_path else (self.base / 'config' / 'targets.yaml')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        settings = raw_config.get('settings') or {'output_dir': 'data', 'snapshot_dir': 'data/snapshots'}
        targets = raw_config.get('targets') or raw_config.get('sites') or []
        self.config = {'settings': settings, 'targets': targets}

        self.include_sites = {s.strip().lower() for s in (include_sites or []) if s.strip()}
        self.exclude_sites = {s.strip().lower() for s in (exclude_sites or []) if s.strip()}
        self.max_pages = max_pages
        self.per_site_max_pages = {k.strip().lower(): int(v) for k, v in (per_site_max_pages or {}).items()}

        self.output_dir = self.base / self.config['settings'].get('output_dir', 'data')
        self.snapshot_dir = self.base / self.config['settings'].get('snapshot_dir', 'data/snapshots')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_dir / 'jobs.csv'
        self.existing_ids = self._load_existing_ids()
        self.stats = {'total_crawled': 0, 'new_jobs': 0, 'updated_jobs': 0,
                      'failed_sites': [], 'success_sites': [], 'errors': [], 'blockers': []}

    def _load_existing_ids(self) -> set:
        if not self.csv_path.exists():
            return set()
        ids = set()
        with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row_id = row.get('id') or row.get('\ufeffid')
                if row_id:
                    ids.add(row_id)
        logger.info(f"已有 {len(ids)} 条记录")
        return ids

    def crawl_all(self) -> List[JobInfo]:
        from playwright.sync_api import sync_playwright
        all_jobs = []

        with sync_playwright() as p:
            browser = make_browser(p)

            for target in self.config['targets']:
                name = str(target['name'])
                url = str(target['url'])
                lname = name.strip().lower()

                if self.include_sites and lname not in self.include_sites:
                    continue
                if lname in self.exclude_sites:
                    logger.info(f"⏭ 跳过站点: {name}")
                    continue

                logger.info(f"\n{'='*50}")
                logger.info(f"🕷 爬取: {name}")

                context, page = new_page(browser)

                try:
                    fn = None
                    for key, func in SITE_MAP.items():
                        if key in url:
                            fn = func
                            break

                    if fn is None:
                        logger.warning(f"⚠️ 未知站点: {name}")
                        self.stats['failed_sites'].append(name)
                        context.close()
                        continue

                    page_limit = self.per_site_max_pages.get(lname, self.max_pages)
                    if page_limit:
                        target = dict(target)
                        target['max_pages'] = int(page_limit)
                    jobs = fn(page, target)

                    if jobs:
                        all_jobs.extend(jobs)
                        logger.info(f"✅ {name}: {len(jobs)} 个岗位")
                        self.stats['success_sites'].append(f"{name}({len(jobs)})")
                    else:
                        logger.warning(f"⚠️ {name}: 未获取到岗位")
                        self.stats['failed_sites'].append(name)
                        self.stats['blockers'].append(f"{name}: 页面结构变化或强反爬，当前未稳定拿到岗位列表")

                except Exception as e:
                    logger.error(f"❌ {name}: {e}")
                    self.stats['errors'].append({'site': name, 'error': str(e)})
                    self.stats['failed_sites'].append(name)
                    self.stats['blockers'].append(f"{name}: {str(e)}")
                finally:
                    context.close()

            browser.close()

        self.stats['total_crawled'] = len(all_jobs)
        return all_jobs

    def save_to_csv(self, jobs: List[JobInfo]) -> int:
        new_count = 0
        write_header = not self.csv_path.exists()

        with open(self.csv_path, 'a', encoding='utf-8', newline='') as f:
            fields = ['id', 'company', 'title', 'location', 'department',
                      'job_type', 'url', 'publish_date', 'deadline',
                      'description', 'requirements', 'crawled_at']
            writer = csv.DictWriter(f, fieldnames=fields)
            if write_header:
                writer.writeheader()

            for job in jobs:
                if job.id not in self.existing_ids:
                    writer.writerow(asdict(job))
                    self.existing_ids.add(job.id)
                    new_count += 1
                    self.stats['new_jobs'] += 1
                else:
                    self.stats['updated_jobs'] += 1

        logger.info(f"写入 {new_count} 条新记录")
        return new_count

    def save_snapshot(self, jobs: List[JobInfo]):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = self.snapshot_dir / f'snapshot_{ts}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': datetime.now().isoformat(),
                       'total': len(jobs),
                       'jobs': [asdict(j) for j in jobs]}, f,
                      ensure_ascii=False, indent=2)
        return path

    def print_report(self):
        s = self.stats
        print(f"\n{'='*55}")
        print(f"📊 爬取报告  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*55}")
        print(f"  总爬取:  {s['total_crawled']}")
        print(f"  新增:    {s['new_jobs']}")
        print(f"  已存在:  {s['updated_jobs']}")
        print(f"\n✅ 成功站点 ({len(s['success_sites'])}):")
        for ss in s['success_sites']:
            print(f"  • {ss}")
        print(f"\n❌ 失败站点 ({len(s['failed_sites'])}):")
        for fs in s['failed_sites']:
            print(f"  • {fs}")
        if s['errors']:
            print(f"\n⚠️ 错误:")
            for e in s['errors']:
                print(f"  • {e['site']}: {e['error'][:120]}")
        if s['blockers']:
            print(f"\n🧱 Blockers:")
            for b in s['blockers']:
                print(f"  • {b}")
        print(f"\n📁 数据文件: {self.csv_path}")
        print(f"{'='*55}\n")
        return s


def parse_args():
    parser = argparse.ArgumentParser(description='Job Crawler')
    parser.add_argument('--config', default='', help='配置文件路径，默认 config/targets.yaml')
    parser.add_argument('--include-sites', default='', help='逗号分隔，仅运行这些站点名称')
    parser.add_argument('--exclude-sites', default='', help='逗号分隔，跳过这些站点名称')
    parser.add_argument('--max-pages', type=int, default=None, help='全局最大分页数')
    parser.add_argument('--site-max-pages', action='append', default=[], help='单站点分页限制，格式: 站点名=页数')
    return parser.parse_args()


def main():
    args = parse_args()
    include_sites = [s.strip() for s in args.include_sites.split(',') if s.strip()]
    exclude_sites = [s.strip() for s in args.exclude_sites.split(',') if s.strip()]
    per_site_max_pages = {}
    for item in args.site_max_pages:
        if '=' not in item:
            continue
        k, v = item.split('=', 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            continue
        try:
            per_site_max_pages[k] = int(v)
        except ValueError:
            logger.warning(f'忽略非法 --site-max-pages 参数: {item}')

    crawler = JobCrawler(
        config_path=args.config or None,
        include_sites=include_sites,
        exclude_sites=exclude_sites,
        max_pages=args.max_pages,
        per_site_max_pages=per_site_max_pages,
    )
    jobs = crawler.crawl_all()
    if jobs:
        crawler.save_to_csv(jobs)
        crawler.save_snapshot(jobs)
    crawler.print_report()


if __name__ == '__main__':
    main()
