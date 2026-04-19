# Tiered Match + Multi-Turn Resume Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one-shot `ResumeFeedbackRun` system with a three-tier career-direction analysis + a persistent multi-turn rewrite copilot chat that lets users iteratively improve their resume and apply specific rewrites back to their confirmed profile.

**Architecture:** A new `direction_analysis.py` service classifies each preferred career direction as Tier 1/2/3 via one batched LLM call. Results are stored in `ResumeDirectionAnalysisRun`, injected into the ReAct agent prompt, and used to seed the first message of a new `ResumeCopilotMessage` chat. A new `chat.py` service handles multi-turn turns (store user msg → call LLM → parse rewrite options → store assistant msg). Applying a rewrite option patch-traverses `ResumeConfirmedProfile.profile_json` by dot-notation path. The frontend replaces the feedback panel with a chat UI and adds direction tabs above the job list.

**Tech Stack:** Python/FastAPI/SQLite backend, Next.js/React/Tailwind frontend. No new dependencies.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/app/schemas_resume_copilot.py` | Modify | Add `DirectionTierResult`, `RewriteOption`, `ResumeCopilotMessageOut`, `ChatMessageIn`, `ApplyRewriteIn`, `target_direction` on `ResumeRecommendationItem` |
| `backend/app/models.py` | Modify | Add `ResumeDirectionAnalysisRun`, `ResumeCopilotMessage`, relationships on `ResumeCopilotSession` |
| `backend/app/services/schema_patch.py` | Modify | CREATE TABLE for both new tables |
| `backend/app/services/resume_copilot/direction_analysis.py` | Create | Provider protocol + LLM call + fallback |
| `backend/app/services/resume_copilot/agent/prompt.py` | Modify | Add `direction_results` param + direction section |
| `backend/app/services/resume_copilot/agent/core.py` | Modify | Pass direction results to prompt; coerce `target_direction` in finalize |
| `backend/app/services/resume_copilot/workflow.py` | Modify | Replace feedback logic with direction analysis + initialize_chat |
| `backend/app/services/resume_copilot/chat.py` | Create | `initialize_chat`, `generate_chat_turn`, `apply_rewrite` |
| `backend/app/routers/resume_copilot.py` | Modify | Replace ResumeFeedbackRun in generate endpoint; add direction-analysis + chat endpoints; update `_get_session_eager` + `_build_session_out` |
| `resume-copilot-web/components/resume-copilot/types.ts` | Modify | Add `DirectionTierResult`, `RewriteOption`, `CopilotMessage`, `target_direction` on recommendation item, `has_direction_analysis` on session |
| `resume-copilot-web/components/resume-copilot/api.ts` | Modify | Add `getDirectionAnalysis`, `getChatMessages`, `postChatMessage`, `postApplyRewrite` |
| `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx` | Modify | Direction tabs + tier info bars; replace feedback panel with chat UI |
| `backend/tests/test_direction_analysis.py` | Create | Unit tests for direction_analysis service |
| `backend/tests/test_chat_service.py` | Create | Unit tests for chat service |
| `backend/tests/test_direction_workflow.py` | Create | Integration tests for updated workflow |

---

## Task 1: New Pydantic Schemas

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py`
- Test: `backend/tests/test_direction_analysis.py` (created in this task, expanded later)

- [ ] **Step 1: Write a failing test that imports the new schemas**

Create `backend/tests/test_direction_analysis.py`:

```python
from app.schemas_resume_copilot import (
    DirectionTierResult,
    RewriteOption,
    ResumeCopilotMessageOut,
    ChatMessageIn,
    ApplyRewriteIn,
    ResumeRecommendationItem,
)
from datetime import datetime


def test_direction_tier_result_schema():
    r = DirectionTierResult(
        direction='投研',
        tier=2,
        tier_label='可迁移',
        strengths=['数据分析经历'],
        gaps=['缺少金融实习'],
        transferable_from=['数据分析实习可往投研方向靠'],
    )
    assert r.tier == 2
    assert r.direction == '投研'


def test_rewrite_option_schema():
    o = RewriteOption(
        option_id='A',
        label='方案A — 突出量化成果',
        section='internships',
        field_path='internships.0.bullets.2',
        original='参与数据分析项目',
        improved='独立搭建 DCF 估值模型，覆盖 3 家上市公司',
        rationale='添加具体成果',
    )
    assert o.field_path == 'internships.0.bullets.2'


def test_copilot_message_out_schema():
    msg = ResumeCopilotMessageOut(
        id=1,
        role='assistant',
        content='建议如下',
        rewrite_options=None,
        applied_option_id=None,
        created_at=datetime(2026, 4, 20),
    )
    assert msg.role == 'assistant'


def test_chat_message_in_schema():
    msg = ChatMessageIn(content='我做过估值模型')
    assert msg.content == '我做过估值模型'


def test_apply_rewrite_in_schema():
    req = ApplyRewriteIn(message_id=5, option_id='A')
    assert req.option_id == 'A'


def test_recommendation_item_has_target_direction():
    item = ResumeRecommendationItem(
        job_id='job-1', company='ABC', job_title='后端', location='上海',
        objective_score=50, preference_score=30, base_job_score=40,
        company_priority_score=10, rule_score=130, final_score=130,
        target_direction='互联网后端',
    )
    assert item.target_direction == '互联网后端'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py -x -q
```

Expected: `ImportError` or `TypeError` — schemas don't exist yet.

- [ ] **Step 3: Add new schemas to `backend/app/schemas_resume_copilot.py`**

Add after the existing `ResumeProfilePayload` class (around line 47), before `ResumeParsedProfileOut`:

```python
class DirectionTierResult(BaseModel):
    direction: str
    tier: int  # 1, 2, or 3
    tier_label: str  # "强匹配" | "可迁移" | "有差距"
    strengths: list[str] = []
    gaps: list[str] = []
    transferable_from: list[str] = []
```

Add after `ResumeFeedbackResultOut` at the bottom of the file:

```python
class RewriteOption(BaseModel):
    option_id: str      # "A" | "B" | "C"
    label: str
    section: str        # "internships" | "projects" | etc.
    field_path: str     # dot-notation: "internships.0.bullets.2"
    original: str
    improved: str
    rationale: str


class ResumeCopilotMessageOut(BaseModel):
    id: int
    role: str           # "system" | "user" | "assistant"
    content: str
    rewrite_options: list[RewriteOption] | None = None
    applied_option_id: str | None = None
    created_at: datetime | None = None


class ChatMessageIn(BaseModel):
    content: str


class ApplyRewriteIn(BaseModel):
    message_id: int
    option_id: str


class ApplyRewriteOut(BaseModel):
    profile: 'ResumeProfilePayload'
    applied: bool = True
```

Also add `target_direction: str = ''` to `ResumeRecommendationItem` (after `risks: list[str] = []`):

```python
    risks: list[str] = []
    target_direction: str = ''   # set by ReAct agent in finalize
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py -x -q
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/schemas_resume_copilot.py tests/test_direction_analysis.py
git commit -m "feat(schemas): add DirectionTierResult, RewriteOption, CopilotMessage, target_direction"
```

---

## Task 2: DB Models + schema_patch

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/schema_patch.py`
- Test: `backend/tests/test_direction_analysis.py`

- [ ] **Step 1: Add failing test for new DB tables**

Append to `backend/tests/test_direction_analysis.py`:

```python
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import ResumeDirectionAnalysisRun, ResumeCopilotMessage
from app.services.schema_patch import ensure_compatible_schema


def _make_engine():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_compatible_schema(engine)
    return engine


def test_direction_analysis_run_table_exists():
    engine = _make_engine()
    inspector = inspect(engine)
    assert 'resume_direction_analysis_runs' in inspector.get_table_names()
    columns = {c['name'] for c in inspector.get_columns('resume_direction_analysis_runs')}
    assert {'id', 'session_id', 'status', 'directions_json', 'error_message', 'created_at'}.issubset(columns)


def test_copilot_message_table_exists():
    engine = _make_engine()
    inspector = inspect(engine)
    assert 'resume_copilot_messages' in inspector.get_table_names()
    columns = {c['name'] for c in inspector.get_columns('resume_copilot_messages')}
    assert {'id', 'session_id', 'role', 'content', 'rewrite_options_json', 'applied_option_id', 'created_at'}.issubset(columns)
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py::test_direction_analysis_run_table_exists -x -q
```

Expected: `ImportError` — models don't exist yet.

- [ ] **Step 3: Add models to `backend/app/models.py`**

After `class ResumeFeedbackRun` (around line 203), add:

```python
class ResumeDirectionAnalysisRun(Base):
    __tablename__ = "resume_direction_analysis_runs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(Text, default="pending")
    error_message = Column(Text, default="")
    directions_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="direction_analysis_run")


class ResumeCopilotMessage(Base):
    __tablename__ = "resume_copilot_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Text, default="user")      # system | user | assistant
    content = Column(Text, default="")
    rewrite_options_json = Column(Text, nullable=True)   # JSON list[RewriteOption] or null
    applied_option_id = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="chat_messages")
