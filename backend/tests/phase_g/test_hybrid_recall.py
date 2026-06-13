"""S1 hybrid_recall 单测:硬过滤丢 sub_cat 闸 / FTS5 BM25 / RRF 融合。fake embedder 不走网络。"""
from datetime import datetime

import numpy as np
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job
from app.services.phase_g.recommendation_v2 import dense_index as di
from app.services.phase_g.recommendation_v2 import sparse_index as si
from app.services.phase_g.recommendation_v2 import hybrid_recall as hr


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()
    di._CACHE = None


_VOCAB = ["量化", "研究", "销售", "产品", "AI", "固收", "投行", "因子"]
def _fake_embed(texts):
    out = []
    for t in texts:
        v = np.zeros(di.DIMENSION, dtype=np.float32)
        for i, w in enumerate(_VOCAB):
            if w in t:
                v[i] = 1.0
        if np.linalg.norm(v) == 0:
            v[200] = 1.0
        out.append(v)
    return out


def _job(jid, company, title, duty, ql="good", sub=None, loc="上海", link=None):
    return Job(id=jid, job_id=f"J{jid}", company=company, job_title=title, job_duty=duty,
               job_req="", quality_label=ql, sub_category=sub, location=loc,
               link_status=link, scraped_at=datetime.utcnow())


def test_rrf_fuse_basic():
    dense = [(1, 0.9), (2, 0.8), (3, 0.1)]
    sparse = [(2, 5.0), (1, 4.0), (4, 1.0)]
    fused = hr.rrf_fuse([dense, sparse])
    ids = [j for j, _ in fused]
    # 1 和 2 两路都高 → 排前;4 只一路、3 只一路 → 靠后
    assert set(ids[:2]) == {1, 2}


def test_hard_filter_drops_subcat_gate(db):
    # job1 sub_category=NULL(没 enrich)—— 旧召回会被 sub_cat 闸挡掉,新硬过滤不挡
    db.add_all([
        _job(1, "九坤", "量化研究员", "量化 研究 因子", sub=None),       # 无 sub_cat
        _job(2, "幻方", "量化策略", "量化 研究", sub="量化研究员·中频"),  # 有 sub_cat
        _job(3, "某公司", "运维", "网络运维", ql="low_signal"),          # 非 good,该挡
    ])
    db.commit()
    allowed = hr.hard_filter_ids(db)
    assert 1 in allowed and 2 in allowed   # 两个 good 的都进(含 sub_cat=NULL 的)
    assert 3 not in allowed                # 非 good 被质量闸挡


def test_hybrid_recall_surfaces_unenriched_relevant(db):
    if not si.fts5_available(db):
        pytest.skip("SQLite 无 FTS5")
    db.add_all([
        _job(1, "九坤", "量化研究员", "量化 研究 因子", sub=None),   # 无 sub_cat 但语义相关
        _job(2, "中金", "投行分析师", "投行 IPO", sub="投行 IBD"),
        _job(3, "某券商", "机构销售", "销售 路演", sub="机构销售·销售支持"),
    ])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    si.rebuild_index(db)
    jobs = hr.hybrid_recall(db, "量化 研究 因子", embed_fn=_fake_embed, k=5)
    # 关键:job1(sub_cat=NULL)被语义召回排第一 —— 解绑标签生效
    assert jobs and jobs[0].id == 1


def test_hybrid_recall_empty_query_falls_back(db):
    db.add_all([_job(1, "九坤", "量化研究员", "量化 研究")])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    jobs = hr.hybrid_recall(db, "", embed_fn=_fake_embed, k=5)
    assert [j.id for j in jobs] == [1]  # 空 query 走硬过滤兜底
