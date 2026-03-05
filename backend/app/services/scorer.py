"""Score all jobs against all tracks. Reads config from DB."""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.models import Job, Track, KeywordGroup, Keyword, JobScore, ScoringConfig, ExcludeRule


def _get_scoring_config(db: Session) -> dict:
    cfg = db.query(ScoringConfig).first()
    if cfg:
        return json.loads(cfg.config_json)
    return {}


def _get_all_exclude_keywords(db: Session) -> list[str]:
    rules = db.query(ExcludeRule).all()
    return [r.keyword.lower() for r in rules]


def _build_track_keywords(track: Track) -> dict[str, list[str]]:
    result = {}
    for group in track.groups:
        result[group.group_name] = [kw.word for kw in group.keywords]
    return result


def _expand_with_synonyms(words: list[str], synonyms: dict) -> list[str]:
    expanded = set(w.lower() for w in words)
    for w in words:
        w_lower = w.lower()
        for _skill_name, skill_data in synonyms.items():
            canonical = skill_data.get("canonical", "").lower()
            syns = [s.lower() for s in skill_data.get("synonyms", [])]
            if w_lower == canonical:
                expanded.update(syns)
            elif w_lower in syns:
                expanded.add(canonical)
                expanded.update(syns)
    return list(expanded)


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    if not text:
        return []
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _job_text(job: Job) -> str:
    return " ".join([
        job.job_title or "",
        job.job_req or "",
        job.job_duty or "",
        job.major_req or "",
    ])


def _should_exclude(job: Job, exclude_kws: list[str]) -> bool:
    text = " ".join([
        job.job_title or "",
        job.job_req or "",
        job.job_duty or "",
        job.location or "",
    ]).lower()
    return any(kw in text for kw in exclude_kws)


def score_all_jobs(db: Session, job_ids: Optional[list[int]] = None) -> int:
    """Score jobs against all tracks. Returns number of scores written."""
    config = _get_scoring_config(db)
    synonyms = config.get("skill_synonyms", {})
    exclude_kws = _get_all_exclude_keywords(db)

    tracks = (
        db.query(Track)
        .options(joinedload(Track.groups).joinedload(KeywordGroup.keywords))
        .all()
    )

    if job_ids:
        jobs = db.query(Job).filter(Job.id.in_(job_ids)).all()
    else:
        jobs = db.query(Job).all()

    count = 0
    for job in jobs:
        if _should_exclude(job, exclude_kws):
            continue

        text = _job_text(job)

        for track in tracks:
            group_kws = _build_track_keywords(track)
            all_matched = []
            total_score = 0

            for group_name, words in group_kws.items():
                expanded = _expand_with_synonyms(words, synonyms)
                matched = _match_keywords(text, expanded)
                if matched:
                    total_score += len(matched) * 2
                    all_matched.extend(matched[:5])

            if total_score < track.min_score:
                continue

            existing = (
                db.query(JobScore)
                .filter(JobScore.job_id == job.id, JobScore.track_id == track.id)
                .first()
            )
            if existing:
                existing.score = total_score
                existing.matched_keywords = json.dumps(all_matched[:15], ensure_ascii=False)
                existing.scored_at = datetime.utcnow()
            else:
                db.add(JobScore(
                    job_id=job.id,
                    track_id=track.id,
                    score=total_score,
                    matched_keywords=json.dumps(all_matched[:15], ensure_ascii=False),
                ))
            count += 1

    db.commit()
    return count
