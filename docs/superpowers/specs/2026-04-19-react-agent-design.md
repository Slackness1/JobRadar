# ReAct Agent for Resume-to-Job Matching — Design Spec

**Date:** 2026-04-19  
**Status:** Approved  
**Scope:** Backend agent core + frontend trace cards

---

## 1. Goal

Replace the current linear `quick_enrichment` pipeline with a ReAct (Reason → Act → Observe) loop that visibly reasons about the candidate's profile, selects tools dynamically, and produces a final ranked recommendation with per-job explanations. The AI's reasoning process is shown to the user in real time as step cards.

---

## 2. Architecture

```
User submits preferences
        │
        ▼
① Rule Engine  (unchanged)
  recommend_jobs_for_profile(limit=100)
  → top-100 candidates, scored by rule engine
        │
        ▼
② ReActAgent
  Input:  profile + preferences + top-100 candidates
  Loop:   Reason → Act → Observe  (max 12 tool calls, 90s)
  Output: final ranked recommendations (8–15 jobs) with reasoning
        │
        ▼
③ Frontend polling  (unchanged, 1.6s interval)
  Each completed ReAct step → new item in agent_trace_json
  Frontend renders a new card per item
```

**What does NOT change:**
- `recommendation.py` rule engine — only `limit` increases from 30 → 100
- `ingest.py`, `parser.py`, `feedback.py` — untouched
- `workflow.py` session state machine — state names unchanged
- DB schema — no new tables; `agent_trace_json` field gains new optional fields (backward-compatible)
- Frontend polling mechanism — unchanged

---

## 3. Tool Design

The agent has exactly 5 tools. Each has a per-tool call limit enforced by the budget.

### `search_candidates(query, filters?)` — limit: 4 calls
Search within the top-100 candidate pool by keyword/semantic query. Returns a ranked subset.

```python
search_candidates(query="券商 研究所 实习", filters={"track": "securities"})
# → list of up to 20 JobSummary from the candidate pool
```

### `inspect_jobs(job_ids)` — limit: 3 calls, max 5 job_ids per call
Fetch full JD text (job_req + job_duty + department) for specific jobs. Used when a job scores well on rules but has sparse JD.

```python
inspect_jobs(job_ids=["JD001", "JD002"])
# → list of JobDetail with full text fields
```

### `get_company_intel(company_name)` — limit: 5 calls
DB-only lookup: tier annotation + high_info_asymmetry flag + cached JobIntelSnapshot summary (if present, 14-day TTL). No network calls — fast.

```python
get_company_intel("中信证券")
# → {tier: "securities:tier1", high_info_asymmetry: True, cached_summary: "..."}
```

### `search_web(query)` — limit: 3 calls
Tavily search (existing implementation) for external job intelligence. Use only for high-ambiguity roles; do not call for every job.

```python
search_web("中金公司 投行部 校招 岗位方向 面经 2024")
# → list of SearchResult(title, url, snippet)
```

### `finalize(ranked_recommendations)` — limit: 1 call
Commit final output and end the loop. Required — the loop cannot end without calling this.

```python
finalize(ranked_recommendations=[
    {
        "job_id": "JD001",
        "final_score": 88,
        "why_recommended": ["背景强匹配", "高信息不对称岗位已补强"],
        "strengths": ["金融实习经历高度相关"],
        "risks": ["岗位真实方向偏业务，弱技术"]
    },
    ...
])
```

**Budget table:**

| Tool | Limit | Purpose |
|---|---|---|
| search_candidates | 4 | Search within candidate pool |
| inspect_jobs | 3 | Read full JD text |
| get_company_intel | 5 | Tier + intel cache lookup |
| search_web | 3 | External Tavily search |
| finalize | 1 | Commit output, end loop |
| **Total** | **≤16** | Hard cap: 12 non-finalize calls |

---

## 4. Budget & Constraint Model

```python
@dataclass
class AgentBudget:
    max_total_calls: int = 12       # excludes finalize
    max_seconds: int = 90
    per_tool_limits: dict = field(default_factory=lambda: {
        "search_candidates": 4,
        "inspect_jobs": 3,
        "get_company_intel": 5,
        "search_web": 3,
        "finalize": 1,
    })
    _call_counts: dict = field(default_factory=dict)
    _start_time: float = field(default_factory=time.monotonic)

    def check(self, tool_name: str) -> tuple[bool, str]:
        """Returns (allowed, rejection_reason)."""
        if tool_name != "finalize":
            if sum(self._call_counts.values()) >= self.max_total_calls:
                return False, "TOTAL_BUDGET_EXHAUSTED"
        if self._call_counts.get(tool_name, 0) >= self.per_tool_limits[tool_name]:
            return False, "TOOL_LIMIT_REACHED"
        if time.monotonic() - self._start_time > self.max_seconds:
            return False, "TIME_BUDGET_EXHAUSTED"
        return True, ""
```

**Force-finish mechanism:** When `TOTAL_BUDGET_EXHAUSTED` or `TIME_BUDGET_EXHAUSTED` is triggered, the loop injects a special observation and forces one final LLM call instructed to call `finalize` immediately with whatever it has.

---

## 5. ReAct Loop — Per-Turn JSON Format

Every LLM response must be `response_format: json_object` with this schema:

