"""In-memory XHS knowledge retrieval — mirror of podcasts.retrieve."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models import XhsInsight, XhsNote
from app.services.podcasts.embed import DIMENSION, embed_one, from_blob

_CACHE_LOCK = threading.Lock()
_CACHE: dict | None = None
_CACHE_LOADED_AT: float = 0.0


@dataclass
class _CachedInsight:
    insight_id: str
    source_note_id: str
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
    dispute: dict  # {topic: [claim_a, claim_b, ...]} — 仅 conflicting 簇有, 其它为 {}
    vector: np.ndarray
    captured_at: float  # epoch seconds, for freshness decay


@dataclass
class _CachedNote:
    note_id: str
    title: str
    author_name: str
    liked_count: int
    comment_count: int
    source_url: str
    matched_keywords: list[str]


def _load_cache(db: Session) -> dict:
    insights = []
    matrix = []
    for row in db.query(XhsInsight).all():
        emb = row.embedding
        if not emb:
            continue
        v = from_blob(emb)
        if v.shape[0] != DIMENSION:
            continue
        types = json.loads(row.type_json or "[]")
        captured = row.captured_at.timestamp() if getattr(row, "captured_at", None) else 0.0
        # corroboration_json 兼容两种格式:
        #   list (verified / 老数据): [sibling_id, ...]
        #   dict (conflicting): {"siblings": [...], "dispute": {topic: [claims]}}
        _corro_raw = json.loads(row.corroboration_json or "[]")
        if isinstance(_corro_raw, dict):
            _siblings = _corro_raw.get("siblings") or []
            _dispute = _corro_raw.get("dispute") or {}
        else:
            _siblings = _corro_raw if isinstance(_corro_raw, list) else []
            _dispute = {}
        insights.append(_CachedInsight(
            insight_id=row.insight_id,
            source_note_id=row.source_note_id,
            types=types,
            primary_type=row.primary_type or (types[0] if types else ""),
            role_target=json.loads(row.role_target_json or "[]"),
            company_target=json.loads(row.company_target_json or "[]"),
            sector_target=json.loads(row.sector_target_json or "[]"),
            content=row.content or "",
            source_quote=row.source_quote or "",
            speaker=row.speaker or "unknown",
            confidence=row.confidence or "med",
            corroboration=_siblings,
            dispute=_dispute,
            vector=v,
            captured_at=captured,
        ))
        matrix.append(v)
    notes = {}
    for n in db.query(XhsNote).all():
        notes[n.note_id] = _CachedNote(
            note_id=n.note_id,
            title=n.title or "",
            author_name=n.author_name or "",
            liked_count=n.liked_count or 0,
            comment_count=n.comment_count or 0,
            source_url=n.source_url or "",
            matched_keywords=json.loads(n.matched_keywords_json or "[]"),
        )
    M = np.stack(matrix, axis=0) if matrix else np.zeros((0, DIMENSION), dtype=np.float32)
    return {"insights": insights, "matrix": M, "notes": notes}


def _ensure_cache(db: Session) -> dict:
    global _CACHE, _CACHE_LOADED_AT
    with _CACHE_LOCK:
        if _CACHE is None:
            _CACHE = _load_cache(db)
            _CACHE_LOADED_AT = time.time()
        return _CACHE


def count_by_company(db: Session, companies: list[str]) -> dict[str, int]:
    """Return {company: n_insights} for the given list.

    Used by platform aggregation to surface "X 条 同辈情报" chips on each
    platform card without a full retrieve() per platform.
    """
    if not companies:
        return {}
    cache = _ensure_cache(db)
    insights: list[_CachedInsight] = cache["insights"]
    if not insights:
        return {c: 0 for c in companies}
    by_company: dict[str, int] = {c: 0 for c in companies}
    company_set = set(companies)
    for ins in insights:
        # company_target 是 LLM 抽取的 canonical 名 list, 一条 insight 可挂多公司
        for tag in ins.company_target:
            if tag in company_set:
                by_company[tag] = by_company.get(tag, 0) + 1
    return by_company


def reload_cache(db: Session) -> int:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = _load_cache(db)
    return len(_CACHE["insights"])


CONF_RANK = {"verified": 5, "high": 3, "med": 2, "low": 1, "conflicting": 1}
# E4 (2026-05-30) 检索加权: confidence 高的乘大、过老的乘小; 半衰期 1 年 (面经长保鲜)
CONF_MUL = {"verified": 1.30, "high": 1.15, "med": 1.0, "low": 0.85, "conflicting": 0.7}


def _score_adj(base: float, ins: "_CachedInsight", now_ts: float) -> float:
    import math
    age_d = max(0.0, (now_ts - ins.captured_at) / 86400.0) if ins.captured_at else 365.0
    fresh = math.exp(-age_d / 365.0)
    return float(base) * CONF_MUL.get(ins.confidence, 1.0) * (0.85 + 0.15 * fresh)


def search(
    db: Session,
    *,
    query: str | None = None,
    types: list[str] | None = None,
    role: list[str] | None = None,
    company: list[str] | None = None,
    sector: list[str] | None = None,
    min_confidence: str | None = None,
    note_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    cache = _ensure_cache(db)
    insights: list[_CachedInsight] = cache["insights"]
    if not insights:
        return []

    type_set = set(types or [])
    role_set = set(role or [])
    company_set = set(company or [])
    sector_set = set(sector or [])
    min_conf = CONF_RANK.get(min_confidence or "low", 1)
    indices = []
    for i, ins in enumerate(insights):
        if note_id and ins.source_note_id != note_id:
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

    now_ts = time.time()
    if query:
        q = embed_one(query)
        sub_matrix = cache["matrix"][indices]
        scores = sub_matrix @ q
        adjusted = [_score_adj(float(scores[k]), insights[idx], now_ts) for k, idx in enumerate(indices)]
        order = sorted(range(len(indices)), key=lambda k: -adjusted[k])[:limit]
        ranked = [(indices[k], adjusted[k]) for k in order]
    else:
        ranked = []
        for i in indices:
            ins = insights[i]
            base = CONF_RANK.get(ins.confidence, 1) + len(ins.content) / 1000.0
            ranked.append((i, _score_adj(base, ins, now_ts)))
        ranked.sort(key=lambda x: -x[1])
        ranked = ranked[:limit]

    notes = cache["notes"]
    out = []
    for i, score in ranked:
        ins = insights[i]
        n = notes.get(ins.source_note_id)
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
            "dispute": ins.dispute,
            "source": {
                "note_id": ins.source_note_id,
                "title": n.title if n else "",
                "author": n.author_name if n else "",
                "liked": n.liked_count if n else 0,
                "comments": n.comment_count if n else 0,
                "url": n.source_url if n else "",
                "keywords": n.matched_keywords if n else [],
            } if n else None,
        })
    return out


def stats(db: Session) -> dict:
    cache = _ensure_cache(db)
    return {
        "n_notes": len(cache["notes"]),
        "n_insights": len(cache["insights"]),
        "cache_loaded_at": _CACHE_LOADED_AT,
    }
