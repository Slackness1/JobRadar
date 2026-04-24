#!/usr/bin/env python3
"""
咨询公司专项 Extraction 脚本 V2
轻量级提取未处理的 Tier B 及以上咨询公司
优先检查内嵌 JSON / API，其次 Playwright
"""

import json
import sys
import os
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'JobRadar', 'backend'))

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("Playwright 未安装，跳过浏览器提取")
    async_playwright = None

# 未处理的公司列表
UNPROCESSED_COMPANIES = [
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
]

# 需要重试 discovery 的公司
RETRY_DISCOVERY_COMPANIES = [
    {"name": "Strategy&", "url": "https://www.strategyand.pwc.com/careers", "tier": "Tier A", "old_status": "entry_missing"},
    {"name": "Roland Berger", "url": "https://www.rolandberger.com/en/Careers", "tier": "Tier A", "old_status": "entry_missing"},
    {"name": "Kearney", "url": "https://www.kearney.com/careers", "tier": "Tier A", "old_status": "failed"},
    {"name": "Deloitte", "url": "https://www2.deloitte.com/cn/careers.html", "tier": "Tier A-", "old_status": "entry_missing"},
    {"name": "BDA", "url": "https://www.bda.com/careers", "tier": "Tier B", "old_status": "entry_missing"},
    {"name": "A&M", "url": "https://www.alvarezandmarsal.com/careers", "tier": "Tier B (Optional)", "old_status": "failed"},
]