```json
{
  "thought": "Internal reasoning (not shown to user). Think step by step.",
  "action": "tool_name",
  "args": { ... },
  "reasoning_display": "One sentence in Chinese, using '你', shown on the step card."
}
```

`finalize` response:
```json
{
  "thought": "...",
  "action": "finalize",
  "args": {
    "recommendations": [
      {
        "job_id": "string",
        "final_score": 0,
        "why_recommended": ["string"],
        "strengths": ["string"],
        "risks": ["string"]
      }
    ]
  },
  "reasoning_display": "分析完成，为你整理了 9 个最匹配的岗位"
}
```

---

## 6. System Prompt Structure

```
你是一个专业的校招求职顾问，正在帮助一名中国大学生匹配最适合的岗位。

## 候选人画像
{profile_summary}

## 求职偏好
{preferences_summary}

## 候选岗位池（规则引擎预筛 top-100，按规则分降序）
{candidates_json}

## 你的任务
从候选池中挑选 8-15 个最匹配的岗位，给出排序和每个岗位的推荐理由。

## 工具预算（每轮动态更新）
- search_candidates: 剩余 {n} 次
- inspect_jobs: 剩余 {n} 次  
- get_company_intel: 剩余 {n} 次
- search_web: 剩余 {n} 次
- finalize: 剩余 1 次（必须调用，结束分析）

## 输出格式（每轮严格返回 JSON）
{ "thought": "...", "action": "...", "args": {...}, "reasoning_display": "..." }

## 行为规则
1. reasoning_display 用中文、用"你"称呼候选人，一句话，面向候选人展示
2. 有足够依据时尽早 finalize，不要为了用完预算而无意义搜索
3. 对高信息不对称赛道（券商/银行/国央企）优先调 get_company_intel
4. search_web 只用于真正模糊的岗位，不对每个岗位都搜
5. 预算耗尽时立即 finalize，不要报错
```

---

## 7. Agent Trace Format

`agent_trace_json` gains new optional fields (backward-compatible with existing `{agent, message, status}`):

```json
[
  {
    "agent": "Agent",
    "message": "你有金融实习背景，我先聚焦券商研究所方向",
    "status": "completed",
    "tool": "search_candidates",
    "step_index": 1,
    "result_summary": "召回 18 个匹配岗位"
  }
]
```

Frontend uses `tool` field to pick the card icon and title. `result_summary` shown as the second line of the card. Existing fields (`agent`, `message`, `status`) continue to drive the Claude spinner logic unchanged.

---

## 8. Frontend Card Design

Five card types mapped to tools:

| Tool | Icon | Card Title |
|---|---|---|
| search_candidates | 🔍 | 检索候选岗位 |
| inspect_jobs | 📄 | 阅读岗位详情 |
| get_company_intel | 🏢 | 查询公司情报 |
| search_web | 🌐 | 搜索外部信息 |
| finalize | ✅ | 生成最终推荐 |

**Render rhythm:**
```
[Claude spinner]           ← agent reasoning (thought phase)
[Card 1 slides in ✓]      ← get_company_intel: "中信证券是头部研究平台"
[Claude spinner]
[Card 2 slides in ✓]      ← search_candidates: "召回 18 个券商岗位"
[Claude spinner]
[Card 3 slides in ✓]      ← inspect_jobs: "读取 3 个 JD 全文"
[Claude spinner]
[Card 4 slides in ✓]      ← search_web: "搜索中金公司实习面经"
[Claude spinner]
[✅ Card 5 slides in]      ← finalize: "为你整理了 9 个最匹配岗位"
```

Cards animate in with a slide-up CSS transition. The spinner runs continuously between cards.

---

## 9. File Structure (New Files Only)

```
backend/app/services/resume_copilot/
  agent/
    __init__.py
    core.py        # ReActAgent main loop (~200 lines)
    tools.py       # 5 tool functions (reuse Tavily/Jina from quick_enrichment.py)
    budget.py      # AgentBudget dataclass
    prompt.py      # System prompt builder
```

**`workflow.py` change (the only existing file that changes meaningfully):**

```python
# Before
recommendations = recommend_jobs_for_profile(db, profile, preferences, limit=30)
recommendations = enrich_recommendations_quickly(...)

# After
candidates, _, _ = recommend_jobs_for_profile(db, profile, preferences, limit=100)
agent = ReActAgent(
    tools=build_tools(db, profile, preferences),
    budget=AgentBudget(),
)
recommendations = agent.run(
    profile=profile,
    preferences=preferences,
    candidates=candidates,
    trace_recorder=lambda **kwargs: _append_agent_trace(db, session_id, agent_trace, **kwargs),
)
```

`quick_enrichment.py` is not deleted — its Tavily/Jina functions are imported by `agent/tools.py`.

---

## 10. Error Handling

- **LLM returns malformed JSON:** Retry once with an error message appended. If still malformed, treat as `finalize` with current best candidates.
- **Tool raises exception:** Append observation `"TOOL_ERROR: {message}"`, agent decides how to proceed. Does not consume budget retry.
- **All tool limits exhausted before finalize:** Force-finish mechanism injects `BUDGET_EXHAUSTED` observation and instructs immediate `finalize`.
- **Agent calls unknown tool:** Return `"UNKNOWN_TOOL"` observation, counts against total budget.
