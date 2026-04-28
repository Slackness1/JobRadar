import json
from unittest.mock import MagicMock, patch
from app.services.resume_copilot.agent.core import ReActAgent
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.tools import ToolResult
from app.schemas_resume_copilot import (
    ResumeProfilePayload, ResumePreferencePayload, ResumeRecommendationItem,
)


def _make_candidate(job_id: str, score: int = 50) -> ResumeRecommendationItem:
    return ResumeRecommendationItem(
        job_id=job_id, company='公司', job_title='岗位', location='上海',
        objective_score=10, preference_score=5, base_job_score=20,
        company_priority_score=15, base_match_score=score,
        enhanced_score=score, final_score=score,
    )


def _llm_finalize_response(candidates):
    return json.dumps({
        'thought': 'ready to finalize',
        'action': 'finalize',
        'args': {
            'recommendations': [
                {
                    'job_id': c.job_id,
                    'final_score': c.final_score,
                    'why_recommended': ['匹配'],
                    'strengths': ['背景相关'],
                    'risks': [],
                }
                for c in candidates[:3]
            ]
        },
        'reasoning_display': '分析完成，为你整理了 3 个推荐岗位',
    })


def _llm_tool_then_finalize(tool_response, candidates):
    """Returns a side_effect list: first call returns tool_response, second returns finalize."""
    return [tool_response, _llm_finalize_response(candidates)]


def test_agent_finalizes_on_first_call():
    candidates = [_make_candidate('J1', 80), _make_candidate('J2', 60)]
    tools = {'search_candidates': MagicMock(return_value=ToolResult('called', []))}
    budget = AgentBudget()

    with patch('app.services.resume_copilot.agent.core._call_llm') as mock_llm:
        mock_llm.return_value = _llm_finalize_response(candidates)
        agent = ReActAgent(tools=tools, budget=budget)
        results = agent.run(ResumeProfilePayload(), None, candidates)

    assert len(results) >= 1
    assert results[0].job_id in ('J1', 'J2')


def test_agent_calls_tool_then_finalizes():
    candidates = [_make_candidate('J1', 80), _make_candidate('J2', 60)]
    search_result = ToolResult('召回 2 个匹配岗位', [{'job_id': 'J1'}])
    mock_search = MagicMock(return_value=search_result)
    tools = {'search_candidates': mock_search}
    budget = AgentBudget()

    tool_call_response = json.dumps({
        'thought': 'searching first',
        'action': 'search_candidates',
        'args': {'query': '数据分析'},
        'reasoning_display': '你有数据背景，先搜数据岗',
    })

    with patch('app.services.resume_copilot.agent.core._call_llm') as mock_llm:
        mock_llm.side_effect = _llm_tool_then_finalize(tool_call_response, candidates)
        agent = ReActAgent(tools=tools, budget=budget)
        results = agent.run(ResumeProfilePayload(), None, candidates)

    mock_search.assert_called_once_with(query='数据分析')
    assert len(results) >= 1


def test_agent_fallback_on_malformed_json():
    candidates = [_make_candidate('J1', 80)]
    tools = {}
    budget = AgentBudget()

    with patch('app.services.resume_copilot.agent.core._call_llm') as mock_llm:
        mock_llm.return_value = 'NOT JSON AT ALL'
        agent = ReActAgent(tools=tools, budget=budget)
        results = agent.run(ResumeProfilePayload(), None, candidates)

    # Should fallback to top-10 candidates
    assert len(results) >= 1
    assert results[0].job_id == 'J1'


def test_agent_respects_tool_budget():
    candidates = [_make_candidate('J1')]
    # Budget has search_candidates=0 to immediately block it
    budget = AgentBudget(per_tool_limits={
        'search_candidates': 0,
        'inspect_jobs': 0,
        'get_company_intel': 0,
        'search_web': 0,
        'finalize': 1,
    })
    tools = {'search_candidates': MagicMock()}

    with patch('app.services.resume_copilot.agent.core._call_llm') as mock_llm:
        mock_llm.return_value = _llm_finalize_response(candidates)
        agent = ReActAgent(tools=tools, budget=budget)
        results = agent.run(ResumeProfilePayload(), None, candidates)

    assert len(results) >= 1


def test_trace_recorder_called_per_step():
    candidates = [_make_candidate('J1', 80)]
    tools = {}
    budget = AgentBudget()
    trace_calls = []

    def recorder(**kwargs):
        trace_calls.append(kwargs)

    with patch('app.services.resume_copilot.agent.core._call_llm') as mock_llm:
        mock_llm.return_value = _llm_finalize_response(candidates)
        agent = ReActAgent(tools=tools, budget=budget)
        agent.run(ResumeProfilePayload(), None, candidates, trace_recorder=recorder)

    assert len(trace_calls) >= 1
    assert any(c.get('tool') == 'finalize' for c in trace_calls)
