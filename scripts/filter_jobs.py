#!/usr/bin/env python3
"""
filter_jobs.py - 根据目标岗位和日期筛选岗位

筛选条件：
1. 最近3天更新的岗位
2. 匹配目标岗位类型：数据挖掘/数据分析、投研、AI产品经理、咨询

使用方法：
python filter_jobs.py
python filter_jobs.py --days 7  # 自定义天数
"""

import csv
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Set

# ============ 配置 ============
INPUT_FILE = "D:/金融知识/爬虫/jobs.csv"
OUTPUT_FILE = "D:/金融知识/爬虫/filtered_jobs.csv"

# 目标岗位关键词（按类别分组）- 扩展版
TARGET_KEYWORDS = {
    "数据挖掘/数据分析": [
        # 核心关键词
        "数据挖掘", "数据分析", "数据科学", "Data Science", "Data Analyst", "Data Scientist",
        "DS", "DA", "DE", 
        # 数据工程
        "数据工程师", "数据开发", "ETL", "数据仓库", "数仓", "Data Warehouse",
        "大数据开发", "大数据工程师", "Hadoop", "Spark", "Flink", "Hive",
        # BI/商业分析
        "BI工程师", "商业分析", "Business Analyst", "BA", "BI分析师",
        "经营分析", "业务分析", "运营分析", "策略分析", "数据运营",
        # 算法/ML
        "算法工程师", "算法", "机器学习", "Machine Learning", "ML",
        "深度学习", "Deep Learning", "DL", "AI工程师", "人工智能",
        "数据建模", "模型", "预测模型", "NLP", "自然语言", "CV", "计算机视觉",
        # 量化/风控
        "量化分析", "量化", "Quant", "风控模型", "风控", "信用分析",
        "评分卡", "反欺诈", "风险模型", "征信",
        # 统计相关
        "统计", "统计学", "统计分析", "精算", "Actuary",
        # 其他
        "数据产品", "数据治理", "数据中台", "数据平台", "数据湖",
    ],
    "投研": [
        # 核心投研
        "投研", "投资研究", "行业研究", "研报", "研究",
        "证券研究", "股票研究", "权益研究", "Equity Research",
        # 宏观/策略
        "宏观研究", "宏观经济", "策略研究", "固收研究", "债券研究",
        "基金研究", "信用研究", "FICC",
        # 分析师
        "投资分析", "投资助理", "研究员", "证券分析师", "行业分析师",
        "分析师", "Analyst", "权益分析师", "信用分析师",
        # 量化/金工
        "量化研究", "量化分析师", "金融工程", "Financial Engineering",
        "衍生品", "期权", "期货", "资产配置", "量化交易",
        # 投资管理
        "基金经理", "投资经理", "交易员", "债券交易", "股票交易",
        "资管", "资产管理", "投资", "Portfolio",
        # 行业方向
        "TMT研究", "消费研究", "医药研究", "新能源研究", "金融研究",
        # ESG/另类
        "ESG", "ESG分析", "绿色金融", "碳中和",
    ],
    "AI产品经理": [
        # 核心产品
        "产品经理", "产品助理", "产品专员", "PM", "Product Manager",
        "产品", "Product", "产品策划", "产品规划",
        # AI/智能产品
        "AI产品", "人工智能产品", "AI PM", "AI产品经理",
        "算法产品", "智能产品", "智慧", "大模型产品", "LLM",
        "AIGC", "ChatGPT", "生成式AI", "GenAI",
        # 技术方向
        "NLP产品", "自然语言产品", "CV产品", "视觉产品",
        "语音产品", "ASR", "TTS", "推荐产品", "搜索产品",
        "知识图谱", "对话系统", "Chatbot",
        # 平台/ToB
        "数据产品经理", "平台产品", "ToB产品", "SaaS产品",
        "企业服务", "B端产品", "中台产品", "技术产品",
        # 创新方向
        "创新产品", "战略产品", "增长产品", "商业化产品",
    ],
    "咨询": [
        # 核心咨询
        "咨询", "Consultant", "Consulting", "顾问", "Advisory",
        # 管理咨询
        "管理咨询", "战略咨询", "Strategy", "战略", "企业管理咨询",
        "McKinsey", "BCG", "Bain", "MBB", "四大",
        # 技术咨询
        "IT咨询", "数字化咨询", "技术咨询", "技术咨询",
        "数字化转型", "信息化", "ERP", "SAP",
        # 业务咨询
        "业务咨询", "实施顾问", "解决方案", "售前", "解决方案顾问",
        "Pre-sales", "Technical Consultant",
        # 专业咨询
        "人力资源咨询", "财务咨询", "风险咨询", "税务咨询",
        "交易咨询", "并购咨询", "M&A",
        # 岗位
        "PTA", "咨询实习", "助理顾问", "咨询分析师",
        "分析员", "Associate", "分析师", "Analyst",
        # 战略/规划
        "战略规划", "战略分析", "商业规划", "业务规划",
        "投资分析", "市场研究", "竞争分析",
    ]
}

# 排除关键词（不想要的岗位类型）- 精简版，避免误伤
EXCLUDE_KEYWORDS = [
    # 明显不相关的职能
    "销售代表", "销售经理", "销售专员", "客户经理",  # 但保留"销售分析"
    "客服", "行政专员", "前台", "保洁", "保安", "司机",
    # 纯技术支持
    "物流专员", "仓储", "配送员",
    # 纯设计（排除过于宽泛的"设计"）
    "UI设计师", "UX设计师", "视觉设计师", "交互设计师",
    "平面设计", "美工", "插画师", 
    # 纯运维/网络
    "网络运维", "IT运维", "系统运维", "网络工程师",
    # 游戏相关
    "游戏开发", "游戏策划", "游戏运营", "特效师", "游戏美术",
    # 硬件相关
    "硬件工程师", "嵌入式开发", "单片机", "电子工程师", "电路设计",
    # 建筑/工程
    "建筑", "土木", "施工", "工程管理",
]


