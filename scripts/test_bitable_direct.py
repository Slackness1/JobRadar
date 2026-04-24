#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接尝试访问多维表格并统计数据
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

def try_get_fields(token):
    """尝试获取字段列表"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    result = response.json()
    
    print(f"获取字段结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result

def try_get_records(token):
    """尝试获取记录"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    params = {"page_size": 1}  # 先尝试获取1条
    
    response = requests.get(url, headers=headers, params=params)
    result = response.json()
    
    print(f"\n获取记录结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result

def main():
    print("测试多维表格访问...")
    print(f"APP_TOKEN: {APP_TOKEN}")
    print(f"TABLE_ID: {TABLE_ID}")
    
    # 1. 获取 token
    print("\n1. 获取 access token...")
    token = get_tenant_access_token()
    if not token:
        print("✗ 获取 token 失败")
        return
    print(f"✓ Token: {token[:20]}...")
    
    # 2. 尝试获取字段
    print("\n2. 尝试获取字段...")
    fields_result = try_get_fields(token)
    
    if fields_result.get("code") == 0:
        print("\n✓ 成功获取字段!")
        
        # 3. 尝试获取记录
        print("\n3. 尝试获取记录...")
        records_result = try_get_records(token)
        
        if records_result.get("code") == 0:
            print("\n✓ 成功获取记录!")
        else:
            print(f"\n✗ 获取记录失败: {records_result.get('msg')}")
    else:
        error_code = fields_result.get("code")
        error_msg = fields_result.get("msg")
        
        print(f"\n✗ 获取字段失败: {error_msg} (code: {error_code})")
        
        if error_code == 91403:
            print("\n错误分析:")
            print("  91403 = Forbidden (权限不足)")
            print("\n解决方法:")
            print("  1. 在多维表格设置中，添加机器人应用为协作者")
            print("  2. 或者在飞书开放平台配置 bitable:record:read 权限")
            print("  3. 或者导出 CSV 文件供我统计")

if __name__ == "__main__":
    main()
