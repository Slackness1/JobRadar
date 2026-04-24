#!/usr/bin/env python3
"""
咨询公司招聘入口 Discovery 脚本
探测 Tier B 及以上咨询公司的招聘入口和 ATS 家族
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from urllib.parse import urlparse, urljoin

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# 咨询公司列表（Tier B 及以上）
CONSULTING_COMPANIES = {
    "Tier S": [
        {"name": "McKinsey", "career_url": "https://www.mckinsey.com/careers"},
        {"name": "BCG", "career_url": "https://www.bcg.com/careers"},
        {"name": "Bain", "career_url": "https://www.bain.com/careers"},
    ],
    "Tier A": [
        {"name": "Oliver Wyman", "career_url": "https://www.oliverwyman.com/careers"},
        {"name": "Strategy&", "career_url": "https://www.strategyand.pwc.com/careers"},
        {"name": "Roland Berger", "career_url": "https://www.rolandberger.com/en/Careers"},
        {"name": "Kearney", "career_url": "https://www.kearney.com/careers"},
        {"name": "LEK", "career_url": "https://www.lek.com/careers"},
        {"name": "EY-Parthenon", "career_url": "https://www.ey.com/careers"},
    ],
    "Tier A-": [
        {"name": "Deloitte", "career_url": "https://www2.deloitte.com/cn/careers.html"},
        {"name": "PwC", "career_url": "https://www.pwccn.com/careers.html"},
        {"name": "EY", "career_url": "https://www.ey.com/cn/zh/careers"},
        {"name": "KPMG", "career_url": "https://home.kpmg/cn/zh/home/careers.html"},
        {"name": "Accenture", "career_url": "https://www.accenture.com/careers"},
        {"name": "IBM Consulting", "career_url": "https://www.ibm.com/careers"},
    ],
    "Tier B": [
        {"name": "Capgemini Invent", "career_url": "https://www.capgemini.com/careers"},
        {"name": "Protiviti", "career_url": "https://www.protiviti.com/careers"},
        {"name": "BearingPoint", "career_url": "https://www.bearingpoint.com/en/careers"},
        {"name": "ZS", "career_url": "https://www.zs.com/careers"},
        {"name": "OC&C", "career_url": "https://www.occstrategy.com/careers"},
        {"name": "BDA", "career_url": "https://www.bda.com/careers"},
    ],
}

# Tier B 的可选公司（若能找到明确校招入口）
OPTIONAL_TIER_B = [
    {"name": "A&M", "career_url": "https://www.alvarezandmarsal.com/careers"},
    {"name": "AlixPartners", "career_url": "https://www.alixpartners.com/careers"},
    {"name": "FTI", "career_url": "https://www.fticonsulting.com/careers"},
]

# ATS 家族检测规则
ATS_SIGNALS = {
    "Greenhouse": {
        "domain_patterns": ["greenhouse.io", "boards.greenhouse.io"],
        "script_patterns": ["greenhouse", "boards.greenhouse.io"],
        "dom_patterns": ["gh-app-id", "greenhouse-apply"],
    },
    "Lever": {
        "domain_patterns": ["jobs.lever.co", "lever.co"],
        "script_patterns": ["lever", "jobs.lever.co"],
        "dom_patterns": ["lever-application", "lever-careers"],
    },
    "Workday": {
        "domain_patterns": ["myworkdayjobs.com", "workday.com"],
        "script_patterns": ["workday", "myworkday"],
        "dom_patterns": ["workday", "css-1", "data-automation-id"],
    },
    "SmartRecruiters": {
        "domain_patterns": ["smartrecruiters.com", "jobs.smartrecruiters.com"],
        "script_patterns": ["smartrecruiters", "sr-"],
        "dom_patterns": ["smartrecruiters", "sr-job"],
    },
    "Moka": {
        "domain_patterns": ["mokahr.com", "moka.com"],
        "script_patterns": ["mokahr", "moka"],
        "dom_patterns": ["moka", "mokahr"],
    },
    "Taleo": {
        "domain_patterns": ["taleo.net", "taleo.com"],
        "script_patterns": ["taleo"],
        "dom_patterns": ["taleo", "ircweb"],
    },
    "iCIMS": {
        "domain_patterns": ["icims.com", "icims.com/platform"],
        "script_patterns": ["icims"],
        "dom_patterns": ["icims", "iCIMS_Container"],
    },
}


def detect_ats_family(url: str, html: str, scripts: List[str]) -> Optional[str]:
    """根据 URL、HTML 和 scripts 检测 ATS 家族"""
    url_lower = url.lower()
    html_lower = html.lower()
    scripts_lower = [s.lower() for s in scripts]

    for ats_name, signals in ATS_SIGNALS.items():
        # 检查域名
        for pattern in signals["domain_patterns"]:
            if pattern in url_lower:
                return ats_name

        # 检查 scripts
        for script in scripts_lower:
            for pattern in signals["script_patterns"]:
                if pattern in script:
                    return ats_name

        # 检查 DOM
        for pattern in signals["dom_patterns"]:
            if pattern.lower() in html_lower:
                return ats_name

    # 如果没有匹配到已知 ATS，检查是否为自定义 SPA
    spa_indicators = ["__NEXT_DATA__", "__NUXT__", "application/ld+json",
                      "react", "vue", "angular", "app-root", "next.js", "nuxt"]
    spa_count = sum(1 for indicator in spa_indicators if indicator in html_lower)

    if spa_count >= 2:
        return "custom_spa"

    return "custom"


def discover_static(url: str) -> Tuple[Optional[str], Dict]:
    """静态探测：检查 URL、HTML、scripts 中的 ATS 信号"""
    result = {
        "status": "unknown",
        "final_url": None,
        "page_title": None,
        "ats_family": None,
        "entry_url": None,
        "job_signal": False,
        "detail_links": [],
        "scripts": [],
        "failure_tags": [],
        "notes": [],
    }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        result["final_url"] = response.url
        result["status"] = response.status_code

        if response.status_code == 200:
            # 检查页面标题
            title_match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
            if title_match:
                result["page_title"] = title_match.group(1).strip()

            # 提取 scripts
            script_pattern = r'<script[^>]*src=["\']([^"\']+)["\']'
            result["scripts"] = re.findall(script_pattern, response.text)

            # 检测 ATS 家族
            result["ats_family"] = detect_ats_family(url, response.text, result["scripts"])

            # 检查 job 信号
            job_keywords = ["job", "career", "opening", "position", "opportunity", "vacancy"]
            html_lower = response.text.lower()
            result["job_signal"] = any(keyword in html_lower for keyword in job_keywords)

            # 收集疑似职位详情链接
            link_patterns = [
                r'href=["\'][^"\']*(?:job|career|position|opening|vacancy)[^"\']*["\']',
                r'href=["\'][^"\']*/(?:details?|view|post)[^"\']*["\']',
            ]
            for pattern in link_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                result["detail_links"].extend(matches)

            # 检查是否有明确的校招入口
            campus_keywords = ["campus", "campus recruitment", "graduate", "entry-level", "fresh graduate"]
            result["notes"].append(f"Campus keywords found: {any(kw in html_lower for kw in campus_keywords)}")

            # 检查是否是 Moka 平台
            if "mokahr.com" in url or "moka.com" in url:
                result["ats_family"] = "Moka"
                result["notes"].append("Detected Moka platform from URL")

        elif response.status_code == 404:
            result["failure_tags"].append("NOT_FOUND_404")
        else:
            result["failure_tags"].append(f"HTTP_{response.status_code}")

    except requests.exceptions.SSLError:
        result["status"] = "ssl_error"
        result["failure_tags"].append("SSL_ERROR")
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["failure_tags"].append("TIMEOUT")
    except requests.exceptions.ConnectionError:
        result["status"] = "connection_error"
        result["failure_tags"].append("CONNECTION_ERROR")
    except Exception as e:
        result["status"] = "error"
        result["failure_tags"].append(f"ERROR:{type(e).__name__}")

    return result["status"], result


async def discover_with_playwright(url: str) -> Tuple[Optional[str], Dict]:
    """使用 Playwright 进行动态探测"""
    result = {
        "status": "unknown",
        "final_url": None,
        "page_title": None,
        "ats_family": None,
        "entry_url": None,
        "job_signal": False,
        "detail_links": [],
        "scripts": [],
        "failure_tags": [],
        "notes": [],
    }

    if not PLAYWRIGHT_AVAILABLE:
        result["failure_tags"].append("PLAYWRIGHT_NOT_AVAILABLE")
        return None, result

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                result["final_url"] = page.url
                result["status"] = 200

                # 获取页面标题
                result["page_title"] = await page.title()

                # 获取 HTML
                html = await page.content()

                # 获取所有 script 标签
                scripts = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('script[src]'))
                        .map(s => s.getAttribute('src'));
                }""")
                result["scripts"] = scripts

                # 检测 ATS 家族
                result["ats_family"] = detect_ats_family(url, html, scripts)

                # 检查 job 信号
                job_keywords = ["job", "career", "opening", "position", "opportunity", "vacancy"]
                html_lower = html.lower()
                result["job_signal"] = any(keyword in html_lower for keyword in job_keywords)

                # 收集职位详情链接
                result["detail_links"] = await page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links
                        .map(a => a.getAttribute('href'))
                        .filter(href => href && (
                            href.includes('/job') ||
                            href.includes('/career') ||
                            href.includes('/position') ||
                            href.includes('/opening') ||
                            href.includes('/vacancy') ||
                            href.includes('/detail') ||
                            href.includes('/view')
                        ));
                }""")

                # 检查是否有校招入口
                campus_keywords = ["campus", "campus recruitment", "graduate", "entry-level", "fresh graduate"]
                result["notes"].append(f"Campus keywords found: {any(kw in html_lower for kw in campus_keywords)}")

                # 检查页面中的招聘相关文本
                await page.wait_for_timeout(2000)
                body_text = await page.evaluate("() => document.body.innerText")
                if "campus" in body_text.lower() or "graduate" in body_text.lower():
                    result["notes"].append("Campus/graduate text found in page body")

                # 尝试找到具体的招聘入口链接
                job_links = await page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    const jobLinks = links.filter(a => {
                        const text = a.innerText?.toLowerCase() || '';
                        const href = a.getAttribute('href')?.toLowerCase() || '';
                        return text.includes('campus') ||
                               text.includes('graduate') ||
                               text.includes('career') ||
                               href.includes('campus') ||
                               href.includes('graduate');
                    });
                    return jobLinks.map(a => ({
                        text: a.innerText?.trim(),
                        href: a.getAttribute('href')
                    })).filter(l => l.text && l.href);
                }""")

                if job_links:
                    result["entry_url"] = job_links[0]["href"]
                    result["notes"].append(f"Found job link: {job_links[0]['text']}")

                await browser.close()

            except Exception as e:
                await browser.close()
                result["failure_tags"].append(f"ERROR:{type(e).__name__}")

    except Exception as e:
        result["failure_tags"].append(f"PLAYWRIGHT_ERROR:{type(e).__name__}")

    return result["status"], result


