#!/usr/bin/env python3
"""
银行春招 Discovery 和 Extraction 脚本

任务：
1. 对每家银行检测春招信号
2. 如果有春招信号，提取岗位
3. 记录每家银行的状态

约束：
- 只保留春招口径
- Discovery > Extraction
- 优先 API / 嵌入数据 / 稳定 HTML / Playwright fallback
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

# 添加路径
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace-projecta/JobRadar/backend')

import requests
from bs4 import BeautifulSoup

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 银行配置
BANK_CONFIGS = {
    "ccb": {
        "name": "建设银行",
        "base_url": "https://job.ccb.com",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
            "/recruitment/spring",
            "/zhaopin/spring",
            "/campus/2026",
            "/campus/2026spring",
        ]
    },
    "icbc": {
        "name": "工商银行",
        "base_url": "https://campus.icbc.com.cn",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/spring",
            "/campus/spring",
            "/recruitment/spring",
            "/2026spring",
            "/2026/spring",
            "/campus/2026",
        ]
    },
    "spdb": {
        "name": "浦发银行",
        "base_url": "https://job.spdb.com.cn",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
            "/recruitment/spring",
            "/zhaopin/spring",
            "/campus/2026spring",
        ]
    },
    "nbc": {
        "name": "宁波银行",
        "base_url": "https://zhaopin.nbcb.cn",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
            "/recruitment/spring",
            "/campus/2026spring",
            "/campus/2026",
        ]
    },
    "cmb": {
        "name": "招商银行",
        "base_url": "https://career.cmbchina.com",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
            "/recruitment/spring",
            "/campus/2026spring",
        ]
    },
    "cib": {
        "name": "兴业银行",
        "base_url": "https://job.cib.com.cn",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
            "/recruitment/spring",
        ]
    },
    "shrcb": {
        "name": "上海农商银行",
        "base_url": "https://job.shrcb.com",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
            "/recruitment/spring",
        ]
    },
    "bosc": {
        "name": "上海银行",
        "base_url": "https://bosc.zhiye.com",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
        ]
    },
    "czbank": {
        "name": "浙商银行",
        "base_url": "https://czbank.zhiye.com",
        "spring_keywords": ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"],
        "possible_spring_paths": [
            "/campus",
            "/campus/spring",
            "/spring",
        ]
    }
}


def get_session():
    """创建 requests session"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    return session


