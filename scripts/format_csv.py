#!/usr/bin/env python3
"""
format_csv.py - 将 jobs.csv 转换为更易读的格式
"""
import csv
import os

INPUT_FILE = "D:/金融知识/爬虫/jobs.csv"
OUTPUT_FILE = "D:/金融知识/爬虫/jobs_formatted.csv"

NEW_ORDER = [
    "job_title",
    "company",
    "location",
    "department",
    "major_req",
    "company_type_industry",
    "company_tags",
    "publish_date",
    "deadline",
    "job_duty",
    "job_req",
    "detail_url",
    "job_id",
    "referral_code",
    "apply_url",
    "scraped_at",
]

NEW_HEADERS = {
    "job_title": "岗位名称",
    "company": "公司",
    "location": "工作地点",
    "department": "部门",
    "major_req": "专业要求",
    "company_type_industry": "公司性质/行业",
    "company_tags": "公司标签",
    "publish_date": "发布时间",
    "deadline": "截止时间",
    "job_duty": "岗位职责",
    "job_req": "岗位要求",
    "detail_url": "详情链接",
    "job_id": "岗位ID",
    "referral_code": "内推码",
    "apply_url": "投递链接",
    "scraped_at": "抓取时间",
}

def truncate(text, max_len=100):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] 文件不存在: {INPUT_FILE}")
        return
    
    rows = []
    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        old_fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)
    
    print(f"[INFO] 读取 {len(rows)} 条记录")
    
    new_fieldnames = [NEW_HEADERS.get(f, f) for f in NEW_ORDER if f in old_fieldnames]
    
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        
        for row in rows:
            new_row = {}
            for old_key in NEW_ORDER:
                if old_key not in old_fieldnames:
                    continue
                new_key = NEW_HEADERS.get(old_key, old_key)
                value = row.get(old_key, "")
                if old_key in ["job_duty", "job_req"]:
                    value = truncate(value, 200)
                new_row[new_key] = value
            writer.writerow(new_row)
    
    print(f"[INFO] 已保存到: {OUTPUT_FILE}")
    print(f"[INFO] 列顺序: {', '.join(new_fieldnames)}")

if __name__ == "__main__":
    main()
