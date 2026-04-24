#!/usr/bin/env python3
"""
测试 custom_spa 公司招聘页面提取
使用 Playwright 提取岗位信息
"""
import asyncio
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

# from JobRadar.backend.app.database import engine
# from JobRadar.backend.app.models import Job


# 代理配置
PROXIES = {
    "server": "http://127.0.0.1:7890"
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _build_job_id(company: str, title: str) -> str:
    raw = f"custom_spa|{company}|{title}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]


def _infer_stage(*texts: str) -> str:
    merged = " ".join(_safe_text(t) for t in texts).lower()
    if "实习" in merged or "intern" in merged or "暑期" in merged:
        return "internship"
    return "campus"


async def extract_custom_spa(target: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """使用 Playwright 提取 custom_spa 招聘页面"""
    entry_url = target["entry_url"]
    company = target["name"]
    category = target.get("category", "")

    print(f"\n[Extraction] {company} ({category})")
    print(f"  entry_url: {entry_url}")

    records = []
    metadata = {
        "company": company,
        "category": category,
        "entry_url": entry_url,
        "detected_family": "custom_spa",
        "total_jobs": 0,
        "status": "failed",
        "failure_tags": [],
        "note": "",
    }

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                proxy=PROXIES,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            # 访问页面
            print(f"  访问页面...")
            await page.goto(entry_url, wait_until="domcontentloaded", timeout=30000)

            # 等待页面稳定
            await asyncio.sleep(3)

            # 获取页面信息
            title = await page.title()
            url = page.url
            print(f"  页面标题: {title}")
            print(f"  最终 URL: {url}")

            # 尝试检测职位列表特征
            page_content = await page.content()

            # 检测常见关键词
            job_keywords = ["职位", "岗位", "招聘", "job", "position", "opening", "campus", "校园"]
            found_keywords = [kw for kw in job_keywords if kw.lower() in page_content.lower()]
            print(f"  发现关键词: {found_keywords}")

            # 检测可能的职位链接
            job_links = await page.locator("a[href*='job'], a[href*='position'], a[href*='campus']").count()
            print(f"  发现疑似职位链接: {job_links}")

            # 检测是否有职位列表容器
            list_selectors = [
                "[class*='job']", "[class*='position']", "[class*='list']",
                "[id*='job']", "[id*='position']", "[id*='list']",
                "[class*='card']"
            ]

            for selector in list_selectors:
                count = await page.locator(selector).count()
                if count > 5:  # 假设至少 5 个职位卡片
                    print(f"  检测到列表容器 ({selector}): {count}")
                    break

            # 尝试提取职位卡片
            # 这里简化处理，只检测页面是否有职位信号
            if found_keywords and job_links > 0:
                metadata["status"] = "suspect_zero"
                metadata["failure_tags"] = []
                metadata["note"] = "发现职位信号，但未实现具体提取逻辑"
            else:
                metadata["status"] = "suspect_zero"
                metadata["failure_tags"] = ["NO_JOB_SIGNAL"]
                metadata["note"] = "未发现明显的职位信号"

            # 截图保存
            screenshot_path = Path(f"/home/ubuntu/.openclaw/workspace-projecta/data/screenshots/{company}_2026-03-24.png")
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"  截图保存: {screenshot_path}")

            await browser.close()

        except Exception as e:
            print(f"  ERROR: {e}")
            metadata["status"] = "failed"
            metadata["failure_tags"] = ["EXTRACTION_ERROR"]
            metadata["note"] = str(e)

    metadata["total_jobs"] = len(records)
    return records, metadata


async def main():
    """主函数"""
    print("="*60)
    print("Custom SPA 提取测试")
    print("="*60)

    # 测试目标
    targets = [
        {
            "name": "三一重能",
            "entry_url": "https://www.sanygroup.com/campus",
            "category": "风电整机",
        },
    ]

    results = []

    for target in targets:
        records, metadata = await extract_custom_spa(target)
        results.append({
            "target": target,
            "records": records,
            "metadata": metadata,
        })

    # 保存结果
    output_file = Path("/home/ubuntu/.openclaw/workspace-projecta/data/custom_spa_test_2026-03-24.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"测试完成，结果保存到: {output_file}")
    print(f"{'='*60}")

    # 统计
    total = len(results)
    success = sum(1 for r in results if r['metadata']['status'] == 'success')
    suspect_zero = sum(1 for r in results if r['metadata']['status'] == 'suspect_zero')
    failed = sum(1 for r in results if r['metadata']['status'] == 'failed')

    print(f"\n统计:")
    print(f"  总计: {total}")
    print(f"  成功: {success}")
    print(f"  可疑零结果: {suspect_zero}")
    print(f"  失败: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
