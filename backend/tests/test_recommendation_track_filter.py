"""Track-aware recall + mismatch penalty 单元测试。

覆盖 4 个修改点:
  1. expand_track_to_canonicals (伞展开)
  2. transferable_for (可迁移)
  3. aliases_for_canonical / recall_keywords_for_canonical
  4. _classify_track_match (4 分支)
  5. _build_track_condition (SQL 行为, in-memory fixture)
  6. _filter_candidate_jobs 分级 fallback
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job  # noqa: F401 — 触发 listener 注册
from app.schemas_resume_copilot import ResumePreferencePayload
from app.services.resume_copilot.recommendation import (
    _build_track_condition,
    _classify_track_match,
    _filter_candidate_jobs,
)
from app.services.taxonomy import (
    aliases_for_canonical,
    expand_track_to_canonicals,
    recall_keywords_for_canonical,
    transferable_for,
)


# ---------- taxonomy helper 层 ----------

class TestExpandUmbrella:
    def test_投研_展开为4个(self):
        canons = set(expand_track_to_canonicals('投研'))
        assert canons == {'二级买方·基本面', '卖方研究·S&T', '一级市场', '量化'}

    def test_买方_展开为2个(self):
        canons = set(expand_track_to_canonicals('买方'))
        assert canons == {'二级买方·基本面', '量化'}

    def test_量化是single_canonical(self):
        assert expand_track_to_canonicals('量化') == ['量化']

    def test_alias_映射到canonical(self):
        # "公募" 不是伞,但是 alias → 二级买方·基本面
        assert expand_track_to_canonicals('公募') == ['二级买方·基本面']

    def test_未知值返空(self):
        assert expand_track_to_canonicals('客户经理') == []
        assert expand_track_to_canonicals('') == []


class TestTransferable:
    def test_投研_可迁移_2个(self):
        canons = set(transferable_for('投研'))
        assert canons == {'金融咨询', '银行·总行核心'}

    def test_未知伞返空(self):
        assert transferable_for('客户经理') == []


class TestRecallKeywords:
    def test_二级买方_含研究员_stem(self):
        kws = recall_keywords_for_canonical('二级买方·基本面')
        assert '研究员' in kws
        assert '基金经理' in kws

    def test_filter掉过短keyword(self):
        # PE/VC 是 2 字符,应被过滤掉避 substring 误命中
        kws = recall_keywords_for_canonical('一级市场')
        assert all(len(k) >= 3 for k in kws)


class TestAliasesForCanonical:
    def test_严格alias集合(self):
        aliases = aliases_for_canonical('量化')
        assert '量化研究' in aliases
        assert 'quant' in aliases


# ---------- _classify_track_match 4 分支 ----------

@pytest.fixture
def touyan_prefs():
    return ResumePreferencePayload(
        preferred_locations=['上海'],
        preferred_company_types=['金融机构'],
        preferred_tracks=['投研'],
        preferred_roles=[],
        all_skipped=False,
    )


class TestClassifyTrackMatch:
    def test_hit_伞内canonical(self, touyan_prefs):
        job = Job(job_title='证券投资研究员', canonical_track='二级买方·基本面', source='funds_official')
        assert _classify_track_match(job, touyan_prefs) == ('hit', 0)

    def test_transferable_可迁移canonical(self, touyan_prefs):
        job = Job(job_title='Senior Consultant', canonical_track='金融咨询', source='consulting_official')
        assert _classify_track_match(job, touyan_prefs) == ('transferable', 0)

    def test_ambiguous_1N_source_NULL(self, touyan_prefs):
        job = Job(job_title='Senior Analyst', canonical_track=None, source='hedge_funds_hotjob')
        assert _classify_track_match(job, touyan_prefs) == ('ambiguous', 0)

    def test_null_hit_title含严格alias(self, touyan_prefs):
        job = Job(job_title='量化研究员', canonical_track=None, source='internet_official')
        assert _classify_track_match(job, touyan_prefs) == ('null_hit', 0)

    def test_mismatch_canonical不在伞且非可迁移(self, touyan_prefs):
        job = Job(job_title='AI算法工程师', canonical_track='金融科技', source='internet_official')
        kind, pen = _classify_track_match(job, touyan_prefs)
        assert kind == 'mismatch'
        assert pen == 15

    def test_mismatch_null无alias(self, touyan_prefs):
        job = Job(job_title='图形学研究员', canonical_track=None, source='internet_official')
        kind, pen = _classify_track_match(job, touyan_prefs)
        # '研究员' 不在严格 alias 里 (是 recall hint),所以走 mismatch
        assert kind == 'mismatch'

    def test_无preferred_tracks不分类(self):
        prefs = ResumePreferencePayload(
            preferred_tracks=[], preferred_locations=[], preferred_roles=[],
            preferred_company_types=[], all_skipped=False,
        )
        job = Job(job_title='AI算法工程师', canonical_track='金融科技')
        assert _classify_track_match(job, prefs) == ('no_pref', 0)

    def test_all_skipped不分类(self):
        prefs = ResumePreferencePayload(
            preferred_tracks=['投研'], preferred_locations=['上海'],
            preferred_roles=[], preferred_company_types=[], all_skipped=True,
        )
        job = Job(job_title='AI算法工程师', canonical_track='金融科技')
        assert _classify_track_match(job, prefs) == ('no_pref', 0)


# ---------- _build_track_condition SQL 行为 ----------

@pytest.fixture
def db_session(tmp_path):
    eng = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(eng)
    Sess = sessionmaker(bind=eng)
    return Sess()


def _make_job(**kwargs) -> Job:
    """Helper to bypass before_insert listener (即 canonical_track 透传)。"""
    defaults = {
        'job_id': 'j' + str(hash(str(kwargs)))[:8],
        'company': 'Co',
        'job_title': '',
        'location': '上海',
        'detail_url': 'https://example.com',
        'source': '',
    }
    defaults.update(kwargs)
    return Job(**defaults)


class TestBuildTrackCondition:
    def test_no_tracks_returns_None(self):
        prefs = ResumePreferencePayload(preferred_tracks=[], preferred_locations=[],
                                         preferred_roles=[], preferred_company_types=[],
                                         all_skipped=False)
        assert _build_track_condition(prefs) is None

    def test_unknown_track_returns_None(self):
        prefs = ResumePreferencePayload(preferred_tracks=['客户经理'], preferred_locations=[],
                                         preferred_roles=[], preferred_company_types=[],
                                         all_skipped=False)
        assert _build_track_condition(prefs) is None

    def test_投研_returns_condition(self, touyan_prefs):
        cond = _build_track_condition(touyan_prefs)
        assert cond is not None


class TestFilterCandidateJobs:
    def test_typed_column_hit(self, db_session, touyan_prefs):
        db_session.add_all([
            _make_job(canonical_track='二级买方·基本面', job_title='行业研究员'),
            _make_job(canonical_track='金融科技', job_title='AI 算法工程师'),  # 应被排除
            _make_job(canonical_track='二级买方·基本面', job_title='量化研究员'),
        ])
        db_session.commit()
        rows = _filter_candidate_jobs(db_session, touyan_prefs)
        canons = [r.canonical_track for r in rows]
        assert '二级买方·基本面' in canons
        assert '金融科技' not in canons

    def test_transferable_included(self, db_session, touyan_prefs):
        db_session.add_all([
            _make_job(canonical_track='金融咨询', job_title='MBB Consultant'),
        ])
        db_session.commit()
        rows = _filter_candidate_jobs(db_session, touyan_prefs)
        assert any(r.canonical_track == '金融咨询' for r in rows)

    def test_null_with_alias_title(self, db_session, touyan_prefs):
        # NULL canonical 但 title 含 stem keyword '研究员' → 走 NULL fallback
        # bypass before_insert: 先 add 再手动 set 回 NULL
        j = _make_job(job_title='证券投资研究员')
        db_session.add(j)
        db_session.commit()
        j.canonical_track = None
        db_session.commit()
        # Verify NULL was preserved
        db_session.refresh(j)
        if j.canonical_track is not None:
            pytest.skip(f"before_update listener overrode NULL → {j.canonical_track}")
        rows = _filter_candidate_jobs(db_session, touyan_prefs)
        assert len(rows) >= 1
