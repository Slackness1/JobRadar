# ReAct Agent for Resume-to-Job Matching — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the linear `quick_enrichment` pipeline in the Resume Copilot backend with a ReAct agent loop that dynamically reasons about a candidate's profile, calls tools, and streams its thinking to the frontend as animated step cards.

**Architecture:** The rule engine still runs first to produce top-100 candidates. The new `ReActAgent` receives those candidates and loops: LLM reasons → picks a tool → tool executes → result fed back → repeat (max 12 calls, 90s). Each completed step is written to `agent_trace_json` and rendered by the frontend as a slide-in card with a Claude-spinner between cards.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, urllib (no new deps), Next.js 15, React 19, Tailwind CSS v4.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/app/services/resume_copilot/agent/__init__.py` | Package marker |
| Create | `backend/app/services/resume_copilot/agent/budget.py` | `AgentBudget` — tracks call counts and time |
| Create | `backend/app/services/resume_copilot/agent/prompt.py` | Builds the system prompt for each LLM turn |
| Create | `backend/app/services/resume_copilot/agent/tools.py` | 5 tool functions (reuses Tavily/Jina from `quick_enrichment.py`) |
| Create | `backend/app/services/resume_copilot/agent/core.py` | `ReActAgent` — the main ReAct loop |
| Modify | `backend/app/schemas_resume_copilot.py` | Add optional `tool`, `step_index`, `result_summary` to `ResumeAgentTraceItem` |
| Modify | `backend/app/services/resume_copilot/workflow.py` | Replace `enrich_recommendations_quickly` call with `ReActAgent.run()` |
| Create | `backend/tests/test_agent_budget.py` | Unit tests for `AgentBudget` |
| Create | `backend/tests/test_agent_tools.py` | Unit tests for the 5 tool functions |
| Create | `backend/tests/test_agent_core.py` | Integration tests for `ReActAgent` with mocked LLM |
| Modify | `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx` | Upgrade `AgentThinkingPanel` to render tool-specific cards |

---

## Task 1: `AgentBudget` — budget tracking

**Files:**
- Create: `backend/app/services/resume_copilot/agent/__init__.py`
- Create: `backend/app/services/resume_copilot/agent/budget.py`
- Create: `backend/tests/test_agent_budget.py`

- [ ] **Step 1: Create package + budget module**

```python
# backend/app/services/resume_copilot/agent/__init__.py
# (empty)
```

```python
# backend/app/services/resume_copilot/agent/budget.py
import time
from dataclasses import dataclass, field

DEFAULT_PER_TOOL_LIMITS: dict[str, int] = {
    'search_candidates': 4,
    'inspect_jobs': 3,
    'get_company_intel': 5,
    'search_web': 3,
    'finalize': 1,
}


@dataclass
class AgentBudget:
    max_total_calls: int = 12
    max_seconds: int = 90
    per_tool_limits: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PER_TOOL_LIMITS)
    )
    _call_counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _start_time: float = field(default_factory=time.monotonic, init=False, repr=False)

    def check(self, tool_name: str) -> tuple[bool, str]:
        """Returns (allowed, rejection_reason). Empty reason means allowed."""
        if not self.is_time_ok():
            return False, 'TIME_BUDGET_EXHAUSTED'
        if tool_name != 'finalize':
            non_finalize = sum(
                v for k, v in self._call_counts.items() if k != 'finalize'
            )
            if non_finalize >= self.max_total_calls:
                return False, 'TOTAL_BUDGET_EXHAUSTED'
        limit = self.per_tool_limits.get(tool_name, 0)
        if self._call_counts.get(tool_name, 0) >= limit:
            return False, 'TOOL_LIMIT_REACHED'
        return True, ''

    def record(self, tool_name: str) -> None:
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1

    def remaining(self) -> dict[str, int]:
        return {
            tool: max(0, limit - self._call_counts.get(tool, 0))
            for tool, limit in self.per_tool_limits.items()
        }

    def is_time_ok(self) -> bool:
        return time.monotonic() - self._start_time <= self.max_seconds
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_agent_budget.py
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
    # 4+3+5 = 12, exactly at max_total_calls
    budget._call_counts = {'search_candidates': 4, 'inspect_jobs': 3, 'get_company_intel': 5}
    allowed, reason = budget.check('search_web')
    assert allowed is False
    assert reason == 'TOTAL_BUDGET_EXHAUSTED'


