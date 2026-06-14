"""Tests for mock-record isolation in the intel orchestrator.

验收目标：
1. _build_mock_records() 产出的记录带有明确 mock 标识（data_version + author_meta）
2. _is_mock_record() 能正确识别 mock 记录（三层规则）
3. real_records_for_job() helper 从混合列表中只返回真实记录

测试策略：全部纯函数 / dict 层面，不依赖 DB 和网络。
real_records_for_job() 的 DB 路径通过内存 SQLite fixture 覆盖。
"""
import json
import types
import pytest

from app.services.intel.orchestrator import (
    _build_mock_records,
    _is_mock_record,
    _to_dict,
)


# ---------------------------------------------------------------------------
# 辅助：构造一个最小 mock ORM 对象
# ---------------------------------------------------------------------------

def _make_orm(data_version: str, author_meta_json: str, url: str, **kwargs):
    """用 SimpleNamespace 伪造 ORM 对象，只需要 _is_mock_record 用到的属性。"""
    obj = types.SimpleNamespace(
        id=1,
        job_id=42,
        task_id=1,
        platform=kwargs.get("platform", ""),
        content_type=kwargs.get("content_type", "post"),
        platform_item_id=kwargs.get("platform_item_id", ""),
        title=kwargs.get("title", ""),
        author_name=kwargs.get("author_name", ""),
        author_meta_json=author_meta_json,
        url=url,
        raw_text=kwargs.get("raw_text", ""),
        cleaned_text=kwargs.get("cleaned_text", ""),
        summary=kwargs.get("summary", ""),
        keywords_json=kwargs.get("keywords_json", "[]"),
        tags_json=kwargs.get("tags_json", "[]"),
        metrics_json=kwargs.get("metrics_json", "{}"),
        entities_json=kwargs.get("entities_json", "{}"),
        relevance_score=kwargs.get("relevance_score", 0.0),
        confidence_score=kwargs.get("confidence_score", 0.0),
        sentiment=kwargs.get("sentiment", "neutral"),
        data_version=data_version,
        fetched_at=None,
        publish_time=None,
    )
    return obj


# ---------------------------------------------------------------------------
# 1. _build_mock_records 产物带 mock 标识
# ---------------------------------------------------------------------------

class TestBuildMockRecords:
    def test_returns_nonempty_list(self):
        recs = _build_mock_records(job_id=99)
        assert len(recs) >= 1

    def test_data_version_is_v1_mock(self):
        """列级 mock 标识：data_version 必须是 'v1-mock'。"""
        for rec in _build_mock_records(job_id=1):
            assert rec.get("data_version") == "v1-mock", (
                f"data_version 应为 'v1-mock'，实际: {rec.get('data_version')}"
            )

    def test_author_meta_source_is_mock(self):
        """JSON 级 mock 标识：author_meta_json['source'] 必须是 'mock'。"""
        for rec in _build_mock_records(job_id=1):
            meta = json.loads(rec.get("author_meta_json", "{}"))
            assert meta.get("source") == "mock", (
                f"author_meta_json[source] 应为 'mock'，实际: {meta}"
            )

    def test_title_contains_mock_marker(self):
        """文本级可读标识：title 应含 'mock' 字样（方便 UI/日志肉眼识别）。"""
        for rec in _build_mock_records(job_id=1):
            assert "mock" in rec.get("title", "").lower(), (
                f"title 应含 'mock'，实际: {rec.get('title')}"
            )

    def test_url_contains_mock_marker(self):
        """URL 文本标识：url 应含 '/mock'。"""
        for rec in _build_mock_records(job_id=1):
            assert "mock" in rec.get("url", ""), (
                f"url 应含 'mock'，实际: {rec.get('url')}"
            )

    def test_job_id_is_embedded(self):
        """platform_item_id 应包含传入的 job_id，确保不同岗位 mock 不冲突。"""
        for rec in _build_mock_records(job_id=777):
            assert "777" in rec.get("platform_item_id", "")


# ---------------------------------------------------------------------------
# 2. _is_mock_record 三层规则
# ---------------------------------------------------------------------------

