#!/usr/bin/env python3
"""
Quick discovery for MBB consulting companies
"""

from playwright.sync_api import sync_playwright
import json

def quick_discovery(company_name, url, is_spa=True):
    '''快速探测公司页面'''
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--proxy-server=http://127.0.0.1:7890'])
        context = browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            locale='en-US',
            viewport={'width': 1440, 'height': 900}
        )
        page = context.new_page()

        evidence = {
            'company': company_name,
            'url': url,
            'title': '',
            'job_signal_detected': False,
            'ats_fingerprint': False,
            'job_cards': 0,
            'spa_detected': False,
            'error': ''
        }

        try:
            print(f'Loading {company_name} page...')

            wait_until = 'networkidle' if not is_spa else 'load'
            page.goto(url, wait_until=wait_until, timeout=30000)

            # 等待 SPA 渲染
            if is_spa:
                page.wait_for_timeout(5000)

            # 获取页面信息
            evidence['title'] = page.title()

            # 检查 job signal
            content = page.content()
            job_keywords = ['job', 'position', 'opening', 'career', 'student', 'campus', 'graduate']
            evidence['job_signal_detected'] = any(keyword.lower() in content.lower() for keyword in job_keywords)

            # 检查 SPA fingerprint
            spa_keywords = ['__NEXT_DATA__', '__NUXT__', 'react', 'vue', 'angular']
            evidence['spa_detected'] = any(keyword in content.lower() for keyword in spa_keywords)

            # 检查 ATS fingerprint
            ats_keywords = ['workday', 'greenhouse', 'lever', 'mokahr', 'phenom']
            evidence['ats_fingerprint'] = any(keyword in content.lower() for keyword in ats_keywords)

            # 查找岗位卡片
            job_selectors = ['.job-item', '.job-card', '[class*="job"]', '[class*="opening"]', 'a[href*="job"]']
            for selector in job_selectors:
                elements = page.query_selector_all(selector)
                if elements:
                    evidence['job_cards'] = len(elements)
                    break

            # 截图
            filename = company_name.lower().replace(' ', '_').replace('&', 'and')
            page.screenshot(path=f'/home/ubuntu/.openclaw/workspace-projecta/data/screenshots/{filename}_page.png', full_page=True)
            print(f'Screenshot saved: {filename}_page.png')

        except Exception as e:
            evidence['error'] = str(e)
            print(f'Error: {e}')

        browser.close()
        return evidence

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print('Usage: python quick_discover_mbb.py <company_name> <url> [is_spa]')
        sys.exit(1)

    company_name = sys.argv[1]
    url = sys.argv[2]
    is_spa = sys.argv[3].lower() == 'true' if len(sys.argv) > 3 else True

    result = quick_discovery(company_name, url, is_spa)

    print('\n' + '='*80)
    print(f'Discovery Result: {company_name}')
    print('='*80)
    print(f"job_signal: {result['job_signal_detected']}")
    print(f"ats_fingerprint: {result['ats_fingerprint']}")
    print(f"spa_detected: {result['spa_detected']}")
    print(f"job_cards: {result['job_cards']}")
    print(f"title: {result['title']}")
    print(f"error: {result['error']}")