def test_finalize_not_subject_to_total_budget():
    budget = AgentBudget()
    budget._call_counts = {'search_candidates': 4, 'inspect_jobs': 3, 'get_company_intel': 5}
    allowed, reason = budget.check('finalize')
    assert allowed is True


def test_record_increments_count():
    budget = AgentBudget()
    budget.record('search_web')
    budget.record('search_web')
    assert budget._call_counts['search_web'] == 2


def test_remaining_decrements_after_record():
    budget = AgentBudget()
    budget.record('search_web')
    assert budget.remaining()['search_web'] == 2  # limit 3, used 1


def test_time_exhausted_blocks_all_tools():
    budget = AgentBudget(max_seconds=0)
    # max_seconds=0 means immediately expired
    import time; time.sleep(0.01)
    allowed, reason = budget.check('search_candidates')
    assert allowed is False
    assert reason == 'TIME_BUDGET_EXHAUSTED'
```

- [ ] **Step 3: Run tests — expect FAIL (module not importable yet until package exists)**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_agent_budget.py -v 2>&1 | head -20
```

Expected: ImportError or ModuleNotFoundError

- [ ] **Step 4: Run tests again — expect PASS**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_agent_budget.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resume_copilot/agent/ backend/tests/test_agent_budget.py
git commit -m "feat(agent): add AgentBudget with per-tool and total call limits"
```

---

## Task 2: `prompt.py` — system prompt builder

**Files:**
- Create: `backend/app/services/resume_copilot/agent/prompt.py`

No separate test file — `prompt.py` is pure string construction, tested implicitly by `test_agent_core.py` in Task 5.

- [ ] **Step 1: Create prompt builder**

```python
# backend/app/services/resume_copilot/agent/prompt.py
import json

from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.agent.budget import AgentBudget


def _summarize_profile(profile: ResumeProfilePayload) -> str:
    parts: list[str] = []
    if profile.basic_info:
        parts.append(f"基本信息：{json.dumps(profile.basic_info, ensure_ascii=False)}")
    if profile.education:
        edu = profile.education[0]
        parts.append(f"学历：{edu.school} {edu.degree} {edu.major}")
    if profile.internships:
        names = [f"{i.company}（{i.role}）" for i in profile.internships[:3]]
        parts.append(f"实习经历：{', '.join(names)}")
    if profile.inferred_roles:
        parts.append(f"推断职能方向：{', '.join(profile.inferred_roles[:5])}")
    if profile.inferred_tracks:
        parts.append(f"推断赛道：{', '.join(profile.inferred_tracks[:3])}")
    if profile.candidate_summary:
        parts.append(f"综合评估：{profile.candidate_summary}")
    return '\n'.join(parts) or '（简历信息不足）'


def _summarize_preferences(preferences: ResumePreferencePayload | None) -> str:
    if not preferences or preferences.all_skipped:
        return '未指定偏好'
    parts: list[str] = []
    if preferences.preferred_locations:
        parts.append(f"期望城市：{', '.join(preferences.preferred_locations)}")
    if preferences.preferred_tracks:
        parts.append(f"目标赛道：{', '.join(preferences.preferred_tracks)}")
    if preferences.preferred_roles:
        parts.append(f"目标职能：{', '.join(preferences.preferred_roles)}")
    if preferences.preferred_company_types:
        parts.append(f"目标公司类型：{', '.join(preferences.preferred_company_types)}")
    return '\n'.join(parts) or '未指定偏好'


def _summarize_candidates(candidates: list[ResumeRecommendationItem]) -> str:
    rows = [
        {
            'rank': i + 1,
            'job_id': item.job_id,
            'company': item.company,
            'job_title': item.job_title,
            'location': item.location,
            'rule_score': item.base_match_score,
            'company_tier': item.company_priority_label or '',
            'need_enrichment': item.need_enrichment,
        }
        for i, item in enumerate(candidates[:100])
    ]
    return json.dumps(rows, ensure_ascii=False)