class TestIsMockRecord:
    # --- dict 形式 ---

    def test_dict_data_version_v1_mock_is_mock(self):
        rec = {"data_version": "v1-mock", "author_meta_json": "{}", "url": "https://x.com/a"}
        assert _is_mock_record(rec) is True

    def test_dict_author_meta_source_mock_is_mock(self):
        rec = {"data_version": "v1-mvp", "author_meta_json": '{"source":"mock"}', "url": "https://x.com/a"}
        assert _is_mock_record(rec) is True

    def test_dict_url_slash_mock_is_mock(self):
        rec = {"data_version": "v1-mvp", "author_meta_json": '{"source":"xhs"}', "url": "https://nowcoder.com/discuss/mock-1"}
        assert _is_mock_record(rec) is True

    def test_dict_real_record_not_mock(self):
        rec = {
            "data_version": "v1-mvp",
            "author_meta_json": '{"source":"xiaohongshu"}',
            "url": "https://www.xiaohongshu.com/explore/abc123",
        }
        assert _is_mock_record(rec) is False

    # --- ORM 对象形式 ---

    def test_orm_data_version_v1_mock_is_mock(self):
        obj = _make_orm(data_version="v1-mock", author_meta_json="{}", url="https://x.com/a")
        assert _is_mock_record(obj) is True

    def test_orm_author_meta_source_mock_is_mock(self):
        obj = _make_orm(
            data_version="v1-mvp",
            author_meta_json='{"source":"mock"}',
            url="https://x.com/a",
        )
        assert _is_mock_record(obj) is True

    def test_orm_url_mock_is_mock(self):
        obj = _make_orm(
            data_version="v1-mvp",
            author_meta_json='{"source":"xhs"}',
            url="https://www.nowcoder.com/discuss/mock-99",
        )
        assert _is_mock_record(obj) is True

    def test_orm_real_record_not_mock(self):
        obj = _make_orm(
            data_version="v1-mvp",
            author_meta_json='{"source":"xiaohongshu","uid":"u12345"}',
            url="https://www.xiaohongshu.com/explore/realpost123",
        )
        assert _is_mock_record(obj) is False

    def test_corrupt_author_meta_json_falls_through_to_url_check(self):
        """author_meta_json 非法 JSON 时不应崩溃，靠 url 或 data_version 兜底。"""
        obj = _make_orm(
            data_version="v1-mvp",
            author_meta_json="NOT_JSON",
            url="https://real.example.com/post/1",
        )
        assert _is_mock_record(obj) is False  # 三层都不命中 → 真实

    def test_corrupt_author_meta_json_with_mock_url_still_detected(self):
        obj = _make_orm(
            data_version="v1-mvp",
            author_meta_json="NOT_JSON",
            url="https://nowcoder.com/discuss/mock-1",
        )
        assert _is_mock_record(obj) is True


# ---------------------------------------------------------------------------
# 3. real_records_for_job via DB fixture
# ---------------------------------------------------------------------------

