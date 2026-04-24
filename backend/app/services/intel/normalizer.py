"""Job Intel Normalizer - 数据格式统一"""
from typing import Dict


def normalize_platform_record(platform: str, raw_item: Dict) -> Dict:
    """将平台原始数据统一成标准格式

    输出格式参考 JobIntelRecord 的字段要求
    """
    # 基础字段
    normalized = {
        "platform": platform,
        "content_type": "post",
        "platform_item_id": raw_item.get("id", ""),
        "title": raw_item.get("title", ""),
        "author_name": raw_item.get("author", ""),
        "author_meta_json": raw_item.get("author_meta", "{}"),
        "url": raw_item.get("url", ""),
        "publish_time": raw_item.get("publish_time"),
        "raw_text": raw_item.get("content", ""),
        "cleaned_text": raw_item.get("content", ""),
        "summary": raw_item.get("summary", ""),
        "keywords_json": raw_item.get("keywords", "[]"),
        "tags_json": raw_item.get("tags", "[]"),
        "metrics_json": raw_item.get("metrics", "{}"),
        "entities_json": raw_item.get("entities", "{}"),
        "relevance_score": 0.5,
        "confidence_score": 0.5,
        "sentiment": "neutral",
        "data_version": "v1",
        "fetched_at": raw_item.get("created_at"),
        "parsed_at": raw_item.get("updated_at"),
    }

    return normalized
