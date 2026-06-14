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


def test_hybrid_recall_pure_dense_default_no_sparse(db):
    """默认 use_sparse=False → 纯 dense:不依赖 FTS5、不调 sparse_search 也能召回排序。
    用 monkeypatch 让 sparse_search 一旦被调用就炸,证明默认路径根本不碰它。"""
    db.add_all([
        _job(1, "九坤", "量化研究员", "量化 研究 因子", sub=None),
        _job(2, "中金", "投行分析师", "投行 IPO", sub="投行 IBD"),
    ])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)

    import pytest as _pt
    orig = si.sparse_search
    si.sparse_search = lambda *a, **k: (_ for _ in ()).throw(AssertionError("纯 dense 不应调 sparse"))
    try:
        jobs = hr.hybrid_recall(db, "量化 研究 因子", embed_fn=_fake_embed, k=5)
    finally:
        si.sparse_search = orig
    # dense 命中:job1(量化研究因子全中)排在 job2(投行,几乎不命中)之前
    assert jobs and jobs[0].id == 1


def test_hybrid_recall_use_sparse_opt_in_still_works(db):
    """use_sparse=True → 回到 dense+sparse RRF 融合路径(留作 tie-breaker 的回退口)。"""
    if not si.fts5_available(db):
        pytest.skip("SQLite 无 FTS5")
    db.add_all([
        _job(1, "九坤", "量化研究员", "量化 研究 因子", sub=None),
        _job(2, "中金", "投行分析师", "投行 IPO", sub="投行 IBD"),
    ])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    si.rebuild_index(db)
    jobs = hr.hybrid_recall(db, "量化 研究 因子", embed_fn=_fake_embed, k=5, use_sparse=True)
    assert jobs and jobs[0].id == 1  # 两路都指向 job1


def test_hybrid_recall_empty_query_falls_back(db):
    db.add_all([_job(1, "九坤", "量化研究员", "量化 研究")])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    jobs = hr.hybrid_recall(db, "", embed_fn=_fake_embed, k=5)
    assert [j.id for j in jobs] == [1]  # 空 query 走硬过滤兜底


def test_hybrid_recall_subcat_soft_demote(db):
    """target_sub_cats 软降权:不在 target 的非空 sub_cat 岗排队尾;NULL sub_cat 保持在前。
    并验证 target_sub_cats=() 时顺序不变。"""
    if not si.fts5_available(db):
        pytest.skip("SQLite 无 FTS5")

    db.add_all([
        _job(1, "九坤", "量化研究员", "量化 研究 因子", sub="量化研究员·中频"),   # in target
        _job(2, "幻方", "量化策略", "量化 研究 因子", sub=None),                  # NULL → keep
        _job(3, "中金", "投行分析师", "量化 研究 因子", sub="投行 IBD"),           # NOT in target → demote
        _job(4, "九坤", "另类数据", "量化 研究", sub="量化研究员·高频"),           # in target
    ])
    db.commit()
    di.backfill_embeddings(db, embed_fn=_fake_embed)
    di.reload_cache(db)
    si.rebuild_index(db)

    target = ["量化研究员·中频", "量化研究员·高频"]
    jobs = hr.hybrid_recall(db, "量化 研究 因子", embed_fn=_fake_embed, k=10,
                            target_sub_cats=target)

    # 所有候选都在结果里(不删任何人)
    assert len(jobs) == 4

    job_ids = [j.id for j in jobs]
    # job3(sub=投行 IBD, NOT in target) 必须在 job1/job2/job4 之后
    pos = {j.id: i for i, j in enumerate(jobs)}
    assert pos[3] > pos[1], "投行 IBD 岗应在目标 sub_cat 岗之后"
    assert pos[3] > pos[2], "投行 IBD 岗应在 NULL sub_cat 岗之后"
    assert pos[3] > pos[4], "投行 IBD 岗应在另一目标 sub_cat 岗之后"

    # 验证 target_sub_cats=() 时不改变顺序(与不传参结果一致)
    jobs_no_target = hr.hybrid_recall(db, "量化 研究 因子", embed_fn=_fake_embed, k=10,
                                      target_sub_cats=())
    jobs_default   = hr.hybrid_recall(db, "量化 研究 因子", embed_fn=_fake_embed, k=10)
    assert [j.id for j in jobs_no_target] == [j.id for j in jobs_default], \
        "target_sub_cats=() 时顺序必须与不传 target_sub_cats 一致"


