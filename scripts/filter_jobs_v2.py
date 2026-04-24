#!/usr/bin/env python3
"""
filter_jobs_v2.py - 基于配置文件的岗位筛选器

特点：
1. 所有规则从 config.yaml 读取，代码不包含硬编码规则
2. 支持 5 个赛道独立评分
3. 支持技能同义词匹配
4. 支持硬性过滤条件
5. 支持阈值控制
"""

import csv
import os
import re
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict

# ============ 配置加载 ============

def load_config(config_path: str = None) -> Dict:
    """加载配置文件"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============ 日期解析 ============

def parse_date(date_str: str) -> datetime:
    """解析日期字符串"""
    if not date_str:
        return None
    
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
    
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except:
        return None


# ============ 关键词匹配 ============

def expand_keywords_with_synonyms(keywords: List[str], synonyms: Dict) -> List[str]:
    """扩展关键词，加入同义词"""
    expanded = set(keywords)
    
    for kw in keywords:
        kw_lower = kw.lower()
        for skill_name, skill_data in synonyms.items():
            if kw_lower == skill_data['canonical'].lower():
                expanded.update(s.lower() for s in skill_data['synonyms'])
            for syn in skill_data['synonyms']:
                if kw_lower == syn.lower():
                    expanded.add(skill_data['canonical'])
                    expanded.update(s.lower() for s in skill_data['synonyms'])
    
    return list(expanded)


def match_keywords(text: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    """检查文本是否匹配关键词"""
    if not text:
        return False, []
    
    text_lower = text.lower()
    matched = []
    
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    
    return len(matched) > 0, matched


def should_exclude(text: str, exclude_rules: Dict) -> Tuple[bool, List[str]]:
    """检查是否应该排除"""
    if not text:
        return False, []
    
    text_lower = text.lower()
    excluded = []
    
    for category, keywords in exclude_rules.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                excluded.append(f"{category}:{kw}")
    
    return len(excluded) > 0, excluded


# ============ 赛道评分 ============

def calculate_track_score(job: Dict, track_config: Dict, synonyms: Dict) -> Tuple[int, List[str], List[str]]:
    """
    计算单个赛道的分数
    
    Returns:
        (score, matched_keywords, skill_tags)
    """
    # 组合岗位相关字段
    job_text = " ".join([
        job.get("job_title", ""),
        job.get("job_req", ""),
        job.get("job_duty", ""),
        job.get("major_req", ""),
    ])
    
    total_score = 0
    all_matched = []
    skill_tags = []
    
    for group_name, group_keywords in track_config.get("keywords", {}).items():
        # 扩展关键词（加入同义词）
        expanded_kws = expand_keywords_with_synonyms(group_keywords, synonyms)
        
        matched, matched_kws = match_keywords(job_text, expanded_kws)
        
        if matched:
            # 计算分数：原始匹配数量 * 2
            group_score = len(matched_kws) * 2
            total_score += group_score
            all_matched.extend(matched_kws[:5])  # 每组最多5个
            
            # 添加技能标签
            for kw in matched_kws[:3]:
                for skill_name, skill_data in synonyms.items():
                    if kw.lower() == skill_data['canonical'].lower():
                        skill_tags.append(skill_name)
                    elif kw.lower() in [s.lower() for s in skill_data['synonyms']]:
                        skill_tags.append(skill_name)
    
    # 去重
    skill_tags = list(set(skill_tags))[:5]
    
    return total_score, all_matched[:15], skill_tags


# ============ 硬性过滤 ============

def apply_hard_filters(job: Dict, filters: Dict) -> Tuple[bool, str]:
    """
    应用硬性过滤条件
    
    Returns:
        (passed, reason)
    """
    job_text = " ".join([
        job.get("job_title", ""),
        job.get("job_req", ""),
        job.get("job_duty", ""),
        job.get("location", ""),
    ]).lower()
    
    # 1. 地点过滤
    loc_config = filters.get("location", {})
    include_locs = loc_config.get("include", [])
    exclude_locs = loc_config.get("exclude", [])
    
    location = job.get("location", "").lower()
    
    if include_locs and not any(loc.lower() in location for loc in include_locs):
        return False, "地点不在包含列表中"
    
    if exclude_locs and any(loc.lower() in location for loc in exclude_locs):
        return False, "地点在排除列表中"
    
    # 2. 必须包含
    must_include = filters.get("must_include", [])
    if must_include:
        if not any(kw.lower() in job_text for kw in must_include):
            return False, "未包含必须关键词"
    
    # 3. 排除关键词
    exclude_kws = filters.get("exclude_keywords", {})
    for category, keywords in exclude_kws.items():
        for kw in keywords:
            if kw.lower() in job_text:
                return False, f"包含排除关键词: {kw}"
    
    return True, ""


# ============ 主筛选函数 ============

def filter_jobs(
    config: Dict,
    input_file: str,
    output_file: str,
    days: int = 3,
) -> Tuple[List[Dict], Dict]:
    """
    筛选岗位
    
    Returns:
        (filtered_jobs, stats)
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    
    tracks = config.get("tracks", {})
    hard_filters = config.get("hard_filters", {})
    synonyms = config.get("skill_synonyms", {})
    thresholds = config.get("thresholds", {})
    
    filtered_jobs = []
    stats = {
        "total": 0,
        "date_filtered": 0,
        "hard_filtered": 0,
        "score_filtered": 0,
        "final_count": 0,
        "by_track": {track_name: 0 for track_name in tracks},
    }
    
    with open(input_file, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats["total"] += 1
            
            # 1. 日期筛选
            publish_date = parse_date(row.get("publish_date", ""))
            if not publish_date or publish_date < cutoff_date:
                continue
            
            stats["date_filtered"] += 1
            
            # 2. 硬性过滤
            passed, reason = apply_hard_filters(row, hard_filters)
            if not passed:
                continue
            
            stats["hard_filtered"] += 1
            
            # 3. 计算各赛道分数
            job = row.copy()
            job["track_scores"] = {}
            job["matched_keywords_by_track"] = {}
            job["skill_tags"] = []
            job["matched_tracks"] = []
            
            for track_name, track_config in tracks.items():
                score, keywords, skills = calculate_track_score(job, track_config, synonyms)
                min_score = track_config.get("min_score", 10)
                
                if score >= min_score:
                    job["track_scores"][track_name] = score
                    job["matched_keywords_by_track"][track_name] = keywords
                    job["skill_tags"].extend(skills)
                    job["matched_tracks"].append(track_name)
                    stats["by_track"][track_name] = stats["by_track"].get(track_name, 0) + 1
            
            # 去重技能标签
            job["skill_tags"] = list(set(job["skill_tags"]))[:10]
            
            # 4. 计算总分
            if not job["matched_tracks"]:
                stats["score_filtered"] += 1
                continue
            
            # 总分 = 各赛道分数 * 赛道权重的总和
            total_score = sum(
                job["track_scores"].get(track_name, 0) * tracks[track_name].get("weight", 1.0)
                for track_name in job["matched_tracks"]
            )
            job["total_score"] = int(total_score)
            job["matched_keywords"] = "; ".join(
                kw for kws in job["matched_keywords_by_track"].values() for kw in kws[:5]
            )[:200]
            
            # 5. 总分阈值过滤
            total_min = thresholds.get("total_score_min", 30)
            if job["total_score"] < total_min:
                stats["score_filtered"] += 1
                continue
            
            filtered_jobs.append(job)
    
    # 排序：按总分降序
    filtered_jobs.sort(key=lambda x: -x.get("total_score", 0))
    
    stats["final_count"] = len(filtered_jobs)
    
    return filtered_jobs, stats


def save_filtered_jobs(jobs: List[Dict], output_file: str, config: Dict):
    """保存筛选结果"""
    if not jobs:
        print("[WARN] 没有符合条件的岗位")
        return
    
    # 从配置获取输出字段
    csv_fields = config.get("output", {}).get("csv_fields", [
        "job_id", "company", "job_title", "location", "publish_date",
        "total_score", "matched_tracks", "matched_keywords", "detail_url"
    ])
    
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
    
    print(f"[SUCCESS] 保存 {len(jobs)} 条记录到: {output_file}")


# ============ 主程序 ============

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="基于配置的岗位筛选器")
    parser.add_argument("--config", default=None, help="配置文件路径 (默认: config.yaml)")
    parser.add_argument("--days", type=int, default=3, help="筛选最近N天")
    parser.add_argument("--input", default="D:/金融知识/爬虫/jobs.csv", help="输入CSV")
    parser.add_argument("--output", default="D:/金融知识/爬虫/filtered_jobs_v2.csv", help="输出CSV")
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    print("=" * 60)
    print("基于配置的岗位筛选器 v2")
    print("=" * 60)
    print(f"赛道: {', '.join(t['name'] for t in config['tracks'].values())}")
    print(f"最近天数: {args.days}")
    print(f"总分阈值: {config['thresholds'].get('total_score_min', 30)}")
    print("=" * 60)
    
    # 筛选
    jobs, stats = filter_jobs(config, args.input, args.output, args.days)
    
    # 打印统计
    print(f"\n[统计]")
    print(f"  总记录数: {stats['total']}")
    print(f"  日期筛选后: {stats['date_filtered']}")
    print(f"  硬性过滤后: {stats['hard_filtered']}")
    print(f"  分数过滤掉: {stats['score_filtered']}")
    print(f"  最终保留: {stats['final_count']}")
    
    print(f"\n[按赛道]")
    for track_name, count in stats['by_track'].items():
        track_name_cn = config['tracks'][track_name]['name']
        print(f"  {track_name_cn}: {count}")
    
    # 保存
    save_filtered_jobs(jobs, args.output, config)
    
    # 热门推荐
    hot_min = config['thresholds'].get('hot_recommend_min', 60)
    hot_jobs = [j for j in jobs if j.get('total_score', 0) >= hot_min]
    
    print(f"\n[热门推荐] (分数 >= {hot_min})")
    for i, job in enumerate(hot_jobs[:10], 1):
        print(f"  {i}. {job['job_title'][:30]} | {job['company']} | 分数:{job['total_score']}")


if __name__ == "__main__":
    main()
