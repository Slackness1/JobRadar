#!/usr/bin/env python3
"""
调试脚本：检查优先公司的HTML内容和内嵌数据
"""
import json
import re
import requests
from bs4 import BeautifulSoup


def debug_site(url, site_name):
    """调试单个网站"""
    print(f"\n{'='*80}")
    print(f"调试: {site_name}")
    print(f"URL: {url}")
    print(f"{'='*80}\n")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    try:
        response = session.get(url, timeout=15)
        print(f"状态码: {response.status_code}")
        print(f"内容长度: {len(response.text)} 字符")

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 检查是否有内嵌JSON数据
        print(f"\n--- 检查内嵌JSON数据 ---")
        patterns = [
            ('__NEXT_DATA__', r'<script id="__NEXT_DATA__"[^>]*type="application/json">(.*?)</script>'),
            ('__NUXT__', r'window\.__NUXT__\s*=\s*({[^;]+});'),
            ('__INITIAL_STATE__', r'window\.__INITIAL_STATE__\s*=\s*({[^;]+});'),
            ('application/ld+json', r'<script type="application/ld\+json">(.*?)</script>'),
            ('window.jobs', r'window\.jobs\s*=\s*(\[.*?\]);'),
            ('jobPostings', r'"jobPostings"\s*:\s*(\[[^\]]+\])'),
        ]

        found_data = False
        for name, pattern in patterns:
            matches = re.findall(pattern, response.text, re.DOTALL)
            if matches:
                found_data = True
                print(f"✓ 找到 {name}: {len(matches)} 个匹配")

                # 只显示第一个匹配的前500字符
                match_str = str(matches[0])[:500]
                print(f"  内容预览: {match_str}...")

        if not found_data:
            print("✗ 未找到内嵌JSON数据")

        # 2. 检查常见的岗位选择器
        print(f"\n--- 检查常见岗位选择器 ---")
        selectors = [
            ('job-title', 'class'),
            ('jobTitle', 'class'),
            ('position-title', 'class'),
            ('job-name', 'class'),
            ('role-title', 'class'),
            ('[data-automation-id]', 'css'),
            ('.job-posting-title', 'css'),
        ]

        for selector_name, selector_type in selectors:
            elements = []
            if selector_type == 'class':
                elements = soup.find_all(class_=selector_name)
            else:
                elements = soup.select(selector_name)

            if elements:
                print(f"✓ 找到 {len(elements)} 个 {selector_name} 元素")

                # 显示前3个元素的文本
                for i, elem in enumerate(elements[:3]):
                    text = elem.get_text(strip=True)
                    if len(text) > 50:
                        text = text[:50] + "..."
                    print(f"  [{i+1}] {text}")

        # 3. 检查是否有职位链接
        print(f"\n--- 检查职位链接 ---")
        job_links = soup.find_all('a', href=re.compile(r'(job|position|vacancy|career)', re.I))

        if job_links:
            print(f"✓ 找到 {len(job_links)} 个可能的职位链接")

            # 显示前5个
            for i, link in enumerate(job_links[:5]):
                text = link.get_text(strip=True)
                href = link.get('href', '')

                if len(text) > 40:
                    text = text[:40] + "..."

                print(f"  [{i+1}] {text} -> {href}")
        else:
            print("✗ 未找到职位链接")

        # 4. 检查是否是SPA/需要JS渲染
        print(f"\n--- 检查是否需要JS渲染 ---")
        has_vue = 'vue' in response.text.lower() or 'vue-router' in response.text.lower()
        has_react = 'react' in response.text.lower() or 'reactdom' in response.text.lower()
        has_angular = 'angular' in response.text.lower() or 'ng-app' in response.text.lower()
        empty_body = len(soup.find('body').get_text(strip=True)) < 100 if soup.find('body') else True

        if has_vue or has_react or has_angular or empty_body:
            print("⚠ 疑似需要JS渲染的SPA")
            if has_vue:
                print("  - 检测到Vue")
            if has_react:
                print("  - 检测到React")
            if has_angular:
                print("  - 检测到Angular")
            if empty_body:
                print("  - body内容很少（需要JS渲染）")
        else:
            print("✓ 疑似静态HTML")

        # 5. 检查是否有反爬/验证码
        print(f"\n--- 检查反爬/验证码 ---")
        anti_bot_signals = [
            'captcha',
            'verify',
            'challenge',
            'cloudflare',
            'access denied',
            'forbidden'
        ]

        found_anti_bot = []
        for signal in anti_bot_signals:
            if signal in response.text.lower():
                found_anti_bot.append(signal)

        if found_anti_bot:
            print(f"⚠ 检测到可能的反爬信号: {', '.join(found_anti_bot)}")
        else:
            print("✓ 未检测到明显的反爬信号")

        # 6. 保存HTML片段
        print(f"\n--- 保存HTML片段 ---")
        body_text = soup.get_text()[:1000] if soup.find('body') else ""
        print(f"Body前1000字符: {body_text}")

    except Exception as e:
        print(f"✗ 错误: {e}")


def main():
    """调试所有目标网站"""
    targets = [
        ("埃森哲-主页", "https://www.accenture.com/cn-zh/careers/jobsearch?jk=&sb=1&vw=0&is_rj=0&pg=1"),
        ("埃森哲-Tupu360", "https://careersite.tupu360.com/accentureats/position/index?recruitmentType=CAMPUSRECRUITMENT&jobCategory="),
        ("ZS", "https://jobs.zs.com/jobs"),
        ("OC&C", "https://careers.occstrategy.com/vacancies/vacancy-search-results.aspx"),
        ("毕马威-Moka", "https://app.mokahr.com/campus-recruitment/kpmg/76195#/jobs?1841380=Audit&page=1&anchorName=jobsList&keyword=&project0=100032245"),
        ("毕马威-主页", "https://kpmg.com/cn/zh/careers/campus/graduate-applications.html"),
    ]

    for site_name, url in targets:
        debug_site(url, site_name)

        # 等待一下避免请求过快
        import time
        time.sleep(2)


if __name__ == "__main__":
    main()
