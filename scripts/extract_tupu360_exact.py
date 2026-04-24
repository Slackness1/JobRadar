#!/usr/bin/env python3
"""
埃森哲Tupu360平台精确提取脚本
基于HTML结构：position-item-container -> position-name -> h4.title -> span.txt
"""
import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def extract_accenture_tupu360_from_html():
    """从保存的HTML文件提取职位"""
    html_file = "/home/ubuntu/.openclaw/workspace-projecta/data/accenture_tupu360.html"

    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    jobs = []

    # 查找所有职位容器
    position_containers = soup.find_all('div', class_='position-item-container')
    print(f"[DEBUG] 找到 {len(position_containers)} 个职位容器")

    for container in position_containers:
        # 提取职位标题
        title_span = container.find('span', class_='txt')
        if title_span:
            title = title_span.get_text(strip=True)
            print(f"[DEBUG] 提取职位: {title}")

            # 提取发布日期
            time_div = container.find('div', class_='time')
            date = None
            if time_div:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', time_div.get_text())
                if date_match:
                    date = date_match.group(1)

            # 提取地点（从整个容器中搜索城市）
            location = None
            container_text = container.get_text()
            cities = ['北京', '上海', '广州', '深圳', '大连', '成都', '杭州', '香港']
            for city in cities:
                if city in container_text:
                    location = city
                    break

            job = {
                "title": title,
                "location": location,
                "date": date,
                "url": None,  # 静态HTML中没有详情链接
                "method": "tupu360_html_parsing"
            }

            jobs.append(job)

    # 汇总结果
    result = {
        "url": "https://careersite.tupu360.com/accentureats/position/index?recruitmentType=CAMPUSRECRUITMENT&jobCategory=",
        "method": "tupu360_html_parsing",
        "status": "success" if jobs else "failed",
        "jobs_count": len(jobs),
        "jobs": jobs
    }

    return result


def main():
    """主函数"""
    print("="*80)
    print("埃森哲Tupu360平台精确提取")
    print("="*80)

    result = extract_accenture_tupu360_from_html()

    # 保存结果
    timestamp = "2026-03-25"
    output_file = f"/home/ubuntu/.openclaw/workspace-projecta/data/accenture_tupu360_exact_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_file}")

    # 打印摘要
    print(f"\n摘要:")
    print(f"  状态: {result['status']}")
    print(f"  职位数: {result['jobs_count']}")

    if result['jobs']:
        print(f"\n  职位列表:")
        for i, job in enumerate(result['jobs'], 1):
            print(f"    {i}. {job['title']}")
            if job.get('location'):
                print(f"       地点: {job['location']}")
            if job.get('date'):
                print(f"       发布日期: {job['date']}")


if __name__ == "__main__":
    main()
