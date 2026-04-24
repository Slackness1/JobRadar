#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尝试通过不同的方式访问飞书多维表格
"""

import requests
import json

# 多维表格信息
APP_TOKEN = "QybYb9aQna9XeBsTf6xcPFnRngk"
TABLE_ID = "tblGAgR5CzuNZjZv"

def test_public_access():
    """测试是否支持公开访问"""
    print("测试公开访问...")
    
    # 尝试获取多维表格的公开信息
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}"
    
    # 不需要 token 的请求（测试公开访问）
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        result = response.json()
        print(f"公开访问结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result
    except Exception as e:
        print(f"公开访问失败: {e}")
        return None

def check_share_link():
    """检查分享链接信息"""
    print("\n检查分享链接...")
    
    # 飞书多维表格可能有分享 token
    # 尝试从 URL 参数中获取分享信息
    url = f"https://my.feishu.cn/base/{APP_TOKEN}"
    
    try:
        response = requests.get(url, allow_redirects=False, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"重定向 URL: {response.headers.get('location', '无')}")
        return response
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def main():
    print("开始测试多维表格访问方式...")
    print(f"多维表格 APP_TOKEN: {APP_TOKEN}")
    print(f"数据表 TABLE_ID: {TABLE_ID}\n")
    
    # 测试 1: 公开访问
    test_public_access()
    
    # 测试 2: 检查分享链接
    check_share_link()
    
    print("\n" + "="*60)
    print("建议:")
    print("1. 检查多维表格是否开启了'公开分享'功能")
    print("2. 在飞书多维表格设置中，添加机器人应用为协作者")
    print("3. 或导出 CSV 文件供我统计")

if __name__ == "__main__":
    main()
