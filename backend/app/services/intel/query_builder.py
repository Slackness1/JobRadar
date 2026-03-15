"""Job Intel Query Builder - 搜索 query 生成"""
from typing import Optional
from datetime import datetime
from app.models import Job


def build_queries_for_job(job: Job) -> dict:
    """为指定岗位生成三层搜索 query

    返回结构：
    {
        "strict": [...],
        "expanded": [...],
        "historical": [...],
        "platform_overrides": {
            "nowcoder": [...],
            "xiaohongshu": [...],
            ...
        }
    }
    """
    company = job.company or ""
    job_title = job.job_title or ""
    department = job.department or ""
    job_stage = job.job_stage or "campus"

    # Level 1: strict - 精准匹配
    strict_queries = [
        f"{company} {job_title} 面经",
        f"{company} {job_title} 一面",
        f"{company} {job_title} 笔试",
        f"{company} {job_title} offer",
        f"{company} {job_title} 面试经验",
    ]

    # Level 2: expanded - 岗位扩展
    expanded_queries = [
        f"{company} {job_title}",
        f"{company} 数据分析",
        f"{company} 数分",
        f"{company} 商分",
    ]

    # Level 3: historical - 历史泛化
    historical_queries = []
    if job_stage == "campus":
        historical_queries = [
            f"{company} {job_title} 提前批",
            f"{company} {job_title} 秋招",
            f"{company} {job_title} 春招",
        ]

    # 平台特定 query 覆盖
    platform_overrides = {
        "nowcoder": [
            f"{company} {job_title} 面经",
            f"{company} {job_title} 笔试回忆",
            f"{company} {job_title} offer 选择",
        ],
        "xiaohongshu": [
            f"{company} {job_title} 薪资",
            f"{company} {job_title} 面经",
            f"{company} {job_title} 面试流程",
        ],
        "zhihu": [
            f"{company} {job_title} 值得去吗",
            f"{company} {job_title} 面试体验",
            f"{company} {job_title} 职业发展",
        ],
    }

    return {
        "strict": strict_queries,
        "expanded": expanded_queries,
        "historical": historical_queries,
        "platform_overrides": platform_overrides,
    }