def test_dispatcher_flag_routing(monkeypatch):
    """flag 路由单测:HYBRID_RECALL_ENABLED=True 时走 hybrid_recall,False 时走 recall_candidates。
    用 monkeypatch 替换两个召回函数并构造最小 profile 调 _recommend_v2_dispatcher。"""
    import app.config as cfg
    from app.services.resume_copilot import recommendation as rec_mod
    from app.schemas_resume_copilot import ResumeProfilePayload, ResumePreferencePayload

    calls: dict[str, int] = {"hybrid": 0, "sql": 0}

    # 最小 Profile — 填能让 dispatcher 跑到召回步骤即可
    profile = ResumeProfilePayload.model_validate({
        "basic_info": {"name": "测试生"},
        "education": [], "internships": [], "projects": [],
        "skills": {"technical": [], "tools": [], "languages": []},
        "languages": [], "awards": [], "candidate_summary": "",
        "inferred_roles": [], "inferred_tracks": ["量化"],
    })
    preferences = None

    # stub hybrid_recall — 直接返回空列表(让 dispatcher 走到 no_candidates 分支)
    def _stub_hybrid(*args, **kwargs):
        calls["hybrid"] += 1
        return []

    def _stub_sql(*args, **kwargs):
        calls["sql"] += 1
        return []

    # monkeypatch 两个召回函数在 dispatcher 实际 import 的命名空间
    monkeypatch.setattr(
        "app.services.phase_g.recommendation_v2.hybrid_recall.hybrid_recall",
        _stub_hybrid,
    )
    monkeypatch.setattr(
        "app.services.phase_g.recommendation_v2.recall.recall_candidates",
        _stub_sql,
    )

    # 构造最小 db stub (只需不报错;两个召回 stub 都不用 db)
    class _FakeDb:
        pass

    db = _FakeDb()

    # --- flag OFF (默认) → 走 recall_candidates ---
    monkeypatch.setattr(cfg, "HYBRID_RECALL_ENABLED", False)
    # 重新导入 HYBRID_RECALL_ENABLED 到 rec_mod 里(dispatcher 在函数体内 import,无需 reload)
    rec_mod._recommend_v2_dispatcher(
        db,  # type: ignore[arg-type]
        profile=profile,
        preferences=preferences,
        rejected_job_ids=[],
        limit=None, min_score=0, top_n=10,
    )
    assert calls["sql"] == 1, "flag OFF 时应调用 recall_candidates"
    assert calls["hybrid"] == 0, "flag OFF 时不应调用 hybrid_recall"

    calls["hybrid"] = 0
    calls["sql"] = 0

    # --- flag ON → 走 hybrid_recall ---
    monkeypatch.setattr(cfg, "HYBRID_RECALL_ENABLED", True)
    rec_mod._recommend_v2_dispatcher(
        db,  # type: ignore[arg-type]
        profile=profile,
        preferences=preferences,
        rejected_job_ids=[],
        limit=None, min_score=0, top_n=10,
    )
    assert calls["hybrid"] == 1, "flag ON 时应调用 hybrid_recall"
    assert calls["sql"] == 0, "flag ON 时不应调用 recall_candidates"


def test_sparse_chinese_segmentation(db):
    """真实无空格中文 JD:jieba 分词后 FTS5 BM25 能召回(证明 unicode61 整段问题已解)。"""
    if not si.fts5_available(db):
        pytest.skip("SQLite 无 FTS5")
    db.add_all([
        _job(1, "九坤投资", "量化研究员", "负责中频量化策略研究与因子挖掘"),  # 无空格
        _job(2, "中金公司", "投行业务部", "负责IPO项目承做与材料制作"),
    ])
    db.commit()
    si.rebuild_index(db)
    # 查"量化策略"(无空格)应召回 job1,不召回 job2
    res = si.sparse_search(db, "量化策略研究", k=5)
    ids = [r[0] for r in res]
    assert 1 in ids and 2 not in ids
    # 英文技术词保留:查"IPO"召回 job2
    res2 = si.sparse_search(db, "IPO承做", k=5)
    assert 2 in [r[0] for r in res2]
