from unittest.mock import MagicMock, patch
from app.services.resume_copilot.agent.tools import build_tools, ToolResult
from app.schemas_resume_copilot import (
    ResumeProfilePayload, ResumePreferencePayload, ResumeRecommendationItem,
)


def _make_candidate(job_id='J1', company='测试公司', job_title='数据分析岗',
                    location='上海', base_match_score=50,
                    company_priority_label='', company_priority_tier='',
                    matched_track_key='', matched_track_label='',
                    matched_role_family='', need_enrichment=False) -> ResumeRecommendationItem:
    return ResumeRecommendationItem(
        job_id=job_id, company=company, job_title=job_title, location=location,
        objective_score=10, preference_score=5, base_job_score=20,
        company_priority_score=15, base_match_score=base_match_score,
        enhanced_score=base_match_score,
        final_score=base_match_score,
        company_priority_label=company_priority_label,
        company_priority_tier=company_priority_tier,
        matched_track_key=matched_track_key,
        matched_track_label=matched_track_label,
        matched_role_family=matched_role_family,
        need_enrichment=need_enrichment,
    )


def test_search_candidates_returns_matching_results():
    db = MagicMock()
    candidates = [
        _make_candidate('J1', '中信证券', '研究员', '上海', 80),
        _make_candidate('J2', '字节跳动', '产品经理', '北京', 60),
    ]
    tools = build_tools(db, ResumeProfilePayload(), None, candidates)
    result = tools['search_candidates'](query='证券 研究')
    assert isinstance(result, ToolResult)
    assert len(result.data) == 1
    assert result.data[0]['job_id'] == 'J1'


def test_search_candidates_empty_query_returns_all():
    db = MagicMock()
    candidates = [_make_candidate('J1'), _make_candidate('J2')]
    tools = build_tools(db, ResumeProfilePayload(), None, candidates)
    result = tools['search_candidates'](query='')
    assert len(result.data) == 2


def test_inspect_jobs_returns_jd_details():
    mock_job = MagicMock()
    mock_job.job_id = 'J1'
    mock_job.company = '测试公司'
    mock_job.job_title = '数据岗'
    mock_job.department = '数据部门'
    mock_job.job_req = '要求Python'
    mock_job.job_duty = '负责数据分析'
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [mock_job]
    tools = build_tools(db, ResumeProfilePayload(), None, [])
    result = tools['inspect_jobs'](job_ids=['J1'])
    assert result.data[0]['job_req'] == '要求Python'


def test_get_company_intel_unknown_company():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    tools = build_tools(db, ResumeProfilePayload(), None, [])
    result = tools['get_company_intel'](company_name='不存在的公司')
    assert '未找到' in result.summary


def test_search_web_returns_tool_result():
    db = MagicMock()
    with patch('app.services.resume_copilot.agent.tools._search_web') as mock_search:
        from app.services.resume_copilot.quick_enrichment import SearchResult
        mock_search.return_value = [SearchResult(title='面经', url='http://x.com', snippet='挺好的')]
        tools = build_tools(db, ResumeProfilePayload(), None, [])
        result = tools['search_web'](query='中信证券面经')
    assert len(result.data) == 1
    assert result.data[0]['title'] == '面经'
