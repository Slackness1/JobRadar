"""Ingest podcast JSONL artifacts into SQLite + compute embeddings.

Idempotent: existing rows updated on rerun (matched by eid / insight_id).

Usage:
    cd backend && PYTHONPATH=. .venv/bin/python -m app.services.podcasts.ingest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.database import SessionLocal, engine
from app.models import Base, PodcastEpisode, PodcastInsight
from app.services.podcasts.embed import embed_many, to_blob

ROOT = Path(__file__).resolve().parents[3]
PROC = ROOT / "data/podcasts/_processed"
SUMMARIES = PROC / "episode_summaries.jsonl"
INSIGHTS = PROC / "insights_dedup.jsonl"


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _embed_text_for_episode(row: dict) -> str:
    """Build searchable text for an episode embedding."""
    parts = [
        row.get("topic_one_liner") or "",
        row.get("title") or "",
        row.get("summary_500") or "",
        " | ".join(row.get("hot_takes") or []),
    ]
    return "\n".join(p for p in parts if p)[:2000]


def _embed_text_for_insight(row: dict) -> str:
    """Build searchable text for an insight embedding."""
    parts = [
        row.get("content") or "",
        row.get("source_quote") or "",
        " ".join(row.get("role_target") or []),
        " ".join(row.get("company_target") or []),
    ]
    return "\n".join(p for p in parts if p)[:1200]


def ingest_episodes(db) -> tuple[int, int]:
    """Returns (created, updated)."""
    rows = _read_jsonl(SUMMARIES)
    print(f"  Read {len(rows)} episodes from {SUMMARIES.name}")
    texts = [_embed_text_for_episode(r) for r in rows]
    print(f"  Embedding {len(texts)} episode texts...")
    vecs = embed_many(texts, on_progress=lambda n, t: print(f"    embed: {n}/{t}", end="\r"))
    print()
    created = updated = 0
    for r, v in zip(rows, vecs):
        existing = db.query(PodcastEpisode).filter(PodcastEpisode.eid == r["eid"]).first()
        payload = dict(
            eid=r["eid"],
            show=r.get("show") or "",
            title=r.get("title") or "",
            duration_sec=int(r.get("duration_min") or 0) * 60,
            topic_one_liner=r.get("topic_one_liner") or "",
            summary_500=r.get("summary_500") or "",
            audience=r.get("audience") or "",
            guests_json=json.dumps(r.get("guests") or [], ensure_ascii=False),
            hot_takes_json=json.dumps(r.get("hot_takes") or [], ensure_ascii=False),
            covers_role_json=json.dumps(r.get("covers_role") or [], ensure_ascii=False),
            covers_company_json=json.dumps(r.get("covers_company") or [], ensure_ascii=False),
            covers_sector_json=json.dumps(r.get("covers_sector") or [], ensure_ascii=False),
            embedding=to_blob(v),
        )
        if existing:
            for k, val in payload.items():
                setattr(existing, k, val)
            updated += 1
        else:
            db.add(PodcastEpisode(**payload))
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
        existing = db.query(PodcastInsight).filter(PodcastInsight.insight_id == r["id"]).first()
        types = r.get("type") or ["role_insight"]
        payload = dict(
            insight_id=r["id"],
            source_eid=r["source_eid"],
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
            db.add(PodcastInsight(**payload))
            created += 1
    db.commit()
    return created, updated


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("=== Episodes ===")
        c, u = ingest_episodes(db)
        print(f"  episodes: created={c}, updated={u}")
        print("=== Insights ===")
        c, u = ingest_insights(db)
        print(f"  insights: created={c}, updated={u}")
        # Final counts
        n_ep = db.query(PodcastEpisode).count()
        n_in = db.query(PodcastInsight).count()
        print(f"\nFinal: {n_ep} episodes, {n_in} insights in DB.")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
