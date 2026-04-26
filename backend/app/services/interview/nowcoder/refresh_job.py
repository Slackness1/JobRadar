import pathlib
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from app.models import InterviewIntelKeyword, InterviewIntelPost
from app.services.interview.nowcoder import scraper, summarizer

_KEYWORDS_PATH = pathlib.Path(__file__).parent / "keywords.yaml"
_DEFAULT_LIMIT = 10
_FETCH_FRESH_HOURS = 24
_STATUS_LOCK = threading.Lock()
_STATUS: dict = {}


@dataclass(slots=True)
class RefreshStats:
    keywords_total: int = 0
    keywords_ok: int = 0
    keywords_failed: int = 0
    posts_fetched: int = 0
    last_error: str = ""


def _load_keywords() -> list[dict]:
    raw = _KEYWORDS_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or []
    return [d for d in data if isinstance(d, dict) and d.get("chip") and d.get("query")]


def _is_fresh(post: Optional[InterviewIntelPost]) -> bool:
    if post is None or post.fetched_at is None:
        return False
    return datetime.utcnow() - post.fetched_at < timedelta(hours=_FETCH_FRESH_HOURS)


def _upsert_post(db: Session, keyword: str, detail: scraper.PostDetail, title: str) -> None:
    row = db.query(InterviewIntelPost).filter_by(pid=detail.pid, keyword=keyword).one_or_none()
    if row is None:
        row = InterviewIntelPost(pid=detail.pid, keyword=keyword)
        db.add(row)
    row.title = title
    row.company = detail.company
    row.interview_date = detail.interview_date
    row.position = detail.position
    row.questions_text = detail.questions_text
    row.parse_status = detail.parse_status
    row.fetched_at = datetime.utcnow()


def _upsert_keyword(db: Session, keyword: str, summary: str, source_count: int, error: str = "") -> None:
    row = db.query(InterviewIntelKeyword).filter_by(keyword=keyword).one_or_none()
    if row is None:
        row = InterviewIntelKeyword(keyword=keyword)
        db.add(row)
    row.summary_md = summary
    row.source_count = source_count
    row.generated_at = datetime.utcnow()
    row.last_error = error


def _record_status(payload: dict) -> None:
    with _STATUS_LOCK:
        _STATUS.clear()
        _STATUS.update(payload)


def get_last_refresh_status() -> dict:
    with _STATUS_LOCK:
        return dict(_STATUS)


def _process_keyword(db: Session, chip: str, query: str, stats: RefreshStats) -> None:
    metas = scraper.search(query, limit=_DEFAULT_LIMIT)
    ok_posts: list[scraper.PostDetail] = []
    for meta in metas:
        existing = db.query(InterviewIntelPost).filter_by(pid=meta.pid, keyword=chip).one_or_none()
        if _is_fresh(existing):
            if existing.parse_status == "ok":
                ok_posts.append(scraper.PostDetail(
                    pid=existing.pid, company=existing.company, interview_date=existing.interview_date,
                    position=existing.position, questions_text=existing.questions_text, parse_status="ok",
                ))
            continue
        detail = scraper.fetch_post(meta.pid)
        _upsert_post(db, chip, detail, meta.title)
        if detail.parse_status == "ok":
            ok_posts.append(detail)
        stats.posts_fetched += 1
        time.sleep(random.uniform(0.4, 1.0))
    db.commit()

    summary = summarizer.summarize_keyword(chip, ok_posts) if ok_posts else ""
    _upsert_keyword(db, chip, summary, len(ok_posts))
    db.commit()


def run_refresh(db: Session) -> RefreshStats:
    stats = RefreshStats()
    started = datetime.utcnow()
    try:
        keywords = _load_keywords()
    except Exception as e:
        _record_status({"last_run": started.isoformat(), "last_status": "failed", "last_error": f"keywords yaml: {e}"})
        stats.last_error = str(e)
        return stats

    stats.keywords_total = len(keywords)
    for entry in keywords:
        chip = entry["chip"]
        query = entry["query"]
        try:
            _process_keyword(db, chip, query, stats)
            stats.keywords_ok += 1
        except Exception as e:
            stats.keywords_failed += 1
            try:
                _upsert_keyword(db, chip, "", 0, error=str(e)[:500])
                db.commit()
            except Exception:
                db.rollback()

    overall_status = "ok"
    if stats.keywords_failed and stats.keywords_failed == stats.keywords_total:
        overall_status = "failed"
    elif stats.keywords_failed:
        overall_status = "partial"

    _record_status({
        "last_run": started.isoformat() + "Z",
        "last_status": overall_status,
        "keywords_total": stats.keywords_total,
        "keywords_ok": stats.keywords_ok,
        "keywords_failed": stats.keywords_failed,
        "posts_fetched": stats.posts_fetched,
        "last_error": stats.last_error or None,
    })
    return stats
