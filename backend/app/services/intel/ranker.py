"""Job Intel Ranker - 相关度打分"""
from typing import Dict
from datetime import datetime


def score_intel_record(record: Dict) -> float:
    """为情报记录计算相关度分数

    评分维度（简化版）：
    - 关键词匹配权重：40%
    - 时间新鲜度权重：30%
    - 互动质量权重：20%
    - 标题匹配权重：10%

    返回 0-100 分
    """
    if not record:
        return 0.0

    score = 0.0

    # 关键词匹配（简化：假设已有）
    title = record.get("title", "")
    summary = record.get("summary", "")
    if title and ("面试" in title or "面经" in title or "薪资" in title):
        score += 40
    elif summary and ("面试" in summary or "薪资" in summary or "offer" in summary):
        score += 30

    # 时间新鲜度（最近30天）
    publish_time = record.get("publish_time")
    if publish_time:
        if isinstance(publish_time, str):
            try:
                pub_dt = datetime.strptime(publish_time, "%Y-%m-%d")
            except:
                pub_dt = datetime.utcnow()
        else:
            pub_dt = publish_time

        days_old = (datetime.utcnow() - pub_dt).days
        if days_old < 7:
            score += 30
        elif days_old < 30:
            score += 20
        elif days_old < 90:
            score += 10

    # 互动质量（点赞/评论数）
    metrics = record.get("metrics_json", "{}")
    try:
        import json
        metrics_dict = json.loads(metrics) if isinstance(metrics, str) else metrics
        likes = metrics_dict.get("like_count", 0) or 0
        comments = metrics_dict.get("comment_count", 0) or 0

        if likes > 10:
            score += 10
        elif likes > 5:
            score += 5

        if comments > 10:
            score += 10
        elif comments > 5:
            score += 5
    except:
        pass

    # 标题匹配
    if title and "数据" in title and ("分析" in title or "挖掘" in title):
        score += 10

    return round(score, 2)