def build_system_prompt(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
    budget: AgentBudget,
) -> str:
    r = budget.remaining()
    return f"""你是一个专业的校招求职顾问，正在帮助一名中国大学生匹配最适合的岗位。

## 候选人画像
{_summarize_profile(profile)}

## 求职偏好
{_summarize_preferences(preferences)}

## 候选岗位池（规则引擎预筛 top-100，按规则分降序）
{_summarize_candidates(candidates)}

## 你的任务
从候选池中挑选 8-15 个最匹配的岗位，给出排序和每个岗位的推荐理由。

## 工具预算（每轮动态更新）
- search_candidates: 剩余 {r.get('search_candidates', 0)} 次
- inspect_jobs: 剩余 {r.get('inspect_jobs', 0)} 次
- get_company_intel: 剩余 {r.get('get_company_intel', 0)} 次
- search_web: 剩余 {r.get('search_web', 0)} 次
- finalize: 剩余 {r.get('finalize', 0)} 次（必须调用，结束分析）

## 输出格式（每轮严格返回 JSON）
{{"thought": "...", "action": "工具名", "args": {{...}}, "reasoning_display": "..."}}

## 行为规则
1. reasoning_display 用中文、用"你"称呼候选人，一句话，面向候选人展示
2. 有足够依据时尽早 finalize，不要为了用完预算而无意义搜索
3. 对高信息不对称赛道（券商/银行/国央企）优先调 get_company_intel
4. search_web 只用于真正模糊的岗位，不对每个岗位都搜
5. 预算耗尽时立即 finalize，不要报错"""
```

- [ ] **Step 2: Smoke-check import**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.services.resume_copilot.agent.prompt import build_system_prompt
from app.schemas_resume_copilot import ResumeProfilePayload, ResumePreferencePayload
from app.services.resume_copilot.agent.budget import AgentBudget
p = build_system_prompt(ResumeProfilePayload(), None, [], AgentBudget())
print(p[:200])
"
```

Expected: prints the first 200 chars of the prompt with no error.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/resume_copilot/agent/prompt.py
git commit -m "feat(agent): add system prompt builder"
```

---

## Task 3: `tools.py` — 5 tool functions

**Files:**
- Create: `backend/app/services/resume_copilot/agent/tools.py`
- Create: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Create tools module**

```python
# backend/app/services/resume_copilot/agent/tools.py
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models import Job, JobIntelSnapshot
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.quick_enrichment import search_web as _search_web
from app.services.resume_copilot.recommendation import compute_company_priority


@dataclass
class ToolResult:
    summary: str
    data: Any = None


