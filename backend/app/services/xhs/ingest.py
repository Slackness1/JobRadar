"""Ingest XHS JSONL artifacts into SQLite + compute embeddings.

Re-uses DashScope text-embedding-v3 via app.services.podcasts.embed.

Usage:
    cd backend && PYTHONPATH=. .venv/bin/python -m app.services.xhs.ingest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.database import SessionLocal, engine
from app.models import Base, XhsInsight, XhsNote
from app.services.podcasts.embed import embed_many, to_blob

ROOT = Path(__file__).resolve().parents[3]
PROC = ROOT / "data/xhs/_processed"
NOTES = PROC / "notes_clean.jsonl"
INSIGHTS = PROC / "insights_dedup.jsonl"


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _embed_text_for_note(row: dict) -> str:
    parts = [
        row.get("title") or "",
        row.get("desc") or "",
        " ".join(row.get("tags") or []),
    ]
    return "\n".join(p for p in parts if p)[:2000]


def _embed_text_for_insight(row: dict) -> str:
    parts = [
        row.get("content") or "",
        row.get("source_quote") or "",
        " ".join(row.get("role_target") or []),
        " ".join(row.get("company_target") or []),
    ]
    return "\n".join(p for p in parts if p)[:1200]


def ingest_notes(db) -> tuple[int, int]:
    rows = _read_jsonl(NOTES)
    print(f"  Read {len(rows)} notes from {NOTES.name}")
    texts = [_embed_text_for_note(r) for r in rows]
    print(f"  Embedding {len(texts)} note texts...")
    vecs = embed_many(texts, on_progress=lambda n, t: print(f"    embed: {n}/{t}", end="\r"))
    print()
    created = updated = 0
    for r, v in zip(rows, vecs):
        existing = db.query(XhsNote).filter(XhsNote.note_id == r["note_id"]).first()
        payload = dict(
            note_id=r["note_id"],
            title=r.get("title") or "",
            desc=r.get("desc") or "",
            author_name=r.get("author_name") or "",
            author_id=r.get("author_id") or "",
            tags_json=json.dumps(r.get("tags") or [], ensure_ascii=False),
            liked_count=int(r.get("liked_count") or 0),
            collected_count=int(r.get("collected_count") or 0),
            comment_count=int(r.get("comment_count") or 0),
            signal_score=float(r.get("signal_score") or 0.0),
            matched_keywords_json=json.dumps(r.get("matched_keywords") or [], ensure_ascii=False),
            source_url=r.get("source_url") or "",
            time_iso=r.get("time_iso") or "",
            embedding=to_blob(v),
        )
        if existing:
            for k, val in payload.items():
                setattr(existing, k, val)
            updated += 1
        else:
            db.add(XhsNote(**payload))
            created += 1
    db.commit()
    return created, updated


def ingest_insights(db) -> tuple[int, int]:
    rows = _read_jsonl(INSIGHTS)
    print(f"  Read {len(rows)} insights from {INSIGHTS.name}")
    texts = [_embed_text_for_insight(r) for r in rows]
    print(f"  Embedding {len(texts)} insight texts...")
    vecs = embed_many(texts, on_progress=lambda n, t: print(f"    embed: {n}/{t}", end="\r"))
    print()
    created = updated = 0
    for r, v in zip(rows, vecs):
        existing = db.query(XhsInsight).filter(XhsInsight.insight_id == r["id"]).first()
        types = r.get("type") or ["role_insight"]
        payload = dict(
            insight_id=r["id"],
            source_note_id=r["source_note_id"],
            type_json=json.dumps(types, ensure_ascii=False),
            primary_type=types[0] if types else "",
            role_target_json=json.dumps(r.get("role_target") or [], ensure_ascii=False),
            company_target_json=json.dumps(r.get("company_target") or [], ensure_ascii=False),
            sector_target_json=json.dumps(r.get("sector_target") or [], ensure_ascii=False),
            content=r.get("content") or "",
            source_quote=r.get("source_quote") or "",
            speaker=r.get("speaker") or "unknown",
            confidence=r.get("confidence") or "med",
            corroboration_json=json.dumps(r.get("corroboration") or [], ensure_ascii=False),
            embedding=to_blob(v),
        )
        if existing:
            for k, val in payload.items():
                setattr(existing, k, val)
            updated += 1
        else:
            db.add(XhsInsight(**payload))
            created += 1
    db.commit()
    return created, updated


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("=== XHS Notes ===")
        c, u = ingest_notes(db)
        print(f"  notes: created={c}, updated={u}")
        print("=== XHS Insights ===")
        c, u = ingest_insights(db)
        print(f"  insights: created={c}, updated={u}")
        n_n = db.query(XhsNote).count()
        n_i = db.query(XhsInsight).count()
        print(f"\nFinal: {n_n} notes, {n_i} insights in DB.")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
