#!/usr/bin/env python3
"""
检查咨询公司网站是否可访问（使用静态 requests）
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any

# 要检查的公司
COMPANIES = [
    {"name": "LEK", "url": "https://www.lek.com/careers", "tier": "Tier A"},
    {"name": "EY-Parthenon", "url": "https://www.ey.com/careers", "tier": "Tier A"},
    {"name": "IBM Consulting", "url": "https://www.ibm.com/careers", "tier": "Tier A-"},
    {"name": "Capgemini Invent", "url": "https://www.capgemini.com/careers", "tier": "Tier B"},
    {"name": "Protiviti", "url": "https://www.protiviti.com/careers", "tier": "Tier B"},
    {"name": "BearingPoint", "url": "https://www.bearingpoint.com/en/careers", "tier": "Tier B"},
    {"name": "ZS", "url": "https://www.zs.com/careers", "tier": "Tier B"},
    {"name": "OC&C", "url": "https://www.occstrategy.com/careers", "tier": "Tier B"},
    {"name": "AlixPartners", "url": "https://www.alixpartners.com/careers", "tier": "Tier B (Optional)"},
    {"name": "FTI", "url": "https://www.fticonsulting.com/careers", "tier": "Tier B (Optional)"},
    {"name": "Strategy&", "url": "https://www.strategyand.pwc.com/careers", "tier": "Tier A"},
    {"name": "Roland Berger", "url": "https://www.rolandberger.com/en/Careers", "tier": "Tier A"},
    {"name": "Kearney", "url": "https://www.kearney.com/careers", "tier": "Tier A"},
    {"name": "Deloitte", "url": "https://www2.deloitte.com/cn/careers.html", "tier": "Tier A-"},
    {"name": "BDA", "url": "https://www.bda.com/careers", "tier": "Tier B"},
    {"name": "A&M", "url": "https://www.alvarezandmarsal.com/careers", "tier": "Tier B (Optional)"},
]


def check_site(url: str, name: str) -> Dict[str, Any]:
    """检查单个网站"""
    result = {
        "name": name,
        "url": url,
        "accessible": False,
        "status_code": None,
        "error": None,
        "title": None,
        "has_job_signal": False,
        "has_detail_links": False,
    }

    try:
        # 尝试访问网站
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        result["status_code"] = response.status_code
        result["accessible"] = 200 <= response.status_code < 400

        # 获取页面标题
        if "<title>" in response.text:
            start = response.text.find("<title>") + 7
            end = response.text.find("</title>")
            result["title"] = response.text[start:end].strip()

        # 检查招聘信号
        job_keywords = ["job", "opening", "position", "vacancy", "career", "apply", "职位", "岗位", "招聘"]
        text_lower = response.text.lower()
        result["has_job_signal"] = any(keyword in text_lower for keyword in job_keywords)

        # 检查是否有职位详情链接
        detail_patterns = ["/job", "/opening", "/position", "/vacancy", "/apply", "/requisition"]
        result["has_detail_links"] = any(pattern in text_lower for pattern in detail_patterns)

    except Exception as e:
        result["error"] = str(e)
        result["accessible"] = False

    return result


def main():
    """主函数"""
    print("="*80)
    print("咨询公司网站可访问性检查")
    print("="*80)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results = []
    accessible_count = 0
    job_signal_count = 0
    detail_links_count = 0

    for company in COMPANIES:
        name = company["name"]
        url = company["url"]
        tier = company["tier"]

        print(f"正在检查: {name} ({tier})")
        print(f"URL: {url}")

        result = check_site(url, name)
        result["tier"] = tier
        results.append(result)

        if result["accessible"]:
            accessible_count += 1
            print(f"  -> 可访问: 是 ({result['status_code']})")
            if result["title"]:
                print(f"  -> 标题: {result['title'][:100]}")
            if result["has_job_signal"]:
                job_signal_count += 1
                print(f"  -> 招聘信号: 是")
            if result["has_detail_links"]:
                detail_links_count += 1
                print(f"  -> 职位链接: 是")
        else:
            print(f"  -> 可访问: 否")
            if result["status_code"]:
                print(f"  -> 状态码: {result['status_code']}")
            if result["error"]:
                print(f"  -> 错误: {result['error'][:100]}")

        print()

    # 统计总结
    print("="*80)
    print("统计总结")
    print("="*80)
    print(f"总数: {len(results)}")
    print(f"可访问: {accessible_count} ({accessible_count/len(results)*100:.1f}%)")
    print(f"有招聘信号: {job_signal_count}")
    print(f"有职位链接: {detail_links_count}")
    print()

    # 列出可访问的公司
    print("可访问的公司:")
    for r in results:
        if r["accessible"]:
            print(f"  - {r['name']} ({r['tier']})")
    print()

    # 列出不可访问的公司
    print("不可访问的公司:")
    for r in results:
        if not r["accessible"]:
            reason = f"状态码 {r['status_code']}" if r['status_code'] else r['error'][:50] if r['error'] else "未知"
            print(f"  - {r['name']} ({r['tier']}) - {reason}")
    print()

    # 保存结果
    output_path = "/home/ubuntu/.openclaw/workspace-projecta/data/consulting_site_check_2026-03-25.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "check_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "results": results,
            "summary": {
                "total": len(results),
                "accessible": accessible_count,
                "has_job_signal": job_signal_count,
                "has_detail_links": detail_links_count,
            }
        }, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
