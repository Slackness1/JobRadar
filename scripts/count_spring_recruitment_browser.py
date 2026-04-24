#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过浏览器访问飞书多维表格，统计春招相关记录
"""

from playwright.sync_api import sync_playwright
import time
import sys

# 多维表格信息
APP_TOKEN = "QybYb9aQna9XeBsTf6xcPFnRngk"
TABLE_ID = "tblGAgR5CzuNZjZv"
BASE_URL = f"https://my.feishu.cn/base/{APP_TOKEN}"

def main():
    print("开始统计春招相关记录...")
    print(f"多维表格链接: {BASE_URL}")
    
    with sync_playwright() as p:
        # 启动浏览器
        print("\n1. 启动浏览器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        try:
            # 访问多维表格
            print("2. 访问多维表格...")
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)
            
            # 截图保存
            screenshot_path = "/home/ubuntu/.openclaw/workspace-projecta/data/screenshots/feishu_bitable.png"
            page.screenshot(path=screenshot_path)
            print(f"截图已保存: {screenshot_path}")
            
            # 检查是否需要登录
            if "login" in page.url or "passport" in page.url:
                print("\n需要登录才能访问该表格")
                print("解决方案:")
                print("  1. 在飞书中将多维表格设置为公开访问")
                print("  2. 或者导出数据为 CSV 文件")
                return
            
            # 尝试获取页面内容
            print("\n3. 获取页面内容...")
            
            # 等待表格加载
            try:
                page.wait_for_selector('[class*="table"]', timeout=10000)
            except:
                print("等待表格加载超时")
            
            # 获取页面标题
            title = page.title()
            print(f"页面标题: {title}")
            
            # 获取页面文本内容
            content = page.content()
            print(f"页面内容长度: {len(content)} 字符")
            
            # 尝试提取表格数据
            # 这里需要根据实际的页面结构来解析
            # 由于多维表格是动态加载的，可能需要更复杂的逻辑
            
            print("\n提示: 由于飞书多维表格需要登录或特定权限，建议:")
            print("  1. 在飞书多维表格中导出数据为 CSV")
            print("  2. 将 CSV 文件发送给我，我来帮你统计")
            
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            browser.close()

if __name__ == "__main__":
    main()