def determine_status(result: Dict) -> str:
    """根据 Discovery 结果确定状态"""
    if result["status"] != 200 and result["status"] != "unknown":
        if "404" in str(result["status"]) or "NOT_FOUND_404" in result["failure_tags"]:
            return "entry_missing"
        elif "ssl" in str(result["status"]).lower() or "SSL_ERROR" in result["failure_tags"]:
            return "entry_missing"
        elif "timeout" in str(result["status"]).lower() or "TIMEOUT" in result["failure_tags"]:
            return "failed"
        elif "connection" in str(result["status"]).lower() or "CONNECTION_ERROR" in result["failure_tags"]:
            return "failed"
        else:
            return "failed"

    if not result["job_signal"]:
        return "entry_missing"

    if result["ats_family"] is None:
        return "suspect_zero"

    return "success"


def determine_next_step(result: Dict, company_name: str) -> str:
    """根据 Discovery 结果确定下一步"""
    status = determine_status(result)

    if status == "entry_missing":
        return "需要人工补充招聘入口"
    elif status == "failed":
        return "需要重试 Discovery 或人工确认网络问题"
    elif status == "suspect_zero":
        return "使用 Playwright 重新探测，或人工确认是否真的无岗位"
    elif status == "success":
        if result["ats_family"] == "Moka":
            return "使用 moka_crawler 进行提取"
        elif result["ats_family"] == "custom_spa":
            return "使用 Playwright 进行提取"
        else:
            return f"根据 ATS 家族 ({result['ats_family']}) 选择提取方式"
    else:
        return "人工确认"


