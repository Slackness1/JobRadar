import hashlib
import pathlib
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import InterviewIntelKeyword, InterviewIntelPost
from app.services.interview.nowcoder import scraper, summarizer, quality_scorer

_KEYWORDS_PATH = pathlib.Path(__file__).parent / "keywords.yaml"
_DEFAULT_LIMIT = 10
_FETCH_FRESH_HOURS = 24
_DEFAULT_MAX_WORKERS = 4
_STATUS_LOCK = threading.Lock()
_STATUS: dict = {}


@dataclass(slots=True)
class RefreshStats:
    keywords_total: int = 0
    keywords_ok: int = 0
    keywords_failed: int = 0
    posts_fetched: int = 0
    last_error: str = ""


@dataclass(slots=True)
class _ChipResult:
    chip: str
    posts_fetched: int = 0
    error: str = ""


@dataclass(slots=True)
class _PidCache:
    """Per-run cross-chip cache: pid → PostDetail. Thread-safe."""
    data: dict[str, scraper.PostDetail] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, pid: str) -> Optional[scraper.PostDetail]:
        with self.lock:
            return self.data.get(pid)

    def set(self, pid: str, detail: scraper.PostDetail) -> None:
        with self.lock:
            self.data[pid] = detail


def _load_keywords() -> list[dict]:
    raw = _KEYWORDS_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or []
    return [d for d in data if isinstance(d, dict) and d.get("chip") and d.get("query")]


def _is_fresh(post: Optional[InterviewIntelPost]) -> bool:
    if post is None or post.fetched_at is None:
        return False
    return datetime.utcnow() - post.fetched_at < timedelta(hours=_FETCH_FRESH_HOURS)


def _upsert_post(
    db: Session, keyword: str, detail: scraper.PostDetail, title: str, quality_score: int
) -> None:
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
    row.quality_score = quality_score
    row.fetched_at = datetime.utcnow()


def _upsert_keyword(
    db: Session, keyword: str, summary: str, source_count: int,
    error: str = "", posts_hash: str = "",
) -> None:
    row = db.query(InterviewIntelKeyword).filter_by(keyword=keyword).one_or_none()
    if row is None:
        row = InterviewIntelKeyword(keyword=keyword)
        db.add(row)
    row.summary_md = summary
    row.source_count = source_count
    row.generated_at = datetime.utcnow()
    row.last_error = error
    row.posts_hash = posts_hash


def _hash_pid_set(pids: list[str]) -> str:
    joined = "\n".join(sorted(pids))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _record_status(payload: dict) -> None:
    with _STATUS_LOCK:
        _STATUS.clear()
        _STATUS.update(payload)


def get_last_refresh_status() -> dict:
    with _STATUS_LOCK:
        return dict(_STATUS)


_SUMMARY_POST_AGE_DAYS = 60
_MAX_SUMMARY_POSTS = 20
_MIN_QUALITY_FOR_SUMMARY = 2


def _collect_ok_posts_for_summary(db: Session, chip: str) -> list[scraper.PostDetail]:
    """Pull parse_status='ok' AND quality_score >= 2 posts for this chip from DB,
    capped to the most recent _MAX_SUMMARY_POSTS within _SUMMARY_POST_AGE_DAYS."""
    cutoff = datetime.utcnow() - timedelta(days=_SUMMARY_POST_AGE_DAYS)
    rows = (
        db.query(InterviewIntelPost)
        .filter(
            InterviewIntelPost.keyword == chip,
            InterviewIntelPost.parse_status == "ok",
            InterviewIntelPost.quality_score >= _MIN_QUALITY_FOR_SUMMARY,
            InterviewIntelPost.fetched_at >= cutoff,
        )
        .order_by(InterviewIntelPost.fetched_at.desc())
        .limit(_MAX_SUMMARY_POSTS)
        .all()
    )
    return [
        scraper.PostDetail(
            pid=r.pid, company=r.company, interview_date=r.interview_date,
            position=r.position, questions_text=r.questions_text, parse_status="ok",
        )
        for r in rows
    ]


