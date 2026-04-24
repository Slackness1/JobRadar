#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计飞书多维表格中所有春招相关的记录数量
"""

import requests
import json
import sys

# 飞书应用凭证
# 默认账户
APP_ID = "cli_a93bdf7772785cbb"
APP_SECRET = "v7FNu403TLwOVlbsAnrrIhgrj4PQPf1v"

# project-b 账户
APP_ID_B = "cli_a9388fc2ab791cd3"
APP_SECRET_B = "W56ZuyIfl9ONZviaLYLPOEOxK0pasCYO"

# 多维表格信息
APP_TOKEN = "QybYb9aQna9XeBsTf6xcPFnRngk"
TABLE_ID = "tblGAgR5CzuNZjZv"

def get_tenant_access_token(use_account_b=False):
    """获取 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    
    # 尝试不同的账户
    if use_account_b:
        app_id = APP_ID_B
        app_secret = APP_SECRET_B
    else:
        app_id = APP_ID
        app_secret = APP_SECRET
    
    data = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    if result.get("code") != 0:
        print(f"获取 token 失败: {result}")
        return None
    
    return result["tenant_access_token"]

def get_table_fields(token):
    """获取表格字段信息"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    result = response.json()
    
    if result.get("code") != 0:
        print(f"获取字段失败: {result}")
        return None
    
    return result["data"]["items"]

def get_all_records(token, filter_conditions=None):
    """获取所有记录（支持分页）"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    all_records = []
    page_token = None
    
    while True:
        data = {"page_size": 500}
        if page_token:
            data["page_token"] = page_token
        if filter_conditions:
            data["filter"] = filter_conditions
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") != 0:
            print(f"查询记录失败: {result}")
            break
        
        items = result["data"].get("items", [])
        all_records.extend(items)
        
        page_token = result["data"].get("page_token")
        if not page_token or not result["data"].get("has_more"):
            break
    
    return all_records

def main():
    print("开始统计春招相关记录...")
    
    # 1. 获取 access token（尝试两个账户）
    print("\n1. 获取 access token...")
    
    # 先尝试默认账户
    token = get_tenant_access_token(use_account_b=False)
    account_name = "默认账户"
    
    if not token:
        print("默认账户失败，尝试 project-b 账户...")
        token = get_tenant_access_token(use_account_b=True)
        account_name = "project-b 账户"
    
    if not token:
        print("✗ 所有账户都无法获取 token")
        return
    
    print(f"✓ Token 获取成功（使用 {account_name}）")
    
    # 2. 获取字段信息
    print("\n2. 获取表格字段信息...")
    fields = get_table_fields(token)
    if not fields:
        print("✗ 获取字段失败")
        print("\n可能的原因:")
        print("  1. 飞书应用没有被授权访问该多维表格")
        print("  2. 需要在飞书开放平台配置 bitable:record:read 权限")
        print("  3. 需要表格管理员将应用添加为协作者")
        return
    
    # 找到招聘类型字段
    recruitment_type_field = None
    for field in fields:
        if field["field_name"] in ["招聘类型", "类型"]:
            recruitment_type_field = field
            break
    
    if not recruitment_type_field:
        print("✗ 未找到'招聘类型'字段")
        print("\n可用字段:")
        for field in fields:
            print(f"  - {field['field_name']} ({field['type']})")
        return
    
    print(f"✓ 找到字段: {recruitment_type_field['field_name']}")
    
    # 获取招聘类型的所有选项
    options = recruitment_type_field.get("property", {}).get("options", [])
    print(f"\n招聘类型选项:")
    for opt in options:
        print(f"  - {opt['name']}")
    
    # 3. 统计所有包含"春招"的记录
    print("\n3. 统计春招相关记录...")
    
    spring_keywords = ["春招", "26春招", "25春招", "春季", "Spring"]
    spring_records = []
    
    # 方案1: 先获取所有记录，然后过滤
    print("正在获取所有记录...")
    all_records = get_all_records(token)
    print(f"总记录数: {len(all_records)}")
    
    # 过滤包含春招关键词的记录
    for record in all_records:
        fields_data = record.get("fields", {})
        recruitment_type = fields_data.get(recruitment_type_field["field_name"], "")
        
        # 如果是字符串，直接检查
        if isinstance(recruitment_type, str):
            if any(keyword in recruitment_type for keyword in spring_keywords):
                spring_records.append(record)
        # 如果是列表（多选），检查每个选项
        elif isinstance(recruitment_type, list):
            if any(any(keyword in opt for keyword in spring_keywords) for opt in recruitment_type):
                spring_records.append(record)
    
    print(f"\n✓ 统计完成!")
    print(f"总记录数: {len(all_records)}")
    print(f"春招相关记录数: {len(spring_records)}")
    
    # 按招聘类型分组统计
    print("\n按招聘类型分组统计:")
    type_stats = {}
    for record in spring_records:
        fields_data = record.get("fields", {})
        recruitment_type = fields_data.get(recruitment_type_field["field_name"], "")
        
        # 处理多选字段
        if isinstance(recruitment_type, list):
            type_str = ", ".join(recruitment_type)
        else:
            type_str = recruitment_type
        
        type_stats[type_str] = type_stats.get(type_str, 0) + 1
    
    for type_name, count in sorted(type_stats.items(), key=lambda x: -x[1]):
        print(f"  {type_name}: {count} 条")

if __name__ == "__main__":
    main()
