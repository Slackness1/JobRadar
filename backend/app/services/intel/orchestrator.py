"""Job Intel Orchestrator - 任务编排与调度"""
import asyncio
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models import Job, JobIntelTask, JobIntelRecord
from app.schemas_job_intel import JobIntelTaskCreatedOut
from app.services.platform_intel.adapters.xiaohongshu import XiaohongshuIntelAdapter


DEFAULT_PLATFORMS = ["xiaohongshu", "maimai", "nowcoder", "boss", "zhihu"]


def create_intel_task_for_job(
    db: Session,
    job_id: int,
    trigger_mode: str = "manual",
    platform_scope: Optional[list[str]] = None,
) -> JobIntelTaskCreatedOut:
    """为指定岗位创建情报搜索任务，并立即执行。"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")

    platforms = platform_scope or DEFAULT_PLATFORMS
    query_bundle = {
        "strict": [f"{job.company} {job.job_title} 面经", f"{job.company} {job.job_title} 薪资"],
        "expanded": [f"{job.company} {job.job_title}"],
    }

    task = JobIntelTask(
        job_id=job_id,
        trigger_mode=trigger_mode,
        search_level="strict",
        platform_scope_json=json.dumps(platforms, ensure_ascii=False),
        query_bundle_json=json.dumps(query_bundle, ensure_ascii=False),
        status="queued",
        started_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    task = run_intel_task(db, task.id)
    return JobIntelTaskCreatedOut(task_id=task.id, status=task.status, query_bundle=query_bundle)


def run_intel_task(db: Session, task_id: int) -> JobIntelTask:
    """执行情报搜索任务。

    当前策略：
    - 小红书：真实最小版（关键词检索 + 详情抓取 + 入库）
    - 其他平台：保留 mock 数据兜底
    """
    task = db.query(JobIntelTask).filter(JobIntelTask.id == task_id).first()
    if not task:
        raise ValueError(f"Task {task_id} not found")

    task.status = "running"
    task.started_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    db.commit()

    db.query(JobIntelRecord).filter(JobIntelRecord.task_id == task.id).delete(synchronize_session=False)
    db.commit()

    try:
        query_bundle = json.loads(task.query_bundle_json or "{}")
    except Exception:
        query_bundle = {}

    try:
        platforms = json.loads(task.platform_scope_json or "[]")
    except Exception:
        platforms = []

    strict_queries = query_bundle.get("strict", []) or []
    fallback_query = query_bundle.get("expanded", [""])
    seed_query = (strict_queries[0] if strict_queries else (fallback_query[0] if fallback_query else "岗位 面经"))

    records_to_insert: List[Dict[str, Any]] = []

    if "xiaohongshu" in platforms:
        xhs_records = _run_xiaohongshu_mvp(seed_query, task.job_id, task.id)
        records_to_insert.extend(xhs_records)

    # 兜底：若真实抓取暂无结果，保留原有 mock 以保证前端链路可见
    if not records_to_insert:
        records_to_insert = _build_mock_records(task.job_id)

    for rec in records_to_insert:
        db.add(
            JobIntelRecord(
                job_id=task.job_id,
                task_id=task.id,
                platform=rec.get("platform", ""),
                content_type=rec.get("content_type", "post"),
                platform_item_id=rec.get("platform_item_id", ""),
                title=rec.get("title", ""),
                author_name=rec.get("author_name", ""),
                author_meta_json=rec.get("author_meta_json", "{}"),
                url=rec.get("url", ""),
                raw_text=rec.get("raw_text", ""),
                cleaned_text=rec.get("cleaned_text", ""),
                summary=rec.get("summary", ""),
                keywords_json=rec.get("keywords_json", "[]"),
                tags_json=rec.get("tags_json", "[]"),
                metrics_json=rec.get("metrics_json", "{}"),
                entities_json=rec.get("entities_json", "{}"),
                publish_time=rec.get("publish_time"),
                relevance_score=rec.get("relevance_score", 0.0),
                confidence_score=rec.get("confidence_score", 0.0),
                sentiment=rec.get("sentiment", "neutral"),
                # 优先使用 rec 里的 data_version（mock 记录携带 "v1-mock"），
                # 真实抓取记录默认 "v1-mvp"
                data_version=rec.get("data_version", "v1-mvp"),
                fetched_at=datetime.utcnow(),
                parsed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

    # Phase 0 (D-4): snapshot building removed — _build_snapshots() deleted.
    task.status = "done"
    task.result_count = len(records_to_insert)
    task.error_message = ""
    task.finished_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def _run_xiaohongshu_mvp(query: str, job_id: int, task_id: int) -> List[Dict[str, Any]]:
    adapter = XiaohongshuIntelAdapter()

    async def _run() -> List[Dict[str, Any]]:
        await adapter.ensure_session()
        items = await adapter.search(query, limit=5)
        out: List[Dict[str, Any]] = []
        for item in items:
            detail = await adapter.fetch_detail(item) or item
            pub_dt = adapter.parse_publish_time(detail.get("publish_time", ""))
            out.append(
                {
                    "platform": "xiaohongshu",
                    "content_type": "post",
                    "platform_item_id": detail.get("id") or f"xiaohongshu-{task_id}-{len(out)+1}",
                    "title": detail.get("title", ""),
                    "author_name": detail.get("author", ""),
                    "author_meta_json": json.dumps(detail.get("author_meta", {}), ensure_ascii=False),
                    "url": detail.get("url", ""),
                    "publish_time": pub_dt,
                    "raw_text": detail.get("content", ""),
                    "cleaned_text": detail.get("content", ""),
                    "summary": (detail.get("summary") or detail.get("content") or "")[:300],
                    "keywords_json": json.dumps(detail.get("keywords", ["小红书", "岗位情报"]), ensure_ascii=False),
                    "tags_json": json.dumps(detail.get("tags", ["xiaohongshu", "mvp"]), ensure_ascii=False),
                    "metrics_json": json.dumps(detail.get("metrics", {}), ensure_ascii=False),
                    "entities_json": json.dumps({"query": query, "job_id": job_id, **detail.get("entities", {})}, ensure_ascii=False),
                    "relevance_score": 0.75,
                    "confidence_score": 0.60,
                    "sentiment": "neutral",
                }
            )
        return out

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # 已有事件循环时的兜底
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()


def _build_mock_records(job_id: int) -> List[Dict[str, Any]]:
    """兜底 mock 数据。每条记录满足以下三个硬标识，供下游过滤：
    1. data_version = "v1-mock"（列级标识，最易 SQL 过滤）
    2. author_meta_json["source"] = "mock"（JSON 级标识，已有）
    3. title 含 "(mock)"、url 含 "mock"（文本级可读标记）
    严禁被推荐/精排/narrative 主链路当真实情报使用 — 用 real_records_for_job() 过滤。
    """
    return [
        {
            "platform": "nowcoder",
            "content_type": "post",
            "platform_item_id": f"nowcoder-{job_id}-1",
            "title": "数据分析师 面经分享（mock）",
            "author_name": "牛客用户",
            "author_meta_json": json.dumps({"source": "mock"}, ensure_ascii=False),
            "url": "https://www.nowcoder.com/discuss/mock-1",
            "publish_time": datetime.strptime("2026-03-10", "%Y-%m-%d"),
            "raw_text": "一面问 SQL 和数据结构，二面考察业务理解。",
            "cleaned_text": "一面问 SQL 和数据结构，二面考察业务理解。",
            "summary": "一面主要问 SQL 与数据结构。",
            "keywords_json": json.dumps(["面经", "SQL", "数据结构"], ensure_ascii=False),
            "tags_json": json.dumps(["interview", "mock"], ensure_ascii=False),
            "metrics_json": json.dumps({"like_count": 12, "comment_count": 4}, ensure_ascii=False),
            "entities_json": json.dumps({"topics": ["interview"]}, ensure_ascii=False),
            "relevance_score": 0.8,
            "confidence_score": 0.7,
            "sentiment": "positive",
            # 硬标识：data_version 区分 mock vs 真实抓取
            "data_version": "v1-mock",
        }
    ]


# ---------------------------------------------------------------------------
# 读取口径：排除 mock 数据
# ---------------------------------------------------------------------------

def real_records_for_job(db, job_id: int) -> List[Dict[str, Any]]:
    """返回指定岗位的**真实**情报记录（排除所有 mock 兜底条目）。

    过滤策略（三层，任意一层命中则排除）：
      1. data_version == "v1-mock"     ← 首选，列级精确匹配
      2. author_meta_json["source"] == "mock"  ← JSON 二次兜底
      3. url 含 "/mock"                ← 文本三次兜底

    返回 dict 列表（非 ORM 对象），调用方可直接序列化。
    当前推荐/精排/narrative 主链路**尚未**接入 job_intel_records；
    本 helper 作为防御层，供未来接入点直接使用。
    """
    from app.models import JobIntelRecord  # 局部 import 避免循环

    rows = (
        db.query(JobIntelRecord)
        .filter(JobIntelRecord.job_id == job_id)
        .all()
    )
    return [_to_dict(r) for r in rows if not _is_mock_record(r)]


def _is_mock_record(record) -> bool:
    """判断一条 JobIntelRecord（ORM 对象或 dict）是否为 mock 兜底数据。"""
    # 支持 ORM 对象和 dict 两种形式
    if isinstance(record, dict):
        dv = record.get("data_version", "")
        meta_str = record.get("author_meta_json", "{}")
        url = record.get("url", "")
    else:
        dv = getattr(record, "data_version", "") or ""
        meta_str = getattr(record, "author_meta_json", "{}") or "{}"
        url = getattr(record, "url", "") or ""

    # 1. 列级标识
    if dv == "v1-mock":
        return True

    # 2. JSON 级标识（兼容历史记录 data_version 未设的情况）
    try:
        meta = json.loads(meta_str)
        if meta.get("source") == "mock":
            return True
    except Exception:
        pass

    # 3. URL 文本标识（再兜底）
    if "/mock" in url or url.endswith("mock"):
        return True

    return False


def _to_dict(record) -> Dict[str, Any]:
    """把 ORM JobIntelRecord 转成普通 dict。"""
    return {
        "id": record.id,
        "job_id": record.job_id,
        "task_id": record.task_id,
        "platform": record.platform,
        "content_type": record.content_type,
        "platform_item_id": record.platform_item_id,
        "title": record.title,
        "author_name": record.author_name,
        "author_meta_json": record.author_meta_json,
        "url": record.url,
        "raw_text": record.raw_text,
        "cleaned_text": record.cleaned_text,
        "summary": record.summary,
        "keywords_json": record.keywords_json,
        "tags_json": record.tags_json,
        "metrics_json": record.metrics_json,
        "entities_json": record.entities_json,
        "relevance_score": record.relevance_score,
        "confidence_score": record.confidence_score,
        "sentiment": record.sentiment,
        "data_version": record.data_version,
        "fetched_at": record.fetched_at,
        "publish_time": record.publish_time,
    }


def refresh_intel_for_job(db: Session, job_id: int, force: bool = False):
    """刷新岗位情报。当前直接重新跑一次任务。"""
    _ = force
    return create_intel_task_for_job(db, job_id, trigger_mode="refresh")
