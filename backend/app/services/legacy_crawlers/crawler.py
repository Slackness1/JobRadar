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

    page_limit = max_pages or int(target.get('max_pages') or MAX_PAGES)

    for page_no in range(1, page_limit + 1):
        logger.info(f'{company} - 第 {page_no}/{page_limit} 页')
        goto_and_wait(page, current_url, timeout=timeout, extra_sleep=extra_sleep)
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

        next_clicked = click_next_page(page)
        if next_clicked:
            time.sleep(2)
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
    jobs = crawl_with_pagination(
        page, target, '字节跳动', 'https://jobs.bytedance.com',
        selectors=['.position-list-item', '[class*="jobItem"]', '[class*="position-item"]', 'a[href*="/position/"]'],
        scroll=False, timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'api']
    )
    return jobs


def crawl_tencent(page, target) -> List[JobInfo]:
    jobs = []
    seen = set()
    for idx in range(1, MAX_PAGES + 1):
        try:
            resp = requests.get(
                'https://careers.tencent.com/tencentcareer/api/post/Query',
                params={'pageIndex': idx, 'pageSize': 100, 'language': 'zh-cn', 'area': 'cn'},
                headers={'User-Agent': UA, 'Accept': 'application/json', 'Referer': 'https://careers.tencent.com/'},
                proxies=REQUEST_PROXIES, timeout=30
            )
            data = resp.json()
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
    return crawl_with_pagination(
        page, target, '美团', 'https://zhaopin.meituan.com',
        selectors=['[class*="position-item"]', '[class*="job-item"]', '.job-list-item', 'a[href*="job"]'],
        scroll=True, timeout=30000, extra_sleep=2
    )


