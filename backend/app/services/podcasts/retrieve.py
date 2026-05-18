"""In-memory podcast knowledge retrieval.

Loads all PodcastInsight rows + embeddings into RAM on first call (small: ~4MB).
Supports semantic search (cosine sim via dot product on normalized vectors)
combined with structured filters (type, role, company, sector, confidence).
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models import PodcastEpisode, PodcastInsight
from app.services.podcasts.embed import DIMENSION, embed_one, from_blob

_CACHE_LOCK = threading.Lock()
_CACHE: dict | None = None
_CACHE_LOADED_AT: float = 0.0


@dataclass
class _CachedInsight:
    insight_id: str
    source_eid: str
    types: list[str]
    primary_type: str
    role_target: list[str]
    company_target: list[str]
    sector_target: list[str]
    content: str
    source_quote: str
    speaker: str
    confidence: str
    corroboration: list
    vector: np.ndarray  # already normalized


@dataclass
class _CachedEpisode:
    eid: str
    show: str
    title: str
    topic_one_liner: str
    audience: str
    duration_sec: int


def _load_cache(db: Session) -> dict:
    insights = []
    matrix = []
    for row in db.query(PodcastInsight).all():
        emb = row.embedding
        if not emb:
            continue
        v = from_blob(emb)
        if v.shape[0] != DIMENSION:
            continue
        types = json.loads(row.type_json or "[]")
        insights.append(_CachedInsight(
            insight_id=row.insight_id,
            source_eid=row.source_eid,
            types=types,
            primary_type=row.primary_type or (types[0] if types else ""),
            role_target=json.loads(row.role_target_json or "[]"),
            company_target=json.loads(row.company_target_json or "[]"),
            sector_target=json.loads(row.sector_target_json or "[]"),
            content=row.content or "",
            source_quote=row.source_quote or "",
            speaker=row.speaker or "unknown",
            confidence=row.confidence or "med",
            corroboration=json.loads(row.corroboration_json or "[]"),
            vector=v,
        ))
        matrix.append(v)
    episodes = {}
    for ep in db.query(PodcastEpisode).all():
        episodes[ep.eid] = _CachedEpisode(
            eid=ep.eid,
            show=ep.show or "",
            title=ep.title or "",
            topic_one_liner=ep.topic_one_liner or "",
            audience=ep.audience or "",
            duration_sec=ep.duration_sec or 0,
        )
    M = np.stack(matrix, axis=0) if matrix else np.zeros((0, DIMENSION), dtype=np.float32)
    return {"insights": insights, "matrix": M, "episodes": episodes}


def _ensure_cache(db: Session) -> dict:
    global _CACHE, _CACHE_LOADED_AT
    with _CACHE_LOCK:
        if _CACHE is None:
            _CACHE = _load_cache(db)
            _CACHE_LOADED_AT = time.time()
        return _CACHE


def reload_cache(db: Session) -> int:
    """Force cache reload (call after ingest)."""
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = _load_cache(db)
    return len(_CACHE["insights"])


CONF_RANK = {"high": 3, "med": 2, "low": 1}


def search(
    db: Session,
    *,
    query: str | None = None,
    types: list[str] | None = None,
    role: list[str] | None = None,
    company: list[str] | None = None,
    sector: list[str] | None = None,
    min_confidence: str | None = None,
    eid: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Returns ranked insight rows with attached source episode metadata."""
    cache = _ensure_cache(db)
    insights: list[_CachedInsight] = cache["insights"]
    if not insights:
        return []

    # Build filter mask
    indices = []
    type_set = set(types or [])
    role_set = set(role or [])
    company_set = set(company or [])
    sector_set = set(sector or [])
    min_conf = CONF_RANK.get(min_confidence or "low", 1)
    for i, ins in enumerate(insights):
        if eid and ins.source_eid != eid:
            continue
        if type_set and not (type_set & set(ins.types)):
            continue
        if role_set and not (role_set & set(ins.role_target)):
            continue
        if company_set and not (company_set & set(ins.company_target)):
            continue
        if sector_set and not (sector_set & set(ins.sector_target)):
            continue
        if CONF_RANK.get(ins.confidence, 1) < min_conf:
            continue
        indices.append(i)

    if not indices:
        return []

    # Score
    if query:
        q = embed_one(query)
        sub_matrix = cache["matrix"][indices]
        scores = sub_matrix @ q  # cosine since normalized
        order = np.argsort(-scores)[:limit]
        ranked = [(indices[int(j)], float(scores[int(j)])) for j in order]
    else:
        # Filter-only: rank by confidence then content length
        ranked = []
        for i in indices:
            ins = insights[i]
            ranked.append((i, CONF_RANK.get(ins.confidence, 1) + len(ins.content) / 1000.0))
        ranked.sort(key=lambda x: -x[1])
        ranked = ranked[:limit]

    episodes = cache["episodes"]
    out = []
    for i, score in ranked:
        ins = insights[i]
        ep = episodes.get(ins.source_eid)
        out.append({
            "insight_id": ins.insight_id,
            "score": round(score, 4),
            "type": ins.types,
            "role_target": ins.role_target,
            "company_target": ins.company_target,
            "sector_target": ins.sector_target,
            "content": ins.content,
            "source_quote": ins.source_quote,
            "speaker": ins.speaker,
            "confidence": ins.confidence,
            "corroboration": ins.corroboration,
            "source": {
                "eid": ins.source_eid,
                "show": ep.show if ep else "",
                "title": ep.title if ep else "",
                "topic": ep.topic_one_liner if ep else "",
            } if ep else None,
        })
    return out


def stats(db: Session) -> dict:
    cache = _ensure_cache(db)
    return {
        "n_episodes": len(cache["episodes"]),
        "n_insights": len(cache["insights"]),
        "cache_loaded_at": _CACHE_LOADED_AT,
    }
