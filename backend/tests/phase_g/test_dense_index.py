"""S1 dense_index 单测:文档构造 / 幂等回填 / cosine 召回。embedder 注入 fake,不走网络。"""
import numpy as np
import pytest

from app.database import Base
from app.models import Job
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.phase_g.recommendation_v2 import dense_index as di


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()
    di.reload_cache(s) if False else None  # noqa
    di._CACHE = None  # 清缓存防跨测污染


def _job(jid, company, title, duty, ql="good", link=None):
    return Job(id=jid, job_id=f"J{jid}", company=company, job_title=title,
               job_duty=duty, job_req="", quality_label=ql, link_status=link)


# 确定性 fake embedder:按关键词造稀疏向量,语义近的向量近。
_VOCAB = ["量化", "研究", "销售", "产品", "AI", "固收", "投行"]
def _fake_embed(texts):
    out = []
    for t in texts:
        v = np.zeros(di.DIMENSION, dtype=np.float32)
        for i, w in enumerate(_VOCAB):
            if w in t:
                v[i] = 1.0
        if np.linalg.norm(v) == 0:
            v[100] = 1.0  # 无命中给个固定向量
        out.append(v)
    return out


def test_job_document_excludes_subcat():
    doc = di.job_document("九坤投资", "量化研究员", "搭建因子回测", "Python")
    assert "九坤投资" in doc and "量化研究员" in doc and "搭建因子回测" in doc
    # 文档里不该有 sub_category 概念(它不是入参)
    assert len(doc) <= di._DOC_MAXLEN


def test_backfill_idempotent(db):
    db.add_all([
        _job(1, "九坤投资", "量化研究员", "量化 研究 因子"),
        _job(2, "中金", "投行分析师", "投行 IPO"),
        _job(3, "某公司", "运维", "网络运维", ql="low_signal"),  # 非 good,不该 embed
    ])
    db.commit()
    r1 = di.backfill_embeddings(db, embed_fn=_fake_embed)
    assert r1["embedded"] == 2  # 只 embed good 的两条
    n = db.execute(__import__("sqlalchemy").text("SELECT COUNT(*) FROM job_embeddings")).scalar()
    assert n == 2
    # 再跑一次:content_hash 没变,全 skip
    r2 = di.backfill_embeddings(db, embed_fn=_fake_embed)
    assert r2["embedded"] == 0 and r2["skipped"] == 2


def test_dense_search_semantic_order(db):
    db.add_all([
        _job(1, "九坤投资", "量化研究员", "量化 研究 因子"),
        _job(2, "中金", "投行分析师", "投行 IPO 承做"),
        _job(3, "某券商", "机构销售", "销售 路演 客户"),
    ])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    # query "量化 研究" 应把 job1 排第一
    res = di.dense_search(db, "量化 研究", embed_fn=_fake_embed, k=3)
    assert res[0][0] == 1
    assert res[0][1] > res[-1][1]


def test_dense_search_respects_allowed_ids(db):
    db.add_all([
        _job(1, "九坤投资", "量化研究员", "量化 研究"),
        _job(2, "幻方", "量化策略", "量化 研究"),
    ])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    res = di.dense_search(db, "量化 研究", embed_fn=_fake_embed, allowed_ids=[2], k=5)
    assert [r[0] for r in res] == [2]  # 只在 allowed 内召回