def crawl_ctrip(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '携程', 'https://job.ctrip.com',
        selectors=['[class*="position"]', '[class*="job"]', 'tr[class*="row"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=2
    )


def crawl_xiaohongshu(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '小红书', 'https://job.xiaohongshu.com',
        selectors=['[class*="position-item"]', '[class*="job-item"]', 'a[href*="position"]'],
        scroll=True, timeout=30000, extra_sleep=2,
        response_keywords=['job', 'position', 'api']
    )


def crawl_alibaba(page, target) -> List[JobInfo]:
    base = 'https://talent.alibaba.com' if 'talent.alibaba.com' in target['url'] else 'https://talent-holding.alibaba.com'
    return crawl_with_pagination(
        page, target, '阿里巴巴', base,
        selectors=['[class*="position-item"]', '[class*="job-card"]', '[class*="list-item"]', 'a[href*="position"]'],
        timeout=30000, extra_sleep=3,
        response_keywords=['position', 'job', 'api']
    )


def crawl_baidu(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    page.goto(target['url'], wait_until='domcontentloaded', timeout=30000)
    selectors = ['[class*="post-item__"]', '[class^="post-item__"]', '[class*=" post-item__"]']
    rows: List[Dict[str, Any]] = []
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=5000)
            rows = page.eval_on_selector_all(
                selector,
                """
                (nodes) => nodes.map((node) => {
                  const titleNode = node.querySelector('[class*="post-title-content__"] span');
                  const metaNodes = Array.from(node.querySelectorAll('[class*="post-subtitle-item__"]'));
                  const detailNode = node.querySelector('[class*="post-detail-text__"], [class*="post-title-content__"]');
                  return {
                    title: titleNode ? titleNode.textContent : '',
                    meta: metaNodes.map((x) => x.textContent || ''),
                    href: detailNode ? (detailNode.getAttribute('href') || '') : ''
                  };
                })
                """
            )
            if rows:
                break
        except Exception:
            continue
    for row in rows:
        title = norm_text(row.get('title'))
        meta = [norm_text(x) for x in (row.get('meta') or [])]
        location = meta[0] if len(meta) > 0 else '未知'
        job_tag = meta[2] if len(meta) > 2 else ''
        href = norm_text(row.get('href'))
        job = JobInfo(
            id='', company='百度', title=title, location=location, department=job_tag,
            job_type=target.get('type', 'campus'), url=abs_url('https://talent.baidu.com', href) or target['url']
        )
        if title and job.id not in seen:
            seen.add(job.id)
            jobs.append(job)
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
    return crawl_with_pagination(
        page, target, '滴滴', 'https://campus.didiglobal.com',
        selectors=['[class*="job-item"]', '[class*="position-item"]', 'li[class*="item"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'api']
    )


def crawl_pingan(page, target) -> List[JobInfo]:
    """平安银行：仅保留银行相关校招岗位，过滤集团泛岗位与社招。"""
    batch = crawl_with_pagination(
        page, target, '平安银行', 'https://campus.pingan.com',
        selectors=['[class*="job-item"]', '[class*="position-item"]', '[class*="card"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'api']
    )

    social_keywords = ['社招', '社会招聘', '社会人才', '成熟人才', '高层次人才']
    bank_keywords = ['银行', '平安银行']
    cleaned: List[JobInfo] = []
    seen: Set[str] = set()
    for job in batch:
        title = norm_text(job.title)
        desc = norm_text(job.description or '')
        url = norm_text(job.url)
        if not url:
            continue
        text = f"{title} {desc}"
        if any(k in text for k in social_keywords):
            continue
        if 'social' in url.lower() or 'socialjob' in url.lower():
            continue
        if not any(k in text for k in bank_keywords):
            continue
        if job.id in seen:
            continue
        seen.add(job.id)
        cleaned.append(job)

    return cleaned


def crawl_pdd(page, target) -> List[JobInfo]:
    return crawl_with_pagination(
        page, target, '拼多多', 'https://careers.pddglobalhr.com',
        selectors=['[class*="job-item"]', '[class*="position"]', '[class*="card"]', 'a[href*="job"]'],
        timeout=30000, extra_sleep=3,
        response_keywords=['position', 'job', 'api']
    )


def crawl_cmb(page, target) -> List[JobInfo]:
    jobs = crawl_with_pagination(
        page, target, '招商银行', 'https://career.cmbchina.com',
        selectors=['[class*="position"]', '[class*="job"]', 'table tbody tr', 'li[class*="item"]'],
        timeout=30000, extra_sleep=2,
        response_keywords=['position', 'job', 'api']
    )
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


def crawl_antgroup(page, target) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    headers = {
        'User-Agent': UA,
        'Accept': 'application/json',
        'Referer': 'https://talent.antgroup.com/',
        'Content-Type': 'application/json;charset=UTF-8',
        'front-user-id': f'{hashlib.md5(str(time.time()).encode()).hexdigest()}30',
    }
    ctoken = f'bigfish_ctoken_{hashlib.md5(str(time.time()).encode()).hexdigest()[:10]}'
    current_page = 1
    page_size = 10
    total_pages = 1
    while current_page <= total_pages and current_page <= MAX_PAGES * 2:
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
                'recruitType': [],
                'batchIds': [],
            },
        )
        data = resp.json()
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
                deadline = f"{norm_text(grad.get('from'))} ~ {norm_text(grad.get('to'))}".strip(' ~')
            job = JobInfo(
                id='', company='蚂蚁集团', title=title,
                location=norm_text('/'.join(item.get('workLocations') or [])) or '未知',
                department=norm_text('/'.join(item.get('categories') or [])) or norm_text(item.get('category') or ''),
                job_type=target.get('type', 'campus'), url=url,
                publish_date=norm_text(item.get('publishTime') or ''),
                deadline=deadline,
                description=norm_text(item.get('requirement') or ''),
                requirements=norm_text(item.get('requirement') or ''),
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'蚂蚁集团 API 第 {current_page} 页: {page_added} 条 / total={total_count}')
        if not rows:
            break
        current_page += 1
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
    """浙商银行：仅抓校园招聘（不混入社会招聘）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    current_page = 1
    page_size = 6
    total_pages = 1
    max_pages = int(target.get('max_pages') or MAX_PAGES)
    headers = {
        'User-Agent': UA,
        'Referer': 'https://zp.czbank.com.cn/zpweb/planController/gotoIndex.mvc?pageType=2',
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest',
    }
    while current_page <= total_pages and current_page <= max_pages:
        start = (current_page - 1) * page_size
        end = current_page * page_size
        resp = requests.get(
            'https://zp.czbank.com.cn/zpweb/planController/getPost.mvc?pageType=2',
            headers=headers, proxies=REQUEST_PROXIES, timeout=30,
            params={'start': start, 'end': end, 'depid': '', 'educ': '', 'orgId': '', 'postName': '', 'workYear': '', 'location': '', 'zpType': '1'},
        )
        body = (resp.json() or {}).get('body') or []
        payload = body[0] if body else {}
        rows = payload.get('dataList') or []
        total_pages = int(payload.get('postTotalPage') or 1)
        page_added = 0
        for item in rows:
            title = norm_text(item.get('name'))
            if not title:
                continue
            pid = item.get('postId')
            desc = '\n'.join(x for x in [norm_text(item.get('baseCond')), norm_text(item.get('postCond'))] if x)
            req = ' / '.join(x for x in [norm_text(item.get('eduCond')), norm_text(item.get('majorCond')), norm_text(item.get('workYear'))] if x)
            job = JobInfo(
                id='', company='浙商银行', title=title,
                location=norm_text(item.get('locationName') or item.get('location')) or '未知',
                department=norm_text(item.get('needDept') or item.get('needOrg') or item.get('mgrOrg') or ''),
                job_type='campus',
                url=f'https://zp.czbank.com.cn/zpweb/zpPostController/jobDetailPage.mvc?postId={pid}' if pid else target['url'],
                publish_date=norm_text(item.get('createTime') or item.get('zpStartDate') or ''),
                deadline=norm_text(item.get('zpEndDate') or item.get('applyEndDate') or ''),
                description=desc,
                requirements=req,
            )
            if job.id not in seen:
                seen.add(job.id)
                jobs.append(job)
                page_added += 1
        logger.info(f'浙商银行（校招）API 第 {current_page} 页: {page_added} 条 / total_pages={total_pages}')
        if not rows:
            break
        current_page += 1
    if not jobs:
        logger.info('浙商银行当前未获取到校招岗位（可能未开招）')
    return jobs


def crawl_zhiye_campus(page, target) -> List[JobInfo]:
    """通用 zhiye 校招接口抓取（如 虎扑/光大）。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()
    parsed = urlparse(target['url'])
    base = f"{parsed.scheme}://{parsed.netloc}"
    max_pages = int(target.get('max_pages') or MAX_PAGES)

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
    """工商银行：通过浏览器访问并捕获 API 响应。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=2)
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f'工商银行页面打开失败: {e}')
        return jobs

    def harvest_from_captured() -> int:
        total_count = 0
        for rec in getattr(page, '_captured_json', []):
            if not any(k in rec.get('url', '') for k in ['job', 'position', 'campus', 'recruit', 'api']):
                continue
            payload = rec.get('data') or {}
            data = payload.get('data') or payload
            rows = data.get('list') or data.get('items') or data.get('records') or data.get('dataList') or []
            if isinstance(rows, dict):
                rows = rows.get('list') or rows.get('items') or rows.get('records') or []
            if not rows:
                continue
            total_count = max(total_count, int(data.get('total') or payload.get('total') or len(rows)))
            for item in rows:
                title = norm_text(item.get('positionName') or item.get('jobName') or item.get('title') or item.get('name') or '')
                if not title:
                    continue
                pid = item.get('positionId') or item.get('id') or item.get('jobId') or ''
                url = f"https://job.icbc.com.cn/campus/detail?id={pid}" if pid else target['url']
                location = norm_text(item.get('workLocation') or item.get('city') or item.get('location') or '') or '未知'
                org = norm_text(item.get('department') or item.get('deptName') or '')
                publish_date = norm_text(item.get('publishTime') or item.get('createTime') or '')
                deadline = norm_text(item.get('deadline') or item.get('endTime') or '')
                job = JobInfo(
                    id='', company='工商银行', title=title, location=location,
                    department=org, job_type='campus', url=url,
                    publish_date=publish_date, deadline=deadline,
                    description=norm_text(item.get('jobDescription') or item.get('description') or ''),
                    requirements=norm_text(item.get('jobRequirement') or item.get('requirement') or ''),
                )
                if job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
        return total_count

    total_count = harvest_from_captured()

    if jobs:
        logger.info(f'工商银行校招岗位: {len(jobs)} 条')
    else:
        logger.info('工商银行当前未获取到校招岗位（可能未开招或页面结构变化）')

    return jobs


def crawl_psbc(page, target) -> List[JobInfo]:
    """邮储银行：智联招聘专题页，通过浏览器捕获 API 响应。"""
    jobs: List[JobInfo] = []
    seen: Set[str] = set()

    try:
        goto_and_wait(page, target['url'], timeout=30000, extra_sleep=3)
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f'邮储银行页面打开失败: {e}')
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
                title = norm_text(item.get('jobName') or item.get('positionName') or item.get('title') or '')
                if not title:
                    continue
                pid = item.get('jobId') or item.get('positionId') or item.get('id') or ''
                url = f"https://psbc.zhaopin.com/job?id={pid}" if pid else target['url']
                location = norm_text(item.get('cityName') or item.get('city') or item.get('workLocation') or '') or '未知'
                org = norm_text(item.get('department') or item.get('deptName') or '')
                publish_date = norm_text(item.get('publishTime') or item.get('createTime') or '')
                job = JobInfo(
                    id='', company='邮储银行', title=title, location=location,
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
        logger.info(f'邮储银行校招岗位: {len(jobs)} 条')
    else:
        logger.info('邮储银行当前未获取到校招岗位（可能未开招或需要人工验证）')

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
