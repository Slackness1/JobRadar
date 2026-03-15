#!/usr/bin/env python3
import csv, hashlib, json, re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import sync_playwright

BASE = Path('/home/ubuntu/workspace/job-crawler')
CSV_PATH = BASE / 'data' / 'jobs.csv'
PROXY = {'server': 'http://127.0.0.1:7890'}
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
API_BASE = 'https://job.bankcomm.com/api/GTMS.GTMS-PORTAL.V-1.0'

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
    return re.sub(r'\s+', ' ', str(x or '')).strip()


def load_existing_ids():
    ids = set()
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            ids.add(row.get('id') or row.get('\ufeffid'))
    return ids


def append_jobs(jobs: List[JobInfo]):
    existing = load_existing_ids()
    new = 0
    with open(CSV_PATH, 'a', encoding='utf-8', newline='') as f:
        fields = ['id','company','title','location','department','job_type','url','publish_date','deadline','description','requirements','crawled_at']
        w = csv.DictWriter(f, fieldnames=fields)
        for job in jobs:
            if job.id not in existing:
                w.writerow(asdict(job))
                existing.add(job.id)
                new += 1
    return new


def count_lines():
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        return sum(1 for _ in f)


def fetch_js(page, endpoint, payload):
    script = """async ({endpoint, payload}) => {
      const body = 'REQ_MESSAGE=' + encodeURIComponent(JSON.stringify(payload));
      const r = await fetch(endpoint, {method: 'POST', headers: {'content-type': 'application/x-www-form-urlencoded'}, body});
      return await r.json();
    }"""
    return page.evaluate(script, {'endpoint': endpoint, 'payload': payload})


def payload_list(engage_type, page_num, page_size=100):
    return {
        'REQ_HEAD': {'TRAN_PROCESS':'','TRAN_ID':'','ACCESS_TOKEN':'','REFRESH_TOKEN':''},
        'REQ_BODY': {
            'params': {
                'businessPara': {'workPlace':'','pubName':'','positionId':'','engageType': engage_type},
                'pagePara': {'pageNum': page_num, 'pageSize': page_size}
            },
            'unnessaryLogin': False
        }
    }


def payload_detail(position_id):
    return {
        'REQ_HEAD': {'TRAN_PROCESS':'','TRAN_ID':'','ACCESS_TOKEN':'','REFRESH_TOKEN':''},
        'REQ_BODY': {'params': {'positionId': position_id}, 'unnessaryLogin': False}
    }


def fetch_all(page, engage_type):
    jobs = []
    page_num = 1
    total = None
    while True:
        data = fetch_js(page, f'{API_BASE}/querySocietyRecruitInfo.do', payload_list(engage_type, page_num))
        body = (data or {}).get('RSP_BODY') or {}
        results = body.get('results') or {}
        rows = results.get('policyList') or []
        total = int(results.get('total') or total or 0)
        if not rows:
            break
        jobs.extend(rows)
        if len(jobs) >= total:
            break
        page_num += 1
    return jobs


def main():
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=PROXY)
        ctx = browser.new_context(user_agent=UA, ignore_https_errors=True)
        page = ctx.new_page()
        page.goto('https://job.bankcomm.com/#/school', wait_until='domcontentloaded', timeout=60000)
        campus_rows = fetch_all(page, 1)
        social_rows = fetch_all(page, 3)
        for engage_type, rows, job_type in [(1, campus_rows, 'campus'), (3, social_rows, 'social')]:
            for row in rows:
                pid = row.get('positionId')
                detail = fetch_js(page, f'{API_BASE}/queryPositionDetail.do', payload_detail(pid))
                info = ((detail or {}).get('RSP_BODY') or {}).get('results') or {}
                title = norm(info.get('pubName') or row.get('pubName'))
                if not title:
                    continue
                url = f'https://job.bankcomm.com/#/{"school" if engage_type == 1 else "social"}/recruitmentInfo/?positionId={pid}'
                out.append(JobInfo(
                    id='', company='交通银行', title=title,
                    location=norm(info.get('workPlace') or row.get('workPlace')) or '未知',
                    department=norm(info.get('deptName') or row.get('deptName') or row.get('bankName')),
                    job_type=job_type, url=url,
                    publish_date=norm(info.get('createTime') or row.get('createTime')) or None,
                    deadline=norm(info.get('endDate') or row.get('endDate')) or None,
                    description=norm(info.get('responsibility')) or None,
                    requirements=norm(info.get('require')) or None,
                ))
        ctx.close(); browser.close()
    new_count = append_jobs(out)
    print(json.dumps({'company':'交通银行','fetched':len(out),'new':new_count,'csv_lines':count_lines()}, ensure_ascii=False))

if __name__ == '__main__':
    main()
