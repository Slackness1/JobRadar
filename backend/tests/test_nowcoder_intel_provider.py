from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewIntelKeyword
from app.services.interview.nowcoder import intel_provider


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _seed(db, keyword: str, summary: str, count: int = 5):
    db.add(InterviewIntelKeyword(
        keyword=keyword, summary_md=summary, source_count=count, generated_at=datetime.utcnow()
    ))
    db.commit()


def test_returns_none_when_no_keyword_table_rows(db):
    assert intel_provider.get_intel_for_target_job(db, "anything") is None


def test_exact_match(db):
    _seed(db, "产品经理", "## 高频\n- 用户增长")
    out = intel_provider.get_intel_for_target_job(db, "产品经理")
    assert out is not None
    assert "用户增长" in out.summary_md
    assert out.source_count == 5


def test_substring_match(db):
    _seed(db, "产品经理", "summary")
    out = intel_provider.get_intel_for_target_job(db, "字节跳动产品经理实习")
    assert out is not None and out.keyword == "产品经理"


def test_no_match_returns_none(db):
    _seed(db, "产品经理", "summary")
    assert intel_provider.get_intel_for_target_job(db, "宁德时代电芯研发") is None


def test_empty_summary_returns_none(db):
    _seed(db, "产品经理", "")
    assert intel_provider.get_intel_for_target_job(db, "产品经理") is None


def test_db_error_returns_none(db):
    db.close()  # subsequent queries fail
    assert intel_provider.get_intel_for_target_job(db, "产品经理") is None
