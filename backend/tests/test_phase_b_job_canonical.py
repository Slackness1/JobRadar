"""Phase B (2026-05-16): 钉死 Job.canonical_track 自动派生契约。

1) `SOURCE_TO_CANONICAL` 必须含 coverage_truth.yaml 1:1 source 映射。
2) `canonicalize_job(source, title)` 优先 title alias,fallback source,
   两边都没就 None。
3) Job 模型有 canonical_track 列(by name+nullable+index)。
4) `before_insert` event listener 自动派生:用 in-memory SQLite 建表插 Job,
   assert canonical_track 被自动填(无须 caller 显式赋值)。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.services.taxonomy import (
    SOURCE_TO_CANONICAL,
    canonicalize_job,
)


# ── source map ──────────────────────────────────────────────────────────


def test_source_map_expected_entries() -> None:
    """coverage_truth.yaml 改了又忘对齐 source_match,这里钉死核心几个。"""
    expected = {
        'internet_official': '金融科技',
        'bank_official': '银行·总行核心',
        'bank-legacy-csv': '银行·总行核心',
        'insurance_official': '公募/资管·投研',
        'pe_vc_official': '一级股权·PE/VC',
        'state_owned_official': '监管·体制内',
    }
    for src, canon in expected.items():
        assert SOURCE_TO_CANONICAL.get(src) == canon, \
            f'source={src!r} 应映 {canon!r},实际 {SOURCE_TO_CANONICAL.get(src)!r}'


def test_source_map_skips_ambiguous() -> None:
    """1:N source(securities/hedge_funds/foreign_ibs)不进 SOURCE_TO_CANONICAL。

    歧义来源不能假设 single canonical,让 job_title 或下游 LLM 决定。
    """
    for ambiguous in [
        'securities_zhiye',
        'hedge_funds_hotjob',
        'foreign_ibs_official',
    ]:
        assert ambiguous not in SOURCE_TO_CANONICAL, \
            f'{ambiguous!r} 是 1:N 不应进 1:1 source map'


# ── canonicalize_job ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "source,title,expected",
    [
        # title 主导(歧义 source 也能命中)
        ('hedge_funds_hotjob', '幻方量化 量化研究员', '量化'),
        ('foreign_ibs_official', 'IBD Analyst · 中金', '投行·并购·资本市场'),
        ('securities_zhiye', '券商研究所 · 食品饮料 卖方研究', '卖方研究'),
        # 1:1 source 命中(title 无信号)
        ('bank_official', '总行管培生', '银行·总行核心'),
        ('internet_official', '蚂蚁集团 数据分析师', '金融科技'),
        # 2026-05-22: 2026-05-21 加 '中石油' → '大宗·能源' alias 后, title 主导优先于
        # source 兜底. 业务上 "中石油综合岗" 走能源 placement 比体制内更精准 (SAIF MF
        # 学生眼里 中石油国际是 trading desk, 不是政府岗位).
        ('state_owned_official', '中石油 综合岗', '大宗·能源'),
        # legacy CSV
        ('bank-legacy-csv', '招商银行 网点客户经理', '银行·总行核心'),
        # 无信号
        ('tatawangshen', '电网 综合岗', None),
        ('legacy-jobcrawler-restore', '', None),
        ('', '', None),
    ],
    ids=lambda v: str(v)[:35],
)
def test_canonicalize_job(source: str, title: str, expected: str | None) -> None:
    assert canonicalize_job(source, title) == expected


# ── model column + listener wiring ──────────────────────────────────────


def test_job_model_has_canonical_track_column() -> None:
    from app.models import Job
    assert hasattr(Job, 'canonical_track'), 'Job 缺 canonical_track 列'
    col = Job.__table__.columns['canonical_track']
    assert col.nullable is True, 'canonical_track 应 nullable(1:N 歧义留空)'
    assert col.index is True, 'canonical_track 应有 index(downstream filter 用)'


def test_before_insert_listener_populates_canonical_track() -> None:
    """事件 listener 必须自动填字段,无论 caller 是否显式赋值。

    这个 test 用 in-memory SQLite,跟项目 DB 隔离。Base.metadata.create_all
    会建所有 model 的表(用 in-mem 的 engine), so safe.
    """
    from app.database import Base
    from app.models import Job

    test_engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()

    # case 1: 1:1 source -> 自动填
    j1 = Job(job_id='test-1', source='bank_official', job_title='总行管培生')
    db.add(j1)
    db.flush()
    assert j1.canonical_track == '银行·总行核心'

    # case 2: title 信号比 source 强
    j2 = Job(job_id='test-2', source='hedge_funds_hotjob', job_title='幻方 量化研究员')
    db.add(j2)
    db.flush()
    assert j2.canonical_track == '量化'

    # case 3: 显式赋值不被覆盖
    j3 = Job(job_id='test-3', source='bank_official', job_title='总行', canonical_track='金融咨询')
    db.add(j3)
    db.flush()
    assert j3.canonical_track == '金融咨询', '显式赋值应被尊重,listener 不应覆盖'

    # case 4: 无信号 -> None
    j4 = Job(job_id='test-4', source='tatawangshen', job_title='电网综合岗')
    db.add(j4)
    db.flush()
    assert j4.canonical_track is None

    db.commit()
    db.close()


def test_before_update_listener_fills_when_null() -> None:
    """update 时 canonical_track 若仍为 None 也要重新尝试派生。"""
    from app.database import Base
    from app.models import Job

    test_engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()

    # 插入时 source 无 1:1 + title 无 alias → canonical_track 留 NULL
    j = Job(job_id='test-update', source='tatawangshen', job_title='待定')
    db.add(j)
    db.flush()
    assert j.canonical_track is None

    # 后续 update title 含 alias → listener 应自动填
    j.job_title = '幻方 量化研究员'
    db.flush()
    assert j.canonical_track == '量化'

    db.close()
