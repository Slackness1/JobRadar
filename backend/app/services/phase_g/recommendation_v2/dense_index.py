"""S1 稠密召回 — 岗位 JD embedding 存储 + in-memory cosine 检索。

全复用 `podcasts/embed.py`(DashScope text-embedding-v3, 1024 维, 已归一化 → dot=cosine)。
只 embed 过质量闸(good/intern)的岗;document = 公司+标题+职责+要求(**不含 sub_category** ——
那是要解绑的标签)。content_hash 幂等:JD 没变就跳过重 embed。

实验期 `job_embeddings` 表用 CREATE TABLE IF NOT EXISTS 懒建;**上 prod 前补正式 Alembic 迁移**。
向量库?不需要 —— 1.3 万岗 53MB 暴力 cosine <10ms,镜像 xhs/retrieve 的内存缓存模式。
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Callable, Optional, Sequence

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.podcasts.embed import DIMENSION, embed_many, from_blob, to_blob

# 注入式 embedder:默认走 DashScope;测试传 fake 避免网络。
EmbedFn = Callable[[Sequence[str]], list[np.ndarray]]

_QUALITY_POOL = ("good", "internship_only")
_DOC_MAXLEN = 2000  # 中文字符截断;text-embedding-v3 容量够,截断只为省 token/稳定


def job_document(company: str, job_title: str, job_duty: str, job_req: str) -> str:
    """构造岗位语义文本(用于 embedding)。故意不含 sub_category。"""
    head = " ".join(p for p in (company or "", job_title or "") if p.strip())
    body = "\n".join(p for p in (job_duty or "", job_req or "") if p.strip())
    doc = (head + "\n" + body).strip()
    return doc[:_DOC_MAXLEN]


def content_hash(doc: str) -> str:
    return hashlib.md5(doc.encode("utf-8")).hexdigest()


def ensure_tables(db: Session) -> None:
    """懒建 job_embeddings 表(实验期)。正式上线走 Alembic。"""
    db.execute(text(
        "CREATE TABLE IF NOT EXISTS job_embeddings ("
        " job_id INTEGER PRIMARY KEY,"
        " vector BLOB NOT NULL,"
        " content_hash TEXT NOT NULL,"
        " embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    ))
    db.commit()


def _pool_rows(db: Session, limit: Optional[int] = None) -> list[tuple]:
    """取过质量闸、活链、有 JD 的岗:(id, company, job_title, job_duty, job_req)。"""
    q = (
        "SELECT id, company, job_title, job_duty, job_req FROM jobs "
        "WHERE quality_label IN ('good','internship_only') "
        "AND (link_status IS NULL OR link_status != 'dead') "
        "AND (COALESCE(job_duty,'')!='' OR COALESCE(job_req,'')!='')"
    )
    if limit:
        q += f" LIMIT {int(limit)}"
    return db.execute(text(q)).fetchall()


def backfill_embeddings(
    db: Session,
    *,
    embed_fn: EmbedFn = embed_many,
    batch: int = 200,
    limit: Optional[int] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """给质量池里 content_hash 缺失/变化的岗补 embedding。幂等、可断点重跑。

    返回 {scanned, embedded, skipped}。
    """
    ensure_tables(db)
    existing = {
        r[0]: r[1]
        for r in db.execute(text("SELECT job_id, content_hash FROM job_embeddings")).fetchall()
    }
    rows = _pool_rows(db, limit=limit)
    todo: list[tuple[int, str]] = []  # (job_id, doc)
    skipped = 0
    for jid, company, title, duty, req in rows:
        doc = job_document(company, title, duty, req)
        if not doc:
            continue
        h = content_hash(doc)
        if existing.get(jid) == h:
            skipped += 1
            continue
        todo.append((jid, doc))

    embedded = 0
    total = len(todo)
    for i in range(0, total, batch):
        chunk = todo[i:i + batch]
        vecs = embed_fn([d for _, d in chunk])
        for (jid, doc), v in zip(chunk, vecs):
            v = np.asarray(v, dtype=np.float32)
            db.execute(
                text(
                    "INSERT INTO job_embeddings (job_id, vector, content_hash, embedded_at) "
                    "VALUES (:jid, :vec, :h, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(job_id) DO UPDATE SET "
                    "vector=excluded.vector, content_hash=excluded.content_hash, "
                    "embedded_at=excluded.embedded_at"
                ),
                {"jid": jid, "vec": to_blob(v), "h": content_hash(doc)},
            )
        db.commit()
        embedded += len(chunk)
        if on_progress:
            on_progress(embedded, total)
    return {"scanned": len(rows), "embedded": embedded, "skipped": skipped}


# ─── in-memory cosine cache(镜像 xhs/retrieve)──────────────────────────────
_CACHE_LOCK = threading.Lock()
_CACHE: dict | None = None
_CACHE_AT: float = 0.0


def _load_cache(db: Session) -> dict:
    ensure_tables(db)
    ids: list[int] = []
    mat: list[np.ndarray] = []
    for jid, blob in db.execute(text("SELECT job_id, vector FROM job_embeddings")).fetchall():
        v = from_blob(blob)
        if v.shape[0] != DIMENSION:
            continue
        ids.append(int(jid))
        mat.append(v)
    M = np.stack(mat, axis=0) if mat else np.zeros((0, DIMENSION), dtype=np.float32)
    return {"ids": ids, "matrix": M, "pos": {jid: i for i, jid in enumerate(ids)}}


def _ensure_cache(db: Session) -> dict:
    global _CACHE, _CACHE_AT
    with _CACHE_LOCK:
        if _CACHE is None:
            _CACHE = _load_cache(db)
            _CACHE_AT = time.time()
        return _CACHE


def reload_cache(db: Session) -> int:
    global _CACHE, _CACHE_AT
    with _CACHE_LOCK:
        _CACHE = _load_cache(db)
        _CACHE_AT = time.time()
    return len(_CACHE["ids"])


def dense_search(
    db: Session,
    query_text: str,
    *,
    embed_fn: EmbedFn = embed_many,
    allowed_ids: Optional[Sequence[int]] = None,
    k: int = 200,
) -> list[tuple[int, float]]:
    """对 query 文本做稠密召回:cosine 排序,可限定在 allowed_ids 内(硬过滤后的集合)。

    返回 [(job_id, cosine_score)],降序,top-k。allowed_ids 为空集 → 返回 []。
    """
    if not (query_text or "").strip():
        return []
    cache = _ensure_cache(db)
    ids: list[int] = cache["ids"]
    M: np.ndarray = cache["matrix"]
    if M.shape[0] == 0:
        return []
    q = np.asarray(embed_fn([query_text])[0], dtype=np.float32)
    n = np.linalg.norm(q)
    if n > 0:
        q = q / n
    sims = M @ q  # 已归一化 → dot = cosine
    if allowed_ids is not None:
        allow = set(int(x) for x in allowed_ids)
        order = [(ids[i], float(sims[i])) for i in range(len(ids)) if ids[i] in allow]
        order.sort(key=lambda t: t[1], reverse=True)
        return order[:k]
    idx = np.argsort(-sims)[:k]
    return [(ids[i], float(sims[i])) for i in idx]