def build_tools(
    db: Session,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
) -> dict[str, Callable]:
    """Returns a dict of tool_name → callable. Each callable matches its spec args."""

    def search_candidates(query: str, filters: dict | None = None) -> ToolResult:
        query_lower = query.lower()
        tokens = {t for t in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', query_lower) if len(t) > 1}
        results: list[ResumeRecommendationItem] = []
        for item in candidates:
            text = ' '.join([
                item.company, item.job_title, item.location,
                item.company_priority_label or '',
                item.matched_track_label or '',
                item.matched_role_family or '',
            ]).lower()
            if not tokens or any(tok in text for tok in tokens):
                if filters and 'track' in filters:
                    tf = filters['track'].lower()
                    tier = (item.company_priority_tier or '').lower()
                    track_key = (item.matched_track_key or '').lower()
                    if tf not in tier and tf not in track_key:
                        continue
                results.append(item)
        results.sort(key=lambda x: x.base_match_score, reverse=True)
        top = results[:20]
        rows = [
            {
                'job_id': i.job_id,
                'company': i.company,
                'job_title': i.job_title,
                'location': i.location,
                'rule_score': i.base_match_score,
                'company_tier': i.company_priority_label or '',
                'need_enrichment': i.need_enrichment,
            }
            for i in top
        ]
        return ToolResult(
            summary=f'召回 {len(top)} 个匹配岗位（共 {len(results)} 个候选）',
            data=rows,
        )

    def inspect_jobs(job_ids: list[str]) -> ToolResult:
        ids = job_ids[:5]
        rows = db.query(Job).filter(Job.job_id.in_(ids)).all()
        job_map = {str(j.job_id): j for j in rows}
        details = []
        for jid in ids:
            job = job_map.get(jid)
            if not job:
                continue
            details.append({
                'job_id': jid,
                'company': job.company,
                'job_title': job.job_title,
                'department': job.department or '',
                'job_req': (job.job_req or '')[:800],
                'job_duty': (job.job_duty or '')[:800],
            })
        return ToolResult(
            summary=f'读取 {len(details)} 个岗位完整 JD',
            data=details,
        )

    def get_company_intel(company_name: str) -> ToolResult:
        job = db.query(Job).filter(Job.company.like(f'%{company_name}%')).first()
        if not job:
            return ToolResult(summary=f'未找到公司「{company_name}」的记录', data={})
        priority = compute_company_priority(job)
        snapshot = (
            db.query(JobIntelSnapshot)
            .filter(JobIntelSnapshot.job_id == job.id)
            .order_by(JobIntelSnapshot.generated_at.desc())
            .first()
        )
        data = {
            'company': company_name,
            'tier': priority.tier,
            'tier_label': priority.label,
            'category': priority.category_label,
            'high_info_asymmetry': priority.high_info_asymmetry,
            'cached_summary': str(snapshot.summary_text or '') if snapshot else '',
        }
        summary = f'{company_name}：{priority.label or "未收录"}'
        if priority.high_info_asymmetry:
            summary += '（高信息不对称）'
        if snapshot:
            summary += '，有缓存情报'
        return ToolResult(summary=summary, data=data)

    def search_web(query: str) -> ToolResult:
        results = _search_web(query, max_results=4)
        rows = [{'title': r.title, 'url': r.url, 'snippet': r.snippet} for r in results]
        return ToolResult(
            summary=f'搜索到 {len(rows)} 条外部结果',
            data=rows,
        )

    return {
        'search_candidates': search_candidates,
        'inspect_jobs': inspect_jobs,
        'get_company_intel': get_company_intel,
        'search_web': search_web,
    }
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_agent_tools.py
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
        enhanced_score=base_match_score, rule_score=base_match_score,
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
```

- [ ] **Step 3: Run tests (expect PASS)**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_agent_tools.py -v
```

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/resume_copilot/agent/tools.py backend/tests/test_agent_tools.py
git commit -m "feat(agent): add 5 tool functions for ReAct loop"
```

---

## Task 4: Extend `ResumeAgentTraceItem` schema

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py` lines 130-133

The existing `ResumeAgentTraceItem` only has `agent`, `message`, `status`. Add three optional fields used by the new card renderer. Old trace items without these fields continue to work.

- [ ] **Step 1: Add optional fields to schema**

In `backend/app/schemas_resume_copilot.py`, replace:

```python
class ResumeAgentTraceItem(BaseModel):
    agent: str
    message: str
    status: str = 'completed'
```

with:

```python
class ResumeAgentTraceItem(BaseModel):
    agent: str
    message: str
    status: str = 'completed'
    tool: str = ''
    step_index: int = 0
    result_summary: str = ''
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_copilot_router.py tests/test_resume_feedback_service.py tests/test_resume_parser_service.py tests/test_resume_recommendation_service.py -v 2>&1 | tail -10
```

Expected: all pass (new fields have defaults, no existing code breaks).

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas_resume_copilot.py
git commit -m "feat(agent): extend ResumeAgentTraceItem with tool/step_index/result_summary"
```

---

## Task 5: `core.py` — ReActAgent main loop

**Files:**
- Create: `backend/app/services/resume_copilot/agent/core.py`
- Create: `backend/tests/test_agent_core.py`

- [ ] **Step 1: Write failing tests first**

```python
# backend/tests/test_agent_core.py
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
        enhanced_score=score, rule_score=score, final_score=score,
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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_agent_core.py -v 2>&1 | head -15
```

Expected: ImportError (core.py doesn't exist yet)

- [ ] **Step 3: Implement `core.py`**

```python
# backend/app/services/resume_copilot/agent/core.py
import json
from typing import Any, Callable
from urllib import request as urllib_request

from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.prompt import build_system_prompt
from app.services.resume_copilot.agent.tools import ToolResult
from app.services.resume_copilot.llm import build_resume_llm_client

TraceRecorder = Callable[..., None]

_FORCE_FINISH = (
    '\n\n⚠️ BUDGET_EXHAUSTED — Call finalize NOW with the best candidates you have. '
    'Return JSON with action="finalize" and no other tool.'
)
_MALFORMED_RETRY = (
    '\n\nYour previous response was not valid JSON. '
    'Return ONLY a JSON object with keys: thought, action, args, reasoning_display.'
)


def _call_llm(messages: list[dict], timeout_seconds: int = 30) -> str:
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': messages,
        'stream': False,
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {client.api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode('utf-8'))
    return body['choices'][0]['message']['content']


def _coerce_recommendation(
    raw: Any,
    candidates_by_id: dict[str, ResumeRecommendationItem],
) -> ResumeRecommendationItem | None:
    if not isinstance(raw, dict):
        return None
    job_id = str(raw.get('job_id', ''))
    base = candidates_by_id.get(job_id)
    if base is None:
        return None
    return base.model_copy(update={
        'final_score': int(raw.get('final_score', base.final_score) or 0),
        'used_ai': True,
        'why_recommended': [str(v) for v in raw.get('why_recommended', [])],
        'strengths': [str(v) for v in raw.get('strengths', [])],
        'risks': [str(v) for v in raw.get('risks', [])],
    })


class ReActAgent:
    def __init__(self, tools: dict[str, Callable], budget: AgentBudget | None = None) -> None:
        self.tools = tools
        self.budget = budget or AgentBudget()

    def run(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        candidates: list[ResumeRecommendationItem],
        trace_recorder: TraceRecorder | None = None,
    ) -> list[ResumeRecommendationItem]:
        candidates_by_id = {item.job_id: item for item in candidates}
        client = build_resume_llm_client()
        messages: list[dict] = [
            {'role': 'system', 'content': build_system_prompt(profile, preferences, candidates, self.budget)}
        ]
        step_index = 0

        while True:
            # Inject force-finish if time is up
            if not self.budget.is_time_ok():
                messages.append({'role': 'user', 'content': _FORCE_FINISH})

            # Call LLM
            last_content = '{}'
            try:
                last_content = _call_llm(messages, timeout_seconds=min(30, client.timeout_seconds))
                parsed = json.loads(last_content)
            except (json.JSONDecodeError, KeyError, Exception):
                # Retry once
                messages.append({'role': 'assistant', 'content': last_content})
                messages.append({'role': 'user', 'content': _MALFORMED_RETRY})
                try:
                    last_content = _call_llm(messages, timeout_seconds=min(30, client.timeout_seconds))
                    parsed = json.loads(last_content)
                except Exception:
                    return self._fallback(candidates)

            action = str(parsed.get('action', ''))
            args = parsed.get('args', {})
            reasoning_display = str(parsed.get('reasoning_display', ''))
            step_index += 1

            # Emit "running" trace so spinner appears immediately
            if trace_recorder:
                trace_recorder(
                    message=reasoning_display,
                    status='running',
                    tool=action,
                    step_index=step_index,
                    result_summary='',
                )

            # Handle finalize
            if action == 'finalize':
                recs_raw = args.get('recommendations', []) if isinstance(args, dict) else []
                results = [
                    r for r in (
                        _coerce_recommendation(raw, candidates_by_id) for raw in recs_raw
                    )
                    if r is not None
                ]
                if not results:
                    results = list(candidates[:10])
                results.sort(key=lambda x: x.final_score, reverse=True)
                if trace_recorder:
                    trace_recorder(
                        message=reasoning_display,
                        status='completed',
                        tool='finalize',
                        step_index=step_index,
                        result_summary=f'输出 {len(results)} 个推荐岗位',
                    )
                return results

            # Check budget
            allowed, budget_reason = self.budget.check(action)
            if not allowed:
                if budget_reason in ('TOTAL_BUDGET_EXHAUSTED', 'TIME_BUDGET_EXHAUSTED'):
                    if trace_recorder:
                        trace_recorder(
                            message='预算已用完，正在生成最终推荐',
                            status='completed',
                            tool=action,
                            step_index=step_index,
                            result_summary=budget_reason,
                        )
                    messages.append({'role': 'assistant', 'content': last_content})
                    messages.append({'role': 'user', 'content': _FORCE_FINISH})
                    continue
                observation = f'TOOL_LIMIT_REACHED for {action}'
                messages.append({'role': 'assistant', 'content': last_content})
                messages.append({'role': 'user', 'content': f'Observation: {observation}'})
                continue

            # Execute tool
            tool_fn = self.tools.get(action)
            if tool_fn is None:
                observation = f'UNKNOWN_TOOL: {action}'
                result_summary = observation
            else:
                try:
                    call_args = args if isinstance(args, dict) else {}
                    tool_result: ToolResult = tool_fn(**call_args)
                    self.budget.record(action)
                    observation = (
                        json.dumps(tool_result.data, ensure_ascii=False)
                        if tool_result.data is not None
                        else tool_result.summary
                    )
                    result_summary = tool_result.summary
                except Exception as exc:
                    observation = f'TOOL_ERROR: {exc}'
                    result_summary = f'工具出错：{exc}'

            if trace_recorder:
                trace_recorder(
                    message=reasoning_display,
                    status='completed',
                    tool=action,
                    step_index=step_index,
                    result_summary=result_summary,
                )

            # Rebuild system prompt with updated budget remaining counts
            messages[0] = {
                'role': 'system',
                'content': build_system_prompt(profile, preferences, candidates, self.budget),
            }
            messages.append({'role': 'assistant', 'content': last_content})
            messages.append({'role': 'user', 'content': f'Observation: {observation}'})

    def _fallback(self, candidates: list[ResumeRecommendationItem]) -> list[ResumeRecommendationItem]:
        return list(candidates[:10])
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_agent_core.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resume_copilot/agent/core.py backend/tests/test_agent_core.py
git commit -m "feat(agent): implement ReActAgent main loop with budget enforcement"
```

---

## Task 6: Wire agent into `workflow.py`

**Files:**
- Modify: `backend/app/services/resume_copilot/workflow.py`

- [ ] **Step 1: Update imports at top of workflow.py**

Remove the import of `enrich_recommendations_quickly` and add the agent imports. Change:

```python
from app.services.resume_copilot.quick_enrichment import enrich_recommendations_quickly, serialize_agent_trace
```

to:

```python
from app.services.resume_copilot.quick_enrichment import serialize_agent_trace
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.core import ReActAgent
from app.services.resume_copilot.agent.tools import build_tools
```

- [ ] **Step 2: Change `RESUME_RECOMMENDATION_LIMIT` constant**

Change:
```python
RESUME_RECOMMENDATION_LIMIT = 30
```
to:
```python
RESUME_RECOMMENDATION_LIMIT = 100
```

- [ ] **Step 3: Update `_append_agent_trace` to accept new keyword args**

Replace the current `_append_agent_trace` function:

```python
def _append_agent_trace(
    db,
    session_id: int,
    agent_trace: list[ResumeAgentTraceItem],
    agent: str,
    message: str,
    status: str = 'completed',
) -> None:
    agent_trace.append(ResumeAgentTraceItem(agent=agent, message=message, status=status))
    recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
    if recommendation_run:
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace)
        db.commit()
