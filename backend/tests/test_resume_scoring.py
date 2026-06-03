"""B1 简历打分 — 单元测试 (provider 注入,不联网)。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.schemas_resume_copilot import (
    DimensionScore,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ScoreReportOut,
    SectionGap,
)
from app.services.resume_copilot.scoring import (
    OpenAICompatibleResumeScorer,
    ScoreReport,
    derive_target_track,
    score_resume,
)
from app.services.resume_copilot.scoring_rubric import DIMENSIONS, build_rubric_prompt_block


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- Task 1: schemas ----

def test_score_report_out_shape():
    report = ScoreReportOut(
        session_id=7,
        target_track='量化',
        overall_current=72,
        overall_potential_low=80,
        overall_potential_high=85,
        dimensions=[
            DimensionScore(key='star', name='STAR 应用', score=60, ceiling=85, reason='缺 Result'),
        ],
        section_gaps=[
            SectionGap(section='internships.0', label='九坤投资', gaps=['STAR 缺 Result', '成果无量化锚点']),
        ],
        used_ai=True,
    )
    assert report.overall_current == 72
    assert report.dimensions[0].ceiling == 85
    assert report.section_gaps[0].gaps[1] == '成果无量化锚点'


# ---- Task 2: rubric content ----

def test_dimensions_are_8_with_keys():
    keys = [d['key'] for d in DIMENSIONS]
    assert keys == [
        'logic', 'star', 'readability', 'completeness',
        'expression', 'quantification', 'track_fit', 'defensibility',
    ]
    for d in DIMENSIONS:
        assert d['name'] and d['high_signal'] and d['low_signal']


def test_rubric_prompt_block_contains_dims_and_track_calibration(db_session):
    block = build_rubric_prompt_block('量化', db_session)
    for d in DIMENSIONS:
        assert d['name'] in block
    assert '因子' in block or 'IC' in block or 'Sharpe' in block


# ---- Task 3: target track derivation ----

def test_derive_prefers_explicit_pref():
    profile = ResumeProfilePayload(inferred_tracks=['公募'])
    prefs = ResumePreferencePayload(preferred_tracks=['量化'])
    assert derive_target_track(profile, prefs) == '量化'


def test_derive_falls_back_to_inferred_when_pref_skipped():
    profile = ResumeProfilePayload(inferred_tracks=['量化'])
    prefs = ResumePreferencePayload(preferred_tracks=['量化'], all_skipped=True)
    assert derive_target_track(profile, prefs) == '量化'


def test_derive_empty_when_nothing():
    assert derive_target_track(ResumeProfilePayload(), None) == ''


# ---- Task 4: score_resume core ----

class _FakeScorer:
    def score(self, messages_payload):
        return {
            'dimensions': [
                {'key': 'logic', 'score': 80, 'ceiling': 85, 'reason': ''},
                {'key': 'star', 'score': 60, 'ceiling': 88, 'reason': '缺 Result'},
                {'key': 'readability', 'score': 75, 'ceiling': 80, 'reason': ''},
                {'key': 'completeness', 'score': 70, 'ceiling': 80, 'reason': ''},
                {'key': 'expression', 'score': 65, 'ceiling': 85, 'reason': ''},
                {'key': 'quantification', 'score': 50, 'ceiling': 80, 'reason': '无量化'},
                {'key': 'track_fit', 'score': 78, 'ceiling': 85, 'reason': ''},
                {'key': 'defensibility', 'score': 60, 'ceiling': 78, 'reason': ''},
            ],
            'section_gaps': [
                {'section': 'internships.0', 'label': '九坤投资',
                 'gaps': ['STAR 缺 Result', '成果无量化锚点']},
            ],
        }


def test_score_resume_computes_overall_and_potential(db_session):
    profile = ResumeProfilePayload(
        internships=[{'company': '九坤投资', 'role': '量化实习',
                      'bullets': ['参与中频 alpha 因子开发']}],
        inferred_tracks=['量化'],
    )
    report = score_resume(
        db_session, profile, target_track='量化', preferences=None, provider=_FakeScorer(),
    )
    assert isinstance(report, ScoreReport)
    assert report.target_track == '量化'
    # mean(scores)= (80+60+75+70+65+50+78+60)/8 = 67.25 -> 67
    assert report.overall_current == 67
    # mean(ceilings)= (85+88+80+80+85+80+85+78)/8 = 82.625 -> 83
    # low=max(67,81)=81 ; high=min(95,86)=86
    assert report.overall_potential_low == 81
    assert report.overall_potential_high == 86
    assert len(report.dimensions) == 8
    assert report.section_gaps[0].gaps == ['STAR 缺 Result', '成果无量化锚点']
    assert report.used_ai is True


# ---- Task 5: honest-score contract ----

class _CheatingScorer:
    """偷塞 overall + rewritten,并给 ceiling<score 的脏数据。"""
    def score(self, messages_payload):
        return {
            'overall': 99,
            'rewritten_resume': '一段改写',
            'dimensions': [
                {'key': k, 'score': 50, 'ceiling': 40, 'reason': ''}
                for k in ['logic', 'star', 'readability', 'completeness',
                          'expression', 'quantification', 'track_fit', 'defensibility']
            ],
            'section_gaps': [],
        }


def test_backend_ignores_llm_overall_and_fixes_ceiling(db_session):
    report = score_resume(
        db_session, ResumeProfilePayload(inferred_tracks=['量化']),
        target_track='量化', preferences=None, provider=_CheatingScorer(),
    )
    assert report.overall_current == 50              # 用确定性算法,不理 LLM 的 99
    assert all(d.ceiling >= d.score for d in report.dimensions)
    assert report.overall_potential_low == 50
    assert report.overall_potential_high == 53
    assert not hasattr(report, 'rewritten_resume')