```

Also add two relationships inside `class ResumeCopilotSession` (after `feedback_run = relationship(...)`, around line 134):

```python
    direction_analysis_run = relationship(
        "ResumeDirectionAnalysisRun",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chat_messages = relationship(
        "ResumeCopilotMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ResumeCopilotMessage.created_at",
    )
```

- [ ] **Step 4: Add table creation to `backend/app/services/schema_patch.py`**

At the end of `ensure_compatible_schema`, before the final closing brace, add:

```python
        direction_analysis_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_direction_analysis_runs'")
        ).fetchone()
        if not direction_analysis_exists:
            conn.execute(text(
                """
                CREATE TABLE resume_direction_analysis_runs (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL UNIQUE REFERENCES resume_copilot_sessions(id) ON DELETE CASCADE,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT DEFAULT '',
                    directions_json TEXT DEFAULT '[]',
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            ))

        messages_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_copilot_messages'")
        ).fetchone()
        if not messages_exists:
            conn.execute(text(
                """
                CREATE TABLE resume_copilot_messages (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES resume_copilot_sessions(id) ON DELETE CASCADE,
                    role TEXT DEFAULT 'user',
                    content TEXT DEFAULT '',
                    rewrite_options_json TEXT,
                    applied_option_id TEXT,
                    created_at DATETIME
                )
                """
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_resume_copilot_messages_session_id ON resume_copilot_messages (session_id)"
            ))
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py -x -q
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/models.py app/services/schema_patch.py tests/test_direction_analysis.py
git commit -m "feat(db): add ResumeDirectionAnalysisRun and ResumeCopilotMessage models"
```

---

## Task 3: direction_analysis.py Service

**Files:**
- Create: `backend/app/services/resume_copilot/direction_analysis.py`
- Test: `backend/tests/test_direction_analysis.py`

- [ ] **Step 1: Add failing tests for the direction analysis service**

Append to `backend/tests/test_direction_analysis.py`:

```python
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumeProfilePayload,
    ResumePreferencePayload,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.direction_analysis import generate_direction_analysis


def _build_profile():
    return ResumeProfilePayload(
        basic_info={'name': 'Jane'},
        education=[],
        internships=[],
        projects=[],
        skills=ResumeSkillsPayload(technical=['Python'], tools=[], languages=[]),
        languages=[],
        awards=[],
        candidate_summary='Data-focused student',
        inferred_roles=['Data Analyst'],
        inferred_tracks=['Internet'],
    )


def _build_preferences(roles=None, tracks=None):
    return ResumePreferencePayload(
        preferred_roles=roles or ['Backend Engineer'],
        preferred_tracks=tracks or ['Internet'],
        preferred_locations=['Shanghai'],
        preferred_company_types=[],
        accept_relocation=False,
        accept_internship=False,
        campus_only=False,
        social_ok=False,
        preference_notes='',
        all_skipped=False,
    )


class _StubDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        return [
            {
                'direction': d,
                'tier': 1 if d == 'Backend Engineer' else 2,
                'tier_label': '强匹配' if d == 'Backend Engineer' else '可迁移',
                'strengths': ['Python skills'],
                'gaps': [] if d == 'Backend Engineer' else ['missing finance experience'],
                'transferable_from': [] if d == 'Backend Engineer' else ['data analysis transferable'],
            }
            for d in directions
        ]


class _FailingDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        raise RuntimeError('LLM unavailable')


def test_generate_direction_analysis_returns_tier_results():
    results = generate_direction_analysis(
        _build_profile(),
        _build_preferences(roles=['Backend Engineer', '投研']),
        provider=_StubDirectionProvider(),
    )
    assert len(results) >= 2
    assert all(isinstance(r, DirectionTierResult) for r in results)
    be = next(r for r in results if r.direction == 'Backend Engineer')
    assert be.tier == 1
    assert be.tier_label == '强匹配'


def test_generate_direction_analysis_falls_back_on_llm_failure():
    results = generate_direction_analysis(
        _build_profile(),
        _build_preferences(roles=['Backend Engineer']),
        provider=_FailingDirectionProvider(),
    )
    # Should return fallback tier=1 for each direction, not raise
    assert len(results) >= 1
    assert all(r.tier == 1 for r in results)


def test_generate_direction_analysis_uses_inferred_when_preferences_all_skipped():
    prefs = _build_preferences()
    prefs.all_skipped = True
    results = generate_direction_analysis(
        _build_profile(),
        prefs,
        provider=_StubDirectionProvider(),
    )
    # Falls back to inferred_roles + inferred_tracks from profile
    assert len(results) >= 1
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py::test_generate_direction_analysis_returns_tier_results -x -q
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create `backend/app/services/resume_copilot/direction_analysis.py`**

```python
import json
from typing import Any, Protocol
from urllib import request as urllib_request

from app.schemas_resume_copilot import DirectionTierResult, ResumePreferencePayload, ResumeProfilePayload
from app.services.resume_copilot.llm import build_resume_llm_client

_SYSTEM_PROMPT = """\
你是一个专业的校招求职顾问。对于候选人的每个目标方向，评估其背景与该方向的匹配程度，分为三层：
- 第1层（强匹配）：有直接相关经历
- 第2层（可迁移）：有相邻经历，经过改写可以靠近
- 第3层（有差距）：几乎没有相关背景

返回 JSON，格式为：
{"directions": [{"direction": "...", "tier": 1, "tier_label": "强匹配", "strengths": [...], "gaps": [...], "transferable_from": [...]}]}

tier_label 的取值只能是 "强匹配" / "可迁移" / "有差距"。
"""


class DirectionAnalysisProvider(Protocol):
    def analyze_directions(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        directions: list[str],
    ) -> list[dict[str, Any]]: ...


class OpenAICompatibleDirectionAnalysisProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def analyze_directions(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        directions: list[str],
    ) -> list[dict[str, Any]]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'candidate_summary': profile.candidate_summary,
                            'inferred_roles': profile.inferred_roles,
                            'inferred_tracks': profile.inferred_tracks,
                            'internships': [
                                {'company': i.company, 'role': i.role, 'bullets': i.bullets}
                                for i in profile.internships
                            ],
                            'projects': [
                                {'name': p.name, 'bullets': p.bullets}
                                for p in profile.projects
                            ],
                            'target_directions': directions,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        return json.loads(content).get('directions', [])


def _collect_directions(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
) -> list[str]:
    if preferences and not preferences.all_skipped:
        seen: dict[str, None] = {}
        for d in preferences.preferred_roles + preferences.preferred_tracks:
            seen[d] = None
        directions = list(seen.keys())[:8]
        if directions:
            return directions
    seen = {}
    for d in profile.inferred_roles[:4] + profile.inferred_tracks[:4]:
        seen[d] = None
    return list(seen.keys())


def generate_direction_analysis(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    provider: DirectionAnalysisProvider | None = None,
) -> list[DirectionTierResult]:
    directions = _collect_directions(profile, preferences)
    if not directions:
        return []

    _provider = provider or OpenAICompatibleDirectionAnalysisProvider()
    try:
        raw_list = _provider.analyze_directions(profile, preferences, directions)
        results = []
        for item in (raw_list or []):
            tier_raw = int(item.get('tier', 1))
            tier = tier_raw if tier_raw in (1, 2, 3) else 1
            results.append(DirectionTierResult(
                direction=str(item.get('direction', '')),
                tier=tier,
                tier_label=str(item.get('tier_label', '强匹配')),
                strengths=[str(s) for s in item.get('strengths', [])],
                gaps=[str(g) for g in item.get('gaps', [])],
                transferable_from=[str(t) for t in item.get('transferable_from', [])],
            ))
        return results
    except Exception:
        return [
            DirectionTierResult(
                direction=d,
                tier=1,
                tier_label='强匹配',
                strengths=[],
                gaps=[],
                transferable_from=[],
            )
            for d in directions
        ]
```

- [ ] **Step 4: Run all direction analysis tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py -x -q
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/resume_copilot/direction_analysis.py tests/test_direction_analysis.py
git commit -m "feat(direction-analysis): add service with provider protocol and graceful fallback"
```

---

## Task 4: agent/prompt.py — direction tiers section + core.py target_direction

**Files:**
- Modify: `backend/app/services/resume_copilot/agent/prompt.py`
- Modify: `backend/app/services/resume_copilot/agent/core.py`
- Test: `backend/tests/test_direction_analysis.py`

- [ ] **Step 1: Add failing test for direction section in prompt**

Append to `backend/tests/test_direction_analysis.py`:

```python
from app.services.resume_copilot.agent.prompt import build_system_prompt
from app.services.resume_copilot.agent.budget import AgentBudget


def test_build_system_prompt_includes_direction_tiers_when_provided():
    profile = _build_profile()
    preferences = _build_preferences()
    direction_results = [
        DirectionTierResult(direction='Backend Engineer', tier=1, tier_label='强匹配',
                            strengths=['Python'], gaps=[], transferable_from=[]),
        DirectionTierResult(direction='投研', tier=2, tier_label='可迁移',
                            strengths=[], gaps=['缺少金融经历'], transferable_from=['数据分析可迁移']),
    ]
    prompt = build_system_prompt(profile, preferences, [], AgentBudget(), direction_results=direction_results)
    assert 'Backend Engineer' in prompt
    assert '强匹配' in prompt
    assert '投研' in prompt
    assert '可迁移' in prompt


def test_build_system_prompt_no_direction_section_when_none():
    profile = _build_profile()
    preferences = _build_preferences()
    prompt = build_system_prompt(profile, preferences, [], AgentBudget(), direction_results=None)
    assert 'Direction Tiers' not in prompt
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py::test_build_system_prompt_includes_direction_tiers_when_provided -x -q
```

Expected: `TypeError` — `build_system_prompt` doesn't accept `direction_results` yet.

- [ ] **Step 3: Update `backend/app/services/resume_copilot/agent/prompt.py`**

Replace the entire file with:

```python
import json

from app.schemas_resume_copilot import (
    DirectionTierResult,
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


def _format_direction_tiers(direction_results: list[DirectionTierResult]) -> str:
    lines = []
    for r in direction_results:
        tier_emoji = '🟢' if r.tier == 1 else '🟡' if r.tier == 2 else '🔴'
        hint = ''
        if r.tier == 1:
            hint = '— 优先在 finalize 中推荐此方向岗位'
        elif r.tier == 2:
            hint = '— 包含部分此方向岗位；在 why_recommended 中注明可迁移性'
        else:
            hint = '— 只包含入门级/容忍度高的岗位；在 finalize 的 target_direction 中标注'
        lines.append(f"{tier_emoji} {r.direction}: 第{r.tier}层 ({r.tier_label}) {hint}")
    return '\n'.join(lines)


def build_system_prompt(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
    budget: AgentBudget,
    direction_results: list[DirectionTierResult] | None = None,
) -> str:
    r = budget.remaining()
    direction_section = ''
    if direction_results:
        direction_section = f"""
## 方向层级分析
{_format_direction_tiers(direction_results)}
在 finalize 的每个推荐岗位中，请根据上述层级设置 target_direction 字段（例如 "投研"）。

"""
    return f"""你是一个专业的校招求职顾问，正在帮助一名中国大学生匹配最适合的岗位。

## 候选人画像
{_summarize_profile(profile)}

## 求职偏好
{_summarize_preferences(preferences)}
{direction_section}
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

## finalize 的 args 格式
{{"recommendations": [{{"job_id": "...", "final_score": 85, "why_recommended": [...], "strengths": [...], "risks": [...], "target_direction": "目标方向名（如 互联网后端）"}}]}}

## 行为规则
1. reasoning_display 用中文、用"你"称呼候选人，一句话，面向候选人展示
2. 有足够依据时尽早 finalize，不要为了用完预算而无意义搜索
3. 对高信息不对称赛道（券商/银行/国央企）优先调 get_company_intel
4. search_web 只用于真正模糊的岗位，不对每个岗位都搜
5. 预算耗尽时立即 finalize，不要报错"""
```

- [ ] **Step 4: Update `_coerce_recommendation` in `backend/app/services/resume_copilot/agent/core.py`**

Find the `_coerce_recommendation` function (lines ~49-65) and replace it:

```python
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
        'target_direction': str(raw.get('target_direction', '') or ''),
    })
```

Also update the `ReActAgent.run` signature in `core.py` to accept optional `direction_results`, and pass them to `build_system_prompt`. Find the `run` method:

```python
def run(
    self,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
    trace_recorder: TraceRecorder | None = None,
    direction_results: list | None = None,
) -> list[ResumeRecommendationItem]:
```

And update the initial system prompt line (two places: initial setup + rebuild after tool call):

```python
messages: list[dict] = [
    {'role': 'system', 'content': build_system_prompt(profile, preferences, candidates, self.budget, direction_results=direction_results)}
]
```

And the rebuild line inside the tool loop:
```python
messages[0] = {
    'role': 'system',
    'content': build_system_prompt(profile, preferences, candidates, self.budget, direction_results=direction_results),
}
```

The import at the top of `core.py` needs updating too — add `DirectionTierResult` is not needed since we use `list | None`, but we need to import `build_system_prompt` from the updated prompt module (already imported).

- [ ] **Step 5: Run tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py -x -q
```

Expected: `13 passed`

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/resume_copilot/agent/prompt.py app/services/resume_copilot/agent/core.py tests/test_direction_analysis.py
git commit -m "feat(agent): inject direction tier context into prompt; coerce target_direction in finalize"
```

---

## Task 5: workflow.py — Replace feedback with direction analysis

**Files:**
- Modify: `backend/app/services/resume_copilot/workflow.py`
- Create: `backend/tests/test_direction_workflow.py`
- Modify: `backend/tests/test_resume_feedback_service.py` (remove broken assertions)

- [ ] **Step 1: Write failing workflow test**

Create `backend/tests/test_direction_workflow.py`:

```python
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Job,
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeDirectionAnalysisRun,
    ResumeCopilotMessage,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.workflow import run_resume_generate_workflow


def _build_session_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _build_profile():
    return ResumeProfilePayload(
        basic_info={'name': 'Jane Doe'},
        education=[],
        internships=[],
        projects=[],
        skills=ResumeSkillsPayload(technical=['Python'], tools=[], languages=[]),
        languages=[],
        awards=[],
        candidate_summary='Backend-focused',
        inferred_roles=['Backend Engineer'],
        inferred_tracks=['Internet'],
    )


def _build_preferences():
    return ResumePreferencePayload(
        preferred_roles=['Backend Engineer'],
        preferred_tracks=['Internet'],
        preferred_locations=['Shanghai'],
        preferred_company_types=['Internet'],
        accept_relocation=False,
        accept_internship=False,
        campus_only=False,
        social_ok=False,
        preference_notes='',
        all_skipped=False,
    )


def _seed(db: Session) -> int:
    session = ResumeCopilotSession(
        file_name='cv.pdf',
        status='awaiting_user_confirmation',
        recommendation_status='running',
        feedback_status='running',
        extracted_text='Jane Doe',
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    profile = _build_profile()
    preferences = _build_preferences()
    db.add(ResumeConfirmedProfile(
        session_id=session.id,
        profile_json=json.dumps(profile.model_dump()),
    ))
    db.add(ResumePreferenceProfile(
        session_id=session.id,
        preferences_json=json.dumps(preferences.model_dump()),
        all_skipped=0,
    ))
    db.add(Job(
        job_id='job-1',
        company='Acme',
        company_type_industry='Internet',
        department='Engineering',
        job_title='Backend Engineer',
        location='Shanghai',
        major_req='CS',
        job_req='Python REST APIs',
        job_duty='Build APIs',
        job_stage='campus',
    ))
    db.commit()
    return int(session.id)


class _StubDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        return [
            {
                'direction': d,
                'tier': 1,
                'tier_label': '强匹配',
                'strengths': ['Python'],
                'gaps': [],
                'transferable_from': [],
            }
            for d in directions
        ]


class _StubRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items):
        return items


def test_workflow_creates_direction_analysis_run():
    factory = _build_session_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=factory,
        direction_provider=_StubDirectionProvider(),
        recommendation_provider=_StubRecommendationProvider(),
    )

    db = factory()
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    assert direction_run is not None
    assert direction_run.status == 'completed'
    directions = json.loads(direction_run.directions_json)
    assert isinstance(directions, list)
    db.close()


def test_workflow_creates_initial_chat_message():
    factory = _build_session_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=factory,
        direction_provider=_StubDirectionProvider(),
        recommendation_provider=_StubRecommendationProvider(),
    )

    db = factory()
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).order_by(ResumeCopilotMessage.created_at).all()
    assert len(msgs) >= 1
    assert msgs[0].role == 'system'
    assert len(msgs[0].content) > 0
    db.close()


def test_workflow_feedback_status_completed():
    factory = _build_session_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=factory,
        direction_provider=_StubDirectionProvider(),
        recommendation_provider=_StubRecommendationProvider(),
    )

    db = factory()
    session = db.query(ResumeCopilotSession).filter(
        ResumeCopilotSession.id == session_id
    ).first()
    assert session.feedback_status == 'completed'
    assert session.status == 'completed'
    db.close()
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_workflow.py::test_workflow_creates_direction_analysis_run -x -q
```

Expected: `TypeError` — `run_resume_generate_workflow` doesn't accept `direction_provider` yet.

- [ ] **Step 3: Rewrite `run_resume_generate_workflow` in `backend/app/services/resume_copilot/workflow.py`**

Replace the entire `run_resume_generate_workflow` function (lines 110–255) with:

```python
def run_resume_generate_workflow(
    session_id: int,
    session_factory=SessionLocal,
    recommendation_provider: ResumeRecommendationProvider | None = None,
    direction_provider=None,
) -> None:
    from app.models import ResumeDirectionAnalysisRun, ResumeCopilotMessage
    from app.services.resume_copilot.direction_analysis import (
        DirectionAnalysisProvider,
        generate_direction_analysis,
    )
    from app.services.resume_copilot.chat import initialize_chat

    db = session_factory()
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        db.close()
        raise ValueError(f'Resume copilot session {session_id} not found')

    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if not recommendation_run:
        recommendation_run = ResumeRecommendationRun(session_id=session_id)
        db.add(recommendation_run)

    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run:
        direction_run = ResumeDirectionAnalysisRun(session_id=session_id)
        db.add(direction_run)

    recommendation_run.status = 'running'
    recommendation_run.error_message = ''
    recommendation_run.used_ai = 0
    recommendation_run.fallback_reason = ''
    recommendation_run.agent_trace_json = '[]'
    recommendation_run.recommendations_json = '[]'
    direction_run.status = 'running'
    direction_run.error_message = ''
    direction_run.directions_json = '[]'
    session.status = 'generating_recommendations'
    session.recommendation_status = 'running'
    session.feedback_status = 'running'
    session.error_message = ''
    db.commit()
    agent_trace: list[ResumeAgentTraceItem] = []

    try:
        confirmed_profile = db.query(ResumeConfirmedProfile).filter(
            ResumeConfirmedProfile.session_id == session_id
        ).first()
        if not confirmed_profile:
            raise ValueError('CONFIRMED_PROFILE_REQUIRED')
        preference_profile = db.query(ResumePreferenceProfile).filter(
            ResumePreferenceProfile.session_id == session_id
        ).first()
        profile = ResumeProfilePayload.model_validate(
            json.loads(str(confirmed_profile.profile_json or '{}'))
        )
        preferences = None
        if preference_profile:
            preferences = ResumePreferencePayload.model_validate(
                json.loads(str(preference_profile.preferences_json or '{}'))
            )
            preferences.all_skipped = bool(preference_profile.all_skipped)

        # ── Step 1: Rule scoring ────────────────────────────────────────────────
        _append_agent_trace(db, session_id, agent_trace, 'Agent',
                            '规则引擎召回中，正在计算基础匹配分…', 'running')
        candidates, used_ai, fallback_reason = recommend_jobs_for_profile(
            db, profile, preferences,
            limit=RESUME_RECOMMENDATION_LIMIT,
            ai_provider=recommendation_provider,
            ai_top_n=0,
        )
        _append_agent_trace(db, session_id, agent_trace, 'Agent',
                            f'规则初筛完成，召回 {len(candidates)} 个候选岗位。', 'completed')

        # Dual-track: persist preliminary results immediately
        recommendation_run.recommendations_json = json.dumps(
            [item.model_dump() for item in candidates[:15]]
        )
        session.recommendation_status = 'running'
        db.commit()

        # ── Step 2: Direction analysis ──────────────────────────────────────────
        direction_results = generate_direction_analysis(
            profile, preferences, provider=direction_provider
        )
        direction_run = db.query(ResumeDirectionAnalysisRun).filter(
            ResumeDirectionAnalysisRun.session_id == session_id
        ).first()
        direction_run.status = 'completed'
        direction_run.directions_json = json.dumps(
            [r.model_dump() for r in direction_results]
        )
        db.commit()

        # ── Step 3: ReAct agent ─────────────────────────────────────────────────
        def agent_trace_recorder(**kwargs: object) -> None:
            _append_agent_trace(db, session_id, agent_trace, **kwargs)

        react_agent = ReActAgent(
            tools=build_tools(db, profile, preferences, candidates),
            budget=AgentBudget(),
        )
        recommendations = react_agent.run(
            profile=profile,
            preferences=preferences,
            candidates=candidates,
            trace_recorder=agent_trace_recorder,
            direction_results=direction_results,
        )
        recommendation_run = db.query(ResumeRecommendationRun).filter(
            ResumeRecommendationRun.session_id == session_id
        ).first()
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        recommendation_run.status = 'completed'
        recommendation_run.error_message = ''
        recommendation_run.used_ai = 1
        recommendation_run.fallback_reason = fallback_reason
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace)
        recommendation_run.recommendations_json = json.dumps(
            [item.model_dump() for item in recommendations]
        )
        session.recommendation_status = 'completed'
        session.status = 'generating_recommendations'
        db.commit()

        # ── Step 4: Initialize chat from direction analysis ─────────────────────
        initialize_chat(session_id, direction_results, recommendations, db)
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        session.feedback_status = 'completed'
        session.status = 'completed'
        session.error_message = ''
        db.commit()

    except Exception as exc:
        db.rollback()
        recommendation_run = db.query(ResumeRecommendationRun).filter(
            ResumeRecommendationRun.session_id == session_id
        ).first()
        direction_run = db.query(ResumeDirectionAnalysisRun).filter(
            ResumeDirectionAnalysisRun.session_id == session_id
        ).first()
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        recommendation_run.status = 'failed'
        recommendation_run.error_message = str(exc)
        recommendation_run.used_ai = 0
        recommendation_run.fallback_reason = ''
        recommendation_run.agent_trace_json = serialize_agent_trace(
            agent_trace + [ResumeAgentTraceItem(agent='Agent', message=str(exc), status='failed')]
        )
        recommendation_run.recommendations_json = '[]'
        if direction_run:
            direction_run.status = 'failed'
            direction_run.error_message = str(exc)
        session.status = 'failed'
        session.error_message = str(exc)
        session.recommendation_status = 'failed'
        session.feedback_status = 'failed'
        db.commit()
    finally:
        db.close()
```

Also remove the imports of `ResumeFeedbackRun`, `generate_feedback_for_profile`, and `ResumeFeedbackProvider` from the top of `workflow.py` (they are no longer used). Keep:

```python
import json

from app import config
from app.database import SessionLocal
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeRecommendationRun,
    ResumeParsedProfile,
    ResumePreferenceProfile,
)
from app.schemas_resume_copilot import ResumeAgentTraceItem, ResumePreferencePayload, ResumeProfilePayload
from app.services.resume_copilot.quick_enrichment import serialize_agent_trace
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.core import ReActAgent
from app.services.resume_copilot.agent.tools import build_tools
from app.services.resume_copilot.recommendation import ResumeRecommendationProvider, recommend_jobs_for_profile

RESUME_RECOMMENDATION_LIMIT = 100
_AGENT_TRACE_CAP = 50
```

- [ ] **Step 4: Fix `backend/tests/test_resume_feedback_service.py`**

The tests in this file that test `ResumeFeedbackRun` behavior no longer apply. Update those tests to avoid breakage:

- Remove `test_generate_workflow_persists_recommendations_and_feedback` (replaced by test_direction_workflow.py)
- Remove `test_generate_workflow_keeps_recommendations_when_feedback_generation_fails`
- Remove `test_generate_workflow_feedback_uses_preferences_and_top_recommendations`
- Keep `test_generate_workflow_falls_back_to_rule_only_when_ai_rerank_fails` but update it since `feedback_provider` is no longer accepted by `run_resume_generate_workflow`

Replace the entire file with:

```python
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Job,
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import ResumePreferencePayload, ResumeProfilePayload, ResumeSkillsPayload
from app.services.resume_copilot.workflow import run_resume_generate_workflow


def _build_session_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _build_profile(**overrides):
    payload = {
        'basic_info': {'name': 'Jane Doe', 'email': 'jane@example.com'},
        'education': [],
        'internships': [],
        'projects': [],
        'skills': ResumeSkillsPayload(technical=['Python', 'SQL'], tools=['Git'], languages=[]),
        'languages': ['English'],
        'awards': [],
        'candidate_summary': 'Backend-focused builder',
        'inferred_roles': ['Backend Engineer'],
        'inferred_tracks': ['Internet'],
    }
    payload.update(overrides)
    return ResumeProfilePayload.model_validate(payload)


def _build_preferences(**overrides):
    payload = {
        'preferred_tracks': ['Internet'],
        'preferred_locations': ['Shanghai'],
        'preferred_roles': ['Backend Engineer'],
        'preferred_company_types': ['Internet'],
        'accept_relocation': False,
        'accept_internship': False,
        'campus_only': False,
        'social_ok': False,
        'preference_notes': '',
        'all_skipped': False,
    }
    payload.update(overrides)
    return ResumePreferencePayload.model_validate(payload)


def _seed_session(db: Session) -> int:
    session = ResumeCopilotSession(
        file_name='resume.pdf',
        status='awaiting_user_confirmation',
        recommendation_status='running',
        feedback_status='running',
        extracted_text='Jane Doe',
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    profile = _build_profile()
    preferences = _build_preferences()
    db.add(ResumeConfirmedProfile(
        session_id=session.id,
        profile_json=json.dumps(profile.model_dump()),
    ))
    db.add(ResumePreferenceProfile(
        session_id=session.id,
        preferences_json=json.dumps(preferences.model_dump()),
        all_skipped=0,
    ))
    db.commit()
    return int(session.id)


def _add_job(db: Session, **overrides) -> Job:
    job = Job(
        job_id=overrides.get('job_id', 'job-1'),
        company=overrides.get('company', 'Example Co'),
        company_type_industry=overrides.get('company_type_industry', 'Internet'),
        department=overrides.get('department', 'Engineering'),
        job_title=overrides.get('job_title', 'Backend Engineer'),
        location=overrides.get('location', 'Shanghai'),
        major_req=overrides.get('major_req', 'Computer Science'),
        job_req=overrides.get('job_req', 'Python SQL APIs'),
        job_duty=overrides.get('job_duty', 'Build backend services'),
        job_stage=overrides.get('job_stage', 'campus'),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class _PassthroughRecommendationProvider:
    def rerank_recommendations(self, profile, preferences, items):
        return items


class _StubDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        return [{'direction': d, 'tier': 1, 'tier_label': '强匹配',
                 'strengths': [], 'gaps': [], 'transferable_from': []}
                for d in directions]


def test_generate_workflow_falls_back_to_rule_only_when_ai_rerank_fails():
    class _FailingRecommendationProvider:
        def rerank_recommendations(self, profile, preferences, items):
            raise RuntimeError('rerank provider unavailable')

    session_factory = _build_session_factory()
    db = session_factory()
    try:
        session_id = _seed_session(db)
        _add_job(db, job_id='job-strong', company='Alpha',
                 job_title='Backend Engineer', job_req='Python SQL APIs')
        _add_job(db, job_id='job-weak', company='Beta',
                 job_title='Analyst', job_req='Excel reporting')
    finally:
        db.close()

    run_resume_generate_workflow(
        session_id,
        session_factory=session_factory,
        recommendation_provider=_FailingRecommendationProvider(),
        direction_provider=_StubDirectionProvider(),
    )

    db = session_factory()
    try:
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        recommendation_run = db.query(ResumeRecommendationRun).filter(
            ResumeRecommendationRun.session_id == session_id
        ).first()
        assert session is not None
        assert recommendation_run is not None
        assert session.status == 'completed'
        assert session.recommendation_status == 'completed'
        assert recommendation_run.status == 'completed'
        assert recommendation_run.used_ai == 1
        recommendations = json.loads(recommendation_run.recommendations_json)
        assert all(item['used_ai'] is False for item in recommendations)
    finally:
        db.close()
```

- [ ] **Step 5: Run all backend tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py tests/test_direction_workflow.py tests/test_resume_feedback_service.py -x -q
```

Expected: all pass (total ~16 tests)

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/resume_copilot/workflow.py tests/test_direction_workflow.py tests/test_resume_feedback_service.py
git commit -m "feat(workflow): replace feedback with direction analysis + initialize_chat"
```

---

## Task 6: Router — replace ResumeFeedbackRun + add direction-analysis endpoint

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`

- [ ] **Step 1: Update imports in router**

At the top of `backend/app/routers/resume_copilot.py`, update the imports:

Remove `ResumeFeedbackRun` from the `app.models` import and add the new models:

```python
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeDirectionAnalysisRun,
    ResumeCopilotMessage,
    ResumeParsedProfile,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
```

Update the `app.schemas_resume_copilot` import to add new types and remove old feedback types:

```python
from app.schemas_resume_copilot import (
    ApplyRewriteIn,
    ApplyRewriteOut,
    ChatMessageIn,
    DirectionTierResult,
    ResumeAgentTraceItem,
    ResumeConfirmedProfileIn,
    ResumeConfirmedProfileOut,
    ResumeCopilotMessageOut,
    ResumeCopilotRenameIn,
    ResumeCopilotSessionCreatedOut,
    ResumeCopilotSessionListItem,
    ResumeCopilotSessionOut,
    ResumeGenerateOut,
    ResumePreferenceIn,
    ResumePreferenceOut,
    ResumeProfilePayload,
    ResumeParsedProfileOut,
    ResumePreferencePayload,
    ResumeRecommendationItem,
    ResumeRecommendationResultOut,
)
```

- [ ] **Step 2: Update `ResumeCopilotSessionOut` schema and `_build_session_out`**

In `backend/app/schemas_resume_copilot.py`, add `has_direction_analysis: bool = False` to `ResumeCopilotSessionOut`:

```python
class ResumeCopilotSessionOut(BaseModel):
    id: int
    file_name: str
    name: str = ''
    status: str
    error_message: str
    recommendation_status: str
    feedback_status: str
    has_parsed_profile: bool
    has_confirmed_profile: bool
    has_preferences: bool
    has_recommendations: bool
    has_feedback: bool
    has_direction_analysis: bool = False   # new
    created_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {'from_attributes': True}
```

- [ ] **Step 3: Update `_get_session_eager` to joinedload new models**

Replace `_get_session_eager` in the router:

```python
def _get_session_eager(db: Session, session_id: int) -> ResumeCopilotSession | None:
    return (
        db.query(ResumeCopilotSession)
        .options(
            joinedload(ResumeCopilotSession.parsed_profile),
            joinedload(ResumeCopilotSession.confirmed_profile),
            joinedload(ResumeCopilotSession.preference_profile),
            joinedload(ResumeCopilotSession.recommendation_run),
            joinedload(ResumeCopilotSession.feedback_run),
            joinedload(ResumeCopilotSession.direction_analysis_run),
        )
        .filter(ResumeCopilotSession.id == session_id)
        .first()
    )
```

- [ ] **Step 4: Update `_build_session_out` to include `has_direction_analysis`**

Replace `_build_session_out`:

```python
def _build_session_out(session: ResumeCopilotSession) -> ResumeCopilotSessionOut:
    return ResumeCopilotSessionOut(
        id=int(getattr(session, 'id')),
        file_name=str(getattr(session, 'file_name', '') or ''),
        name=str(getattr(session, 'name', '') or ''),
        status=str(getattr(session, 'status', '') or ''),
        error_message=str(getattr(session, 'error_message', '') or ''),
        recommendation_status=str(getattr(session, 'recommendation_status', '') or ''),
        feedback_status=str(getattr(session, 'feedback_status', '') or ''),
        has_parsed_profile=session.parsed_profile is not None,
        has_confirmed_profile=session.confirmed_profile is not None,
        has_preferences=session.preference_profile is not None,
        has_recommendations=session.recommendation_run is not None,
        has_feedback=session.feedback_run is not None,
        has_direction_analysis=session.direction_analysis_run is not None,
        created_at=getattr(session, 'created_at', None),
        updated_at=getattr(session, 'updated_at', None),
        finished_at=getattr(session, 'finished_at', None),
    )
```

- [ ] **Step 5: Replace ResumeFeedbackRun logic in `generate_resume_recommendations`**

Replace the `generate_resume_recommendations` router function body to use `ResumeDirectionAnalysisRun` instead of `ResumeFeedbackRun`:

```python
@router.post(
    '/sessions/{session_id}/generate',
    response_model=ResumeGenerateOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_resume_recommendations(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    confirmed_profile = db.query(ResumeConfirmedProfile).filter(
        ResumeConfirmedProfile.session_id == session_id
    ).first()
    if not confirmed_profile:
        raise HTTPException(status_code=409, detail='CONFIRMED_PROFILE_REQUIRED')

    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if not recommendation_run:
        recommendation_run = ResumeRecommendationRun(session_id=session_id)
        db.add(recommendation_run)

    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run:
        direction_run = ResumeDirectionAnalysisRun(session_id=session_id)
        db.add(direction_run)

    recommendation_run.status = 'running'
    recommendation_run.error_message = ''
    recommendation_run.used_ai = 0
    recommendation_run.fallback_reason = ''
    recommendation_run.recommendations_json = '[]'
    direction_run.status = 'running'
    direction_run.error_message = ''
    direction_run.directions_json = '[]'
    session.status = 'generating_recommendations'
    session.recommendation_status = 'running'
    session.feedback_status = 'running'
    session.error_message = ''
    db.commit()
    background_tasks.add_task(run_resume_generate_workflow, int(session_id))

    return ResumeGenerateOut(session_id=session_id, status='running')
```

- [ ] **Step 6: Add `GET /sessions/{id}/direction-analysis` endpoint**

Add after the existing `get_resume_copilot_recommendations` function:

```python
@router.get('/sessions/{session_id}/direction-analysis', response_model=list[DirectionTierResult])
def get_direction_analysis(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run or direction_run.status != 'completed':
        return []
    directions_json = getattr(direction_run, 'directions_json', '[]') or '[]'
    return [
        DirectionTierResult.model_validate(item)
        for item in json.loads(str(directions_json))
    ]
```

- [ ] **Step 7: Remove the old `GET /sessions/{id}/feedback` endpoint and its imports**

Delete the `get_resume_copilot_feedback` function entirely (it references `ResumeFeedbackRun`). Also remove `ResumeFeedbackDiagnosticItem` and `ResumeFeedbackResultOut` from the schemas import in the router.

- [ ] **Step 8: Run all backend tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py tests/test_direction_workflow.py tests/test_resume_feedback_service.py -x -q
```

Expected: all pass

- [ ] **Step 9: Commit**

```bash
cd backend && git add app/routers/resume_copilot.py app/schemas_resume_copilot.py
git commit -m "feat(router): replace feedback run with direction analysis; add direction-analysis endpoint"
```

---

## Task 7: chat.py — initialize_chat, generate_chat_turn, apply_rewrite

**Files:**
- Create: `backend/app/services/resume_copilot/chat.py`
- Create: `backend/tests/test_chat_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_chat_service.py`:

```python
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotMessage,
    ResumeCopilotSession,
)
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumeProfilePayload,
    ResumeRecommendationItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.chat import apply_rewrite, generate_chat_turn, initialize_chat


def _make_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed(db: Session, profile_dict: dict | None = None) -> int:
    session = ResumeCopilotSession(
        file_name='cv.pdf',
        status='completed',
        recommendation_status='completed',
        feedback_status='running',
        extracted_text='Jane',
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    if profile_dict is None:
        profile_dict = {
            'basic_info': {'name': 'Jane'},
            'education': [],
            'internships': [
                {
                    'company': 'Acme',
                    'role': 'Data Analyst',
                    'start_date': '2025-06',
                    'end_date': '2025-09',
                    'bullets': ['分析数据', '完成报告'],
                }
            ],
            'projects': [],
            'skills': {'technical': ['Python'], 'tools': [], 'languages': []},
            'languages': [],
            'awards': [],
            'candidate_summary': '',
            'inferred_roles': [],
            'inferred_tracks': [],
        }
    db.add(ResumeConfirmedProfile(
        session_id=session.id,
        profile_json=json.dumps(profile_dict),
    ))
    db.commit()
    return int(session.id)


def _make_direction_results():
    return [
        DirectionTierResult(
            direction='Backend Engineer', tier=1, tier_label='强匹配',
            strengths=['Python'], gaps=[], transferable_from=[],
        )
    ]


def _make_recs():
    return [
        ResumeRecommendationItem(
            job_id='job-1', company='Acme', job_title='后端', location='上海',
            objective_score=50, preference_score=30, base_job_score=40,
            company_priority_score=10, rule_score=130, final_score=130,
        )
    ]


def test_initialize_chat_creates_system_message():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    db = factory()
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).all()
    assert len(msgs) == 1
    assert msgs[0].role == 'system'
    assert len(msgs[0].content) > 10
    db.close()


def test_initialize_chat_idempotent_on_second_call():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    db = factory()
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    # Second call must not duplicate the system message
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id,
        ResumeCopilotMessage.role == 'system',
    ).all()
    assert len(msgs) == 1
    db.close()


class _StubChatLLMProvider:
    def generate_turn(self, messages_payload):
        return {
            'content': '这是建议',
            'rewrite_options': [
                {
                    'option_id': 'A',
                    'label': '方案A',
                    'section': 'internships',
                    'field_path': 'internships.0.bullets.0',
                    'original': '分析数据',
                    'improved': '独立完成数据分析，覆盖 100 个样本',
                    'rationale': '更具体',
                }
            ],
        }


def test_generate_chat_turn_stores_user_and_assistant_messages():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    db = factory()
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    db.close()

    db = factory()
    result = generate_chat_turn(
        session_id, '我做过估值模型', db,
        provider=_StubChatLLMProvider(),
    )
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).all()
    assert len(msgs) == 3  # system + user + assistant
    assert result.role == 'assistant'
    assert result.content == '这是建议'
    assert result.rewrite_options is not None
    assert result.rewrite_options[0].option_id == 'A'
    db.close()


def test_apply_rewrite_patches_profile_field():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    # Set up an assistant message with a rewrite option
    db = factory()
    option_json = json.dumps([{
        'option_id': 'A',
        'label': '方案A',
        'section': 'internships',
        'field_path': 'internships.0.bullets.0',
        'original': '分析数据',
        'improved': '独立完成数据分析，覆盖 100 个样本',
        'rationale': '更具体',
    }])
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content='建议',
        rewrite_options_json=option_json,
        applied_option_id=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    message_id = int(msg.id)
    db.close()

    db = factory()
    updated_profile = apply_rewrite(session_id, message_id, 'A', db)
    db.close()

    db = factory()
    confirmed = db.query(ResumeConfirmedProfile).filter(
        ResumeConfirmedProfile.session_id == session_id
    ).first()
    profile_dict = json.loads(confirmed.profile_json)
    assert profile_dict['internships'][0]['bullets'][0] == '独立完成数据分析，覆盖 100 个样本'
    msg_after = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.id == message_id
    ).first()
    assert msg_after.applied_option_id == 'A'
    db.close()


def test_apply_rewrite_raises_on_invalid_field_path():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    option_json = json.dumps([{
        'option_id': 'A',
        'label': '方案A',
        'section': 'internships',
        'field_path': 'internships.99.bullets.0',  # index 99 doesn't exist
        'original': 'x',
        'improved': 'y',
        'rationale': 'z',
    }])
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content='建议',
        rewrite_options_json=option_json,
        applied_option_id=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    message_id = int(msg.id)

    import pytest
    with pytest.raises(ValueError):
        apply_rewrite(session_id, message_id, 'A', db)
    db.close()
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_chat_service.py::test_initialize_chat_creates_system_message -x -q
```

Expected: `ImportError` — module doesn't exist.

- [ ] **Step 3: Create `backend/app/services/resume_copilot/chat.py`**

```python
import json
from typing import Any, Protocol
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.models import ResumeConfirmedProfile, ResumeCopilotMessage
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumeProfilePayload,
    ResumeRecommendationItem,
    ResumeCopilotMessageOut,
    RewriteOption,
)
from app.services.resume_copilot.llm import build_resume_llm_client

_MAX_HISTORY = 10

_CHAT_SYSTEM_PROMPT = """\
你是一个简历优化助手。根据用户的真实经历，帮助他们改写简历描述，使其更符合目标岗位要求。

规则：
1. 每次回复必须包含 2 个具体改写选项（方案A、方案B）
2. 每个选项必须指向 field_path（dot-notation，如 internships.0.bullets.2）
3. 不要编造经历；如信息不足先追问
4. 返回严格的 JSON 格式

返回格式：
{"content": "面向用户的回复文字（中文）", "rewrite_options": [{"option_id": "A", "label": "方案A — 突出XX", "section": "internships", "field_path": "internships.0.bullets.2", "original": "原始文字", "improved": "改写后文字", "rationale": "一句话理由"}]}
"""


class ChatLLMProvider(Protocol):
    def generate_turn(self, messages_payload: list[dict]) -> dict[str, Any]: ...


class OpenAICompatibleChatLLMProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def generate_turn(self, messages_payload: list[dict]) -> dict[str, Any]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': messages_payload,
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        return json.loads(content)


def _build_first_message_content(
    direction_results: list[DirectionTierResult],
    recommendations: list[ResumeRecommendationItem],
) -> str:
    lines = ['✨ 方向分析完成！以下是你各目标方向的匹配评估：\n']
    for r in direction_results:
        emoji = '🟢' if r.tier == 1 else '🟡' if r.tier == 2 else '🔴'
        lines.append(f'{emoji} **{r.direction}** — {r.tier_label}（第{r.tier}层）')
        if r.strengths:
            lines.append(f'  优势：{"; ".join(r.strengths[:2])}')
        if r.tier == 2 and r.transferable_from:
            lines.append(f'  可迁移：{r.transferable_from[0]}')
        if r.tier == 3 and r.gaps:
            lines.append(f'  差距：{"; ".join(r.gaps[:2])}')
    top = recommendations[:3]
    if top:
        lines.append('\n🎯 已推荐以下高匹配岗位：')
        for rec in top:
            lines.append(f'  · {rec.company} · {rec.job_title}')
    lines.append('\n有什么想深入优化的方向吗？告诉我你的真实经历，我帮你改写简历描述。')
    return '\n'.join(lines)


def initialize_chat(
    session_id: int,
    direction_results: list[DirectionTierResult],
    recommendations: list[ResumeRecommendationItem],
    db: Session,
) -> None:
    existing = (
        db.query(ResumeCopilotMessage)
        .filter(
            ResumeCopilotMessage.session_id == session_id,
            ResumeCopilotMessage.role == 'system',
        )
        .first()
    )
    if existing:
        return
    content = _build_first_message_content(direction_results, recommendations)
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='system',
        content=content,
        rewrite_options_json=None,
        applied_option_id=None,
    )
    db.add(msg)
    db.commit()


def _load_profile_dict(session_id: int, db: Session) -> dict:
    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    if not confirmed:
        return {}
    return json.loads(str(confirmed.profile_json or '{}'))


def generate_chat_turn(
    session_id: int,
    user_content: str,
    db: Session,
    provider: ChatLLMProvider | None = None,
) -> ResumeCopilotMessageOut:
    _provider = provider or OpenAICompatibleChatLLMProvider()

    history = (
        db.query(ResumeCopilotMessage)
        .filter(ResumeCopilotMessage.session_id == session_id)
        .order_by(ResumeCopilotMessage.created_at)
        .limit(_MAX_HISTORY)
        .all()
    )

    profile_dict = _load_profile_dict(session_id, db)

    messages_payload: list[dict] = [
        {
            'role': 'system',
            'content': _CHAT_SYSTEM_PROMPT + '\n\n候选人简历摘要：\n' + json.dumps(
                {
                    'internships': profile_dict.get('internships', []),
                    'projects': profile_dict.get('projects', []),
                    'candidate_summary': profile_dict.get('candidate_summary', ''),
                },
                ensure_ascii=False,
            ),
        }
    ]
    for msg in history:
        messages_payload.append({
            'role': 'user' if msg.role == 'user' else 'assistant',
            'content': msg.content,
        })
    messages_payload.append({'role': 'user', 'content': user_content})

    user_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='user',
        content=user_content,
        rewrite_options_json=None,
        applied_option_id=None,
    )
    db.add(user_msg)
    db.commit()

    raw = _provider.generate_turn(messages_payload)
    content = str(raw.get('content', ''))
    raw_options = raw.get('rewrite_options') or []
    options: list[RewriteOption] = []
    for item in raw_options:
        try:
            options.append(RewriteOption.model_validate(item))
        except Exception:
            pass

    assistant_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content=content,
        rewrite_options_json=json.dumps([o.model_dump() for o in options]) if options else None,
        applied_option_id=None,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ResumeCopilotMessageOut(
        id=int(assistant_msg.id),
        role='assistant',
        content=content,
        rewrite_options=options or None,
        applied_option_id=None,
        created_at=assistant_msg.created_at,
    )


def _traverse_and_set(data: dict, path: str, value: str) -> None:
    parts = path.split('.')
    current: Any = data
    for part in parts[:-1]:
        try:
            if isinstance(current, list):
                current = current[int(part)]
            else:
                current = current[part]
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f'field_path traversal failed at "{part}": {exc}') from exc
    last = parts[-1]
    try:
        if isinstance(current, list):
            current[int(last)] = value
        else:
            current[last] = value
    except (IndexError, ValueError, KeyError) as exc:
        raise ValueError(f'field_path assignment failed at "{last}": {exc}') from exc


def apply_rewrite(
    session_id: int,
    message_id: int,
    option_id: str,
    db: Session,
) -> ResumeProfilePayload:
    msg = (
        db.query(ResumeCopilotMessage)
        .filter(
            ResumeCopilotMessage.id == message_id,
            ResumeCopilotMessage.session_id == session_id,
        )
        .first()
    )
    if not msg:
        raise ValueError(f'Message {message_id} not found for session {session_id}')

    options_raw = json.loads(str(msg.rewrite_options_json or '[]'))
    option = next((o for o in options_raw if o.get('option_id') == option_id), None)
    if not option:
        raise ValueError(f'Option {option_id} not found in message {message_id}')

    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    if not confirmed:
        raise ValueError(f'Confirmed profile for session {session_id} not found')

    profile_dict = json.loads(str(confirmed.profile_json or '{}'))
    _traverse_and_set(profile_dict, option['field_path'], option['improved'])

    confirmed.profile_json = json.dumps(profile_dict)
    msg.applied_option_id = option_id
    db.commit()

    return ResumeProfilePayload.model_validate(profile_dict)
```

Note: add `from typing import Any` at the top if not already there.

- [ ] **Step 4: Run chat service tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_chat_service.py -x -q
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/resume_copilot/chat.py tests/test_chat_service.py
git commit -m "feat(chat): add initialize_chat, generate_chat_turn, apply_rewrite services"
```

---

## Task 8: Chat Router Endpoints + Workflow initialize_chat Integration

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`

- [ ] **Step 1: Add GET /chat endpoint**

Add after `get_direction_analysis` in the router:

```python
@router.get('/sessions/{session_id}/chat', response_model=list[ResumeCopilotMessageOut])
def get_chat_messages(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
    msgs = (
        db.query(ResumeCopilotMessage)
        .filter(ResumeCopilotMessage.session_id == session_id)
        .order_by(ResumeCopilotMessage.created_at)
        .all()
    )
    return [
        ResumeCopilotMessageOut(
            id=int(msg.id),
            role=str(msg.role),
            content=str(msg.content or ''),
            rewrite_options=(
                [RewriteOption.model_validate(o)
                 for o in json.loads(str(msg.rewrite_options_json))]
                if msg.rewrite_options_json else None
            ),
            applied_option_id=msg.applied_option_id,
            created_at=msg.created_at,
        )
        for msg in msgs
    ]
```

Add `RewriteOption` to the schemas import at the top of the router.

- [ ] **Step 2: Add POST /chat endpoint**

```python
@router.post('/sessions/{session_id}/chat', response_model=ResumeCopilotMessageOut)
def post_chat_message(
    session_id: int,
    payload: ChatMessageIn,
    db: Session = Depends(get_db),
):
    from app.services.resume_copilot.chat import generate_chat_turn

    session = _get_session_or_404(db, session_id)
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run or direction_run.status != 'completed':
        raise HTTPException(status_code=409, detail='DIRECTION_ANALYSIS_NOT_READY')

    try:
        return generate_chat_turn(session_id, payload.content, db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
```

- [ ] **Step 3: Add POST /chat/apply-rewrite endpoint**

```python
@router.post('/sessions/{session_id}/chat/apply-rewrite', response_model=ApplyRewriteOut)
def post_apply_rewrite(
    session_id: int,
    payload: ApplyRewriteIn,
    db: Session = Depends(get_db),
):
    from app.services.resume_copilot.chat import apply_rewrite

    _get_session_or_404(db, session_id)
    try:
        updated_profile = apply_rewrite(
            session_id, payload.message_id, payload.option_id, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ApplyRewriteOut(profile=updated_profile, applied=True)
```

- [ ] **Step 4: Run all backend tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py tests/test_direction_workflow.py tests/test_resume_feedback_service.py tests/test_chat_service.py -x -q
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/resume_copilot.py
git commit -m "feat(router): add GET/POST /chat and POST /chat/apply-rewrite endpoints"
```

---

## Task 9: Feature A Frontend — Direction Tabs + Tier Info Bars

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/types.ts`
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`
- Modify: `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx`

- [ ] **Step 1: Add new types to `types.ts`**

Add at the end of `resume-copilot-web/components/resume-copilot/types.ts`:

```typescript
export interface DirectionTierResult {
  direction: string;
  tier: 1 | 2 | 3;
  tier_label: string;
  strengths: string[];
  gaps: string[];
  transferable_from: string[];
}

export interface RewriteOption {
  option_id: string;
  label: string;
  section: string;
  field_path: string;
  original: string;
  improved: string;
  rationale: string;
}

export interface CopilotMessage {
  id: number;
  role: 'system' | 'user' | 'assistant';
  content: string;
  rewrite_options: RewriteOption[] | null;
  applied_option_id: string | null;
  created_at: string | null;
}

export interface ApplyRewriteOut {
  profile: ResumeProfilePayload;
  applied: boolean;
}
```

Also add `target_direction: string;` to `ResumeRecommendationItem` (after `risks: string[];`).

Also add `has_direction_analysis: boolean;` to `ResumeCopilotSession` (after `has_feedback: boolean;`).

- [ ] **Step 2: Add API functions to `api.ts`**

Add at the end of `resume-copilot-web/components/resume-copilot/api.ts`:

```typescript
import type { ApplyRewriteOut, CopilotMessage, DirectionTierResult } from './types';

export function getDirectionAnalysis(sessionId: number) {
  return requestJson<DirectionTierResult[]>(
    `/api/resume-copilot/sessions/${sessionId}/direction-analysis`
  );
}

export function getChatMessages(sessionId: number) {
  return requestJson<CopilotMessage[]>(
    `/api/resume-copilot/sessions/${sessionId}/chat`
  );
}

export function postChatMessage(sessionId: number, content: string) {
  return requestJson<CopilotMessage>(`/api/resume-copilot/sessions/${sessionId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function postApplyRewrite(sessionId: number, messageId: number, optionId: string) {
  return requestJson<ApplyRewriteOut>(
    `/api/resume-copilot/sessions/${sessionId}/chat/apply-rewrite`,
    {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, option_id: optionId }),
    }
  );
}
```

Note: move the `import type { ... }` block at the top of `api.ts` to include the new types.

- [ ] **Step 3: Add direction analysis state + fetch in `public-resume-copilot.tsx`**

Find the section where `recommendations` state is declared (search for `useRecommendations` or `recommendations` state). Add nearby:

```typescript
const [directionResults, setDirectionResults] = React.useState<DirectionTierResult[]>([]);
const [activeDirection, setActiveDirection] = React.useState<string | null>(null);
```

Find the `useEffect` or polling logic that fetches recommendations when `session.recommendation_status === 'completed'`. Add a parallel fetch for direction analysis when `session.feedback_status === 'completed'`:

```typescript
// When direction analysis completes, fetch results
React.useEffect(() => {
  if (!session || session.feedback_status !== 'completed') return;
  getDirectionAnalysis(session.id).then((results) => {
    setDirectionResults(results);
    if (results.length > 0 && !activeDirection) {
      // Default to highest-tier (lowest tier number) direction
      const sorted = [...results].sort((a, b) => a.tier - b.tier);
      setActiveDirection(sorted[0].direction);
    }
  }).catch(() => {/* ignore */});
}, [session?.feedback_status, session?.id]);
```

- [ ] **Step 4: Add direction tab bar + tier info bars to the recommendations section**

Find the recommendations render section (search for `recommendation` or job card rendering). Add a `DirectionTabBar` component just above the job list:

```typescript
// Direction tab bar — add near top of recommendations section render
{directionResults.length > 0 && (
  <div style={{ display: 'flex', gap: 6, padding: '10px 12px 0', flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
    {directionResults.map((dr) => {
      const isActive = activeDirection === dr.direction;
      const badgeColor = dr.tier === 1 ? { bg: '#dcfce7', color: '#166534' }
        : dr.tier === 2 ? { bg: '#fef9c3', color: '#854d0e' }
        : { bg: '#fee2e2', color: '#991b1b' };
      return (
        <button
          key={dr.direction}
          onClick={() => setActiveDirection(dr.direction)}
          style={{
            padding: '5px 12px 8px',
            borderRadius: '8px 8px 0 0',
            border: `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
            borderBottom: isActive ? '1px solid white' : '1px solid transparent',
            background: isActive ? 'white' : 'transparent',
            color: isActive ? 'var(--ink)' : 'var(--muted)',
            fontWeight: isActive ? 600 : 400,
            fontSize: 12,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            position: 'relative',
            bottom: -1,
          }}
        >
          {dr.direction}
          <span style={{ background: badgeColor.bg, color: badgeColor.color, borderRadius: 10, padding: '1px 7px', fontSize: 10, fontWeight: 600 }}>
            {dr.tier_label}
          </span>
        </button>
      );
    })}
  </div>
)}
```

Add tier 2/3 info bars inside the job list area, before the job cards:

```typescript
{/* Tier info bars */}
{activeDirectionResult?.tier === 2 && activeDirectionResult.transferable_from.length > 0 && (
  <div style={{ background: '#fefce8', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 12px', fontSize: 11.5, color: '#78350f', marginBottom: 8, lineHeight: 1.5 }}>
    💡 <strong>可迁移方向</strong> · {activeDirectionResult.transferable_from[0]}——右侧对话可帮你改写表达
  </div>
)}
{activeDirectionResult?.tier === 3 && (
  <div style={{ background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, padding: '8px 12px', fontSize: 11.5, color: '#881337', marginBottom: 8, lineHeight: 1.5 }}>
    ⚠️ <strong>差距较大</strong>{activeDirectionResult.gaps.length > 0 ? ` · 缺少：${activeDirectionResult.gaps.slice(0, 2).join('、')}` : ''}。当前为你推荐接受零经验的入门机会。
  </div>
)}
```

Add the helper variable before the return:
```typescript
const activeDirectionResult = directionResults.find(r => r.direction === activeDirection) ?? null;
```

Filter job cards by `target_direction` when a direction is selected:
```typescript
const filteredRecommendations = activeDirection
  ? recommendations.filter(r => !r.target_direction || r.target_direction === activeDirection)
  : recommendations;
```

Use `filteredRecommendations` instead of `recommendations` when rendering job cards.

- [ ] **Step 5: Run lint**

```bash
cd resume-copilot-web && npm run lint
```

Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
cd resume-copilot-web && git add components/resume-copilot/types.ts components/resume-copilot/api.ts components/resume-copilot/public-resume-copilot.tsx
git commit -m "feat(frontend): add direction tabs and tier info bars to recommendations"
```

---

## Task 10: Feature B Frontend — Replace Feedback Panel with Chat UI

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx`

- [ ] **Step 1: Add chat state and initialization effect**

Find existing feedback-related state (search for `feedback` or `ResumeFeedbackResult`). Replace or supplement with:

```typescript
const [chatMessages, setChatMessages] = React.useState<CopilotMessage[]>([]);
const [chatInput, setChatInput] = React.useState('');
const [chatSending, setChatSending] = React.useState(false);
const [chatError, setChatError] = React.useState<string | null>(null);
const [rewriteAppliedSection, setRewriteAppliedSection] = React.useState<string | null>(null);
const chatEndRef = React.useRef<HTMLDivElement>(null);
```

Add effect to load chat when `feedback_status` completes:

```typescript
React.useEffect(() => {
  if (!session || session.feedback_status !== 'completed') return;
  getChatMessages(session.id).then(setChatMessages).catch(() => {});
}, [session?.feedback_status, session?.id]);

// Auto-scroll to bottom on new messages
React.useEffect(() => {
  chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [chatMessages]);
```

- [ ] **Step 2: Add `sendChatMessage` handler**

```typescript
async function sendChatMessage() {
  if (!session || !chatInput.trim() || chatSending) return;
  const content = chatInput.trim();
  setChatInput('');
  setChatSending(true);
  setChatError(null);
  // Optimistically show user message
  const optimistic: CopilotMessage = {
    id: Date.now(),
    role: 'user',
    content,
    rewrite_options: null,
    applied_option_id: null,
    created_at: null,
  };
  setChatMessages(prev => [...prev, optimistic]);
  try {
    const reply = await postChatMessage(session.id, content);
    setChatMessages(prev => [...prev, reply]);
  } catch {
    setChatError('生成失败，请重试');
  } finally {
    setChatSending(false);
  }
}
```

- [ ] **Step 3: Add `applyRewriteOption` handler**

```typescript
async function applyRewriteOption(messageId: number, optionId: string, section: string) {
  if (!session) return;
  try {
    const result = await postApplyRewrite(session.id, messageId, optionId);
    // Update confirmed profile state
    setConfirmedProfile(result.profile);
    // Mark the option as applied in local state
    setChatMessages(prev =>
      prev.map(msg =>
        msg.id === messageId ? { ...msg, applied_option_id: optionId } : msg
      )
    );
    setRewriteAppliedSection(section);
  } catch {
    // show inline error if needed
  }
}
```

Note: `setConfirmedProfile` must already exist in the component's state. If the confirmed profile is stored differently, update accordingly.

- [ ] **Step 4: Replace the feedback panel JSX with the chat panel**

Find the existing feedback panel JSX (search for `ResumeFeedbackResult` or `feedback_run` references in the render, or find the panel that shows `diagnostics`). Replace its entire render block with:

```tsx
{/* ── Copilot Chat Panel ───────────────────────────────── */}
<div style={{
  background: 'white',
  border: '1px solid var(--border)',
  borderRadius: 14,
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  minHeight: 400,
}}>
  <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
    ✦ 简历优化助手
  </div>

  {/* Message list */}
  <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
    {session?.feedback_status === 'running' && chatMessages.length === 0 && (
      <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: 12, paddingTop: 24 }}>
        正在分析你的方向匹配…
      </div>
    )}
    {chatMessages.map((msg) => (
      <CopilotMessageBubble
        key={msg.id}
        msg={msg}
        onApply={(optionId, section) => applyRewriteOption(msg.id, optionId, section)}
      />
    ))}
    {chatSending && (
      <div style={{ fontSize: 12, color: 'var(--muted)' }}>正在生成建议…</div>
    )}
    {chatError && (
      <div style={{ fontSize: 12, color: '#dc2626' }}>{chatError}</div>
    )}
    <div ref={chatEndRef} />
  </div>

  {/* Input area */}
  <div style={{ borderTop: '1px solid var(--border)', padding: '8px 10px', display: 'flex', gap: 7, alignItems: 'flex-end' }}>
    <textarea
      value={chatInput}
      onChange={e => setChatInput(e.target.value)}
      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); } }}
      placeholder="补充真实经历，或让我调整方案…"
      rows={2}
      style={{
        flex: 1,
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: '7px 11px',
        fontSize: 12,
        color: 'var(--ink)',
        background: 'var(--soft)',
        outline: 'none',
        resize: 'none',
        lineHeight: 1.5,
        fontFamily: 'inherit',
      }}
    />
    <button
      onClick={sendChatMessage}
      disabled={chatSending || !chatInput.trim()}
      style={{
        background: 'var(--primary)',
        color: 'white',
        border: 'none',
        borderRadius: 9,
        padding: '7px 14px',
        fontSize: 12,
        fontWeight: 600,
        cursor: chatSending || !chatInput.trim() ? 'not-allowed' : 'pointer',
        opacity: chatSending || !chatInput.trim() ? 0.6 : 1,
        whiteSpace: 'nowrap',
      }}
    >
      发送
    </button>
  </div>
</div>
```

- [ ] **Step 5: Add `CopilotMessageBubble` component (inside the file, before the main component or as a local const)**

Add before the main component export:

```tsx
function CopilotMessageBubble({
  msg,
  onApply,
}: {
  msg: CopilotMessage;
  onApply: (optionId: string, section: string) => void;
}) {
  const [expandedOption, setExpandedOption] = React.useState<string | null>(null);

  if (msg.role === 'system') {
    return (
      <div style={{ background: 'var(--soft)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 12px', fontSize: 12, color: 'var(--muted)', lineHeight: 1.6 }}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)', marginBottom: 5 }}>分析完成</div>
        <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
      </div>
    );
  }

  if (msg.role === 'user') {
    return (
      <div style={{ alignSelf: 'flex-end', background: 'var(--primary)', color: 'white', borderRadius: '12px 12px 2px 12px', padding: '8px 12px', fontSize: 12, maxWidth: '85%', lineHeight: 1.5 }}>
        {msg.content}
      </div>
    );
  }

  // assistant
  return (
    <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6 }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)', marginBottom: 6 }}>助手</div>
      <div style={{ marginBottom: msg.rewrite_options ? 8 : 0 }}>{msg.content}</div>
      {msg.rewrite_options && msg.rewrite_options.length > 0 && (
        <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', background: 'white' }}>
          {msg.rewrite_options.map((opt) => {
            const isExpanded = expandedOption === opt.option_id;
            const isApplied = msg.applied_option_id === opt.option_id;
            return (
              <div key={opt.option_id} style={{ borderBottom: '1px solid var(--border)' }}>
                <div
                  onClick={() => setExpandedOption(isExpanded ? null : opt.option_id)}
                  style={{ padding: '9px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                >
                  <div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>{opt.option_id === 'A' ? '方案 A' : opt.option_id === 'B' ? '方案 B' : '方案 C'}</span>
                    <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 8 }}>{opt.label.replace(/^方案[ABC]\s*[—–-]\s*/, '')}</span>
                  </div>
                  {isApplied
                    ? <span style={{ background: '#dcfce7', color: '#166534', borderRadius: 7, padding: '2px 8px', fontSize: 10, fontWeight: 600 }}>✓ 已应用</span>
                    : <span style={{ color: 'var(--muted)', fontSize: 11 }}>{isExpanded ? '▾' : '▸'}</span>
                  }
                </div>
                {isExpanded && (
                  <div style={{ padding: '0 12px 12px', borderTop: '1px solid var(--soft)' }}>
                    <div style={{ fontSize: 11, color: '#a0aec0', textDecoration: 'line-through', margin: '6px 0 3px', lineHeight: 1.5 }}>{opt.original}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--ink)', lineHeight: 1.6, marginBottom: 8 }}>{opt.improved}</div>
                    {!isApplied && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onApply(opt.option_id, opt.section); }}
                        style={{ background: 'var(--primary)', color: 'white', border: 'none', borderRadius: 7, padding: '5px 14px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
                      >
                        一键应用
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Add update banner above recommendations**

Find the area above the recommendations section in the render. Add:

```tsx
{rewriteAppliedSection && (
  <div style={{
    background: 'var(--soft-blue)',
    border: '1px solid var(--border-strong)',
    borderRadius: 8,
    padding: '8px 12px',
    fontSize: 11.5,
    color: 'var(--ink)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  }}>
    <span>✏️ 简历已更新（{rewriteAppliedSection}）</span>
    <button
      onClick={() => {
        if (!session) return;
        setRewriteAppliedSection(null);
        postResumeCopilotGenerate(session.id);
      }}
      style={{ background: 'var(--primary)', color: 'white', border: 'none', borderRadius: 7, padding: '4px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
    >
      重新生成推荐 →
    </button>
  </div>
)}
```

- [ ] **Step 7: Remove feedback-related dead code**

Search for `getResumeCopilotFeedback`, `ResumeFeedbackResult`, `feedbackResult`, `diagnostics`, `rewrite_examples` in `public-resume-copilot.tsx` and delete the now-unused state variables, fetch calls, and render blocks. Run lint after to catch missed references.

- [ ] **Step 8: Run lint**

```bash
cd resume-copilot-web && npm run lint
```

Expected: 0 errors

- [ ] **Step 9: Commit**

```bash
cd resume-copilot-web && git add components/resume-copilot/public-resume-copilot.tsx
git commit -m "feat(frontend): replace feedback panel with multi-turn copilot chat UI"
```

---

## Final Verification

After all 10 tasks, run:

```bash
# Backend tests
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_direction_analysis.py tests/test_direction_workflow.py tests/test_resume_feedback_service.py tests/test_chat_service.py -q
# Expected: all pass

# Frontend lint + build
cd resume-copilot-web && npm run lint && npm run build
# Expected: 0 errors, build succeeds
```
