#!/usr/bin/env python3
import json, time
from playwright.sync_api import sync_playwright

TASKS = [
    ('工商银行','https://job.icbc.com.cn/pc/index.html#/main/home'),
    ('农业银行','https://career.abchina.com/build/index.html#/'),
    ('建设银行','https://job1.ccb.com/cn/job/index.html'),
    ('交通银行','https://job.bankcomm.com/#/'),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, proxy={'server':'http://127.0.0.1:7890'})
    ctx = browser.new_context(ignore_https_errors=True)
    for name, url in TASKS:
        page = ctx.new_page()
        logs=[]
        page.on('response', lambda r, logs=logs: logs.append({'url':r.url,'status':r.status,'ct':(r.headers or {}).get('content-type','')}))
        print('\n###', name)
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        print('title=', page.title())
        print('url=', page.url)
        links = page.eval_on_selector_all('a', "els => els.map((a,i)=>({i,text:(a.innerText||'').trim(),href:a.href||'',cls:a.className||''})).filter(x=>x.text).slice(0,80)")
        for l in links[:25]:
            print(l)
        print('interesting reqs:')
        for r in [x for x in logs if any(k in x['url'].lower() for k in ['job','post','position','recruit','api','query','plan'])][:50]:
            print(r)
        page.close()
    browser.close()
