#!/usr/bin/env python3
"""
咨询公司专项静态提取脚本
只对可访问的公司做轻量级静态 HTML 提取
"""

import requests
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

# 可访问的公司
ACCESSIBLE_COMPANIES = [
    {"name": "LEK", "url": "https://www.lek.com/careers", "tier": "Tier A"},
    {"name": "EY-Parthenon", "url": "https://www.ey.com/careers", "tier": "Tier A"},
    {"name": "IBM Consulting", "url": "https://www.ibm.com/careers", "tier": "Tier A-"},
    {"name": "Capgemini Invent", "url": "https://www.capgemini.com/careers", "tier": "Tier B"},
    {"name": "Protiviti", "url": "https://www.protiviti.com/careers", "tier": "Tier B"},
    {"name": "BearingPoint", "url": "https://www.bearingpoint.com/en/careers", "tier": "Tier B"},
    {"name": "ZS", "url": "https://www.zs.com/careers", "tier": "Tier B"},
    {"name": "AlixPartners", "url": "https://www.alixpartners.com/careers", "tier": "Tier B (Optional)"},
    {"name": "FTI", "url": "https://www.fticonsulting.com/careers", "tier": "Tier B (Optional)"},
]


def extract_jobs_static(name: str, url: str) -> Dict[str, Any]:
    """静态提取岗位（不使用 Playwright）"""
    result = {
        "status": "failed",
        "method": "static_html",
        "result_count": 0,
        "failure_tag": None,
        "evidence": {},
        "jobs": []
    }

    try:
        # 获取页面
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

        if response.status_code != 200:
            return {
                **result,
                "failure_tag": f"HTTP_{response.status_code}",
                "evidence": {"status_code": response.status_code}
            }

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # 收集证据
        evidence = {
            "title": soup.title.string if soup.title else "",
            "final_url": response.url,
            "has_json_ld": bool(soup.find('script', type='application/ld+json')),
            "has_json_scripts": bool(soup.find_all('script', type='application/json')),
            "job_keywords_found": _check_job_keywords(html),
            "ats_fingerprint": _detect_ats(html, url),
            "has_detail_links": _has_detail_links(html),
            "job_card_selectors_found": _find_job_card_selectors(html),
        }

        # 提取内嵌 JSON 数据
        json_jobs = _extract_json_jobs(html, url)
        if json_jobs:
            result["status"] = "success"
            result["result_count"] = len(json_jobs)
            result["jobs"] = json_jobs[:10]  # 只返回前 10 个
            result["evidence"] = evidence
            result["extraction_method"] = "embedded_json"
            return result

        # 尝试提取 DOM 中的岗位
        dom_jobs = _extract_dom_jobs(soup, html)
        if dom_jobs:
            result["status"] = "success"
            result["result_count"] = len(dom_jobs)
            result["jobs"] = dom_jobs[:10]  # 只返回前 10 个
            result["evidence"] = evidence
            result["extraction_method"] = "dom_parsing"
            return result

        # 没有提取到岗位，区分 confirmed zero vs suspect zero
        if evidence["job_keywords_found"] or evidence["has_detail_links"] or evidence["job_card_selectors_found"]:
            result["status"] = "suspect_zero"
            result["failure_tag"] = "JOB_SIGNAL_BUT_ZERO_EXTRACTED"
            result["evidence"] = evidence
        else:
            result["status"] = "confirmed_zero"
            result["failure_tag"] = "NO_JOB_SIGNAL"
            result["evidence"] = evidence

    except Exception as e:
        result["failure_tag"] = f"ERROR:{type(e).__name__}"
        result["error_message"] = str(e)

    return result


def _check_job_keywords(html: str) -> bool:
    """检查页面是否包含招聘相关关键词"""
    keywords = ["job", "opening", "position", "vacancy", "requisition", "apply now", "职位", "岗位", "招聘"]
    html_lower = html.lower()
    return any(keyword in html_lower for keyword in keywords)


