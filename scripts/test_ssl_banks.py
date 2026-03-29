#!/usr/bin/env python3
"""
测试 SSL 错误的银行（禁用 SSL 验证）

警告：仅用于测试，不推荐用于生产
"""

import sys
import ssl
import urllib3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 创建不验证 SSL 的上下文
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 银行配置
SSL_BANKS = {
    "ccb": {
        "name": "建设银行",
        "base_url": "https://job.ccb.com",
    },
    "icbc": {
        "name": "工商银行",
        "base_url": "https://campus.icbc.com.cn",
    },
    "nbc": {
        "name": "宁波银行",
        "base_url": "https://zhaopin.nbcb.cn",
    },
    "shrcb": {
        "name": "上海农商银行",
        "base_url": "https://job.shrcb.com",
    },
}

# 春招关键词
SPRING_KEYWORDS = ["春招", "春季招聘", "春季校园招聘", "spring", "春季校招"]


def check_spring_signal(page_content: str) -> bool:
    """检查是否有春招信号"""
    page_content_lower = page_content.lower()
    return any(keyword.lower() in page_content_lower for keyword in SPRING_KEYWORDS)


def test_bank_no_ssl(bank_code: str, config: dict):
    """测试银行（不验证 SSL）"""
    print(f"\n{'='*60}")
    print(f"Testing: {config['name']} ({bank_code})")
    print(f"{'='*60}")

    base_url = config["base_url"]

    # 创建不验证 SSL 的 session
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })

    results = {
        "bank_code": bank_code,
        "bank_name": config["name"],
        "base_url": base_url,
        "status": "unknown",
        "spring_signal": False,
        "title": "",
        "error": None,
        "tested_urls": [],
    }

    # 测试主页
    print(f"Testing: {base_url}")

    try:
        # 禁用 SSL 验证
        resp = session.get(base_url, verify=False, timeout=15)
        results["tested_urls"].append(base_url)

        if resp.status_code == 200:
            print(f"✓ Status: 200 OK")
            print(f"✓ Content length: {len(resp.text)}")

            # 解析页面
            soup = BeautifulSoup(resp.text, 'html.parser')
            results["title"] = soup.title.string.strip() if soup.title else "No title"

            print(f"✓ Title: {results['title'][:100]}")

            # 检查春招信号
            has_spring = check_spring_signal(resp.text)
            results["spring_signal"] = has_spring

            if has_spring:
                print(f"✓ Spring signal found!")
                results["status"] = "success_with_spring"
            else:
                print(f"✗ No spring signal")
                results["status"] = "success_no_spring"

            # 保存 HTML
            output_file = f"/tmp/{bank_code}_homepage.html"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"✓ Saved HTML to: {output_file}")

        else:
            print(f"✗ Status: {resp.status_code}")
            results["status"] = f"http_{resp.status_code}"

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        results["status"] = "error"
        results["error"] = str(e)

    return results


def main():
    """主函数"""
    print("="*60)
    print("SSL Error Banks Test (No SSL Verification)")
    print("="*60)
    print("Warning: SSL verification is disabled for testing only\n")

    all_results = []

    for bank_code, config in SSL_BANKS.items():
        result = test_bank_no_ssl(bank_code, config)
        all_results.append(result)

    # 汇总
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    success_count = 0
    spring_count = 0
    error_count = 0

    for result in all_results:
        status = result["status"]
        print(f"\n{result['bank_name']} ({result['bank_code']}):")
        print(f"  Status: {status}")

        if status.startswith("success"):
            success_count += 1
            if result["spring_signal"]:
                spring_count += 1
        else:
            error_count += 1

    print(f"\nTotal: {len(all_results)}")
    print(f"Success: {success_count}")
    print(f"Spring signal: {spring_count}")
    print(f"Error: {error_count}")

    # 保存结果
    import json
    output_file = "/home/ubuntu/.openclaw/workspace-projecta/data/ssl_banks_test_2026-03-25.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": "2026-03-25T12:40:00Z",
            "results": all_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved results to: {output_file}")


if __name__ == "__main__":
    main()