def parse_date(date_str: str) -> datetime:
    """解析日期字符串"""
    if not date_str:
        return None
    
    # 尝试多种格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:19] if 'T' in date_str else date_str, fmt)
        except:
            continue
    
    # 尝试只取日期部分
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except:
        return None


def matches_keywords(text: str, keywords: List[str]) -> tuple:
    """检查文本是否匹配关键词，返回 (是否匹配, 匹配的关键词)"""
    if not text:
        return False, []
    
    text_lower = text.lower()
    matched = []
    
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    
    return len(matched) > 0, matched


def should_exclude(text: str) -> tuple:
    """检查是否应该排除，返回 (是否排除, 匹配的排除词)"""
    if not text:
        return False, []
    
    text_lower = text.lower()
    excluded = []
    
    for kw in EXCLUDE_KEYWORDS:
        if kw.lower() in text_lower:
            excluded.append(kw)
    
    return len(excluded) > 0, excluded


def categorize_job(job: Dict) -> tuple:
    """
    为岗位分类
    返回 (类别列表, 匹配的关键词列表)
    """
    # 组合岗位相关字段
    job_text = " ".join([
        job.get("job_title", ""),
        job.get("job_req", ""),
        job.get("job_duty", ""),
        job.get("major_req", ""),
    ])
    
    # 先检查排除
    excluded, exclude_words = should_exclude(job_text)
    if excluded:
        return [], [], exclude_words
    
    # 检查每个类别
    categories = []
    all_matched_keywords = []
    
    for category, keywords in TARGET_KEYWORDS.items():
        matched, matched_kws = matches_keywords(job_text, keywords)
        if matched:
            categories.append(category)
            all_matched_keywords.extend(matched_kws)
    
    return categories, all_matched_keywords, []


def filter_jobs(days: int = 3, min_score: int = 1) -> List[Dict]:
    """
    筛选岗位
    
    Args:
        days: 最近N天的岗位
        min_score: 最低匹配分数（匹配的关键词数量）
    
    Returns:
        筛选后的岗位列表
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    print(f"[INFO] 筛选条件: 最近 {days} 天 (>= {cutoff_date.strftime('%Y-%m-%d')})")
    
    filtered_jobs = []
    stats = {
        "total": 0,
        "date_filtered": 0,
        "category_matched": 0,
        "excluded": 0,
        "by_category": {cat: 0 for cat in TARGET_KEYWORDS.keys()}
    }
    
    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats["total"] += 1
            
            # 1. 日期筛选
            publish_date = parse_date(row.get("publish_date", ""))
            if not publish_date or publish_date < cutoff_date:
                continue
            
            stats["date_filtered"] += 1
            
            # 2. 岗位分类
            categories, matched_keywords, exclude_words = categorize_job(row)
            
            if exclude_words:
                stats["excluded"] += 1
                continue
            
            if not categories:
                continue
            
            # 3. 添加筛选信息
            filtered_job = row.copy()
            filtered_job["matched_categories"] = "; ".join(categories)
            filtered_job["matched_keywords"] = "; ".join(list(set(matched_keywords))[:10])  # 最多10个
            filtered_job["match_score"] = len(matched_keywords)
            
            filtered_jobs.append(filtered_job)
            stats["category_matched"] += 1
            
            for cat in categories:
                stats["by_category"][cat] += 1
    
    # 打印统计信息
    print(f"\n[统计]")
    print(f"  总记录数: {stats['total']}")
    print(f"  最近{days}天: {stats['date_filtered']}")
    print(f"  排除(不相关): {stats['excluded']}")
    print(f"  匹配目标岗位: {stats['category_matched']}")
    print(f"\n[按类别]")
    for cat, count in stats["by_category"].items():
        print(f"  {cat}: {count}")
    
    return filtered_jobs


def save_filtered_jobs(jobs: List[Dict], output_file: str):
    """保存筛选后的岗位"""
    if not jobs:
        print("[WARN] 没有符合条件的岗位")
        return
    
    # 输出字段（在原有字段基础上添加筛选信息）
    base_fields = [
        "job_id", "company", "company_type_industry", "company_tags",
        "department", "job_title", "location", "major_req",
        "job_req", "job_duty", "publish_date", "deadline",
        "detail_url", "matched_categories", "matched_keywords", "match_score"
    ]
    
    # 按匹配分数和发布日期排序
    jobs.sort(key=lambda x: (-x.get("match_score", 0), x.get("publish_date", "")), reverse=False)
    jobs.sort(key=lambda x: -x.get("match_score", 0))  # 分数高的在前
    
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=base_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
    
    print(f"\n[SUCCESS] 保存 {len(jobs)} 条记录到: {output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="筛选目标岗位")
    parser.add_argument("--days", type=int, default=3, help="筛选最近N天的岗位（默认3天）")
    parser.add_argument("--input", default=INPUT_FILE, help="输入CSV文件")
    parser.add_argument("--output", default=OUTPUT_FILE, help="输出CSV文件")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("岗位筛选器")
    print("=" * 50)
    print(f"目标类别: {', '.join(TARGET_KEYWORDS.keys())}")
    print(f"输入文件: {args.input}")
    print(f"输出文件: {args.output}")
    print("=" * 50)
    
    # 筛选
    filtered = filter_jobs(days=args.days)
    
    # 保存
    save_filtered_jobs(filtered, args.output)


if __name__ == "__main__":
    main()