def check_spring_signal(page_content: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    """
    检查页面是否有春招信号

    Returns:
        (has_signal, matched_keywords)
    """
    page_content_lower = page_content.lower()
    matched_keywords = []

    for keyword in keywords:
        if keyword.lower() in page_content_lower:
            matched_keywords.append(keyword)

    has_signal = len(matched_keywords) > 0
    return has_signal, matched_keywords


def discover_spring_recruitment(bank_code: str, config: Dict, session: requests.Session) -> Dict:
    """
    Discover 银行的春招信号

    Returns:
        Dict with keys:
        - bank_code
        - bank_name
        - has_spring_signal (bool)
        - spring_urls (list of URLs with spring signal)
        - signal_evidence (dict of URL -> matched keywords)
        - failure_stage (str if failed)
        - failure_reason (str if failed)
    """
    result = {
        "bank_code": bank_code,
        "bank_name": config["name"],
        "base_url": config["base_url"],
        "has_spring_signal": False,
        "spring_urls": [],
        "signal_evidence": {},
        "failure_stage": None,
        "failure_reason": None,
        "tested_urls": [],
    }

    base_url = config["base_url"]
    keywords = config["spring_keywords"]
    possible_paths = config.get("possible_spring_paths", ["/"])

    # 测试主页
    logger.info(f"[{bank_code}] Testing main page: {base_url}")
    try:
        resp = session.get(base_url, timeout=15)
        result["tested_urls"].append(base_url)

        if resp.status_code != 200:
            result["failure_stage"] = "HTTP_ERROR"
            result["failure_reason"] = f"Main page returned {resp.status_code}"
            logger.warning(f"[{bank_code}] Main page failed: {resp.status_code}")
            # 继续尝试其他路径
        else:
            # 检查主页是否有春招信号
            has_signal, matched = check_spring_signal(resp.text, keywords)
            if has_signal:
                result["has_spring_signal"] = True
                result["spring_urls"].append(base_url)
                result["signal_evidence"][base_url] = matched
                logger.info(f"[{bank_code}] Main page has spring signal: {matched}")
                # 如果主页有信号，继续提取
                return result

    except requests.exceptions.SSLError as e:
        result["failure_stage"] = "SSL_ERROR"
        result["failure_reason"] = str(e)
        logger.error(f"[{bank_code}] SSL Error: {e}")
        return result
    except requests.exceptions.ConnectionError as e:
        result["failure_stage"] = "CONNECTION_ERROR"
        result["failure_reason"] = str(e)
        logger.error(f"[{bank_code}] Connection Error: {e}")
        return result
    except requests.exceptions.Timeout as e:
        result["failure_stage"] = "TIMEOUT"
        result["failure_reason"] = str(e)
        logger.error(f"[{bank_code}] Timeout: {e}")
        return result
    except Exception as e:
        result["failure_stage"] = "UNKNOWN_ERROR"
        result["failure_reason"] = str(e)
        logger.error(f"[{bank_code}] Unknown error: {e}")
        # 继续尝试其他路径

    # 测试可能的春招路径
    for path in possible_paths:
        url = urljoin(base_url, path)
        logger.info(f"[{bank_code}] Testing path: {url}")

        try:
            resp = session.get(url, timeout=15)
            result["tested_urls"].append(url)

            if resp.status_code == 200:
                has_signal, matched = check_spring_signal(resp.text, keywords)
                if has_signal:
                    result["has_spring_signal"] = True
                    result["spring_urls"].append(url)
                    result["signal_evidence"][url] = matched
                    logger.info(f"[{bank_code}] Found spring signal at {url}: {matched}")
                    # 保存页面内容用于后续提取
                    result["spring_page_content"] = resp.text
                    result["spring_page_url"] = url
                    return result
            elif resp.status_code == 500:
                logger.warning(f"[{bank_code}] {url} returned 500")
            elif resp.status_code == 404:
                logger.debug(f"[{bank_code}] {url} returned 404")
            else:
                logger.warning(f"[{bank_code}] {url} returned {resp.status_code}")

        except Exception as e:
            logger.warning(f"[{bank_code}] Failed to test {url}: {e}")
            continue

    # 如果没有发现春招信号，但主页可以访问，标记为"无春招信号但可访问"
    if not result["has_spring_signal"] and not result["failure_stage"]:
        result["failure_stage"] = "NO_SPRING_SIGNAL"
        result["failure_reason"] = "访问成功但未发现春招信号"

    return result


def extract_jobs_from_page(page_url: str, page_content: str, bank_code: str, bank_name: str) -> List[Dict]:
    """
    从页面中提取春招岗位

    Returns:
        List of job dicts
    """
    jobs = []
    soup = BeautifulSoup(page_content, 'html.parser')

    # 尝试多种选择器
    selectors = [
        ".job-list-item",
        ".position-item",
        ".job-item",
        "tr.job-row",
        ".recruit-item",
        ".position-card",
        ".job-card",
        "[class*='job']",
        "[class*='position']",
    ]

    for selector in selectors:
        job_elements = soup.select(selector)
        if job_elements:
            logger.info(f"[{bank_code}] Using selector '{selector}' found {len(job_elements)} elements")
            break
    else:
        logger.warning(f"[{bank_code}] No standard job selectors found, trying fallback")
        # Fallback: 查找所有包含职位信息的链接
        job_elements = soup.find_all("a", href=True)
        logger.info(f"[{bank_code}] Fallback: found {len(job_elements)} links")

    # 限制数量，避免过多
    max_jobs = 50
    processed = 0

    for job_elem in job_elements[:max_jobs]:
        try:
            # 提取职位标题
            title = None

            # 尝试多种方式提取标题
            title_selectors = [
                "h3, .job-title, .position-name, .title, .recruit-title",
                "td:first-child",  # 表格第一列
            ]

            for title_selector in title_selectors:
                title_elem = job_elem.select_one(title_selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break

            if not title:
                # 如果是链接，使用链接文本
                if job_elem.name == "a":
                    title = job_elem.get_text(strip=True)
                    if len(title) < 3 or len(title) > 100:
                        title = None

            if not title:
                continue

            # 过滤非职位标题
            if any(keyword in title for keyword in [
                "更多", "查看", "详情", "申请", "提交", "下一页",
                "首页", "上一页", "上一页", "返回", "搜索"
            ]):
                continue

            # 提取详情链接
            detail_url = None
            if job_elem.name == "a":
                detail_url = job_elem.get("href")
            else:
                link_elem = job_elem.select_one("a")
                if link_elem:
                    detail_url = link_elem.get("href")

            if detail_url:
                if not detail_url.startswith("http"):
                    detail_url = urljoin(page_url, detail_url)

            # 提取其他字段
            location = None
            location_elem = job_elem.select_one(".location, .city, .workplace, .place")
            if location_elem:
                location = location_elem.get_text(strip=True)

            department = None
            dept_elem = job_elem.select_one(".department, .dept")
            if dept_elem:
                department = dept_elem.get_text(strip=True)

            # 生成 job_id
            import hashlib
            job_id = hashlib.md5(f"{detail_url}_{title}_{bank_name}".encode('utf-8')).hexdigest()

            job_data = {
                "job_id": job_id,
                "source": f"bank-{bank_code}",
                "company": bank_name,
                "company_type_industry": "银行",
                "company_tags": "银行",
                "job_title": title,
                "location": location,
                "department": department,
                "application_status": "待申请",
                "job_stage": "campus",  # 假设是校园招聘
                "source_config_id": bank_code,
                "detail_url": detail_url,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "is_spring": True,  # 标记为春招
            }

            jobs.append(job_data)
            processed += 1

        except Exception as e:
            logger.warning(f"[{bank_code}] Failed to parse job element: {e}")
            continue

    logger.info(f"[{bank_code}] Extracted {len(jobs)} jobs")
    return jobs


def main():
    """主函数"""
    logger.info("Starting bank spring recruitment discovery")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # 优先目标
    priority_banks = [
        "ccb",  # 建设银行
        "icbc",  # 工商银行
        "spdb",  # 浦发银行
        "nbc",   # 宁波银行
        "cmb",   # 招商银行
        "cib",   # 兴业银行
        "shrcb", # 上海农商银行
        "bosc",  # 上海银行
        "czbank",# 浙商银行
    ]

    session = get_session()

    results = []
    summary = {
        "total_banks": len(priority_banks),
        "discovered_spring": 0,
        "extracted_jobs": 0,
        "failed_banks": 0,
        "no_signal_banks": 0,
        "details": []
    }

    for bank_code in priority_banks:
        if bank_code not in BANK_CONFIGS:
            logger.warning(f"[{bank_code}] Bank config not found, skipping")
            continue

        config = BANK_CONFIGS[bank_code]
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {config['name']} ({bank_code})")
        logger.info(f"{'='*60}")

        # Discovery
        discovery_result = discover_spring_recruitment(bank_code, config, session)
        results.append(discovery_result)

        # 提取
        if discovery_result["has_spring_signal"]:
            summary["discovered_spring"] += 1

            # 尝试提取岗位
            spring_url = discovery_result.get("spring_page_url")
            if spring_url and "spring_page_content" in discovery_result:
                jobs = extract_jobs_from_page(
                    spring_url,
                    discovery_result["spring_page_content"],
                    bank_code,
                    config["name"]
                )
                discovery_result["jobs"] = jobs
                discovery_result["job_count"] = len(jobs)
                summary["extracted_jobs"] += len(jobs)
            else:
                discovery_result["jobs"] = []
                discovery_result["job_count"] = 0
        else:
            # 记录失败原因
            if discovery_result["failure_stage"]:
                if discovery_result["failure_stage"] in ["SSL_ERROR", "CONNECTION_ERROR", "TIMEOUT", "HTTP_ERROR"]:
                    summary["failed_banks"] += 1
                elif discovery_result["failure_stage"] == "NO_SPRING_SIGNAL":
                    summary["no_signal_banks"] += 1

        summary["details"].append({
            "bank_code": bank_code,
            "bank_name": config["name"],
            "has_spring_signal": discovery_result["has_spring_signal"],
            "job_count": discovery_result.get("job_count", 0),
            "failure_stage": discovery_result["failure_stage"],
            "spring_urls": discovery_result.get("spring_urls", []),
        })

    # 输出总结
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total banks: {summary['total_banks']}")
    logger.info(f"Discovered spring: {summary['discovered_spring']}")
    logger.info(f"Total jobs extracted: {summary['extracted_jobs']}")
    logger.info(f"Failed banks: {summary['failed_banks']}")
    logger.info(f"No signal banks: {summary['no_signal_banks']}")

    # 保存结果
    output_dir = "/home/ubuntu/.openclaw/workspace-projecta/data"
    os.makedirs(output_dir, exist_ok=True)

    # 保存 JSON 结果
    json_file = os.path.join(output_dir, "bank_spring_round2_2026-03-25.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved results to: {json_file}")

    # 保存 Markdown 报告
    md_file = os.path.join(output_dir, "bank_spring_round2_2026-03-25.md")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# 银行春招 Discovery 和 Extraction - Round 2\n\n")
        f.write(f"**执行时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        f.write(f"**任务范围**: 只爬春招岗位\n\n")
        f.write(f"**执行模式**: Fallback Discovery（表内无春招记录）\n\n")

        f.write("## 执行说明\n\n")
        f.write("由于飞书表格中这批银行未发现明确的\"春招\"记录（很多是秋招或无记录），")
        f.write("本轮按既定规则进入 fallback：在表内无春招记录的前提下，")
        f.write("参考现有 config / 现有银行爬虫 / 官方入口做外部 spring-only discovery 和 extraction。\n\n")

        f.write("## 汇总\n\n")
        f.write(f"- **测试银行数**: {summary['total_banks']}\n")
        f.write(f"- **发现春招信号**: {summary['discovered_spring']}\n")
        f.write(f"- **提取岗位数**: {summary['extracted_jobs']}\n")
        f.write(f"- **技术失败**: {summary['failed_banks']}\n")
        f.write(f"- **无春招信号**: {summary['no_signal_banks']}\n\n")

        f.write("## 各银行详细结果\n\n")

        for detail in summary["details"]:
            bank_code = detail["bank_code"]
            bank_name = detail["bank_name"]
            has_spring = detail["has_spring_signal"]
            job_count = detail["job_count"]
            failure_stage = detail["failure_stage"]
            spring_urls = detail["spring_urls"]

            f.write(f"### {bank_name} ({bank_code})\n\n")
            f.write(f"- **春招信号**: {'✓' if has_spring else '✗'}\n")

            if has_spring:
                f.write(f"- **提取岗位数**: {job_count}\n")
                f.write(f"- **春招入口**: {', '.join(spring_urls)}\n")
            elif failure_stage:
                f.write(f"- **失败阶段**: {failure_stage}\n")
                if failure_stage == "NO_SPRING_SIGNAL":
                    f.write(f"- **状态**: 待确认春招（访问成功但未发现明确春招信号）\n")
                else:
                    f.write(f"- **状态**: 技术问题需要修复\n")
            else:
                f.write(f"- **状态**: 未测试\n")

            f.write("\n")

        f.write("## 技术说明\n\n")
        f.write("### 春招识别标准\n")
        f.write("- 页面包含关键词：春招、春季招聘、春季校园招聘、spring、春季校招\n\n")
        f.write("### 提取策略\n")
        f.write("- Discovery > Extraction\n")
        f.write("- 优先 API / 嵌入数据 / 稳定 HTML / Playwright fallback\n")
        f.write("- 只在确有春招信号时才算命中\n")
        f.write("- 如果只是校招总入口但无春招信号，标记为\"待确认春招\"\n\n")
        f.write("### 下一步建议\n")
        f.write("- 对技术失败的银行（SSL/Connection/Timeout）需要进一步诊断\n")
        f.write("- 对无春招信号的银行需要人工复核或等待表格更新\n")
        f.write("- 对已发现春招信号的银行可以继续完善提取逻辑\n\n")

    logger.info(f"Saved report to: {md_file}")

    return results, summary


if __name__ == "__main__":
    results, summary = main()
