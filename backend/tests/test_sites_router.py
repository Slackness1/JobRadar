from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base, CompanyCrawlLog, CrawlLog


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, Session
    app.dependency_overrides.clear()


def _seed(session, **kw):
    row = CompanyCrawlLog(
        source=kw.get("source", "internet_official"),
        company=kw["company"],
        started_at=kw["started_at"],
        finished_at=kw.get("finished_at", kw["started_at"] + timedelta(seconds=5)),
        status=kw.get("status", "success"),
        fetched_count=kw.get("fetched_count", 10),
        new_count=kw.get("new_count", 2),
        error_message=kw.get("error_message", ""),
        parent_log_id=kw.get("parent_log_id"),
        duration_ms=kw.get("duration_ms", 5000),
    )
    session.add(row)
    session.commit()
    return row


def test_summary_counts_active_and_alerted(client):
    c, Session = client
    db = Session()
    from app.routers.sites import _shanghai_today_start
    today_start = _shanghai_today_start()
    # Seed all rows safely inside today's Shanghai window (today_start + 1h)
    in_today = today_start + timedelta(hours=1)
    _seed(db, company="腾讯", started_at=in_today, status="success", new_count=5)
    _seed(db, company="阿里巴巴", started_at=in_today, status="failed", new_count=0)
    _seed(db, company="阿里巴巴", started_at=in_today - timedelta(days=1), status="failed", new_count=0)
    _seed(db, company="字节跳动", started_at=in_today, status="success", new_count=20)
    db.close()

    res = c.get("/api/sites/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["active"] == 2          # 腾讯 + 字节跳动
    assert body["alerted"] == 1         # 阿里巴巴 red
    assert body["total_today_new"] >= 25


def test_list_returns_one_row_per_company(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    _seed(db, company="腾讯", started_at=now - timedelta(hours=2), new_count=5)
    _seed(db, company="腾讯", started_at=now - timedelta(days=1), new_count=3)
    _seed(db, company="阿里巴巴", started_at=now - timedelta(hours=1), new_count=2)
    db.close()

    res = c.get("/api/sites")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    companies = {r["company"] for r in rows}
    assert companies == {"腾讯", "阿里巴巴"}
    tencent = next(r for r in rows if r["company"] == "腾讯")
    assert tencent["alert_level"] == "green"


def test_list_filters_by_source(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    _seed(db, source="internet_official", company="腾讯", started_at=now)
    _seed(db, source="state_owned_official", company="中电科技", started_at=now)
    db.close()

    res = c.get("/api/sites?source=state_owned_official")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["company"] == "中电科技"


def test_runs_endpoint_returns_recent_history(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    for i in range(5):
        _seed(db, company="腾讯", started_at=now - timedelta(hours=i))
    db.close()

    res = c.get("/api/sites/腾讯/runs?limit=3")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) == 3
    # newest first
    started_times = [r["started_at"] for r in runs]
    assert started_times == sorted(started_times, reverse=True)


def test_recrawl_unknown_company_returns_400(client):
    c, _ = client
    res = c.post("/api/sites/不存在的公司/recrawl")
    assert res.status_code == 400
