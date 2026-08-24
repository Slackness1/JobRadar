from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jobradar_core.database import LocalDatabase
from jobradar_core.models import JobRecord, JobSearchQuery, JobSearchResult, utc_now_iso
from jobradar_core.workspace import Workspace

_TERM_RE = re.compile(r"[A-Za-z0-9+#.\-]{2,}|[\u4e00-\u9fff]{2,}")
_TOP_QUALITY_HINTS = ("top", "tier1", "头部", "大厂", "一线", "央企", "外资")


@dataclass(frozen=True)
class ImportResult:
    source_path: str
    imported: int
    skipped: int
    errors: tuple[str, ...] = ()


class JobRepository:
    def __init__(self, database: LocalDatabase):
        self.database = database

    def upsert_many(self, jobs: Iterable[JobRecord]) -> tuple[int, int]:
        imported = 0
        skipped = 0
        with self.database.transaction() as connection:
            for job in jobs:
                if not job.job_id or not (job.title or job.description or job.requirements):
                    skipped += 1
                    continue
                search_text = " ".join(
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.track,
                        job.description,
                        job.requirements,
                    )
                ).lower()
                connection.execute(
                    """INSERT INTO jobs
                       (job_id, source, company, title, location, track, job_type,
                        description, requirements, url, publish_date, deadline,
                        crawled_at, quality_label, link_status, search_text, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(job_id) DO UPDATE SET
                         source=excluded.source,
                         company=excluded.company,
                         title=excluded.title,
                         location=excluded.location,
                         track=excluded.track,
                         job_type=excluded.job_type,
                         description=excluded.description,
                         requirements=excluded.requirements,
                         url=excluded.url,
                         publish_date=excluded.publish_date,
                         deadline=excluded.deadline,
                         crawled_at=excluded.crawled_at,
                         quality_label=excluded.quality_label,
                         link_status=excluded.link_status,
                         search_text=excluded.search_text,
                         updated_at=excluded.updated_at""",
                    (
                        job.job_id,
                        job.source,
                        job.company,
                        job.title,
                        job.location,
                        job.track,
                        job.job_type,
                        job.description,
                        job.requirements,
                        job.url,
                        job.publish_date,
                        job.deadline,
                        job.crawled_at,
                        job.quality_label,
                        job.link_status,
                        search_text,
                        utc_now_iso(),
                    ),
                )
                imported += 1
        return imported, skipped

    def count(self) -> int:
        with self.database.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    def get(self, job_id: str) -> JobRecord | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def search(self, query: JobSearchQuery) -> list[JobSearchResult]:
        terms = _search_terms(query.text)
        clauses: list[str] = []
        params: list[object] = []
        if query.company:
            clauses.append("j.company LIKE ?")
            params.append(f"%{query.company}%")
        if query.location:
            clauses.append("j.location LIKE ?")
            params.append(f"%{query.location}%")
        if query.track:
            clauses.append("(j.track LIKE ? OR j.search_text LIKE ?)")
            params.extend((f"%{query.track}%", f"%{query.track.lower()}%"))
        if query.job_type:
            clauses.append("j.job_type=?")
            params.append(query.job_type)
        if terms:
            term_clauses = []
            for term in terms:
                term_clauses.append("j.search_text LIKE ?")
                params.append(f"%{term.lower()}%")
            clauses.append(f"({' OR '.join(term_clauses)})")
        if query.favorites_only:
            clauses.append("COALESCE(s.favorite, 0)=1")
        if not query.include_excluded:
            clauses.append("COALESCE(s.excluded, 0)=0")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        candidate_limit = max(query.limit * 8, 200)
        sql = f"""SELECT j.*, COALESCE(s.favorite, 0) AS favorite,
                         COALESCE(s.excluded, 0) AS excluded
                  FROM jobs j
                  LEFT JOIN job_user_state s ON s.job_id=j.job_id
                  {where}
                  ORDER BY j.publish_date DESC, j.updated_at DESC
                  LIMIT ?"""
        params.append(candidate_limit)

        fts_scores = self._fts_scores(terms, candidate_limit)
        with self.database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        ranked = [self._score_row(row, query, terms, fts_scores) for row in rows]
        ranked.sort(key=lambda item: (item.score, item.job.publish_date), reverse=True)
        return ranked[: query.limit]

    def _fts_scores(self, terms: list[str], limit: int) -> dict[int, float]:
        if not terms:
            return {}
        safe_terms = [term.replace('"', "") for term in terms if term.replace('"', "")]
        if not safe_terms:
            return {}
        expression = " OR ".join(f'"{term}"' for term in safe_terms)
        try:
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT rowid, bm25(jobs_fts) AS rank FROM jobs_fts "
                    "WHERE jobs_fts MATCH ? LIMIT ?",
                    (expression, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            return {}
        if not rows:
            return {}
        raw = {int(row["rowid"]): abs(float(row["rank"])) for row in rows}
        maximum = max(raw.values()) or 1.0
        return {row_id: min(score / maximum, 1.0) for row_id, score in raw.items()}

    def _score_row(
        self,
        row: sqlite3.Row,
        query: JobSearchQuery,
        terms: list[str],
        fts_scores: dict[int, float],
    ) -> JobSearchResult:
        job = _row_to_job(row)
        text = " ".join(
            (job.title, job.company, job.location, job.track, job.description, job.requirements)
        ).lower()
        title_text = f"{job.title} {job.track}".lower()
        matched = [term for term in terms if term.lower() in text]
        title_matches = [term for term in terms if term.lower() in title_text]
        lexical = (len(matched) / len(terms)) if terms else 0.45
        title_score = (len(title_matches) / len(terms)) if terms else 0.0
        fts = fts_scores.get(int(row["id"]), 0.0)
        location = 1.0 if query.location and query.location in job.location else 0.0
        track = 1.0 if query.track and query.track.lower() in text else 0.0
        recency, stale = _recency_score(job.publish_date or job.crawled_at)
        quality = 1.0 if any(h in job.quality_label.lower() for h in _TOP_QUALITY_HINTS) else 0.0
        favorite = bool(row["favorite"])
        score = (
            lexical * 0.34
            + title_score * 0.18
            + fts * 0.08
            + location * 0.12
            + track * 0.12
            + recency * 0.11
            + quality * 0.03
            + (0.02 if favorite else 0.0)
        )
        reasons: list[str] = []
        if title_matches:
            reasons.append(f"Title match: {', '.join(title_matches[:3])}")
        elif matched:
            reasons.append(f"JD match: {', '.join(matched[:3])}")
        if location:
            reasons.append(f"Location match: {query.location}")
        if track:
            reasons.append(f"Track match: {query.track}")
        if quality:
            reasons.append("Matched a local source-quality signal")
        if not reasons:
            reasons.append("Matched the current structured filters")
        risks: list[str] = []
        if stale:
            risks.append("Older listing; verify that it is still open at the source")
        if job.link_status == "dead":
            risks.append("The source link was previously marked unavailable")
        if not job.requirements and not job.description:
            risks.append("The job description is incomplete")
        return JobSearchResult(
            job=job,
            score=max(0.0, min(round(score, 4), 1.0)),
            reasons=reasons,
            risks=risks,
            features={
                "lexical": round(lexical, 3),
                "title": round(title_score, 3),
                "location": location,
                "track": track,
                "recency": round(recency, 3),
            },
            favorite=favorite,
            excluded=bool(row["excluded"]),
        )

    def set_favorite(self, job_id: str, favorite: bool) -> None:
        self._set_state(job_id, favorite=int(favorite))

    def set_excluded(self, job_id: str, excluded: bool, reason: str = "") -> None:
        self._set_state(job_id, excluded=int(excluded), exclude_reason=reason)

    def _set_state(self, job_id: str, **updates: object) -> None:
        if not self.get(job_id):
            raise KeyError(f"unknown job_id: {job_id}")
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO job_user_state(
                       job_id, favorite, excluded, exclude_reason, updated_at
                   )
                   VALUES (?, 0, 0, '', ?)
                   ON CONFLICT(job_id) DO NOTHING""",
                (job_id, utc_now_iso()),
            )
            values = {**updates, "updated_at": utc_now_iso()}
            assignments = ", ".join(f"{key}=?" for key in values)
            connection.execute(
                f"UPDATE job_user_state SET {assignments} WHERE job_id=?",  # noqa: S608
                (*values.values(), job_id),
            )


class JobImporter:
    def __init__(self, repository: JobRepository, workspace: Workspace):
        self.repository = repository
        self.workspace = workspace

    def import_path(self, path: Path) -> ImportResult:
        source = path.expanduser().resolve(strict=True)
        preserved = self.workspace.import_user_file(source, self.workspace.job_imports)
        errors: list[str] = []
        jobs: list[JobRecord] = []
        try:
            rows = list(self._read_rows(source))
        except (OSError, ValueError, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
            return ImportResult(str(preserved), 0, 0, (str(exc),))
        for index, row in enumerate(rows, start=1):
            try:
                jobs.append(_mapping_to_job(row, source.stem))
            except (TypeError, ValueError) as exc:
                errors.append(f"row {index}: {exc}")
        imported, skipped = self.repository.upsert_many(jobs)
        return ImportResult(str(preserved), imported, skipped, tuple(errors[:20]))

    def _read_rows(self, path: Path) -> Iterable[Mapping[str, object]]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                yield from csv.DictReader(handle)
            return
        if suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        data = json.loads(line)
                        if not isinstance(data, dict):
                            raise ValueError("each JSONL row must be an object")
                        yield data
            return
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("jobs", [data])
            if not isinstance(data, list):
                raise ValueError("JSON import must be an object, list, or {'jobs': [...]} object")
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError("every job must be a JSON object")
                yield item
            return
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                for row in connection.execute("SELECT * FROM jobs"):
                    yield dict(row)
            finally:
                connection.close()
            return
        raise ValueError("supported job imports: .csv, .json, .jsonl, .db, .sqlite")


def _mapping_to_job(row: Mapping[str, object], fallback_source: str) -> JobRecord:
    def value(*keys: str) -> str:
        for key in keys:
            candidate = row.get(key)
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()
        return ""

    source = value("source") or fallback_source or "local_import"
    company = value("company", "company_name")
    title = value("job_title", "title", "position", "name")
    location = value("location", "city")
    description = value("job_duty", "description", "duties", "content")
    requirements = value("job_req", "requirements", "requirement")
    url = value("detail_url", "url", "apply_url")
    raw_id = value("job_id", "id")
    job_id = (
        raw_id
        or hashlib.sha256(
            "\x1f".join((source, company, title, location, url)).encode()
        ).hexdigest()[:16]
    )
    return JobRecord(
        job_id=job_id,
        source=source,
        company=company,
        title=title,
        location=location,
        track=value("sub_category", "canonical_track", "track", "track_predicted"),
        job_type=value("job_stage", "job_type", "type") or "campus",
        description=description,
        requirements=requirements,
        url=url,
        publish_date=value("publish_date", "published_at"),
        deadline=value("deadline", "close_date"),
        crawled_at=value("scraped_at", "crawled_at", "updated_at"),
        quality_label=value("quality_label", "institution_tier"),
        link_status=value("link_status"),
    )


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        job_id=row["job_id"],
        source=row["source"],
        company=row["company"],
        title=row["title"],
        location=row["location"],
        track=row["track"],
        job_type=row["job_type"],
        description=row["description"],
        requirements=row["requirements"],
        url=row["url"],
        publish_date=row["publish_date"],
        deadline=row["deadline"],
        crawled_at=row["crawled_at"],
        quality_label=row["quality_label"],
        link_status=row["link_status"],
    )


def _search_terms(text: str) -> list[str]:
    terms = _TERM_RE.findall(text.strip())
    seen: set[str] = set()
    output: list[str] = []
    for term in terms:
        normalized = term.lower()
        if normalized not in seen:
            seen.add(normalized)
            output.append(term)
    return output[:12]


def _recency_score(value: str) -> tuple[float, bool]:
    if not value:
        return 0.25, False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        age_days = max(0, (datetime.now(UTC) - parsed).days)
    except ValueError:
        return 0.25, False
    if age_days <= 7:
        return 1.0, False
    if age_days <= 30:
        return 0.75, False
    if age_days <= 60:
        return 0.45, True
    return 0.15, True