def _make_db_with_records(records_data: list[dict]):
    """构造一个最小内存 SQLite + SessionLocal，插入测试记录，返回 session。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    # 导入所有 model 确保表被创建
    import app.models  # noqa: F401 — side-effect: registers all ORM classes

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    from app.models import JobIntelRecord
    from datetime import datetime

    for rd in records_data:
        db.add(JobIntelRecord(
            job_id=rd.get("job_id", 42),
            task_id=1,
            platform=rd.get("platform", ""),
            content_type=rd.get("content_type", "post"),
            platform_item_id=rd.get("platform_item_id", "x"),
            title=rd.get("title", ""),
            author_name=rd.get("author_name", ""),
            author_meta_json=rd.get("author_meta_json", "{}"),
            url=rd.get("url", "https://real.example.com"),
            raw_text=rd.get("raw_text", ""),
            cleaned_text=rd.get("cleaned_text", ""),
            summary=rd.get("summary", ""),
            keywords_json=rd.get("keywords_json", "[]"),
            tags_json=rd.get("tags_json", "[]"),
            metrics_json=rd.get("metrics_json", "{}"),
            entities_json=rd.get("entities_json", "{}"),
            publish_time=datetime(2026, 3, 10),
            relevance_score=rd.get("relevance_score", 0.5),
            confidence_score=rd.get("confidence_score", 0.5),
            sentiment=rd.get("sentiment", "neutral"),
            data_version=rd.get("data_version", "v1-mvp"),
            fetched_at=datetime.utcnow(),
            parsed_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
    db.commit()
    return db


class TestRealRecordsForJob:
    def test_excludes_mock_returns_only_real(self):
        """混合库中 helper 只返回真实记录。"""
        from app.services.intel.orchestrator import real_records_for_job

        db = _make_db_with_records([
            # 真实记录
            {
                "job_id": 42,
                "platform": "xiaohongshu",
                "url": "https://www.xiaohongshu.com/explore/real1",
                "author_meta_json": '{"source":"xiaohongshu"}',
                "data_version": "v1-mvp",
                "title": "真实面经",
            },
            # mock 兜底（data_version 标识）
            {
                "job_id": 42,
                "platform": "nowcoder",
                "url": "https://www.nowcoder.com/discuss/mock-1",
                "author_meta_json": '{"source":"mock"}',
                "data_version": "v1-mock",
                "title": "数据分析师 面经分享（mock）",
            },
        ])
        results = real_records_for_job(db, job_id=42)
        assert len(results) == 1
        assert results[0]["title"] == "真实面经"
        assert results[0]["data_version"] == "v1-mvp"

    def test_all_real_returns_all(self):
        from app.services.intel.orchestrator import real_records_for_job

        db = _make_db_with_records([
            {"job_id": 10, "url": "https://xhs.com/a", "data_version": "v1-mvp", "title": "帖子A"},
            {"job_id": 10, "url": "https://xhs.com/b", "data_version": "v1-mvp", "title": "帖子B"},
        ])
        results = real_records_for_job(db, job_id=10)
        assert len(results) == 2

    def test_all_mock_returns_empty(self):
        from app.services.intel.orchestrator import real_records_for_job

        db = _make_db_with_records([
            {
                "job_id": 7,
                "url": "https://nowcoder.com/discuss/mock-7",
                "author_meta_json": '{"source":"mock"}',
                "data_version": "v1-mock",
                "title": "mock title",
            }
        ])
        results = real_records_for_job(db, job_id=7)
        assert results == []

    def test_different_job_id_not_returned(self):
        """不同 job_id 的记录不应被返回。"""
        from app.services.intel.orchestrator import real_records_for_job

        db = _make_db_with_records([
            {"job_id": 1, "url": "https://xhs.com/j1", "data_version": "v1-mvp", "title": "j1帖子"},
            {"job_id": 2, "url": "https://xhs.com/j2", "data_version": "v1-mvp", "title": "j2帖子"},
        ])
        results = real_records_for_job(db, job_id=1)
        assert len(results) == 1
        assert results[0]["title"] == "j1帖子"

    def test_legacy_mock_without_data_version_flag_still_excluded(self):
        """历史遗留 mock 记录（data_version='v1-mvp' 但 author_meta source=mock）也应被排除。"""
        from app.services.intel.orchestrator import real_records_for_job

        db = _make_db_with_records([
            {
                "job_id": 5,
                "url": "https://xhs.com/real",
                "author_meta_json": '{"source":"xiaohongshu"}',
                "data_version": "v1-mvp",
                "title": "真实",
            },
            # 旧 mock：data_version 还是 v1-mvp，但 author_meta source=mock
            {
                "job_id": 5,
                "url": "https://nowcoder.com/discuss/mock-5",
                "author_meta_json": '{"source":"mock"}',
                "data_version": "v1-mvp",  # 历史遗留，data_version 未更新
                "title": "老 mock 记录",
            },
        ])
        results = real_records_for_job(db, job_id=5)
        assert len(results) == 1
        assert results[0]["title"] == "真实"
