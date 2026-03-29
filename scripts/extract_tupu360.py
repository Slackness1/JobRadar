#!/usr/bin/env python3
"""
埃森哲Tupu360平台提取脚本
从调试信息看，已经发现4个职位
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any


def extract_accenture_tupu360():
    """提取埃森哲Tupu360平台的职位"""
    url = "https://careersite.tupu360.com/accentureats/position/index?recruitmentType=CAMPUSRECRUITMENT&jobCategory="

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    try:
        print(f"[DEBUG] 请求URL: {url}")
        response = session.get(url, timeout=15)
        response.raise_for_status()
        print(f"[DEBUG] 状态码: {response.status_code}")
        print(f"[DEBUG] 内容长度: {len(response.text)} 字符")

        soup = BeautifulSoup(response.text, 'html.parser')

        # 方法1：查找职位标题元素
        jobs = []

        # 查找所有职位卡片
        job_cards = soup.find_all('div', class_='job-card')
        print(f"[DEBUG] 找到 {len(job_cards)} 个job-card")

        if job_cards:
            for card in job_cards:
                # 查找职位标题
                title_elem = card.find('h3') or card.find('h4') or card.find('a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link_elem = card.find('a')
                    link = None

                    if link_elem and link_elem.get('href'):
                        link = urljoin(url, link_elem.get('href'))

                    # 查找地点
                    location_elem = card.find(string=re.compile(r'北京|上海|广州|深圳|大连|成都|杭州|香港', re.I))
                    location = location_elem.strip() if location_elem else None

                    # 查找发布日期
                    date_elem = card.find(string=re.compile(r'发布于:|发布时间', re.I))
                    date = None
                    if date_elem:
                        date_match = re.search(r'\d{4}-\d{2}-\d{2}', date_elem)
                        if date_match:
                            date = date_match.group()

                    job = {
                        "title": title,
                        "url": link,
                        "location": location,
                        "date": date,
                        "method": "tupu360_card"
                    }

                    if title and len(title) > 5:
                        jobs.append(job)
                        print(f"[DEBUG] 提取岗位: {title}")

        # 方法2：如果没找到job-card，尝试查找所有职位标题链接
        if not jobs:
            print(f"[DEBUG] 方法1失败，尝试方法2...")

            all_links = soup.find_all('a')
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                # 过滤出职位链接（通常包含job、position、vacancy等关键词）
                if (len(text) > 5 and
                    not any(x in text.lower() for x in ['登录', '注册', '退出', '更多', '搜索', '主页', '招聘', 'FAQ']) and
                    any(x in href.lower() for x in ['job', 'position', 'vacancy', 'detail'])):

                    job = {
                        "title": text,
                        "url": urljoin(url, href),
                        "method": "link_pattern"
                    }

                    # 避免重复
                    if not any(j["title"] == text for j in jobs):
                        jobs.append(job)
                        print(f"[DEBUG] 提取岗位: {text}")

        # 方法3：如果还是没找到，从HTML文本中提取
        if not jobs:
            print(f"[DEBUG] 方法2失败，尝试方法3...")

            # 从调试信息看，职位格式是：职位标题\n地点\n发布于: 日期
            body_text = soup.get_text()

            # 查找职位模式
            job_pattern = r'([^\n]+?)\n(北京|上海|广州|深圳|大连|成都|杭州|香港|辽宁省-.*|广东省-.*)\n发布于:\s*(\d{4}-\d{2}-\d{2})'
            matches = re.findall(job_pattern, body_text)

            for title, location, date in matches:
                title = title.strip()
                if len(title) > 5 and not any(x in title for x in ['职位列表', '筛选项', '搜索职位', '共\d+个职位']):
                    job = {
                        "title": title,
                        "location": location,
                        "date": date,
                        "url": None,  # 无法直接提取链接
                        "method": "text_pattern"
                    }

                    # 避免重复
                    if not any(j["title"] == title for j in jobs):
                        jobs.append(job)
                        print(f"[DEBUG] 提取岗位: {title}")

        result = {
            "url": url,
            "method": "tupu360_multi_method",
            "status": "success" if jobs else "failed",
            "jobs_count": len(jobs),
            "jobs": jobs
        }

        print(f"\n[DEBUG] 最终提取到 {len(jobs)} 个职位")

        return result

    except Exception as e:
        print(f"[ERROR] 提取失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "url": url,
            "method": "tupu360_multi_method",
            "status": "error",
            "jobs_count": 0,
            "jobs": [],
            "error": str(e)
        }


def main():
    """主函数"""
    from urllib.parse import urljoin

    print("="*80)
    print("埃森哲Tupu360平台提取")
    print("="*80)

    result = extract_accenture_tupu360()

    # 保存结果
    timestamp = "2026-03-25"
    output_file = f"/home/ubuntu/.openclaw/workspace-projecta/data/accenture_tupu360_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_file}")

    # 打印摘要
    print(f"\n摘要:")
    print(f"  状态: {result['status']}")
    print(f"  职位数: {result['jobs_count']}")
    if result['jobs']:
        print(f"  职位列表:")
        for i, job in enumerate(result['jobs'][:10], 1):  # 只显示前10个
            print(f"    {i}. {job['title']}")
            if job.get('location'):
                print(f"       地点: {job['location']}")
            if job.get('date'):
                print(f"       日期: {job['date']}")
            if job.get('url'):
                print(f"       链接: {job['url']}")


if __name__ == "__main__":
    main()
