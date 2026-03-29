#!/usr/bin/env python3
"""测试代理配置是否可用"""
import os
from playwright.sync_api import sync_playwright

PROXY_SERVER = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7890"

def test_proxy():
    print(f"使用代理: {PROXY_SERVER}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_SERVER}
        )

        try:
            page = browser.new_page()
            print("\n尝试访问 https://www.baidu.com")
            response = page.goto("https://www.baidu.com", wait_until="networkidle", timeout=30000)

            if response:
                print(f"HTTP 状态码: {response.status}")
                print(f"页面标题: {page.title()}")
                print("\n✓ 代理配置正确！")
            else:
                print("\n✗ 响应为空")

            page.close()
            browser.close()

        except Exception as e:
            print(f"\n✗ 错误: {e}")
            try:
                browser.close()
            except:
                pass

if __name__ == "__main__":
    test_proxy()
