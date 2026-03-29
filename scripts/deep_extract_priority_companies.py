#!/usr/bin/env python3
"""
咨询公司优先级深度提取脚本
目标：埃森哲、ZS、OC&C、毕马威
优先级：公开API > 内嵌JSON/hydration > 稳定HTML > Playwright fallback
避免Playwright，优先绕开
"""
import json
import re
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


class ConsultingExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.results = {}

    def extract_from_url(self, url: str, method: str = "auto") -> Dict[str, Any]:
        """从URL提取岗位信息，自动选择最佳方法"""
        print(f"\n[DEBUG] 开始提取: {url}")
        print(f"[DEBUG] 使用方法: {method}")

        result = {
            "url": url,
            "method": method,
            "status": "failed",
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {},
            "error": None,
            "blocking_point": None
        }

        try:
            # 尝试1：公开API探测
            if method in ["auto", "api"]:
                api_result = self._try_api_extraction(url)
                if api_result["jobs_count"] > 0:
                    result.update(api_result)
                    result["method"] = "api"
                    return result

            # 尝试2：内嵌JSON/hydration
            if method in ["auto", "hydration"]:
                html_result = self._try_hydration_extraction(url)
                if html_result["jobs_count"] > 0:
                    result.update(html_result)
                    result["method"] = "hydration"
                    return result

            # 尝试3：稳定HTML解析
            if method in ["auto", "html"]:
                html_result = self._try_html_extraction(url)
                if html_result["jobs_count"] > 0:
                    result.update(html_result)
                    result["method"] = "html"
                    return result

            # 所有方法都失败
            result["status"] = "no_jobs_extracted"
            result["blocking_point"] = "no_method_worked"
            result["error"] = "所有提取方法都未返回岗位"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["blocking_point"] = "exception"

        return result

    def _try_api_extraction(self, url: str) -> Dict[str, Any]:
        """尝试从API提取"""
        print(f"[DEBUG] 尝试API提取...")

        result = {
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {}
        }

        # Workday API模式
        if "accenture" in url.lower() or "workday" in url.lower():
            return self._try_workday_api(url)

        # Moka API模式
        if "mokahr" in url.lower() or "moka" in url.lower():
            return self._try_moka_api(url)

        # Yello Enterprise模式
        if "recsolu" in url.lower():
            return self._try_yello_api(url)

        return result

    def _try_hydration_extraction(self, url: str) -> Dict[str, Any]:
        """尝试从内嵌JSON/hydration数据提取"""
        print(f"[DEBUG] 尝试hydration提取...")

        result = {
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {}
        }

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            html = response.text

            # 搜索常见的内嵌数据模式
            patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({[^;]+});',
                r'__NEXT_DATA__.*?type="application/json">(.*?)</script>',
                r'window\.__NUXT__\s*=\s*({[^;]+});',
                r'application/ld\+json">(.*?)</script>',
                r'data-job\s*=\s*"([^"]+)"',
                r'"jobs"\s*:\s*(\[[^\]]+\])',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                if matches:
                    print(f"[DEBUG] 找到hydration数据模式: {pattern[:50]}...")

                    for match in matches:
                        try:
                            data = json.loads(match)

                            # 尝试提取岗位信息
                            jobs = self._extract_jobs_from_json(data, url)
                            if jobs:
                                result["jobs_count"] = len(jobs)
                                result["jobs"] = jobs
                                result["raw_data"]["hydration"] = str(data)[:500]
                                print(f"[DEBUG] Hydration提取成功: {len(jobs)}个岗位")
                                return result

                        except json.JSONDecodeError as e:
                            print(f"[DEBUG] JSON解析失败: {e}")
                            continue

        except Exception as e:
            print(f"[DEBUG] Hydration提取失败: {e}")

        return result

    def _try_html_extraction(self, url: str) -> Dict[str, Any]:
        """尝试从稳定HTML解析"""
        print(f"[DEBUG] 尝试HTML提取...")

        result = {
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {}
        }

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 多种岗位提取模式
            job_patterns = [
                # 通用class模式
                ('class', 'job-title'),
                ('class', 'jobTitle'),
                ('class', 'position-title'),
                ('class', 'role-title'),
                # Workday特定模式
                ('data-automation-id', 'jobTitle'),
                # Moka特定模式
                ('class', 'job-name'),
                # Yello特定模式
                ('class', 'job-posting-title'),
            ]

            jobs = []

            for attr_name, attr_value in job_patterns:
                elements = soup.find_all(attrs={attr_name: attr_value})
                if elements:
                    print(f"[DEBUG] 找到{len(elements)}个{attr_name}={attr_value}元素")

                    for elem in elements:
                        title = elem.get_text(strip=True)
                        if title and len(title) > 3:
                            # 查找关联链接
                            link = None
                            parent_link = elem.find_parent('a')
                            if parent_link and parent_link.get('href'):
                                link = urljoin(url, parent_link.get('href'))

                            job = {
                                "title": title,
                                "url": link,
                                "method": "html_selector"
                            }

                            # 避免重复
                            if not any(j["title"] == title for j in jobs):
                                jobs.append(job)

                    if jobs:
                        break

            if jobs:
                result["jobs_count"] = len(jobs)
                result["jobs"] = jobs
                print(f"[DEBUG] HTML提取成功: {len(jobs)}个岗位")
            else:
                print(f"[DEBUG] HTML提取未找到岗位")

        except Exception as e:
            print(f"[DEBUG] HTML提取失败: {e}")

        return result

    def _try_workday_api(self, url: str) -> Dict[str, Any]:
        """尝试提取Workday平台的API"""
        print(f"[DEBUG] 尝试Workday API...")

        result = {
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {}
        }

        try:
            # Workday通常有API endpoint
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            # 尝试常见的API endpoint
            api_patterns = [
                f"{base_url}/wday/cxs/monolith/accenture/jobs",
                f"{base_url}/wday/cxs/monolith/accenture/jobs/",
            ]

            for api_url in api_patterns:
                try:
                    response = self.session.get(api_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()

                        # 提取岗位
                        jobs = []
                        for job_data in data.get("jobPostings", []):
                            job = {
                                "title": job_data.get("title"),
                                "url": job_data.get("externalPath"),
                                "method": "workday_api"
                            }
                            if job["title"]:
                                jobs.append(job)

                        if jobs:
                            result["jobs_count"] = len(jobs)
                            result["jobs"] = jobs
                            result["raw_data"]["workday_api"] = str(data)[:500]
                            print(f"[DEBUG] Workday API提取成功: {len(jobs)}个岗位")
                            return result

                except Exception as e:
                    print(f"[DEBUG] Workday API {api_url} 失败: {e}")
                    continue

        except Exception as e:
            print(f"[DEBUG] Workday API探测失败: {e}")

        return result

    def _try_moka_api(self, url: str) -> Dict[str, Any]:
        """尝试提取Moka平台的API"""
        print(f"[DEBUG] 尝试Moka API...")

        result = {
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {}
        }

        try:
            # Moka通常有API endpoint
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            # 尝试常见的API endpoint
            api_patterns = [
                f"{base_url}/api/external/jobs",
                f"{base_url}/api/jobs",
            ]

            for api_url in api_patterns:
                try:
                    response = self.session.get(api_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()

                        # 提取岗位
                        jobs = []
                        for job_data in data.get("data", {}).get("list", []):
                            job = {
                                "title": job_data.get("name"),
                                "url": job_data.get("url"),
                                "method": "moka_api"
                            }
                            if job["title"]:
                                jobs.append(job)

                        if jobs:
                            result["jobs_count"] = len(jobs)
                            result["jobs"] = jobs
                            result["raw_data"]["moka_api"] = str(data)[:500]
                            print(f"[DEBUG] Moka API提取成功: {len(jobs)}个岗位")
                            return result

                except Exception as e:
                    print(f"[DEBUG] Moka API {api_url} 失败: {e}")
                    continue

        except Exception as e:
            print(f"[DEBUG] Moka API探测失败: {e}")

        return result

    def _try_yello_api(self, url: str) -> Dict[str, Any]:
        """尝试提取Yello Enterprise平台的API"""
        print(f"[DEBUG] 尝试Yello Enterprise API...")

        result = {
            "jobs_count": 0,
            "jobs": [],
            "raw_data": {}
        }

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Yello Enterprise的岗位通常在a标签中
            jobs = []
            job_links = soup.find_all('a', href=re.compile(r'/jobs/'))

            for link in job_links:
                title = link.get_text(strip=True)
                href = link.get('href')

                if title and len(title) > 5 and 'job' in href.lower():
                    job = {
                        "title": title,
                        "url": urljoin(url, href),
                        "method": "yello_html"
                    }

                    # 避免重复
                    if not any(j["title"] == title for j in jobs):
                        jobs.append(job)

            if jobs:
                result["jobs_count"] = len(jobs)
                result["jobs"] = jobs
                print(f"[DEBUG] Yello HTML提取成功: {len(jobs)}个岗位")

        except Exception as e:
            print(f"[DEBUG] Yello API探测失败: {e}")

        return result

    def _extract_jobs_from_json(self, data: Any, base_url: str) -> List[Dict[str, str]]:
        """从JSON数据中提取岗位信息"""
        jobs = []

        def extract_from_dict(d):
            if isinstance(d, dict):
                # 查找常见的岗位字段
                for key in ['jobs', 'jobPostings', 'positions', 'openings', 'vacancies']:
                    if key in d and isinstance(d[key], list):
                        for item in d[key]:
                            if isinstance(item, dict):
                                title = item.get('title') or item.get('name') or item.get('position')
                                url = item.get('url') or item.get('externalPath') or item.get('link')

                                if title:
                                    jobs.append({
                                        "title": title,
                                        "url": url,
                                        "method": "json_extraction"
                                    })

                # 递归查找
                for v in d.values():
                    extract_from_dict(v)

            elif isinstance(d, list):
                for item in d:
                    extract_from_dict(item)

        extract_from_dict(data)
        return jobs


def main():
    """主函数：提取4家优先公司"""
    extractor = ConsultingExtractor()

    # 定义4家公司的目标URL
    targets = {
        "埃森哲": [
            "https://www.accenture.com/cn-zh/careers/jobsearch?jk=&sb=1&vw=0&is_rj=0&pg=1",
            "https://careersite.tupu360.com/accentureats/position/index?recruitmentType=CAMPUSRECRUITMENT&jobCategory="
        ],
        "ZS": [
            "https://jobs.zs.com/jobs",
            # 如果上面失败，尝试从公告页提取
        ],
        "OC&C": [
            "https://careers.occstrategy.com/vacancies/vacancy-search-results.aspx",
        ],
        "毕马威": [
            "https://app.mokahr.com/campus-recruitment/kpmg/76195#/jobs?1841380=Audit&page=1&anchorName=jobsList&keyword=&project0=100032245",
            "https://kpmg.com/cn/zh/careers/campus/graduate-applications.html",
        ]
    }

    results = {}

    for company, urls in targets.items():
        print(f"\n{'='*60}")
        print(f"开始处理: {company}")
        print(f"{'='*60}")

        company_results = []

        for url in urls:
            if not url:
                continue

            print(f"\n尝试URL: {url}")
            result = extractor.extract_from_url(url, method="auto")
            company_results.append(result)

            # 找到第一个成功的URL就停止
            if result["jobs_count"] > 0:
                print(f"✓ 找到 {result['jobs_count']} 个岗位，停止尝试其他URL")
                break

            time.sleep(1)  # 避免请求过快

        # 汇总这家公司的结果
        results[company] = {
            "company": company,
            "status": "success" if any(r["jobs_count"] > 0 for r in company_results) else "failed",
            "total_jobs": sum(r["jobs_count"] for r in company_results),
            "all_results": company_results,
            "best_result": max(company_results, key=lambda x: x["jobs_count"]) if company_results else None
        }

    # 保存结果
    timestamp = "2026-03-25"
    output_file = f"/home/ubuntu/.openclaw/workspace-projecta/data/consulting_priority_round2_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成！")
    print(f"{'='*60}")
    print(f"\n结果已保存到: {output_file}")

    # 打印汇总
    print("\n汇总:")
    for company, data in results.items():
        status = "✓ 成功" if data["status"] == "success" else "✗ 失败"
        print(f"  {company}: {status} - {data['total_jobs']} 个岗位")

        if data["best_result"]:
            br = data["best_result"]
            print(f"    方法: {br.get('method', 'N/A')}")
            print(f"    URL: {br.get('url', 'N/A')}")

            if br.get("blocking_point"):
                print(f"    阻塞点: {br['blocking_point']}")
            if br.get("error"):
                print(f"    错误: {br['error']}")

    return results


if __name__ == "__main__":
    results = main()