async def main():
    """主函数：对所有咨询公司进行 Discovery"""
    all_results = {}

    # 合并 Tier B 可选公司
    all_tiers = CONSULTING_COMPANIES.copy()
    all_tiers["Tier B (Optional)"] = OPTIONAL_TIER_B

    for tier, companies in all_tiers.items():
        print(f"\n{'='*60}")
        print(f"Processing {tier}: {len(companies)} companies")
        print(f"{'='*60}")

        for company in companies:
            company_name = company["name"]
            career_url = company["career_url"]
            print(f"\n[{company_name}] {career_url}")

            # 先尝试静态探测
            print(f"  -> Static discovery...")
            static_status, static_result = discover_static(career_url)

            # 如果静态探测失败，尝试 Playwright
            if static_status != 200 and PLAYWRIGHT_AVAILABLE:
                print(f"  -> Static failed, trying Playwright...")
                playwright_status, playwright_result = await discover_with_playwright(career_url)
                if playwright_status == 200:
                    result = playwright_result
                    result["method"] = "playwright"
                else:
                    result = static_result
                    result["method"] = "static"
            else:
                result = static_result
                result["method"] = "static"

            # 确定状态和下一步
            result["tier"] = tier
            result["company_name"] = company_name
            result["career_url"] = career_url
            result["status"] = determine_status(result)
            result["next_step"] = determine_next_step(result, company_name)

            # 如果有 entry_url，转换为绝对 URL
            if result["entry_url"] and not result["entry_url"].startswith("http"):
                base_url = result["final_url"] or career_url
                result["entry_url"] = urljoin(base_url, result["entry_url"])

            all_results[company_name] = result

            # 输出摘要
            print(f"  -> ATS Family: {result['ats_family']}")
            print(f"  -> Status: {result['status']}")
            print(f"  -> Entry URL: {result['entry_url'] or result['final_url']}")
            print(f"  -> Job Signal: {result['job_signal']}")
            print(f"  -> Detail Links: {len(result['detail_links'])}")
            print(f"  -> Next Step: {result['next_step']}")

    # 保存结果
    output_file = "/home/ubuntu/.openclaw/workspace-projecta/data/consulting_discovery_2026-03-24.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Discovery complete! Results saved to: {output_file}")
    print(f"{'='*60}")

    # 输出统计
    total = len(all_results)
    success = sum(1 for r in all_results.values() if r["status"] == "success")
    entry_missing = sum(1 for r in all_results.values() if r["status"] == "entry_missing")
    suspect_zero = sum(1 for r in all_results.values() if r["status"] == "suspect_zero")
    failed = sum(1 for r in all_results.values() if r["status"] == "failed")

    print(f"\nSummary:")
    print(f"  Total: {total}")
    print(f"  Success: {success}")
    print(f"  Entry Missing: {entry_missing}")
    print(f"  Suspect Zero: {suspect_zero}")
    print(f"  Failed: {failed}")

    return all_results


if __name__ == "__main__":
    asyncio.run(main())
