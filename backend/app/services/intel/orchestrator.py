"""Job Intel Orchestrator - 任务编排与调度"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Job, JobIntelTask, JobIntelRecord, JobIntelSnapshot
from app.schemas_job_intel import JobIntelTaskCreatedOut


DEFAULT_PLATFORMS = ["xiaohongshu", "maimai", "nowcoder", "boss", "zhihu"]


def create_intel_task_for_job(
    db: Session,
    job_id: int,
    trigger_mode: str = "manual",
    platform_scope: Optional[list[str]] = None,
) -> JobIntelTaskCreatedOut:
    """为指定岗位创建情报搜索任务，并立即执行 mock 流程。"""
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
    """执行情报搜索任务（当前为 mock/stub，可完整写入 records + snapshots）。"""
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

    mock_records = [
        {
            "platform": "nowcoder",
            "content_type": "post",
            "platform_item_id": f"nowcoder-{task.job_id}-1",
            "title": "阿里数据分析师 面经分享",
            "author_name": "牛客用户",
            "url": "https://www.nowcoder.com/discuss/mock-1",
            "publish_time": "2026-03-10",
            "raw_text": "一面问 SQL 和数据结构，二面考察业务理解。",
            "cleaned_text": "一面问 SQL 和数据结构，二面考察业务理解。",
            "summary": "一面主要问 SQL 和数据结构，二面考察业务理解。",
            "keywords_json": json.dumps(["面经", "SQL", "数据结构"], ensure_ascii=False),
            "tags_json": json.dumps(["interview", "nowcoder"], ensure_ascii=False),
            "metrics_json": json.dumps({"like_count": 12, "comment_count": 4}, ensure_ascii=False),
            "entities_json": json.dumps({"topics": ["interview"], "company": ["阿里"]}, ensure_ascii=False),
            "relevance_score": 0.92,
            "confidence_score": 0.85,
            "sentiment": "positive",
        },
        {
            "platform": "xiaohongshu",
            "content_type": "post",
            "platform_item_id": f"xiaohongshu-{task.job_id}-1",
            "title": "数据分析岗薪资爆料",
            "author_name": "小红书用户",
            "url": "https://www.xiaohongshu.com/explore/mock-1",
            "publish_time": "2026-03-08",
            "raw_text": "阿里数据分析岗 25k-35k，看部门差异较大。",
            "cleaned_text": "阿里数据分析岗 25k-35k，看部门差异较大。",
            "summary": "阿里数据分析 25k-35k，看部门。",
            "keywords_json": json.dumps(["薪资", "数据分析"], ensure_ascii=False),
            "tags_json": json.dumps(["salary", "xiaohongshu"], ensure_ascii=False),
            "metrics_json": json.dumps({"like_count": 23, "comment_count": 8}, ensure_ascii=False),
            "entities_json": json.dumps({"topics": ["salary"], "company": ["阿里"]}, ensure_ascii=False),
            "relevance_score": 0.88,
            "confidence_score": 0.78,
            "sentiment": "neutral",
        },
    ]

    for mock in mock_records:
        db.add(
            JobIntelRecord(
                job_id=task.job_id,
                task_id=task.id,
                platform=mock["platform"],
                content_type=mock["content_type"],
                platform_item_id=mock["platform_item_id"],
                title=mock["title"],
                author_name=mock["author_name"],
                url=mock["url"],
                raw_text=mock["raw_text"],
                cleaned_text=mock["cleaned_text"],
                summary=mock["summary"],
                keywords_json=mock["keywords_json"],
                tags_json=mock["tags_json"],
                metrics_json=mock["metrics_json"],
                entities_json=mock["entities_json"],
                publish_time=datetime.strptime(mock["publish_time"], "%Y-%m-%d"),
                relevance_score=mock["relevance_score"],
                confidence_score=mock["confidence_score"],
                sentiment=mock["sentiment"],
                data_version="v1",
                fetched_at=datetime.utcnow(),
                parsed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

    snapshots = [
        JobIntelSnapshot(
            job_id=task.job_id,
            snapshot_type="interview",
            summary_text="面试流程相对规范：一面偏 SQL / 数据结构，二面偏业务理解，整体难度中等。",
            evidence_count=1,
            source_platforms_json=json.dumps(["nowcoder"], ensure_ascii=False),
            confidence_score=0.85,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        JobIntelSnapshot(
            job_id=task.job_id,
            snapshot_type="salary",
            summary_text="薪资范围约 25k-35k，部门差异较大。",
            evidence_count=1,
            source_platforms_json=json.dumps(["xiaohongshu"], ensure_ascii=False),
            confidence_score=0.78,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        JobIntelSnapshot(
            job_id=task.job_id,
            snapshot_type="wlb",
            summary_text="当前为 mock 数据，工作强度信息不足，建议后续补充脉脉/知乎来源。",
            evidence_count=0,
            source_platforms_json=json.dumps([], ensure_ascii=False),
            confidence_score=0.5,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]
    for snap in snapshots:
        db.add(snap)

    task.status = "done"
    task.result_count = len(mock_records)
    task.finished_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def refresh_intel_for_job(db: Session, job_id: int, force: bool = False):
    """刷新岗位情报。当前直接重新跑一次 mock 流程。"""
    _ = force
    return create_intel_task_for_job(db, job_id, trigger_mode="refresh")