def _process_keyword(db: Session, chip: str, query: str, pid_cache: _PidCache) -> _ChipResult:
    result = _ChipResult(chip=chip)
    metas = scraper.search(query, limit=_DEFAULT_LIMIT)
    if not metas:
        return result

    for meta in metas:
        existing = db.query(InterviewIntelPost).filter_by(pid=meta.pid, keyword=chip).one_or_none()
        if _is_fresh(existing):
            continue
        cached = pid_cache.get(meta.pid)
        if cached is not None:
            detail = cached
        else:
            detail = scraper.fetch_post(meta.pid, title=meta.title)
            pid_cache.set(meta.pid, detail)
            time.sleep(random.uniform(0.4, 1.0))
        score = quality_scorer.score_post_quality(detail) if detail.parse_status == "ok" else 0
        _upsert_post(db, chip, detail, meta.title, quality_score=score)
        result.posts_fetched += 1
    db.commit()

    ok_posts = _collect_ok_posts_for_summary(db, chip)
    if not ok_posts:
        # Preserve existing summary if any — don't blow away a good one with empty.
        existing_kw = db.query(InterviewIntelKeyword).filter_by(keyword=chip).one_or_none()
        if existing_kw is None:
            _upsert_keyword(db, chip, "", 0)
            db.commit()
        return result

    posts_hash = _hash_pid_set([p.pid for p in ok_posts])
    existing_kw = db.query(InterviewIntelKeyword).filter_by(keyword=chip).one_or_none()
    if (
        existing_kw is not None
        and existing_kw.posts_hash == posts_hash
        and existing_kw.summary_md
    ):
        # Same pid set as last summary — skip the LLM call.
        return result

    summary = summarizer.summarize_keyword(chip, ok_posts)
    if summary:
        _upsert_keyword(db, chip, summary, len(ok_posts), posts_hash=posts_hash)
        db.commit()
    return result


def _run_chip_in_worker(chip: str, query: str, pid_cache: _PidCache) -> _ChipResult:
    db = SessionLocal()
    try:
        try:
            return _process_keyword(db, chip, query, pid_cache)
        except Exception as e:
            try:
                _upsert_keyword(db, chip, "", 0, error=str(e)[:500])
                db.commit()
            except Exception:
                db.rollback()
            return _ChipResult(chip=chip, error=str(e))
    finally:
        db.close()


def run_refresh(db: Optional[Session] = None, *, max_workers: int = _DEFAULT_MAX_WORKERS) -> RefreshStats:
    """Refresh nowcoder intel for all keywords.

    - max_workers > 1 (default): parallel chip fan-out; each worker opens its
      own SessionLocal. The `db` argument is ignored in this mode.
    - max_workers == 1: serial path using the passed `db`. Used by tests with
      in-memory SQLite (which is per-connection and not shareable across threads).
    """
    stats = RefreshStats()
    started = datetime.utcnow()
    try:
        keywords = _load_keywords()
    except Exception as e:
        _record_status({"last_run": started.isoformat(), "last_status": "failed", "last_error": f"keywords yaml: {e}"})
        stats.last_error = str(e)
        return stats

    stats.keywords_total = len(keywords)
    pid_cache = _PidCache()

    if max_workers <= 1:
        if db is None:
            raise ValueError("serial run_refresh requires a db session")
        for entry in keywords:
            chip, query = entry["chip"], entry["query"]
            try:
                result = _process_keyword(db, chip, query, pid_cache)
                stats.keywords_ok += 1
                stats.posts_fetched += result.posts_fetched
            except Exception as e:
                stats.keywords_failed += 1
                try:
                    _upsert_keyword(db, chip, "", 0, error=str(e)[:500])
                    db.commit()
                except Exception:
                    db.rollback()
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_run_chip_in_worker, e["chip"], e["query"], pid_cache) for e in keywords]
            for fut in as_completed(futures):
                result = fut.result()
                if result.error:
                    stats.keywords_failed += 1
                else:
                    stats.keywords_ok += 1
                    stats.posts_fetched += result.posts_fetched

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
