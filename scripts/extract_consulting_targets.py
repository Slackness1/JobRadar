#!/usr/bin/env python3
"""
咨询公司专项 Extraction 脚本（同步版本）
按优先级提取 Tier B 及以上咨询公司的岗位
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'JobRadar', 'backend'))

from app.database import SessionLocal
from app.services.moka_crawler import crawl_moka_campus, create_moka_playwright, save_jobs_to_db

# 优先级顺序
PRIORITY_ORDER = {
    "Moka": [
        {"name": "PwC", "campus_url": "https://app.mokahr.com/campus_apply/pwc/148260"},
        {"name": "EY", "campus_url": "https://ey.hotjob.cn/wt/EY/web/index#/"},
    ],
    "Custom_Simple": [
        {"name": "LEK", "url": "https://www.lek.com/join-lek"},
        {"name": "ZS", "url": "https://jobs.zs.com/jobs"},
        {"name": "OC&C", "url": "https://careers.occstrategy.com/vacancies/vacancy-search-results.aspx"},
        {"name": "AlixPartners", "url": "https://www.alixpartners.com/careers/students-and-recent-graduates/"},
        {"name": "FTI", "url": "https://www.fticonsulting.com/careers"},
    ],
    "Custom_Complex": [
        {"name": "McKinsey", "url": "https://www.mckinsey.com/careers/students"},
        {"name": "BCG", "url": "https://careers.bcg.com/global/en/early-careers"},
        {"name": "Bain", "url": "https://www.bain.com/careers/work-with-us/students/"},
    ],
    "Custom_Other": [
        {"name": "Oliver Wyman", "url": "https://www.oliverwyman.com/careers.html"},
        {"name": "EY-Parthenon", "url": "https://www.ey.com/en_gl/careers"},
        {"name": "KPMG", "url": "https://kpmg.com/cn/zh/careers/campus.html"},
        {"name": "Accenture", "url": "https://www.accenture.com/sg-en/careers"},
        {"name": "IBM Consulting", "url": "https://www.ibm.com/careers"},
        {"name": "Capgemini Invent", "url": "https://www.capgemini.com/careers/career-paths/students-and-graduates/"},
        {"name": "Protiviti", "url": "https://www.protiviti.com/gl-en/careers"},
        {"name": "BearingPoint", "url": "https://www.bearingpoint.com/en/careers/graduates/"},
    ],
}


def extract_moka_companies(db, companies: List[Dict]) -> Dict[str, Any]:
    """提取 Moka 平台公司"""
    results = {}

    # 创建 Playwright 实例（复用）
    playwright = None
    browser = None

    try:
        playwright, browser = create_moka_playwright()

        for company in companies:
            company_name = company["name"]
            campus_url = company["campus_url"]

            print(f"\n{'='*60}")
            print(f"正在提取: {company_name} (Moka 平台)")
            print(f"{'='*60}")
            print(f"URL: {campus_url}")

            try:
                jobs = crawl_moka_campus(company_name, campus_url, playwright, browser)
                new_count = save_jobs_to_db(db, jobs)

                results[company_name] = {
                    "detected_family": "Moka",
                    "entry_url": campus_url,
                    "extraction_method": "moka_crawler",
                    "result_count": new_count,
                    "status": "success" if new_count > 0 else "suspect_zero",
                    "failure_tag": None,
                    "next_step": "已完成提取" if new_count > 0 else "使用 Playwright 重新验证",
                    "jobs": len(jobs),
                }

                print(f"  -> 结果: 新增 {new_count} 个岗位")
                print(f"  -> 状态: {results[company_name]['status']}")

            except Exception as e:
                results[company_name] = {
                    "detected_family": "Moka",
                    "entry_url": campus_url,
                    "extraction_method": "moka_crawler",
                    "result_count": 0,
                    "status": "failed",
                    "failure_tag": f"ERROR:{type(e).__name__}",
                    "next_step": "检查错误日志并重试",
                }
                print(f"  -> 失败: {str(e)}")

    finally:
        # 清理 Playwright 资源
        if browser:
            try:
                browser.close()
            except:
                pass
        if playwright:
            try:
                playwright.stop()
            except:
                pass

    return results


def extract_custom_companies(db, companies: List[Dict], complexity: str = "simple") -> Dict[str, Any]:
    """提取自建站点公司（使用 Playwright）"""
    results = {}

    for company in companies:
        company_name = company["name"]
        url = company["url"]

        print(f"\n{'='*60}")
        print(f"正在提取: {company_name} (自建 {complexity} 站点)")
        print(f"{'='*60}")
        print(f"URL: {url}")

        # 这里需要实现通用 Playwright 提取逻辑
        # 暂时标记为待实现
        results[company_name] = {
            "detected_family": "custom",
            "entry_url": url,
            "extraction_method": "Playwright (待实现)",
            "result_count": 0,
            "status": "pending",
            "failure_tag": "NOT_IMPLEMENTED",
            "next_step": "需要实现自定义 Playwright 提取逻辑",
        }

        print(f"  -> 状态: {results[company_name]['status']}")
        print(f"  -> 说明: 自定义站点提取逻辑待实现")

    return results


def main():
    """主函数：按优先级提取咨询公司岗位"""
    print("="*60)
    print("咨询公司专项 Extraction")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = {}
    db = SessionLocal()

    try:
        # 第一优先级：Moka 平台
        print(f"\n\n{'#'*60}")
        print(f"# 第一优先级：Moka 平台 (2 家)")
        print(f"{'#'*60}")

        moka_results = extract_moka_companies(
            db,
            PRIORITY_ORDER["Moka"]
        )
        all_results.update(moka_results)

        # 统计
        moka_success = sum(1 for r in moka_results.values() if r["status"] == "success")
        moka_zero = sum(1 for r in moka_results.values() if r["status"] == "suspect_zero")
        moka_failed = sum(1 for r in moka_results.values() if r["status"] == "failed")

        print(f"\nMoka 平台提取统计:")
        print(f"  Success: {moka_success}")
        print(f"  Suspect Zero: {moka_zero}")
        print(f"  Failed: {moka_failed}")

        # 第二优先级：简单自建站点（标记为待实现）
        print(f"\n\n{'#'*60}")
        print(f"# 第二优先级：简单自建站点 (5 家) - 待实现")
        print(f"{'#'*60}")

        simple_results = extract_custom_companies(
            db,
            PRIORITY_ORDER["Custom_Simple"],
            complexity="simple"
        )
        all_results.update(simple_results)

        # 第三优先级：复杂 SPA 站点（标记为待实现）
        print(f"\n\n{'#'*60}")
        print(f"# 第三优先级：复杂 SPA 站点 (3 家) - 待实现")
        print(f"{'#'*60}")

        complex_results = extract_custom_companies(
            db,
            PRIORITY_ORDER["Custom_Complex"],
            complexity="complex"
        )
        all_results.update(complex_results)

        # 第四优先级：其他自建站点（标记为待实现）
        print(f"\n\n{'#'*60}")
        print(f"# 第四优先级：其他自建站点 (8 家) - 待实现")
        print(f"{'#'*60}")

        other_results = extract_custom_companies(
            db,
            PRIORITY_ORDER["Custom_Other"],
            complexity="other"
        )
        all_results.update(other_results)

        # 总体统计
        total_companies = len(all_results)
        total_success = sum(1 for r in all_results.values() if r["status"] == "success")
        total_jobs = sum(r["result_count"] for r in all_results.values())

        print(f"\n\n{'='*60}")
        print(f"总体统计")
        print(f"{'='*60}")
        print(f"处理公司数: {total_companies}")
        print(f"成功提取: {total_success}")
        print(f"新增岗位: {total_jobs}")

        # 保存结果
        output_file = "/home/ubuntu/.openclaw/workspace-projecta/data/consulting_extraction_2026-03-24.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        print(f"\n结果已保存到: {output_file}")

    finally:
        db.close()

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    return all_results


if __name__ == "__main__":
    main()
