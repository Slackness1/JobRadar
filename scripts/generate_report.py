#!/usr/bin/env python3
"""
generate_report.py - 生成岗位推荐MD报告
"""

import csv
from datetime import datetime
from collections import defaultdict

INPUT_FILE = "D:/金融知识/爬虫/filtered_jobs.csv"
OUTPUT_FILE = "D:/金融知识/爬虫/今日岗位推荐.md"

def generate_report():
    # 读取筛选后的数据
    jobs = []
    with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        jobs = list(reader)
    
    # 按类别分组
    categories = defaultdict(list)
    for job in jobs:
        for cat in job['matched_categories'].split('; '):
            categories[cat].append(job)
    
    # 按分数排序
    for cat in categories:
        categories[cat].sort(key=lambda x: -int(x.get('match_score', 0)))
    
    # 生成MD内容
    md = []
    md.append(f"# 每日岗位推荐报告")
    md.append(f"")
    md.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"> 数据来源: 塔塔网申 (tatawangshen.com)")
    md.append(f"> 筛选范围: 最近3天更新的岗位")
    md.append(f"")
    md.append(f"---")
    md.append(f"")
    md.append(f"## 统计概览")
    md.append(f"")
    md.append(f"| 类别 | 数量 |")
    md.append(f"|------|------|")
    total = 0
    for cat_name in ["数据挖掘/数据分析", "投研", "AI产品经理", "咨询"]:
        count = len(categories.get(cat_name, []))
        total += count
        md.append(f"| {cat_name} | {count} |")
    md.append(f"| **总计** | **{len(jobs)}** |")
    md.append(f"")
    md.append(f"---")
    md.append(f"")
    
    # 高分推荐区
    md.append(f"## ⭐ 高匹配度推荐 (Top 20)")
    md.append(f"")
    md.append(f"按匹配分数排序，优先关注这些岗位：")
    md.append(f"")
    
    # 取前20个高分岗位
    top_jobs = sorted(jobs, key=lambda x: -int(x.get('match_score', 0)))[:20]
    
    for i, job in enumerate(top_jobs, 1):
        score = job.get('match_score', '0')
        title = job.get('job_title', '')[:35]
        company = job.get('company', '')[:20]
        dept = job.get('department', '')[:20] if job.get('department') else ''
        location = job.get('location', '')[:20] if job.get('location') else '未标注'
        date = job.get('publish_date', '')[:10]
        cats = job.get('matched_categories', '')
        keywords = job.get('matched_keywords', '')[:60]
        url = job.get('detail_url', '')
        
        md.append(f"### {i}. {title}")
        md.append(f"")
        md.append(f"| 属性 | 信息 |")
        md.append(f"|------|------|")
        md.append(f"| 公司 | **{company}** |")
        if dept:
            md.append(f"| 部门 | {dept} |")
        md.append(f"| 地点 | {location} |")
        md.append(f"| 发布 | {date} |")
        md.append(f"| 匹配分数 | **{score}** |")
        md.append(f"| 岗位类别 | {cats} |")
        md.append(f"| 匹配关键词 | {keywords} |")
        if url:
            md.append(f"| 链接 | [查看详情]({url}) |")
        md.append(f"")
    
    md.append(f"---")
    md.append(f"")
    
    # 按类别详细展示
    category_icons = {
        "数据挖掘/数据分析": "📊",
        "投研": "📈",
        "AI产品经理": "🤖",
        "咨询": "💼"
    }
    
    for cat_name in ["数据挖掘/数据分析", "投研", "AI产品经理", "咨询"]:
        cat_jobs = categories.get(cat_name, [])
        if not cat_jobs:
            continue
        
        icon = category_icons.get(cat_name, "📋")
        md.append(f"## {icon} {cat_name} ({len(cat_jobs)}条)")
        md.append(f"")
        
        # 每类显示前30条
        for i, job in enumerate(cat_jobs[:30], 1):
            title = job.get('job_title', '')[:40]
            company = job.get('company', '')[:15]
            location = job.get('location', '')[:15] if job.get('location') else '未标注'
            date = job.get('publish_date', '')[:10]
            score = job.get('match_score', '0')
            url = job.get('detail_url', '')
            
            if url:
                md.append(f"{i}. **{title}** | {company} | {location} | {date} | 分数:{score}")
                md.append(f"   [链接]({url})")
            else:
                md.append(f"{i}. **{title}** | {company} | {location} | {date} | 分数:{score}")
            md.append(f"")
        
        if len(cat_jobs) > 30:
            md.append(f"> *...还有 {len(cat_jobs)-30} 条岗位，详见 filtered_jobs.csv*")
            md.append(f"")
        
        md.append(f"---")
        md.append(f"")
    
    # 底部说明
    md.append(f"## 使用说明")
    md.append(f"")
    md.append(f"- **匹配分数**: 基于岗位标题、要求、职责中匹配关键词的数量计算")
    md.append(f"- **岗位类别**: 可能跨多个类别，一个岗位可能同时属于数据分析和AI产品")
    md.append(f"- **完整数据**: 所有筛选结果保存在 `filtered_jobs.csv`，可用Excel打开查看")
    md.append(f"")
    md.append(f"### 每日更新命令")
    md.append(f"")
    md.append(f"```bash")
    md.append(f"# 1. 抓取最新数据")
    md.append(f"python auto_login_scraper.py --max-pages 100")
    md.append(f"")
    md.append(f"# 2. 筛选目标岗位")
    md.append(f"python filter_jobs.py --days 3")
    md.append(f"")
    md.append(f"# 3. 生成报告")
    md.append(f"python generate_report.py")
    md.append(f"```")
    
    # 写入文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    
    print(f"[SUCCESS] 报告已生成: {OUTPUT_FILE}")
    print(f"[INFO] 共 {len(jobs)} 条岗位推荐")

if __name__ == "__main__":
    generate_report()