def _detect_ats(html: str, url: str) -> str:
    """检测 ATS 平台"""
    ats_patterns = {
        "Greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
        "Lever": ["lever.co"],
        "Workday": ["workday.com"],
        "SmartRecruiters": ["smartrecruiters.com"],
        "Taleo": ["taleo.net", "oracle.com/hcm"],
        "Moka": ["mokahr.com", "hotjob.cn"],
        "Phenom People": ["phenompeople.com"],
        "Eightfold": ["eightfold.ai"],
        "iCIMS": ["icims.com"],
        "Next.js": ["/_next/static"],
        "React": ["react", "react-dom"],
    }

    for ats, patterns in ats_patterns.items():
        if any(pattern in url or pattern in html for pattern in patterns):
            return ats
    return "custom"


def _has_detail_links(html: str) -> bool:
    """检查是否有职位详情链接"""
    job_link_patterns = [
        r'href="[^"]*job[^"]*"',
        r'href="[^"]*opening[^"]*"',
        r'href="[^"]*position[^"]*"',
        r'href="[^"]*vacancy[^"]*"',
        r'href="[^"]*requisition[^"]*"',
    ]
    return any(re.search(pattern, html, re.IGNORECASE) for pattern in job_link_patterns)


def _find_job_card_selectors(html: str) -> List[str]:
    """查找可能的职位卡片选择器"""
    selectors = []
    selector_patterns = [
        r'class="[^"]*job[^"]*card[^"]*"',
        r'class="[^"]*job[^"]*item[^"]*"',
        r'class="[^"]*opening[^"]*card[^"]*"',
        r'class="[^"]*job[^"]*list[^"]*item[^"]*"',
        r'data-test="[^"]*job[^"]*"',
        r'data-testid="[^"]*job[^"]*"',
    ]

    for pattern in selector_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            selectors.extend(matches[:5])  # 最多取 5 个

    return list(set(selectors))  # 去重


def _extract_json_jobs(html: str, url: str) -> List[Dict[str, Any]]:
    """提取内嵌 JSON 数据中的岗位"""
    jobs = []

    # 查找 application/ld+json
    soup = BeautifulSoup(html, 'html.parser')
    json_ld_scripts = soup.find_all('script', type='application/ld+json')

    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            # 查找 JobPosting 类型的数据
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') == 'JobPosting':
                        jobs.append({
                            "title": item.get('title', ''),
                            "description": item.get('description', '')[:200] if item.get('description') else '',
                            "location": item.get('jobLocation', {}).get('address', {}).get('addressLocality', ''),
                            "source": "json_ld",
                        })
            elif isinstance(data, dict) and data.get('@type') == 'JobPosting':
                jobs.append({
                    "title": data.get('title', ''),
                    "description": data.get('description', '')[:200] if data.get('description') else '',
                    "location": data.get('jobLocation', {}).get('address', {}).get('addressLocality', ''),
                    "source": "json_ld",
                })
        except:
            pass

    # 查找其他 JSON 脚本
    json_scripts = soup.find_all('script', type='application/json')
    for script in json_scripts:
        try:
            data = json.loads(script.string)
            # 简单查找可能包含 jobs 或 openings 字段的数据
            if isinstance(data, dict):
                for key in ['jobs', 'openings', 'positions', 'vacancies', 'jobListings']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key][:5]:  # 最多取 5 个
                            if isinstance(item, dict):
                                jobs.append({
                                    "title": item.get('title') or item.get('name') or item.get('role', ''),
                                    "source": f"json_{key}",
                                })
        except:
            pass

    return jobs