class SimpleExtractor:
    """轻量级提取器"""

    def __init__(self):
        self.results = {}

    async def extract_with_playwright(self, name: str, url: str) -> Dict[str, Any]:
        """使用 Playwright 提取（轻量级）"""
        if not async_playwright:
            return {
                "status": "failed",
                "method": "none",
                "result_count": 0,
                "failure_tag": "PLAYWRIGHT_NOT_AVAILABLE",
                "evidence": {}
            }

        async with async_playwright() as p:
            browser = None
            page = None
            try:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")

                # 获取页面基本信息
                title = await page.title()
                content = await page.content()

                # 收集证据
                evidence = {
                    "title": title,
                    "final_url": page.url,
                    "job_keywords_found": self._check_job_keywords(content),
                    "ats_fingerprint": self._detect_ats(content, url),
                    "has_detail_links": self._has_detail_links(content),
                    "json_data_found": self._find_json_data(content),
                }

                # 尝试提取岗位（轻量级）
                jobs = await self._extract_jobs_lightweight(page, content)

                if jobs:
                    return {
                        "status": "success",
                        "method": "playwright_lightweight",
                        "result_count": len(jobs),
                        "failure_tag": None,
                        "evidence": evidence,
                        "jobs": jobs[:5],  # 只返回前 5 个作为示例
                    }
                else:
                    # 区分 confirmed zero vs suspect zero
                    if evidence["job_keywords_found"] or evidence["has_detail_links"] or evidence["json_data_found"]:
                        return {
                            "status": "suspect_zero",
                            "method": "playwright_lightweight",
                            "result_count": 0,
                            "failure_tag": "JOB_SIGNAL_BUT_ZERO_EXTRACTED",
                            "evidence": evidence,
                        }
                    else:
                        return {
                            "status": "confirmed_zero",
                            "method": "playwright_lightweight",
                            "result_count": 0,
                            "failure_tag": "NO_JOB_SIGNAL",
                            "evidence": evidence,
                        }

            except Exception as e:
                return {
                    "status": "failed",
                    "method": "playwright_lightweight",
                    "result_count": 0,
                    "failure_tag": f"ERROR:{type(e).__name__}",
                    "error_message": str(e),
                }
            finally:
                if page:
                    await page.close()
                if browser:
                    await browser.close()

    def _check_job_keywords(self, html: str) -> bool:
        """检查页面是否包含招聘相关关键词"""
        keywords = ["job", "opening", "position", "vacancy", "requisition", "职位", "岗位", "招聘"]
        html_lower = html.lower()
        return any(keyword in html_lower for keyword in keywords)

    def _detect_ats(self, html: str, url: str) -> str:
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

    def _has_detail_links(self, html: str) -> bool:
        """检查是否有职位详情链接"""
        # 简单检查：查找包含 job, opening, position, vacancy 等关键词的链接
        job_link_patterns = [
            r'href="[^"]*job[^"]*"',
            r'href="[^"]*opening[^"]*"',
            r'href="[^"]*position[^"]*"',
            r'href="[^"]*vacancy[^"]*"',
            r'href="[^"]*requisition[^"]*"',
        ]
        return any(re.search(pattern, html, re.IGNORECASE) for pattern in job_link_patterns)

    def _find_json_data(self, html: str) -> Dict[str, Any]:
        """查找内嵌 JSON 数据"""
        json_data = {}

        # 查找常见的 JSON 脚本标签
        json_patterns = [
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
            r'window\.__NEXT_DATA__\s*=\s*(.*?);',
            r'window\.__NUXT__\s*=\s*(.*?);',
            r'window\.__INITIAL_STATE__\s*=\s*(.*?);',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            if matches:
                try:
                    data = json.loads(matches[0])
                    json_data["json_found"] = True
                    json_data["json_keys"] = list(data.keys()) if isinstance(data, dict) else []
                    break
                except:
                    pass

        return json_data

    async def _extract_jobs_lightweight(self, page: Page, html: str) -> List[Dict[str, Any]]:
        """轻量级提取岗位（只提取基本信息）"""
        jobs = []

        try:
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle", timeout=5000)

            # 尝试查找常见的职位卡片选择器
            selectors = [
                "[data-test='job-item']",
                "[data-testid='job-item']",
                ".job-card",
                ".job-item",
                ".opening-card",
                ".vacancy-item",
                ".job-listing",
                "article.job",
                "li.job",
            ]

            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for element in elements[:10]:  # 最多提取 10 个
                            try:
                                title = await element.inner_text()
                                if title and len(title.strip()) > 3:
                                    jobs.append({
                                        "title": title.strip(),
                                        "selector": selector,
                                    })
                            except:
                                pass
                        if jobs:
                            break
                except:
                    pass

        except:
            pass

        return jobs


async def main():
    """主函数"""
    print("="*80)
    print("咨询公司专项 Extraction V2 - 轻量级提取")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    extractor = SimpleExtractor()
    all_results = {
        "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "unprocessed": {},
        "retry_discovery": {},
        "summary": {}
    }

    # 第一部分：提取未处理的公司
    print(f"\n{'#'*80}")
    print(f"# 第一部分：提取未处理的 10 家公司")
    print(f"{'#'*80}\n")

    for company in UNPROCESSED_COMPANIES:
        name = company["name"]
        url = company["url"]
        tier = company["tier"]

        print(f"正在处理: {name} ({tier})")
        print(f"URL: {url}")

        result = await extractor.extract_with_playwright(name, url)

        all_results["unprocessed"][name] = {
            "tier": tier,
            "url": url,
            **result
        }

        print(f"  -> 状态: {result['status']}")
        print(f"  -> 方法: {result['method']}")
        print(f"  -> 结果数: {result['result_count']}")
        if result.get('failure_tag'):
            print(f"  -> 失败原因: {result['failure_tag']}")
        print()

    # 第二部分：重试 discovery
    print(f"\n{'#'*80}")
    print(f"# 第二部分：重试 discovery (6 家)")
    print(f"{'#'*80}\n")

    for company in RETRY_DISCOVERY_COMPANIES:
        name = company["name"]
        url = company["url"]
        tier = company["tier"]
        old_status = company["old_status"]

        print(f"正在重试: {name} ({tier}) - 原状态: {old_status}")
        print(f"URL: {url}")

        result = await extractor.extract_with_playwright(name, url)

        all_results["retry_discovery"][name] = {
            "tier": tier,
            "url": url,
            "old_status": old_status,
            **result
        }

        print(f"  -> 新状态: {result['status']}")
        print(f"  -> 方法: {result['method']}")
        print(f"  -> 结果数: {result['result_count']}")
        if result.get('failure_tag'):
            print(f"  -> 失败原因: {result['failure_tag']}")
        print()

    # 统计总结
    print(f"\n{'#'*80}")
    print(f"# 统计总结")
    print(f"{'#'*80}\n")

    # 未处理公司的统计
    unprocessed_stats = {
        "total": len(all_results["unprocessed"]),
        "success": sum(1 for r in all_results["unprocessed"].values() if r["status"] == "success"),
        "suspect_zero": sum(1 for r in all_results["unprocessed"].values() if r["status"] == "suspect_zero"),
        "confirmed_zero": sum(1 for r in all_results["unprocessed"].values() if r["status"] == "confirmed_zero"),
        "failed": sum(1 for r in all_results["unprocessed"].values() if r["status"] == "failed"),
    }

    # 重试 discovery 的统计
    retry_stats = {
        "total": len(all_results["retry_discovery"]),
        "success": sum(1 for r in all_results["retry_discovery"].values() if r["status"] == "success"),
        "suspect_zero": sum(1 for r in all_results["retry_discovery"].values() if r["status"] == "suspect_zero"),
        "confirmed_zero": sum(1 for r in all_results["retry_discovery"].values() if r["status"] == "confirmed_zero"),
        "failed": sum(1 for r in all_results["retry_discovery"].values() if r["status"] == "failed"),
        "needs_manual_entry": [],  # 需要人工补入口的公司
    }

    # 找出仍需要人工补入口的公司
    for name, result in all_results["retry_discovery"].items():
        if result["status"] in ["failed", "confirmed_zero"] and result.get("old_status") == "entry_missing":
            retry_stats["needs_manual_entry"].append(name)

    print("未处理公司统计:")
    print(f"  总数: {unprocessed_stats['total']}")
    print(f"  成功提取: {unprocessed_stats['success']}")
    print(f"  可疑零结果: {unprocessed_stats['suspect_zero']}")
    print(f"  确认零结果: {unprocessed_stats['confirmed_zero']}")
    print(f"  失败: {unprocessed_stats['failed']}")
    print()

    print("重试 Discovery 统计:")
    print(f"  总数: {retry_stats['total']}")
    print(f"  成功提取: {retry_stats['success']}")
    print(f"  可疑零结果: {retry_stats['suspect_zero']}")
    print(f"  确认零结果: {retry_stats['confirmed_zero']}")
    print(f"  失败: {retry_stats['failed']}")
    print(f"  仍需人工补入口: {retry_stats['needs_manual_entry']}")
    print()

    all_results["summary"] = {
        "unprocessed_stats": unprocessed_stats,
        "retry_stats": retry_stats,
    }

    # 保存结果
    output_path = "/home/ubuntu/.openclaw/workspace-projecta/data/consulting_extraction_v2_2026-03-25.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
