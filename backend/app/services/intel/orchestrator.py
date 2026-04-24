"""Job Intel Orchestrator - 任务编排与调度"""
import asyncio
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models import Job, JobIntelTask, JobIntelRecord, JobIntelSnapshot
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
    db.query(JobIntelSnapshot).filter(JobIntelSnapshot.job_id == task.job_id).delete(synchronize_session=False)
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
                data_version="v1-mvp",
                fetched_at=datetime.utcnow(),
                parsed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

    snapshots = _build_snapshots(task.job_id, records_to_insert)
    for snap in snapshots:
        db.add(snap)

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
        }
    ]


def _build_snapshots(job_id: int, records: List[Dict[str, Any]]) -> List[JobIntelSnapshot]:
    xhs_records = [r for r in records if r.get("platform") == "xiaohongshu"]
    interview_records = [r for r in records if "面经" in (r.get("keywords_json") or "")]

    interview_summary = (
        f"共发现 {len(interview_records)} 条面试相关线索。"
        if interview_records
        else "当前未抓到明确面试线索。"
    )

    salary_summary = (
        f"小红书侧共发现 {len(xhs_records)} 条内容，可继续提炼薪资/强度信息。"
        if xhs_records
        else "当前小红书结果不足，建议扩大关键词或补充登录态。"
    )

    return [
        JobIntelSnapshot(
            job_id=job_id,
            snapshot_type="interview",
            summary_text=interview_summary,
            evidence_count=len(interview_records),
            source_platforms_json=json.dumps(sorted({r.get("platform", "") for r in interview_records}), ensure_ascii=False),
            confidence_score=0.7 if interview_records else 0.4,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        JobIntelSnapshot(
            job_id=job_id,
            snapshot_type="salary",
            summary_text=salary_summary,
            evidence_count=len(xhs_records),
            source_platforms_json=json.dumps(["xiaohongshu"] if xhs_records else [], ensure_ascii=False),
            confidence_score=0.6 if xhs_records else 0.3,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        JobIntelSnapshot(
            job_id=job_id,
            snapshot_type="wlb",
            summary_text="MVP 阶段：建议后续接入评论抓取与多平台交叉验证。",
            evidence_count=0,
            source_platforms_json=json.dumps([], ensure_ascii=False),
            confidence_score=0.5,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]


def refresh_intel_for_job(db: Session, job_id: int, force: bool = False):
    """刷新岗位情报。当前直接重新跑一次任务。"""
    _ = force
    return create_intel_task_for_job(db, job_id, trigger_mode="refresh")
