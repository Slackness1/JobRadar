#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查多维表格的分享设置
"""

import requests

APP_TOKEN = "QybYb9aQna9XeBsTf6xcPFnRngk"
TABLE_ID = "tblGAgR5CzuNZjZv"

def check_share_settings():
    """检查分享设置"""
    print("检查多维表格分享设置...")
    
    # 尝试访问公开分享链接
    # 飞书多维表格的公开分享链接格式可能是:
    # https://xxx.feishu.cn/base/xxx?table=xxx&view=xxx
    
    urls_to_try = [
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}",
        f"https://my.feishu.cn/base/{APP_TOKEN}",
    ]
    
    for url in urls_to_try:
        print(f"\n尝试: {url}")
        try:
            response = requests.get(url, timeout=10, allow_redirects=False)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 302:
                print(f"  重定向到: {response.headers.get('location')}")
        except Exception as e:
            print(f"  错误: {e}")

def main():
    print("="*60)
    print("多维表格访问测试")
    print("="*60)
    print(f"\nAPP_TOKEN: {APP_TOKEN}")
    print(f"TABLE_ID: {TABLE_ID}")
    print(f"完整链接: https://my.feishu.cn/base/{APP_TOKEN}?table={TABLE_ID}")
    
    check_share_settings()
    
    print("\n" + "="*60)
    print("诊断结果:")
    print("="*60)
    print("\n当前状态: 飞书应用无权访问该多维表格")
    print("\n可能的原因:")
    print("  1. 机器人应用未被添加为多维表格协作者")
    print("  2. 应用缺少 bitable:record:read 权限")
    print("  3. 多维表格未开启公开分享")
    print("\n建议解决方案:")
    print("\n方案A: 添加应用为协作者 (推荐)")
    print("  1. 打开多维表格")
    print("  2. 点击右上角 '分享' 或 '协作'")
    print("  3. 添加机器人: cli_a93bdf7772785cbb")
    print("  4. 授予 '可查看' 权限")
    print("\n方案B: 导出 CSV 文件 (最快)")
    print("  1. 在多维表格中点击 '...' 菜单")
    print("  2. 选择 '导出' → 'CSV'")
    print("  3. 发送 CSV 文件给我")
    print("  4. 我会立即统计所有春招记录")

if __name__ == "__main__":
    main()