def _extract_dom_jobs(soup: BeautifulSoup, html: str) -> List[Dict[str, Any]]:
    """从 DOM 中提取岗位"""
    jobs = []

    # 尝试多种选择器
    selectors = [
        {'selector': '[data-test="job-item"]', 'title_attr': None},
        {'selector': '[data-testid="job-item"]', 'title_attr': None},
        {'selector': '.job-card', 'title_attr': None},
        {'selector': '.job-item', 'title_attr': None},
        {'selector': '.opening-card', 'title_attr': None},
        {'selector': '.vacancy-item', 'title_attr': None},
        {'selector': '.job-listing', 'title_attr': None},
        {'selector': 'article.job', 'title_attr': None},
        {'selector': 'li.job', 'title_attr': None},
    ]

    for config in selectors:
        try:
            elements = soup.select(config['selector'])
            if elements and len(elements) > 0:
                for element in elements[:10]:  # 最多提取 10 个
                    try:
                        # 获取标题
                        if config['title_attr']:
                            title = element.get(config['title_attr'], '')
                        else:
                            title = element.get_text(strip=True)

                        if title and len(title) > 3:
                            jobs.append({
                                "title": title[:100],  # 限制长度
                                "selector": config['selector'],
                                "source": "dom",
                            })
                    except:
                        pass

                if jobs:
                    break
        except:
            pass

    # 如果没有找到标准选择器，尝试查找包含特定关键词的元素
    if not jobs:
        for element in soup.find_all(['a', 'div', 'li']):
            try:
                text = element.get_text(strip=True)
                # 查找包含 job/position/opening 等关键词的简短文本
                if text and 10 < len(text) < 100:
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in ['consultant', 'analyst', 'associate', 'manager', 'intern']):
                        jobs.append({
                            "title": text,
                            "selector": f"tag:{element.name}",
                            "source": "dom_fallback",
                        })
                        if len(jobs) >= 10:
                            break
            except:
                pass

    return jobs


def main():
    """主函数"""
    print("="*80)
    print("咨询公司专项静态提取")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_results = {
        "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "results": {},
        "summary": {}
    }

    success_count = 0
    suspect_zero_count = 0
    confirmed_zero_count = 0
    failed_count = 0

    for company in ACCESSIBLE_COMPANIES:
        name = company["name"]
        url = company["url"]
        tier = company["tier"]

        print(f"正在提取: {name} ({tier})")
        print(f"URL: {url}")

        result = extract_jobs_static(name, url)

        all_results["results"][name] = {
            "tier": tier,
            "url": url,
            **result
        }

        if result["status"] == "success":
            success_count += 1
        elif result["status"] == "suspect_zero":
            suspect_zero_count += 1
        elif result["status"] == "confirmed_zero":
            confirmed_zero_count += 1
        else:
            failed_count += 1

        print(f"  -> 状态: {result['status']}")
        print(f"  -> 方法: {result.get('extraction_method', result['method'])}")
        print(f"  -> 结果数: {result['result_count']}")
        if result.get('failure_tag'):
            print(f"  -> 失败原因: {result['failure_tag']}")
        if result.get('evidence', {}).get('ats_fingerprint'):
            print(f"  -> ATS: {result['evidence']['ats_fingerprint']}")
        print()

    # 统计总结
    print("="*80)
    print("统计总结")
    print("="*80)
    print(f"总数: {len(ACCESSIBLE_COMPANIES)}")
    print(f"成功提取: {success_count}")
    print(f"可疑零结果: {suspect_zero_count}")
    print(f"确认零结果: {confirmed_zero_count}")
    print(f"失败: {failed_count}")
    print()

    # 列出成功提取的公司
    if success_count > 0:
        print("成功提取的公司:")
        for name, result in all_results["results"].items():
            if result["status"] == "success":
                print(f"  - {name} ({result['tier']}): {result['result_count']} 个岗位 (方法: {result.get('extraction_method', result['method'])})")
        print()

    # 列出可疑零结果的公司
    if suspect_zero_count > 0:
        print("可疑零结果的公司（有招聘信号但未提取到岗位）:")
        for name, result in all_results["results"].items():
            if result["status"] == "suspect_zero":
                print(f"  - {name} ({result['tier']}): ATS={result['evidence'].get('ats_fingerprint', 'N/A')}")
        print()

    all_results["summary"] = {
        "total": len(ACCESSIBLE_COMPANIES),
        "success": success_count,
        "suspect_zero": suspect_zero_count,
        "confirmed_zero": confirmed_zero_count,
        "failed": failed_count,
    }

    # 保存结果
    output_path = "/home/ubuntu/.openclaw/workspace-projecta/data/consulting_static_extraction_2026-03-25.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
