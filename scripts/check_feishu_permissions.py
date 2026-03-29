#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查飞书应用权限并尝试访问多维表格
"""

import requests
import json

# 飞书应用凭证
APP_ID = "cli_a93bdf7772785cbb"
APP_SECRET = "v7FNu403TLwOVlbsAnrrIhgrj4PQPf1v"

# 多维表格信息
APP_TOKEN = "QybYb9aQna9XeBsTf6xcPFnRngk"
TABLE_ID = "tblGAgR5CzuNZjZv"

def get_tenant_access_token():
    """获取 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    if result.get("code") != 0:
        print(f"获取 token 失败: {result}")
        return None
    
    return result["tenant_access_token"]

def check_app_permissions(token):
    """检查应用权限"""
    print("\n检查应用权限...")
    
    # 获取应用信息
    url = "https://open.feishu.cn/open-apis/auth/v3/app_permissions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    result = response.json()
    print(f"应用权限: {json.dumps(result, indent=2, ensure_ascii=False)}")

def try_bitable_access(token):
    """尝试访问多维表格"""
    print("\n尝试访问多维表格...")
    
    # 1. 尝试获取多维表格元信息
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    result = response.json()
    print(f"多维表格元信息: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # 2. 尝试获取字段列表
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    response = requests.get(url, headers=headers)
    result = response.json()
    print(f"\n字段列表: {json.dumps(result, indent=2, ensure_ascii=False)}")

def main():
    print("开始检查飞书应用权限...")
    
    # 1. 获取 token
    print("\n1. 获取 access token...")
    token = get_tenant_access_token()
    if not token:
        return
    print(f"✓ Token 获取成功")
    
    # 2. 检查权限
    check_app_permissions(token)
    
    # 3. 尝试访问多维表格
    try_bitable_access(token)
    
    print("\n" + "="*60)
    print("如果仍然返回 91403 错误，需要:")
    print("1. 在飞书开放平台添加权限: bitable:record:read")
    print("2. 在多维表格中添加机器人应用为协作者")
    print("3. 或者导出 CSV 文件供我统计")

if __name__ == "__main__":
    main()
