#!/usr/bin/env python3
import json, time
from playwright.sync_api import sync_playwright

TASKS = [
    ('交通银行','https://job.bankcomm.com/#/school', ['api/']),
    ('建设银行','https://job1.ccb.com/cn/job/plan_index.html?planType=XY', ['TXCODE=', '/tran/']),
    ('工商银行','https://job.icbc.com.cn/pc/index.html#/main/home', ['/post/', '/announ/']),
    ('农业银行','https://career.abchina.com/build/index.html#/', ['/get', '/list', '/query', '/position', '/job', '/post']),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, proxy={'server':'http://127.0.0.1:7890'})
    ctx = browser.new_context(ignore_https_errors=True)
    for name, url, kws in TASKS:
        page = ctx.new_page()
        page.set_default_timeout(45000)
        seen=[]
        def on_resp(r):
            u=r.url.lower()
            if any(k.lower() in u for k in kws):
                try:
                    txt=r.text()[:1200]
                except Exception as e:
                    txt=f'<err {e}>'
                seen.append({'url':r.url,'status':r.status,'text':txt})
        page.on('response', on_resp)
        print('\n###',name,url)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(8)
            print('title', page.title(), 'url', page.url)
            for item in seen[:20]:
                print('URL', item['url'])
                print(item['text'][:600].replace('\n',' '))
                print('---')
        except Exception as e:
            print('ERR',e)
        page.close()
    browser.close()
