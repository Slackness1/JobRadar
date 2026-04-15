#!/usr/bin/env python3
import json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright

SITES = [
    ('工商银行','https://job.icbc.com.cn/'),
    ('农业银行','https://career.abchina.com/'),
    ('中国银行','https://campus.bankofchina.com/'),
    ('建设银行','https://job.ccb.com/'),
    ('交通银行','https://job.bankcomm.com/'),
    ('广发银行','https://career.cgbchina.com.cn/'),
    ('渤海银行','https://career.cbhb.com.cn/'),
    ('邮储银行','https://psbc.zhaopin.com/'),
]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
OUT = PROJECT_ROOT / 'backend' / 'reports' / 'bank_probe.json'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
PROXY = {'server': 'http://127.0.0.1:7890'}


def text(s):
    return re.sub(r'\s+', ' ', s or '').strip()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, proxy=PROXY)
    context = browser.new_context(user_agent=UA, ignore_https_errors=True)
    results = []
    for name, url in SITES:
        page = context.new_page()
        page.set_default_timeout(30000)
        reqs, fails = [], []
        page.on('response', lambda resp, reqs=reqs: reqs.append({'url': resp.url, 'status': resp.status, 'ct': (resp.headers or {}).get('content-type','')}))
        page.on('requestfailed', lambda req, fails=fails: fails.append({'url': req.url, 'err': req.failure}))
        item = {'name': name, 'url': url}
        try:
            resp = page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(8)
            item['goto_status'] = resp.status if resp else None
            item['final_url'] = page.url
            item['title'] = page.title()
            body = text(page.locator('body').inner_text()[:1500])
            item['body'] = body
            anchors = page.eval_on_selector_all('a', "els => els.slice(0,120).map(a => ({text:(a.innerText||'').trim(), href:a.href||'', cls:a.className||''}))")
            item['anchors'] = anchors[:40]
            interesting = [r for r in reqs if any(k in r['url'].lower() for k in ['job','post','position','career','recruit','api','search','query','campus','zhaopin'])]
            item['interesting_requests'] = interesting[:120]
            item['requestfailed'] = fails[:40]
        except Exception as e:
            item['error'] = str(e)
            item['final_url'] = page.url
            item['requestfailed'] = fails[:40]
        results.append(item)
        page.close()
    browser.close()
OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(str(OUT))
