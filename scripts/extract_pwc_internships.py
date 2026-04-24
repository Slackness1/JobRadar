#!/usr/bin/env python3
"""
Extract PwC internships from Moka platform
"""

from playwright.sync_api import sync_playwright
import json
import time

def extract_pwc_internships():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--proxy-server=http://127.0.0.1:7890'])
        context = browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            locale='zh-CN',
            viewport={'width': 1440, 'height': 900}
        )
        page = context.new_page()

        jobs = []
        evidence = {
            'final_url': '',
            'job_signal_detected': False,
            'job_count': 0,
            'job_links': []
        }

        try:
            print('Loading PwC campus page...')
            page.goto('https://app.mokahr.com/campus_apply/pwc/148260', wait_until='networkidle', timeout=30000)

            # 等待页面渲染
            page.wait_for_timeout(3000)

            # 查找 Internship 链接并点击
            print('Looking for Internship link...')
            internship_link = page.query_selector('a[href*="Internship"]')

            if internship_link:
                print('Found Internship link, clicking...')
                internship_link.click()
                page.wait_for_load_state('networkidle', timeout=10000)
                page.wait_for_timeout(3000)

                evidence['final_url'] = page.url
                print(f'Navigated to: {page.url}')

                # 查找岗位元素
                job_selectors = [
                    '.job-item',
                    '.job-card',
                    '[class*="job"]',
                    '[class*="position"]',
                    'a[href*="job"]',
                    'li[class*="job"]'
                ]

                found_selector = None
                for selector in job_selectors:
                    elements = page.query_selector_all(selector)
                    if elements:
                        found_selector = selector
                        print(f'Found {len(elements)} job elements using selector: {selector}')
                        break

                if not found_selector:
                    print('No job elements found, checking page content...')
                    content = page.content()
                    job_keywords = ['job', 'position', '职位', '岗位', '招聘', 'openings', 'vacancies']
                    evidence['job_signal_detected'] = any(keyword.lower() in content.lower() for keyword in job_keywords)

                    # 查找所有链接
                    all_links = page.query_selector_all('a')
                    print(f'Total links found: {len(all_links)}')

                    # 查找可能包含 job 的链接
                    for link in all_links:
                        href = link.get_attribute('href') or ''
                        if href and ('job' in href.lower() or 'position' in href.lower()):
                            evidence['job_links'].append({
                                'href': href,
                                'text': link.inner_text().strip()[:50]
                            })

                    print(f'Job-like links found: {len(evidence["job_links"])}')

                    # 保存截图
                    page.screenshot(path='/home/ubuntu/.openclaw/workspace-projecta/data/screenshots/pwc_internship_page.png', full_page=True)
                    print('Screenshot saved')
                else:
                    # 提取岗位信息
                    elements = page.query_selector_all(found_selector)
                    print(f'Extracting jobs from {len(elements)} elements...')

                    for i, element in enumerate(elements[:20], 1):
                        try:
                            # 查找标题
                            title_selectors = ['a', '[class*="title"]', '[class*="name"]', 'h1', 'h2', 'h3']
                            title = ''
                            for ts in title_selectors:
                                title_elem = element.query_selector(ts)
                                if title_elem:
                                    title = title_elem.inner_text().strip()
                                    if title:
                                        break

                            # 查找链接
                            link_elem = element.query_selector('a')
                            url = link_elem.get_attribute('href') if link_elem else ''

                            if title and url:
                                jobs.append({
                                    'title': title,
                                    'url': url
                                })
                                print(f'{i}. {title}')

                        except Exception as e:
                            print(f'Error extracting element {i}: {e}')

                evidence['job_count'] = len(jobs)
            else:
                print('No Internship link found')

        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()

        browser.close()

        # 保存结果
        result = {
            'success': len(jobs) > 0,
            'job_count': len(jobs),
            'jobs': jobs,
            'evidence': evidence
        }

        with open('/home/ubuntu/.openclaw/workspace-projecta/data/pwc_internship_extraction.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result

if __name__ == '__main__':
    result = extract_pwc_internships()
    print(f'\nFinal result: {result["success"]}, jobs: {result["job_count"]}')
    print(f'Evidence: {result["evidence"]}')