```

with:

```python
def _append_agent_trace(
    db,
    session_id: int,
    agent_trace: list[ResumeAgentTraceItem],
    agent: str = 'Agent',
    message: str = '',
    status: str = 'completed',
    tool: str = '',
    step_index: int = 0,
    result_summary: str = '',
) -> None:
    agent_trace.append(ResumeAgentTraceItem(
        agent=agent,
        message=message,
        status=status,
        tool=tool,
        step_index=step_index,
        result_summary=result_summary,
    ))
    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if recommendation_run:
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace)
        db.commit()
```

- [ ] **Step 4: Replace the enrichment block in `run_resume_generate_workflow`**

Find and replace in `run_resume_generate_workflow` — the block from `_append_agent_trace(db, session_id, agent_trace, 'Agent 1', '正在召回岗位...` through `recommendations = enrich_recommendations_quickly(...)`:

```python
        _append_agent_trace(db, session_id, agent_trace, 'Agent', '规则引擎召回中，正在计算基础匹配分…', 'running')
        candidates, used_ai, fallback_reason = recommend_jobs_for_profile(
            db,
            profile,
            preferences,
            limit=RESUME_RECOMMENDATION_LIMIT,
            ai_provider=recommendation_provider,
            ai_top_n=0,  # disable built-in AI rerank — agent handles this
        )
        _append_agent_trace(db, session_id, agent_trace, 'Agent', f'规则初筛完成，召回 {len(candidates)} 个候选岗位。', 'completed')

        def agent_trace_recorder(**kwargs: object) -> None:
            _append_agent_trace(db, session_id, agent_trace, **kwargs)

        agent = ReActAgent(
            tools=build_tools(db, profile, preferences, candidates),
            budget=AgentBudget(),
        )
        recommendations = agent.run(
            profile=profile,
            preferences=preferences,
            candidates=candidates,
            trace_recorder=agent_trace_recorder,
        )
```

Also update the lines after (which set `recommendation_run.used_ai`). The `used_ai` variable no longer comes from `recommend_jobs_for_profile` in a meaningful way — set it based on whether the agent produced AI-annotated results:

```python
        recommendation_run.used_ai = 1 if any(item.used_ai for item in recommendations) else 0
        recommendation_run.fallback_reason = ''
```

- [ ] **Step 5: Verify backend starts and route is reachable**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.services.resume_copilot.workflow import run_resume_generate_workflow
print('import OK')
"
```

Expected: prints `import OK`

- [ ] **Step 6: Run existing router tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_copilot_router.py -v 2>&1 | tail -15
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/resume_copilot/workflow.py
git commit -m "feat(agent): wire ReActAgent into generate workflow, replace quick_enrichment"
```

---

## Task 7: Frontend — rich agent step cards

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx`

The existing `AgentRow` component uses `agent/message/status` from trace items. We upgrade it to also use `tool/result_summary` when present, rendering a richer two-line card.

- [ ] **Step 1: Update `ResumeAgentTraceItem` type in `types.ts`**

Open `resume-copilot-web/components/resume-copilot/types.ts` and add the new optional fields to `ResumeAgentTraceItem`:

```typescript
export interface ResumeAgentTraceItem {
  agent: string;
  message: string;
  status: string;
  tool?: string;
  step_index?: number;
  result_summary?: string;
}
```

- [ ] **Step 2: Add tool metadata constants above `AgentRow` in `public-resume-copilot.tsx`**

Add these constants just above the existing `AgentRow` function (after the `AGENT_SPINNER_OFFSETS` block):

```tsx
const TOOL_META: Record<string, { icon: string; label: string }> = {
  search_candidates: { icon: '🔍', label: '检索候选岗位' },
  inspect_jobs:      { icon: '📄', label: '阅读岗位详情' },
  get_company_intel: { icon: '🏢', label: '查询公司情报' },
  search_web:        { icon: '🌐', label: '搜索外部信息' },
  finalize:          { icon: '✅', label: '生成最终推荐' },
};
```

- [ ] **Step 3: Replace `AgentRow` with upgraded version**

Replace the entire `AgentRow` function with:

```tsx
function AgentRow({
  agentName,
  latest,
  running,
}: {
  agentName: AgentName;
  latest: ResumeAgentTraceItem | undefined;
  running: boolean;
}) {
  const isDone = latest?.status === 'completed' || latest?.status === 'failed';
  const animate = running && !isDone;

  const [frameIdx, setFrameIdx] = useState(AGENT_SPINNER_OFFSETS[agentName]);
  const [verbIdx, setVerbIdx] = useState(0);

  useEffect(() => {
    if (!animate) return;
    const spinTimer = setInterval(
      () => setFrameIdx((i) => (i + 1) % SPINNER_FRAMES.length),
      120,
    );
    const verbMs = 2000 + AGENT_SPINNER_OFFSETS[agentName] * 150;
    const verbTimer = setInterval(
      () => setVerbIdx((i) => (i + 1) % AGENT_VERBS[agentName].length),
      verbMs,
    );
    return () => {
      clearInterval(spinTimer);
      clearInterval(verbTimer);
    };
  }, [animate, agentName]);

  const spinChar = isDone ? '✓' : SPINNER_FRAMES[frameIdx];
  const toolMeta = latest?.tool ? TOOL_META[latest.tool] : undefined;
  const displayMessage = latest?.message ?? (running ? AGENT_VERBS[agentName][verbIdx] : '—');

  return (
    <div
      className="flex items-start gap-3 py-2"
      style={{
        animation: isDone && latest?.tool ? 'slideInUp 0.28s ease-out both' : 'none',
      }}
    >
      <span
        className="mt-[2px] shrink-0 font-mono text-[15px] leading-snug"
        style={{
          color: isDone ? '#4ade80' : '#7c9ef7',
          minWidth: '1ch',
          display: 'inline-block',
          textAlign: 'center',
        }}
      >
        {spinChar}
      </span>
      <div className="min-w-0 flex-1">
        {toolMeta && isDone ? (
          <>
            <div className="flex items-center gap-1.5">
              <span className="text-[13px]">{toolMeta.icon}</span>
              <span className="text-[13px] font-semibold text-white/90">{toolMeta.label}</span>
            </div>
            <div className="mt-0.5 text-[12px] leading-snug text-white/55">{displayMessage}</div>
            {latest?.result_summary && (
              <div className="mt-0.5 text-[11px] leading-snug text-white/30">{latest.result_summary}</div>
            )}
          </>
        ) : (
          <div className="flex items-baseline gap-2">
            <span className="shrink-0 text-[13px] font-semibold text-white/90">{agentName}</span>
            <span className="shrink-0 text-[12px] text-white/20">·</span>
            <span className="min-w-0 truncate text-[13px] leading-snug text-white/45">{displayMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add `slideInUp` keyframe to `globals.css`**

Append to `resume-copilot-web/app/globals.css`:

```css
@keyframes slideInUp {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 5: Run lint + build**

```bash
cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -20
```

Expected: 0 errors, clean build.

- [ ] **Step 6: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx \
        resume-copilot-web/app/globals.css \
        resume-copilot-web/components/resume-copilot/types.ts
git commit -m "feat(frontend): upgrade AgentThinkingPanel to render tool-specific step cards"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by task |
|---|---|
| Rule engine → top-100 candidates | Task 6 (RESUME_RECOMMENDATION_LIMIT=100, ai_top_n=0) |
| ReAct loop (Reason→Act→Observe) | Task 5 core.py |
| 5 tools with per-tool limits | Tasks 3+1 |
| Budget: max 12 calls, 90s | Task 1 budget.py |
| Force-finish on budget exhaust | Task 5 core.py |
| Malformed JSON retry | Task 5 core.py |
| system prompt with dynamic budget | Task 2 prompt.py |
| agent_trace_json extended fields | Task 4 schema + Task 6 workflow |
| Frontend spinner + step cards | Task 7 |
| slideInUp card animation | Task 7 |
| Backward-compatible trace format | Task 4 (all new fields have defaults) |

**No placeholders found.** All code blocks are complete and runnable.

**Type consistency verified:** `ToolResult` defined in `tools.py`, imported by `core.py`. `AgentBudget` defined in `budget.py`, used in `prompt.py` and `core.py`. `ResumeAgentTraceItem` extended in Task 4, consumed in Task 6 and Task 7.
