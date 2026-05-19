import pytest
from app.services.resume_copilot.agent.budget import AgentBudget


def test_check_allows_fresh_budget():
    budget = AgentBudget()
    allowed, reason = budget.check('search_candidates')
    assert allowed is True
    assert reason == ''


def test_check_blocks_per_tool_limit():
    budget = AgentBudget()
    budget._call_counts['search_candidates'] = 4
    allowed, reason = budget.check('search_candidates')
    assert allowed is False
    assert reason == 'TOOL_LIMIT_REACHED'


def test_check_blocks_total_budget():
    budget = AgentBudget()
    # 4+3+5 = 12, exactly at max_total_calls (Phase 0: search_web removed,
    # but total still 12 since the previous budget was over-allocated)
    budget._call_counts = {'search_candidates': 4, 'inspect_jobs': 3, 'get_company_intel': 5}
    allowed, reason = budget.check('inspect_jobs')
    assert allowed is False
    assert reason == 'TOTAL_BUDGET_EXHAUSTED'


def test_finalize_not_subject_to_total_budget():
    budget = AgentBudget()
    budget._call_counts = {'search_candidates': 4, 'inspect_jobs': 3, 'get_company_intel': 5}
    allowed, reason = budget.check('finalize')
    assert allowed is True


def test_record_increments_count():
    budget = AgentBudget()
    budget.record('search_candidates')
    budget.record('search_candidates')
    assert budget._call_counts['search_candidates'] == 2


def test_remaining_decrements_after_record():
    budget = AgentBudget()
    budget.record('get_company_intel')
    assert budget.remaining()['get_company_intel'] == 4  # limit 5, used 1


def test_time_exhausted_blocks_all_tools():
    budget = AgentBudget(max_seconds=0)
    # max_seconds=0 means immediately expired
    import time; time.sleep(0.01)
    allowed, reason = budget.check('search_candidates')
    assert allowed is False
    assert reason == 'TIME_BUDGET_EXHAUSTED'
