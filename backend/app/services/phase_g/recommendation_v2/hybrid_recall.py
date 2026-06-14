"""S1 升级版混合召回:稀疏(FTS5 BM25)+ 稠密(cosine)+ metadata 硬过滤 → RRF 融合。

核心设计(对照 recall.py 的纯 SQL 路径):
- **硬过滤(SQL)** 只管"能不能要":quality good/intern、活链、新鲜度、城市。
  **故意丢掉 `sub_category IN (...)` 闸** —— 这是把召回从标签解绑的关键:
  sub_cat 为空/标错的岗只要 JD 语义相关也能召回。
- **语义相关(dense + sparse)** 在硬过滤后的集合里排序,RRF 融合两路。
- 输出 Job 列表(按融合序),喂给现有 scoring + LLM 精排(不改它们)。

feature-flag 在 dispatcher 控制;本模块纯函数式,默认不被调用。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Job
from app.services.phase_g.recommendation_v2 import dense_index, sparse_index

_LOCATION_AGNOSTIC_KW = ("全国", "远程", "不限", "多地", "各地")


def hard_filter_ids(
    db: Session,
    *,
    freshness_days: int = 30,
    preferred_locations: Sequence[str] = (),
    quality_labels: tuple[str, ...] = ("good", "internship_only"),
) -> set[int]:
    """SQL 硬过滤 → allowed job id 集合。**不含 sub_category 闸**(解绑关键)。"""
    cutoff = datetime.utcnow() - timedelta(days=freshness_days)
    conds = [
        "quality_label IN :qls",
        "scraped_at > :cutoff",
        "(link_status IS NULL OR link_status != 'dead')",
        "(COALESCE(job_duty,'')!='' OR COALESCE(job_req,'')!='')",
    ]
    params: dict = {"cutoff": cutoff}
    locs = [str(c).strip() for c in (preferred_locations or []) if str(c).strip()]
    loc_sql = ""
    if locs:
        ors = ["location IS NULL", "location = ''"]
        for i, kw in enumerate(_LOCATION_AGNOSTIC_KW):
            ors.append(f"location LIKE :agk{i}")
            params[f"agk{i}"] = f"%{kw}%"
        for i, city in enumerate(locs):
            ors.append(f"location LIKE :loc{i}")
            params[f"loc{i}"] = f"%{city}%"
        loc_sql = " AND (" + " OR ".join(ors) + ")"
    # quality_labels 用 expanding bindparam
    q = text(
        "SELECT id FROM jobs WHERE quality_label IN :qls AND scraped_at > :cutoff "
        "AND (link_status IS NULL OR link_status != 'dead') "
        "AND (COALESCE(job_duty,'')!='' OR COALESCE(job_req,'')!='')" + loc_sql
    ).bindparams(__import__("sqlalchemy").bindparam("qls", expanding=True))
    params["qls"] = list(quality_labels)
    rows = db.execute(q, params).fetchall()
    return {int(r[0]) for r in rows}


def rrf_fuse(
    rankers: list[list[tuple[int, float]]],
    *,
    k_rrf: int = 60,
    weights: Optional[list[float]] = None,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion:每路 ranker 贡献 w/(k_rrf + rank)。返回融合降序 [(id, score)]。

    RRF 对不同量纲(cosine vs BM25)鲁棒 —— 只用排名,不用绝对分。
    """
    if weights is None:
        weights = [1.0] * len(rankers)
    score: dict[int, float] = {}
    for ranker, w in zip(rankers, weights):
        for rank, (jid, _s) in enumerate(ranker):
            score[jid] = score.get(jid, 0.0) + w / (k_rrf + rank)
    fused = sorted(score.items(), key=lambda t: t[1], reverse=True)
    return fused


def hybrid_recall(
    db: Session,
    query_text: str,
    *,
    freshness_days: int = 30,
    preferred_locations: Sequence[str] = (),
    k: int = 200,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    embed_fn=dense_index.embed_many,
    target_sub_cats: Sequence[str] = (),
) -> list[Job]:
    """混合召回:硬过滤 → dense + sparse(在 allowed 内)→ RRF → 软降权 → 返回 Job 列表。

    query_text 空时退化为"硬过滤集合按新鲜度"(稀疏/稠密都需 query)。

    target_sub_cats:
        非空时对结果做软降权 —— sub_category 非空且不在 target_sub_cats 的 Job
        移到列表队尾(sub_category 为 NULL/''/在 target 内的保持原相对顺序在前)。
        不删除任何候选,仅重排,供下游分层展示。
        target_sub_cats=() → 不降权,顺序不变。
    """
    allowed = hard_filter_ids(
        db, freshness_days=freshness_days, preferred_locations=preferred_locations
    )
    if not allowed:
        return []
    if not (query_text or "").strip():
        # 无 query:硬过滤集合按新鲜度返回(兜底,等价于"拉全 enriched 帖"的语义)
        rows = db.execute(
            text("SELECT id FROM jobs WHERE id IN :ids ORDER BY scraped_at DESC LIMIT :lim")
            .bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
            {"ids": list(allowed), "lim": k},
        ).fetchall()
        ids = [int(r[0]) for r in rows]
        jobs = _fetch_jobs_in_order(db, ids)
        return _soft_demote(jobs, target_sub_cats)

    dense = dense_index.dense_search(db, query_text, embed_fn=embed_fn, allowed_ids=allowed, k=k * 2)
    sparse = sparse_index.sparse_search(db, query_text, allowed_ids=allowed, k=k * 2)
    fused = rrf_fuse([dense, sparse], weights=[dense_weight, sparse_weight])
    ids = [jid for jid, _ in fused[:k]]
    # RRF 可能漏掉两路都没召到但在 allowed 里的岗 —— 不补,语义不相关本就该靠后
    jobs = _fetch_jobs_in_order(db, ids)
    return _soft_demote(jobs, target_sub_cats)


def _soft_demote(jobs: list[Job], target_sub_cats: Sequence[str]) -> list[Job]:
    """把 sub_category 非空且不在 target_sub_cats 里的 Job 稳定移到队尾。

    - sub_category 为 None/'' 的:保持在前(未 enrich 的语义命中岗不降)。
    - sub_category 在 target_sub_cats 里的:保持在前。
    - 其余(sub_category 有值但不在 target 里):移到队尾。
    - target_sub_cats 为空 → 直接返回原列表(不降权)。
    """
    if not target_sub_cats:
        return jobs
    target_set = set(target_sub_cats)
    keep: list[Job] = []
    demote: list[Job] = []
    for job in jobs:
        sc = job.sub_category or ""
        if not sc or sc in target_set:
            keep.append(job)
        else:
            demote.append(job)
    return keep + demote


def _fetch_jobs_in_order(db: Session, ids: list[int]) -> list[Job]:
    if not ids:
        return []
    jobs = db.query(Job).filter(Job.id.in_(ids)).all()
    by_id = {j.id: j for j in jobs}
    return [by_id[i] for i in ids if i in by_id]
