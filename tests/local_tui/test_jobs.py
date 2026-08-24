from __future__ import annotations

import json
from pathlib import Path

from jobradar_core.models import JobSearchQuery
from jobradar_core.service import JobRadarLocal


def _write_jobs(path: Path) -> None:
    rows = [
        {
            "job_id": "job-agent-sh",
            "source": "fixture",
            "company": "测试科技",
            "job_title": "AI Agent 后端工程师",
            "location": "上海",
            "sub_category": "AI Agent 后端",
            "job_duty": "负责 Agent Runtime 和工具调用",
            "job_req": "Python、Redis、WebSocket",
            "publish_date": "2026-08-20",
        },
        {
            "job_id": "job-data-bj",
            "source": "fixture",
            "company": "数据公司",
            "job_title": "数据分析师",
            "location": "北京",
            "job_duty": "负责指标分析",
            "job_req": "SQL",
            "publish_date": "2026-08-19",
        },
    ]
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content, encoding="utf-8")


def test_import_search_favorite_and_exclude(app_config, tmp_path: Path) -> None:
    service = JobRadarLocal(app_config)
    source = tmp_path / "jobs.jsonl"
    _write_jobs(source)
    imported = service.job_importer.import_path(source)
    assert imported.imported == 2
    results = service.search_jobs(JobSearchQuery(text="AI Agent 后端", location="上海", limit=20))
    assert [item.job.job_id for item in results] == ["job-agent-sh"]
    assert results[0].reasons
    assert 0 <= results[0].score <= 1

    service.jobs.set_favorite("job-agent-sh", True)
    favorite = service.jobs.search(JobSearchQuery(favorites_only=True))
    assert favorite[0].favorite is True

    service.jobs.set_excluded("job-agent-sh", True, "not interested")
    assert service.jobs.search(JobSearchQuery(text="Agent")) == []
    included = service.jobs.search(JobSearchQuery(text="Agent", include_excluded=True))
    assert included[0].excluded is True


def test_import_preserves_source_file(app_config, tmp_path: Path) -> None:
    service = JobRadarLocal(app_config)
    source = tmp_path / "jobs.jsonl"
    _write_jobs(source)
    result = service.job_importer.import_path(source)
    assert Path(result.source_path).is_relative_to(service.workspace.root)
    preserved = Path(result.source_path).read_text(encoding="utf-8")
    assert preserved == source.read_text(encoding="utf-8")
