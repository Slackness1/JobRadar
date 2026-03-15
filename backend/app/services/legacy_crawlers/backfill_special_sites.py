#!/usr/bin/env python3
import csv, json, hashlib, re, time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from playwright.sync_api import sync_playwright

BASE = Path('/home/ubuntu/workspace/job-crawler')
CSV_PATH = BASE / 'data' / 'jobs.csv'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
PROXY = {'server': 'http://127.0.0.1:7890'}

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
    crawled_at: str = ''
    def __post_init__(self):
        if not self.crawled_at:
            self.crawled_at = datetime.now().isoformat()
        if not self.id:
            self.id = hashlib.md5(f'{self.company}:{self.title}:{self.url}'.encode()).hexdigest()[:12]


def norm(x):
    if x is None:
        return ''
    return re.sub(r'\s+', ' ', str(x)).strip()


def load_existing_ids():
    ids = set()
    if not CSV_PATH.exists():
        return ids
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            ids.add(row.get('id') or row.get('\ufeffid'))
    return ids


def append_jobs(jobs: List[JobInfo]):
    existing = load_existing_ids()
    new = 0
    write_header = not CSV_PATH.exists()
    with open(CSV_PATH, 'a', encoding='utf-8', newline='') as f:
        fields = ['id', 'company', 'title', 'location', 'department', 'job_type', 'url', 'publish_date', 'deadline', 'description', 'requirements', 'crawled_at']
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        for job in jobs:
            if job.id not in existing:
                w.writerow(asdict(job))
                existing.add(job.id)
                new += 1
    return new


def capture_api_template(context, url: str, keyword='/api/v1/search/job/posts', wait_s=10):
    page = context.new_page()
    page.set_default_timeout(30000)
    holder = {}
    def on_req(req):
        if keyword in req.url:
            holder['headers'] = req.headers
            holder['url'] = req.url
            holder['post'] = req.post_data
    page.on('request', on_req)
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    time.sleep(wait_s)
    body_text = page.locator('body').inner_text()[:500]
    page.close()
    if not holder:
        raise RuntimeError(f'未捕获到岗位 API 请求; page={url}; body={body_text}')
    headers = dict(holder['headers'])
    for k in list(headers):
        if k.startswith(':'):
            headers.pop(k, None)
    return headers, holder['url'], json.loads(holder['post'])


def paged_fetch(context, first_url: str, headers: Dict, payload: Dict):
    jobs = []
    offset = int(payload.get('offset', 0) or 0)
    limit = int(payload.get('limit', 10) or 10)
    total = None
    while True:
        url = re.sub(r'offset=\d+', f'offset={offset}', first_url)
        body = dict(payload)
        body['offset'] = offset
        resp = context.request.post(url, headers=headers, data=json.dumps(body))
        if resp.status != 200:
            raise RuntimeError(f'API status={resp.status} offset={offset}')
        data = resp.json().get('data') or {}
        rows = data.get('job_post_list') or []
        total = int(data.get('count') or data.get('total') or total or 0)
        if not rows:
            break
        jobs.extend(rows)
        offset += limit
        if total and offset >= total:
            break
    return jobs, total or len(jobs)


def fetch_xiaomi(context):
    portals = [
        ('https://xiaomi.jobs.f.mioffice.cn/campus/position/list', 'https://xiaomi.jobs.f.mioffice.cn/campus'),
        ('https://xiaomi.jobs.f.mioffice.cn/internship/position/list', 'https://xiaomi.jobs.f.mioffice.cn/internship'),
        ('https://xiaomi.jobs.f.mioffice.cn/newretailing/position/list', 'https://xiaomi.jobs.f.mioffice.cn/newretailing'),
    ]
    out = []
    seen = set()
    for list_url, detail_base in portals:
        headers, first_url, payload = capture_api_template(context, list_url)
        rows, _ = paged_fetch(context, first_url, headers, payload)
        for item in rows:
            pid = str(item.get('id') or '')
            title = norm(item.get('title'))
            if not title:
                continue
            city = ((item.get('city_info') or {}).get('name')) or ''
            department = norm(((item.get('job_function') or {}).get('name')) or ((item.get('subject') or {}).get('name')) or '')
            detail_url = f'{detail_base}/job/{pid}' if pid else detail_base
            job = JobInfo(id='', company='小米', title=title, location=norm(city) or '未知', department=department, job_type='campus', url=detail_url, description=norm(item.get('description')), requirements=norm(item.get('requirement')))
            if job.id not in seen:
                seen.add(job.id); out.append(job)
    return out


def fetch_dux(context):
    headers, first_url, payload = capture_api_template(context, 'https://duxiaoman.jobs.feishu.cn/index/position/list')
    rows, _ = paged_fetch(context, first_url, headers, payload)
    out = []
    seen = set()
    for item in rows:
        pid = str(item.get('id') or '')
        title = norm(item.get('title'))
        if not title:
            continue
        city = ((item.get('city_info') or {}).get('name')) or ''
        department = norm(((item.get('job_function') or {}).get('name')) or ((item.get('job_category') or {}).get('name')) or '')
        detail_url = f'https://duxiaoman.jobs.feishu.cn/index/position/{pid}/detail' if pid else 'https://duxiaoman.jobs.feishu.cn/index/position/list'
        job = JobInfo(id='', company='度小满', title=title, location=norm(city) or '未知', department=department, job_type='social', url=detail_url, description=norm(item.get('description')), requirements=norm(item.get('requirement')))
        if job.id not in seen:
            seen.add(job.id); out.append(job)
    return out


def count_lines():
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        return sum(1 for _ in f)


def main():
    summary = {'success': [], 'failed': [], 'new_counts': {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=PROXY)
        context = browser.new_context(user_agent=UA, ignore_https_errors=True)
        try:
            try:
                jobs = fetch_xiaomi(context)
                summary['new_counts']['小米'] = append_jobs(jobs)
                summary['success'].append('小米')
            except Exception as e:
                summary['failed'].append(('小米', str(e)))
                summary['new_counts']['小米'] = 0
            try:
                jobs = fetch_dux(context)
                summary['new_counts']['度小满'] = append_jobs(jobs)
                summary['success'].append('度小满')
            except Exception as e:
                summary['failed'].append(('度小满', str(e)))
                summary['new_counts']['度小满'] = 0
        finally:
            context.close(); browser.close()
    print(json.dumps({'success': summary['success'], 'failed': summary['failed'], 'new_counts': summary['new_counts'], 'csv_lines': count_lines()}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
