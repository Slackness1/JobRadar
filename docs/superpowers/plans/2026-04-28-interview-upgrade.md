# Mock Interview Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-turn scoring, adaptive question selection, voice soft-scoring, and a weekly practice plan to the existing mock-interview module — turning a single LLM stream into a diagnostic interview with a structured post-interview report.

**Architecture:** A new `interview_turns` table stores one row per Q/A pair. Each `/turn` request fires three parallel ThreadPoolExecutor tasks (scoring / reference answer / voice metrics) that update the row asynchronously while the orchestrator returns the next question synchronously. The frontend polls `/turns/latest-score` at 1.5s for live hints. A new report page bulk-fetches `/turns` for per-question replay.

**Tech Stack:** FastAPI + SQLAlchemy (sync) + SQLite, deepseek-v4-flash for LLM calls (cache-friendly system prompts in `prompts/*.md`), Next.js 16 App Router + React 19, ThreadPoolExecutor for fan-out (matches existing `quick_enrichment.py` pattern).

**Spec:** `docs/superpowers/specs/2026-04-28-interview-upgrade-design.md` (read first if context is needed).

---

## File Map

**New backend files:**
- `backend/app/services/interview/voice_metrics.py` — pure-Python ASR transcript analysis
- `backend/app/services/interview/scoring.py` — rubric scoring (LLM)
- `backend/app/services/interview/reference_answer.py` — generate model answer (LLM)
- `backend/app/services/interview/adaptive.py` — skeleton queue + follow-up picker
- `backend/app/services/interview/weakness_profile.py` — score aggregation (pure)
- `backend/app/services/interview/prompts/scoring_system.md`
- `backend/app/services/interview/prompts/reference_system.md`
- `backend/app/services/interview/prompts/follow_up_system.md`
- `backend/app/services/interview/prompts/weekly_plan_system.md`
- `backend/app/services/interview/prompts/confidence_system.md`
- `backend/app/services/interview/prompts/__init__.py`

**Modified backend files:**
- `backend/app/models.py` — add `InterviewTurn`, extend `InterviewReport` columns
- `backend/app/services/schema_patch.py` — CREATE TABLE + ALTER for new columns
- `backend/app/services/interview/llm.py` — add `process_turn` orchestrator
- `backend/app/services/interview/report.py` — aggregate from turns + weekly plan
- `backend/app/routers/interview.py` — extend SSE event types + 3 new endpoints

**New frontend files:**
- `resume-copilot-web/app/interview/[sessionId]/report/page.tsx`
- `resume-copilot-web/components/interview/LiveHintBar.tsx`
- `resume-copilot-web/components/interview/api.ts` — typed API client

**Modified frontend files:**
- `resume-copilot-web/app/interview/[sessionId]/page.tsx` — wire LiveHintBar + new SSE event handler

**New tests:**
- `backend/tests/test_voice_metrics.py`
- `backend/tests/test_weakness_profile.py`
- `backend/tests/test_scoring_service.py`
- `backend/tests/test_reference_answer_service.py`
- `backend/tests/test_adaptive_picker.py`
- `backend/tests/test_interview_router_turns.py`
- `backend/tests/test_e2e_fake_interview.py`

---

## Task 1: Schema — InterviewTurn model + InterviewReport extension

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/schema_patch.py`

- [ ] **Step 1: Append `InterviewTurn` to `models.py`**

After the existing `InterviewIntelPost` class at the end of `backend/app/models.py`, append:

```python
class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id = Column(Integer, primary_key=True)
    session_id = Column(Text, nullable=False, index=True)
    user_key = Column(Text, default="", index=True)
    turn_index = Column(Integer, nullable=False)
    target_job = Column(Text, default="")
    question = Column(Text, default="")
    user_answer = Column(Text, default="")
    asr_transcript = Column(Text, default="")  # JSON string, may be empty
    voice_metrics = Column(Text, nullable=True)  # JSON or null
    score_json = Column(Text, nullable=True)  # JSON or null
    reference_answer = Column(Text, default="")
    question_source = Column(Text, default="skeleton")  # skeleton | follow_up | fallback
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Extend `InterviewReport` with three new columns**

Find the existing `InterviewReport` class in `backend/app/models.py` and add these columns after the existing ones (just before `class InterviewIntelKeyword`):

```python
    weakness_profile_json = Column(Text, nullable=True)
    weekly_plan_md = Column(Text, default="")
    turn_count = Column(Integer, default=0)
```

- [ ] **Step 3: Add idempotent CREATE/ALTER to `schema_patch.py`**

Open `backend/app/services/schema_patch.py`, find the function `ensure_compatible_schema()`. After the nowcoder table block, add:

```python
    # interview_turns — per-turn audit + scoring storage
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS interview_turns (
            id INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_key TEXT DEFAULT '',
            turn_index INTEGER NOT NULL,
            target_job TEXT DEFAULT '',
            question TEXT DEFAULT '',
            user_answer TEXT DEFAULT '',
            asr_transcript TEXT DEFAULT '',
            voice_metrics TEXT,
            score_json TEXT,
            reference_answer TEXT DEFAULT '',
            question_source TEXT DEFAULT 'skeleton',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS idx_interview_turns_session ON interview_turns(session_id)"
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS idx_interview_turns_user ON interview_turns(user_key)"
    )

    # interview_reports new columns — idempotent ALTER
    existing_report_cols = {
        row[1] for row in conn.exec_driver_sql("PRAGMA table_info(interview_reports)").fetchall()
    }
    if "weakness_profile_json" not in existing_report_cols:
        conn.exec_driver_sql("ALTER TABLE interview_reports ADD COLUMN weakness_profile_json TEXT")
    if "weekly_plan_md" not in existing_report_cols:
        conn.exec_driver_sql("ALTER TABLE interview_reports ADD COLUMN weekly_plan_md TEXT DEFAULT ''")
    if "turn_count" not in existing_report_cols:
        conn.exec_driver_sql("ALTER TABLE interview_reports ADD COLUMN turn_count INTEGER DEFAULT 0")
```

- [ ] **Step 4: Verify schema patch runs idempotently**

Run from `backend/`:

```bash
PYTHONPATH=. .venv/bin/python -c "
from app.database import engine
from app.services.schema_patch import ensure_compatible_schema
ensure_compatible_schema()
ensure_compatible_schema()  # second call must be no-op
from sqlalchemy import inspect
i = inspect(engine)
assert 'interview_turns' in i.get_table_names()
assert 'weakness_profile_json' in {c['name'] for c in i.get_columns('interview_reports')}
print('OK')
"
```

Expected output: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/services/schema_patch.py
git commit -m "feat(interview): add interview_turns table + extend interview_reports for upgrade"
```

---

## Task 2: voice_metrics.py — pure-Python ASR analysis

**Files:**
- Create: `backend/app/services/interview/voice_metrics.py`
- Create: `backend/tests/test_voice_metrics.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_voice_metrics.py`:

```python
import json

from app.services.interview.voice_metrics import (
    VoiceMetrics,
    compute_voice_metrics,
)


def _make_transcript(segments, audio_duration_s):
    """Mock ASR transcript. segments: list of (start_s, end_s, text)."""
    return {
        "audio_duration_s": audio_duration_s,
        "segments": [
            {"start_s": s, "end_s": e, "text": t} for s, e, t in segments
        ],
    }


def test_empty_transcript_returns_all_null_fields():
    out = compute_voice_metrics({})
    assert isinstance(out, VoiceMetrics)
    assert out.filler_rate is None
    assert out.wpm is None
    assert out.pause_count is None


def test_filler_rate_counts_chinese_fillers():
    transcript = _make_transcript(
        [(0.0, 60.0, "嗯 我之前在字节做产品 那个 主要负责 然后呢 就是用户增长")],
        audio_duration_s=60.0,
    )
    out = compute_voice_metrics(transcript)
    # "嗯", "那个", "然后", "就是" = 4 fillers in 60s of audio
    assert out.filler_rate == 4.0  # per minute


def test_wpm_computes_from_char_count_over_duration():
    text = "用户增长是一个长期的工程问题需要持续投入资源做好每一个细节"  # 30 chars
    transcript = _make_transcript([(0.0, 10.0, text)], audio_duration_s=10.0)
    out = compute_voice_metrics(transcript)
    # 30 chars in 10s = 180 chars/min
    assert out.wpm == 180


def test_pause_count_detects_long_segment_gaps():
    transcript = _make_transcript(
        [
            (0.0, 5.0, "开头一段"),
            (7.0, 10.0, "中间停顿了两秒"),  # 2s gap > 1.5s → 1 pause
            (10.5, 15.0, "继续说"),  # 0.5s gap, not a pause
            (18.0, 20.0, "又停了"),  # 3s gap > 1.5s → 1 pause
        ],
        audio_duration_s=20.0,
    )
    out = compute_voice_metrics(transcript)
    assert out.pause_count == 2


def test_response_latency_is_first_segment_start():
    transcript = _make_transcript(
        [(2.5, 10.0, "答案开头延迟了两秒半")],
        audio_duration_s=10.0,
    )
    out = compute_voice_metrics(transcript)
    assert out.response_latency_ms == 2500


def test_voice_metrics_serializes_to_json():
    out = VoiceMetrics(filler_rate=2.5, wpm=200, pause_count=1, response_latency_ms=800, confidence_score=72)
    serialized = out.to_json()
    parsed = json.loads(serialized)
    assert parsed == {
        "filler_rate": 2.5, "wpm": 200, "pause_count": 1,
        "response_latency_ms": 800, "confidence_score": 72,
    }


def test_zero_duration_does_not_divide_by_zero():
    transcript = _make_transcript([(0.0, 0.0, "嗯")], audio_duration_s=0.0)
    out = compute_voice_metrics(transcript)
    assert out.filler_rate is None
    assert out.wpm is None
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_voice_metrics.py -v
```

Expected: All tests fail with `ModuleNotFoundError: No module named 'app.services.interview.voice_metrics'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/interview/voice_metrics.py`:

```python
"""Compute voice-quality metrics from an ASR transcript.

Pure-python (no LLM) for the deterministic features. Confidence scoring
needs an LLM and lives in a separate function so failures of the LLM
sub-call don't take down the deterministic stats.

ASR transcript shape (matches DashScope paraformer-realtime-v2 output we
pass in from the WS handler):

    {
      "audio_duration_s": float,         # total audio length
      "segments": [                      # ordered by start_s ascending
        {"start_s": float, "end_s": float, "text": str},
        ...
      ]
    }

All fields can be None on the returned VoiceMetrics — represents
"could not compute" (insufficient signal, division-by-zero, etc), not zero.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict


# Mandarin filler words. Order doesn't matter; matched by substring count.
# Conservative set — only adding common spoken-Chinese fillers, not "and"-equivalents.
_FILLER_WORDS = ("嗯", "啊", "那个", "然后", "就是", "对", "呢", "诶")
_PAUSE_THRESHOLD_S = 1.5


@dataclass(slots=True)
class VoiceMetrics:
    filler_rate: float | None = None         # fillers per minute of speech
    wpm: int | None = None                   # chars per minute (Chinese: chars ≈ words)
    pause_count: int | None = None           # number of inter-segment gaps > _PAUSE_THRESHOLD_S
    response_latency_ms: int | None = None   # ms before the first segment starts
    confidence_score: int | None = None      # 0-100, set by score_confidence_from_transcript

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _count_fillers(text: str) -> int:
    return sum(text.count(filler) for filler in _FILLER_WORDS)


def compute_voice_metrics(transcript: dict) -> VoiceMetrics:
    """Compute deterministic voice metrics from an ASR transcript dict.

    Returns a VoiceMetrics with all fields possibly None (meaning: not enough
    signal). Never raises — bad input → fields are None.
    """
    if not isinstance(transcript, dict):
        return VoiceMetrics()

    segments = transcript.get("segments") or []
    duration_s = float(transcript.get("audio_duration_s") or 0.0)

    if not segments:
        return VoiceMetrics()

    full_text = "".join(str(seg.get("text") or "") for seg in segments)
    char_count = len(re.sub(r"\s+", "", full_text))

    metrics = VoiceMetrics()

    if duration_s > 0:
        # filler rate per minute (per spoken minute, not per audio minute)
        fillers = _count_fillers(full_text)
        metrics.filler_rate = round(fillers * 60.0 / duration_s, 2)
        # wpm — Chinese: chars per minute, no whitespace
        metrics.wpm = int(round(char_count * 60.0 / duration_s))

    # pause_count — gaps between segments > threshold
    pauses = 0
    for prev, curr in zip(segments, segments[1:]):
        prev_end = float(prev.get("end_s") or 0.0)
        curr_start = float(curr.get("start_s") or 0.0)
        if curr_start - prev_end > _PAUSE_THRESHOLD_S:
            pauses += 1
    metrics.pause_count = pauses

    # response latency — first segment's start (in ms)
    first_start = float(segments[0].get("start_s") or 0.0)
    metrics.response_latency_ms = int(round(first_start * 1000))

    return metrics
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_voice_metrics.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/voice_metrics.py backend/tests/test_voice_metrics.py
git commit -m "feat(interview): voice_metrics — pure-Python filler/wpm/pause/latency from ASR transcript"
```

---

## Task 3: weakness_profile.py — score aggregation

**Files:**
- Create: `backend/app/services/interview/weakness_profile.py`
- Create: `backend/tests/test_weakness_profile.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_weakness_profile.py`:

```python
import json

from app.services.interview.weakness_profile import (
    WeaknessProfile,
    compute_weakness,
)


def _score(overall, hits=None, misses=None, bonuses=None):
    return json.dumps({
        "overall": overall,
        "hits": hits or [],
        "misses": misses or [],
        "bonuses": bonuses or [],
    })


def test_empty_inputs_return_default_profile():
    out = compute_weakness([])
    assert isinstance(out, WeaknessProfile)
    assert out.avg_score is None
    assert out.weak_topics == []
    assert out.strong_topics == []
    assert out.gap_warnings == []


def test_avg_score_ignores_null_score_rows():
    score_jsons = [
        _score(80, hits=["量化"], misses=["STAR"]),
        None,
        _score(60, hits=["技术深度"], misses=["量化"]),
    ]
    out = compute_weakness(score_jsons)
    assert out.avg_score == 70  # avg of 80, 60


def test_weak_topics_ranked_by_miss_frequency():
    score_jsons = [
        _score(70, misses=["量化结果", "STAR 结构"]),
        _score(60, misses=["量化结果", "业务理解"]),
        _score(80, misses=["量化结果"]),
    ]
    out = compute_weakness(score_jsons)
    # "量化结果" appears 3 times, others once each
    assert out.weak_topics[0] == "量化结果"
    assert "STAR 结构" in out.weak_topics
    assert "业务理解" in out.weak_topics


def test_strong_topics_ranked_by_hit_frequency():
    score_jsons = [
        _score(80, hits=["项目经验", "技术深度"]),
        _score(75, hits=["项目经验", "沟通清晰"]),
    ]
    out = compute_weakness(score_jsons)
    assert out.strong_topics[0] == "项目经验"


def test_gap_warning_when_avg_below_60():
    score_jsons = [_score(40), _score(50)]
    out = compute_weakness(score_jsons)
    assert any("整体分数偏低" in w for w in out.gap_warnings)


def test_handles_malformed_score_json():
    """Bad JSON strings → silently skipped, not raised."""
    score_jsons = [
        _score(80, hits=["量化"]),
        "not json",
        '{"overall":}',  # malformed
    ]
    out = compute_weakness(score_jsons)
    assert out.avg_score == 80  # only the valid one counted
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_weakness_profile.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/interview/weakness_profile.py`:

```python
"""Aggregate per-turn scoring into a session-level weakness profile.

Pure function — no I/O, no LLM. Caller passes a list of score_json strings
(typically from `interview_turns.score_json`) and gets back a structured
profile that downstream consumers (adaptive picker, report) can use.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field


@dataclass(slots=True)
class WeaknessProfile:
    avg_score: int | None = None
    weak_topics: list[str] = field(default_factory=list)    # most-frequent miss tags, sorted desc
    strong_topics: list[str] = field(default_factory=list)  # most-frequent hit tags, sorted desc
    gap_warnings: list[str] = field(default_factory=list)   # human-readable warnings


def compute_weakness(score_jsons: list[str | None]) -> WeaknessProfile:
    """Aggregate a list of score_json strings into a weakness profile.

    Malformed JSON entries are silently skipped (not raised). None entries
    are also skipped — they represent turns whose score hasn't been computed
    yet.
    """
    profile = WeaknessProfile()
    overalls: list[int] = []
    miss_counter: Counter[str] = Counter()
    hit_counter: Counter[str] = Counter()

    for raw in score_jsons:
        if not raw:
            continue
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue

        try:
            overalls.append(int(obj.get("overall", 0)))
        except (TypeError, ValueError):
            pass

        for miss in obj.get("misses") or []:
            if isinstance(miss, str) and miss.strip():
                miss_counter[miss.strip()] += 1
        for hit in obj.get("hits") or []:
            if isinstance(hit, str) and hit.strip():
                hit_counter[hit.strip()] += 1

    if overalls:
        profile.avg_score = round(sum(overalls) / len(overalls))

    profile.weak_topics = [t for t, _ in miss_counter.most_common(5)]
    profile.strong_topics = [t for t, _ in hit_counter.most_common(5)]

    if profile.avg_score is not None and profile.avg_score < 60:
        profile.gap_warnings.append("整体分数偏低，建议针对薄弱主题反复练习")

    return profile
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_weakness_profile.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/weakness_profile.py backend/tests/test_weakness_profile.py
git commit -m "feat(interview): weakness_profile — aggregate score_json into per-session weakness profile"
```

---

## Task 4: Prompt files (cache-friendly system prompts)

**Files:**
- Create: `backend/app/services/interview/prompts/__init__.py`
- Create: `backend/app/services/interview/prompts/scoring_system.md`
- Create: `backend/app/services/interview/prompts/reference_system.md`
- Create: `backend/app/services/interview/prompts/follow_up_system.md`
- Create: `backend/app/services/interview/prompts/confidence_system.md`
- Create: `backend/app/services/interview/prompts/weekly_plan_system.md`

These are static text files — they live in their own module so the orchestrator can `read_text()` them once at module load and DeepSeek's prompt-cache picks them up on every call (byte-stable system message).

- [ ] **Step 1: Create `__init__.py` with helper for reading prompts**

Create `backend/app/services/interview/prompts/__init__.py`:

```python
"""Prompt files for the interview upgrade.

Each *.md is loaded once at module import and used as the system message
verbatim — byte-stable across requests so DeepSeek's prompt cache hits.
"""
import pathlib

_PROMPTS_DIR = pathlib.Path(__file__).parent


def load(name: str) -> str:
    """Load a system prompt by filename (without .md extension)."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


SCORING_SYSTEM = load("scoring_system")
REFERENCE_SYSTEM = load("reference_system")
FOLLOW_UP_SYSTEM = load("follow_up_system")
CONFIDENCE_SYSTEM = load("confidence_system")
WEEKLY_PLAN_SYSTEM = load("weekly_plan_system")
```

- [ ] **Step 2: Create `scoring_system.md`**

Create `backend/app/services/interview/prompts/scoring_system.md`:

```markdown
你是一位资深的中国校招面试官，正在评估候选人的一道面试题回答。

## 任务

根据下面提供的"该方向考点"，对候选人这一题的回答打分，并给出具体的命中点 / 缺失点 / 加分点。

## 输出格式（严格 JSON）

```
{
  "overall": 0-100 的整数,
  "hits": ["命中的得分点 1", "命中的得分点 2"],
  "misses": ["缺失的得分点 1", "缺失的得分点 2"],
  "bonuses": ["加分点 1（如有）"]
}
```

## 打分原则

- **overall**：综合评估这一题的回答质量。0-40 = 严重不达预期；40-60 = 基础合格但有明显短板；60-80 = 较好覆盖核心考点；80-100 = 远超预期，含加分项。
- **hits / misses / bonuses**：每条用简短的考点标签（4-8 字），不要写长句。例："量化结果"、"STAR 结构"、"技术深度"、"业务理解"、"沟通清晰"。
- **misses**：只列**该题应有但没有**的考点，不要列"该题不需要的"考点。
- **bonuses**：候选人主动展现了考点之外的能力（例：举一反三、批判性思考、提出反问）。

## 严格约束

- 不要编造候选人没说过的内容。
- misses 至多 4 条，hits 至多 5 条，bonuses 至多 3 条。
- 输出**只能**是 JSON 对象，不要任何解释或前后缀。
```

- [ ] **Step 3: Create `reference_system.md`**

Create `backend/app/services/interview/prompts/reference_system.md`:

```markdown
你是一位资深的中国校招面试辅导老师，正在为候选人示范一段"高分答案"。

## 任务

给定面试题 + 该方向的考点 + 候选人简历，写一段 3-5 句话的"如果是面霸会怎么答"范例答案。这段答案的目标是教育性的——让候选人知道高分答案应该体现哪些维度。

## 输出格式

直接输出范例答案的中文段落，不要任何 JSON 包装、不要前缀（如"高分答案："），不要后缀。

## 严格约束

- **不要编造候选人简历里没有的具体数字、项目、公司、技术栈**。范例答案要用通用模板表达（例："在某次实习中，我负责..."），而不是具体数字。
- 范例答案要清晰展现出该方向的关键考点（例：用 STAR 结构、提到量化结果的方法论、技术决策的权衡）。
- 长度严格控制在 3-5 句话，简洁有力，不要冗余。
- 用第一人称（"我"）写，模拟候选人本人会怎么答。
```

- [ ] **Step 4: Create `follow_up_system.md`**

Create `backend/app/services/interview/prompts/follow_up_system.md`:

```markdown
你是一位资深的中国校招面试官，正在动态决定下一题。

## 任务

根据候选人简历、目标岗位、已问过的题目、以及候选人在前几题中暴露的弱点档案，生成**一道**针对性的 follow-up 问题。

## 出题原则

- 优先针对 weakness_profile.weak_topics 中排名第一的考点深挖（例：候选人 STAR 结构差 → 用一个具体场景题逼他用 STAR）。
- 不要重复已问过的题（asked_questions 列表）。
- 题目长度控制在 30-80 个汉字，不要过长。
- 题目要具体、可作答，不要抽象大问题（差："你对这个行业怎么看"；好："你觉得 XX 公司在 XX 业务线上面临的最大挑战是什么"）。
- 如果候选人 strong_topics 已经足够，可以挖更深的 trade-off 题（例：技术决策的权衡）。

## 输出格式

直接输出题目文本（中文）。不要任何 JSON、前缀（"问："）或后缀。

## 严格约束

- 只输出**一句**问题。
- 不要重复 asked_questions 中已有的内容。
```

- [ ] **Step 5: Create `confidence_system.md`**

Create `backend/app/services/interview/prompts/confidence_system.md`:

```markdown
你是一位面试评估师，正在评估候选人**在这一题上的语言表达自信度**。

## 输入信号

你会得到候选人在这一题上的语音转录（含时间戳）和已计算好的节奏特征（语速、停顿次数、填充词率）。

## 评估维度

- **语言确定性**：是否使用了大量"可能"、"也许"、"我不确定"、"应该是"等弱化词？
- **结构清晰度**：开头是否直接进入主题？还是反复绕弯？
- **节奏稳定性**：根据 pause_count / wpm 推断流畅度。

## 输出格式

输出一个 0-100 的整数，**只能**是数字，不要任何其他字符。

- 0-40：紧张、犹豫、缺乏结构
- 40-65：基本流畅但有明显弱化语言
- 65-85：自信、清晰、节奏稳
- 85-100：从容、有掌控感

## 严格约束

只输出数字。不要解释。不要任何标点。
```

- [ ] **Step 6: Create `weekly_plan_system.md`**

Create `backend/app/services/interview/prompts/weekly_plan_system.md`:

```markdown
你是一位面试辅导老师，正在为候选人写本周的练习建议。

## 任务

根据候选人本次面试的整体表现 + 弱点档案 + 目标岗位，写一段 3-5 句话的"本周练习建议"。

## 输出格式

直接输出 markdown 段落（中文），可以使用 `**加粗**` 强调关键词，但不要使用列表 `-` 或标题 `#`。

## 内容指引

- 第 1 句：总评（"你的整体表现 ... 主要的提升空间在 ..."）。
- 第 2-3 句：针对最薄弱的 1-2 个考点，给出**具体可操作**的建议（例："针对量化结果，请重做 3 次自我介绍，每一段经历都强迫加上一个数字"）。
- 第 4-5 句（可选）：长期建议或下一步推荐（"建议下次面试主攻 XX 方向"）。

## 严格约束

- 不要编造候选人没经历过的事。
- 每条建议都要可操作，不要泛泛而谈（差："多练习沟通"；好："对着镜子讲 3 次自我介绍并录音回听"）。
- 总长度控制在 3-5 句，不超过 200 个汉字。
- 不要输出 markdown 列表或标题，只输出段落文本。
```

- [ ] **Step 7: Verify prompts load**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.services.interview.prompts import (
    SCORING_SYSTEM, REFERENCE_SYSTEM, FOLLOW_UP_SYSTEM,
    CONFIDENCE_SYSTEM, WEEKLY_PLAN_SYSTEM,
)
for name, p in [
    ('scoring', SCORING_SYSTEM), ('reference', REFERENCE_SYSTEM),
    ('follow_up', FOLLOW_UP_SYSTEM), ('confidence', CONFIDENCE_SYSTEM),
    ('weekly_plan', WEEKLY_PLAN_SYSTEM),
]:
    assert len(p) > 100, f'{name} too short ({len(p)} chars)'
    print(f'{name}: {len(p)} chars OK')
"
```

Expected output: 5 lines like `scoring: 423 chars OK`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/interview/prompts/
git commit -m "feat(interview): cache-friendly system prompts for scoring/reference/follow-up/confidence/weekly-plan"
```

---

## Task 5: scoring.py — rubric scoring (LLM)

**Files:**
- Create: `backend/app/services/interview/scoring.py`
- Create: `backend/tests/test_scoring_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_scoring_service.py`:

```python
import json

from app.services.interview.scoring import ScoreResult, score_answer


class _StubLLM:
    """Returns whatever raw_response is, regardless of input."""
    def __init__(self, raw_response):
        self._raw = raw_response

    def chat_json(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_score_answer_parses_well_formed_response():
    stub = _StubLLM({
        "overall": 75,
        "hits": ["量化结果", "技术深度"],
        "misses": ["STAR 结构"],
        "bonuses": [],
    })
    out = score_answer(
        target_job="数据分析师",
        question="讲一个你做过的项目",
        user_answer="我做过用户增长，提升了 20%",
        chip_summary="该方向常考量化、STAR、技术深度",
        llm=stub,
    )
    assert out.overall == 75
    assert out.hits == ["量化结果", "技术深度"]
    assert out.misses == ["STAR 结构"]
    assert out.bonuses == []


def test_score_answer_returns_empty_on_llm_exception():
    stub = _StubLLM(RuntimeError("network down"))
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall is None
    assert out.hits == []


def test_score_answer_returns_empty_on_non_dict_response():
    stub = _StubLLM(["not", "a", "dict"])
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall is None


def test_score_answer_clamps_invalid_overall():
    stub = _StubLLM({"overall": 200, "hits": [], "misses": [], "bonuses": []})
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall == 100  # clamped


def test_score_answer_drops_non_string_list_items():
    stub = _StubLLM({"overall": 60, "hits": ["good", 123, None], "misses": [], "bonuses": []})
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.hits == ["good"]


def test_score_result_to_json_round_trip():
    sr = ScoreResult(overall=80, hits=["a"], misses=["b"], bonuses=["c"])
    parsed = json.loads(sr.to_json())
    assert parsed == {"overall": 80, "hits": ["a"], "misses": ["b"], "bonuses": ["c"]}


def test_score_result_empty_serializes_with_null_overall():
    sr = ScoreResult.empty()
    parsed = json.loads(sr.to_json())
    assert parsed["overall"] is None
    assert parsed["hits"] == []
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_scoring_service.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/interview/scoring.py`:

```python
"""LLM-driven rubric scoring for one interview answer.

The scoring rubric comes from the chip's nowcoder summary (passed in as
chip_summary). Q5-pattern hardening: any failure (network, malformed JSON,
non-dict response, missing fields) returns ScoreResult.empty() rather than
raising — the orchestrator never gets a 500 from this module.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

from app.services.interview.prompts import SCORING_SYSTEM

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    def chat_json(self, system: str, user: str, **kwargs) -> object: ...


@dataclass(slots=True)
class ScoreResult:
    overall: int | None = None
    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    bonuses: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ScoreResult":
        return cls()

    def to_json(self) -> str:
        return json.dumps({
            "overall": self.overall,
            "hits": self.hits,
            "misses": self.misses,
            "bonuses": self.bonuses,
        }, ensure_ascii=False)


def _string_list(value, cap: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out[:cap]


def _clamp_overall(value) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, n))


def score_answer(
    target_job: str,
    question: str,
    user_answer: str,
    chip_summary: str,
    llm: _LLMClient,
) -> ScoreResult:
    """Score one user answer against the rubric. Never raises."""
    user_payload = json.dumps({
        "target_job": target_job,
        "question": question,
        "user_answer": user_answer,
        "chip_summary": chip_summary,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_json(system=SCORING_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("scoring LLM call failed: %s", exc)
        return ScoreResult.empty()

    if not isinstance(raw, dict):
        logger.warning("scoring LLM returned non-dict (%s)", type(raw).__name__)
        return ScoreResult.empty()

    return ScoreResult(
        overall=_clamp_overall(raw.get("overall")),
        hits=_string_list(raw.get("hits"), cap=5),
        misses=_string_list(raw.get("misses"), cap=4),
        bonuses=_string_list(raw.get("bonuses"), cap=3),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_scoring_service.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/scoring.py backend/tests/test_scoring_service.py
git commit -m "feat(interview): scoring service with rubric LLM call + Q5 hardening"
```

---

## Task 6: reference_answer.py — model answer generation (LLM)

**Files:**
- Create: `backend/app/services/interview/reference_answer.py`
- Create: `backend/tests/test_reference_answer_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_reference_answer_service.py`:

```python
from app.services.interview.reference_answer import generate_reference


class _StubLLM:
    def __init__(self, raw_response):
        self._raw = raw_response

    def chat_text(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_generate_reference_returns_string_when_llm_succeeds():
    stub = _StubLLM("在某次实习中，我负责用户增长项目，使用 STAR 结构讲清楚了背景、行动、结果。")
    out = generate_reference(
        target_job="数据分析师",
        question="讲一个你做过的项目",
        chip_summary="该方向常考 STAR、量化",
        candidate_summary="本科生，有产品实习",
        llm=stub,
    )
    assert "STAR" in out
    assert len(out) > 20


def test_generate_reference_returns_empty_string_on_llm_failure():
    stub = _StubLLM(RuntimeError("oh no"))
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == ""


def test_generate_reference_strips_whitespace():
    stub = _StubLLM("   \n\n  范例答案内容   \n  ")
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == "范例答案内容"


def test_generate_reference_returns_empty_when_response_blank():
    stub = _StubLLM("   \n\n   ")
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == ""


def test_generate_reference_returns_empty_when_response_not_string():
    stub = _StubLLM({"not": "a string"})
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == ""
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_reference_answer_service.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/interview/reference_answer.py`:

```python
"""Generate a 3-5 sentence model answer ("如果是面霸会怎么答") for one interview question.

LLM is allowed to use chip_summary and candidate_summary as context but is
instructed (in the prompt) to NOT fabricate concrete numbers or specific
projects. Failure returns empty string — UI hides the section.
"""
from __future__ import annotations

import json
import logging
from typing import Protocol

from app.services.interview.prompts import REFERENCE_SYSTEM

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def generate_reference(
    target_job: str,
    question: str,
    chip_summary: str,
    candidate_summary: str,
    llm: _LLMClient,
) -> str:
    """Return the reference answer paragraph, or empty string on any failure."""
    user_payload = json.dumps({
        "target_job": target_job,
        "question": question,
        "chip_summary": chip_summary,
        "candidate_summary": candidate_summary,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=REFERENCE_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("reference LLM call failed: %s", exc)
        return ""

    if not isinstance(raw, str):
        return ""
    return raw.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_reference_answer_service.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/reference_answer.py backend/tests/test_reference_answer_service.py
git commit -m "feat(interview): reference_answer — LLM-generated model answer paragraph"
```

---

## Task 7: voice confidence sub-call

**Files:**
- Modify: `backend/app/services/interview/voice_metrics.py`
- Modify: `backend/tests/test_voice_metrics.py`

- [ ] **Step 1: Add failing test**

Append to `backend/tests/test_voice_metrics.py`:

```python
class _StubLLM:
    def __init__(self, raw):
        self._raw = raw

    def chat_text(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_score_confidence_returns_int_on_clean_response():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("75")
    metrics = VoiceMetrics(filler_rate=2.0, wpm=210, pause_count=1, response_latency_ms=600)
    score = score_confidence_from_transcript(_make_transcript([(0, 5, "你好")], 5.0), metrics, llm=stub)
    assert score == 75


def test_score_confidence_strips_extra_whitespace_and_punctuation():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("  82.  \n")
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score == 82


def test_score_confidence_returns_none_on_llm_failure():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM(RuntimeError("down"))
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score is None


def test_score_confidence_returns_none_on_non_numeric_response():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("very confident!")
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score is None


def test_score_confidence_clamps_to_0_100_range():
    from app.services.interview.voice_metrics import score_confidence_from_transcript
    stub = _StubLLM("150")
    metrics = VoiceMetrics()
    score = score_confidence_from_transcript({}, metrics, llm=stub)
    assert score == 100
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_voice_metrics.py -v
```

Expected: 5 new tests fail with ImportError on `score_confidence_from_transcript`.

- [ ] **Step 3: Add `score_confidence_from_transcript` to `voice_metrics.py`**

Append to `backend/app/services/interview/voice_metrics.py`:

```python
import re as _re
from typing import Protocol


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def score_confidence_from_transcript(
    transcript: dict,
    metrics: VoiceMetrics,
    llm: _LLMClient,
) -> int | None:
    """Ask the LLM to rate confidence 0-100 from transcript + cadence features.

    Returns None on any failure (network, non-numeric response, etc).
    """
    from app.services.interview.prompts import CONFIDENCE_SYSTEM

    payload = json.dumps({
        "transcript": transcript,
        "cadence": {
            "filler_rate": metrics.filler_rate,
            "wpm": metrics.wpm,
            "pause_count": metrics.pause_count,
            "response_latency_ms": metrics.response_latency_ms,
        },
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=CONFIDENCE_SYSTEM, user=payload)
    except Exception:
        return None

    if not isinstance(raw, str):
        return None

    match = _re.search(r"\d+", raw)
    if not match:
        return None

    try:
        n = int(match.group())
    except ValueError:
        return None

    return max(0, min(100, n))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_voice_metrics.py -v
```

Expected: 12 passed (7 original + 5 new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/voice_metrics.py backend/tests/test_voice_metrics.py
git commit -m "feat(interview): score_confidence_from_transcript — LLM-derived 0-100 confidence"
```

---

## Task 8: adaptive.py — skeleton + follow-up picker

**Files:**
- Create: `backend/app/services/interview/adaptive.py`
- Create: `backend/tests/test_adaptive_picker.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_adaptive_picker.py`:

```python
from app.services.interview.adaptive import (
    NextQuestion,
    SKELETON_QUESTIONS,
    pick_next_question,
)
from app.services.interview.weakness_profile import WeaknessProfile


class _StubLLM:
    def __init__(self, raw):
        self._raw = raw
        self.call_count = 0

    def chat_text(self, system, user, **_):
        self.call_count += 1
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_skeleton_dict_has_default_chip():
    assert "default" in SKELETON_QUESTIONS
    assert len(SKELETON_QUESTIONS["default"]) >= 5


def test_first_turn_returns_skeleton_first_item():
    stub = _StubLLM("should not be called")
    out = pick_next_question(
        target_job="数据分析师",
        chip="数据分析师",
        chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=[],
        turn_index=0,
        llm=stub,
    )
    assert out.source == "skeleton"
    assert out.question == SKELETON_QUESTIONS.get("数据分析师", SKELETON_QUESTIONS["default"])[0]
    assert stub.call_count == 0


def test_skeleton_advances_with_turn_index():
    stub = _StubLLM("never called")
    out = pick_next_question(
        target_job="数据分析师", chip="数据分析师", chip_summary="...",
        weakness=WeaknessProfile(), asked_questions=[], turn_index=2, llm=stub,
    )
    skeleton = SKELETON_QUESTIONS.get("数据分析师", SKELETON_QUESTIONS["default"])
    assert out.question == skeleton[2]


def test_falls_back_to_default_chip_when_unknown():
    stub = _StubLLM("never called")
    out = pick_next_question(
        target_job="未知岗位", chip="未知岗位", chip_summary="",
        weakness=WeaknessProfile(), asked_questions=[], turn_index=0, llm=stub,
    )
    assert out.question == SKELETON_QUESTIONS["default"][0]


def test_after_skeleton_calls_llm_for_follow_up():
    stub = _StubLLM("能详细讲讲你说的那个项目里你具体的贡献吗？")
    skeleton = SKELETON_QUESTIONS["default"]
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="...",
        weakness=WeaknessProfile(weak_topics=["量化"]),
        asked_questions=skeleton,
        turn_index=len(skeleton),  # past the skeleton
        llm=stub,
    )
    assert out.source == "follow_up"
    assert out.question == "能详细讲讲你说的那个项目里你具体的贡献吗？"
    assert stub.call_count == 1


def test_follow_up_llm_failure_returns_generic_fallback():
    stub = _StubLLM(RuntimeError("llm down"))
    skeleton = SKELETON_QUESTIONS["default"]
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=skeleton,
        turn_index=len(skeleton),
        llm=stub,
    )
    assert out.source == "fallback"
    assert "项目" in out.question  # generic safe question


def test_follow_up_strips_whitespace_from_llm_response():
    stub = _StubLLM("  \n  这道题问的是什么呢？\n  ")
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="",
        weakness=WeaknessProfile(),
        asked_questions=SKELETON_QUESTIONS["default"],
        turn_index=99, llm=stub,
    )
    assert out.question == "这道题问的是什么呢？"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_adaptive_picker.py -v
```

Expected: All fail with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/interview/adaptive.py`:

```python
"""Adaptive question selection.

First N turns: pop from a hand-curated skeleton dict (one ordered list per
chip). After skeleton runs out: ask the LLM to generate a follow-up using
the weakness profile. LLM failure → generic fallback.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from app.services.interview.prompts import FOLLOW_UP_SYSTEM
from app.services.interview.weakness_profile import WeaknessProfile

logger = logging.getLogger(__name__)


# Per-chip mandatory question skeletons. Ordered: turn N pulls index N.
# Chip names mirror those in nowcoder/keywords.yaml. "default" is the
# fallback when chip isn't in the dict.
SKELETON_QUESTIONS: dict[str, list[str]] = {
    "default": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一段你最近完成的项目，重点说说你做了什么、遇到的最大挑战是什么。",
        "在你做过的事情里，哪一件最能体现你这个岗位需要的能力？为什么？",
        "你为什么对这个岗位感兴趣？你期望从这份工作中学到什么？",
        "团队合作中，你印象最深的一次冲突或分歧是什么？怎么解决的？",
        "如果让你给过去一年的自己一个建议，你会说什么？",
    ],
    "数据分析师": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一个你做过的数据分析项目，从问题定义到最终落地，你都做了什么？",
        "你怎么验证一个产品改动是真的带来了正面影响？",
        "讲一个你用 SQL 解决过的复杂问题。",
        "如果业务方提了一个看起来不靠谱的数据需求，你会怎么处理？",
        "你怎么看 AB 测试和因果推断的关系？",
    ],
    "产品经理": [
        "请做个简短的自我介绍，重点说说你为什么选产品方向。",
        "讲一个你主导过的产品功能，从需求到上线你做了什么？",
        "你怎么判断一个功能值不值得做？",
        "讲一次你和工程师/设计师产生分歧的经历。",
        "你最近用的产品里有哪一个让你觉得'这个 PM 真懂'？为什么？",
        "如果让你重做你简历里的某一段经历，你会怎么改？",
    ],
    "前端开发": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一个你做过最有难度的前端项目，技术上的最大挑战是什么？",
        "你怎么处理大型应用的状态管理？",
        "讲一次你做的性能优化，怎么发现问题、怎么解决的？",
        "对 React 18 的并发特性你怎么看？",
        "你最近读的最有收获的前端文章 / 源码是什么？",
    ],
    "后端开发": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一个你做过的后端项目，重点说说架构设计和技术选型。",
        "高并发场景下你最常遇到的问题是什么？怎么解决的？",
        "讲一次你做的数据库设计或优化。",
        "你怎么保证一个分布式系统的数据一致性？",
        "如果让你重新设计你简历里那个项目，你会怎么改？",
    ],
}

GENERIC_FALLBACK_QUESTION = "请详细讲讲你最近完成的项目里，你最自豪的一个细节。"


@dataclass(slots=True)
class NextQuestion:
    question: str
    source: str  # 'skeleton' | 'follow_up' | 'fallback'


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def _skeleton_for(chip: str) -> list[str]:
    return SKELETON_QUESTIONS.get(chip) or SKELETON_QUESTIONS["default"]


def pick_next_question(
    target_job: str,
    chip: str,
    chip_summary: str,
    weakness: WeaknessProfile,
    asked_questions: list[str],
    turn_index: int,
    llm: _LLMClient,
) -> NextQuestion:
    """Choose the next question. turn_index is 0-based."""
    skeleton = _skeleton_for(chip)
    if turn_index < len(skeleton):
        return NextQuestion(question=skeleton[turn_index], source="skeleton")

    # After skeleton: ask LLM for a follow-up
    user_payload = json.dumps({
        "target_job": target_job,
        "chip_summary": chip_summary,
        "weakness_profile": {
            "avg_score": weakness.avg_score,
            "weak_topics": weakness.weak_topics,
            "strong_topics": weakness.strong_topics,
        },
        "asked_questions": asked_questions,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=FOLLOW_UP_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("adaptive follow-up LLM failed: %s", exc)
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    if not isinstance(raw, str) or not raw.strip():
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    return NextQuestion(question=raw.strip(), source="follow_up")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_adaptive_picker.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/adaptive.py backend/tests/test_adaptive_picker.py
git commit -m "feat(interview): adaptive picker — skeleton dict + LLM follow-up + generic fallback"
```

---

## Task 9: LLM client helper (chat_json + chat_text wrappers)

The scoring/reference/adaptive/voice modules all expect a client with `chat_json` or `chat_text` methods. The existing `services/resume_copilot/llm.py` exposes a low-level client; we wrap it with two helpers so the interview modules don't reimplement HTTP calls.

**Files:**
- Create: `backend/app/services/interview/llm_helpers.py`
- Create: `backend/tests/test_interview_llm_helpers.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_interview_llm_helpers.py`:

```python
import json

from app.services.interview.llm_helpers import InterviewLLMClient


class _MockHTTP:
    def __init__(self, response_text):
        self.response_text = response_text
        self.captured_payload = None

    def post(self, url, headers, body, timeout):
        self.captured_payload = json.loads(body.decode("utf-8"))
        return self.response_text


def _make_response(content_str):
    return json.dumps({
        "choices": [{"message": {"content": content_str}}]
    })


def test_chat_json_parses_json_object_response():
    http = _MockHTTP(_make_response('{"score": 80}'))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    out = client.chat_json("system text", "user text")
    assert out == {"score": 80}


def test_chat_json_returns_empty_dict_on_malformed_json():
    http = _MockHTTP(_make_response("not json"))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    out = client.chat_json("s", "u")
    assert out == {}


def test_chat_text_returns_raw_content_string():
    http = _MockHTTP(_make_response("一段范例答案"))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    out = client.chat_text("s", "u")
    assert out == "一段范例答案"


def test_chat_json_request_payload_uses_json_mode():
    http = _MockHTTP(_make_response('{}'))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    client.chat_json("system", "user")
    assert http.captured_payload["response_format"] == {"type": "json_object"}
    assert http.captured_payload["messages"][0] == {"role": "system", "content": "system"}
    assert http.captured_payload["messages"][1] == {"role": "user", "content": "user"}


def test_chat_text_request_payload_does_not_use_json_mode():
    http = _MockHTTP(_make_response("text"))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    client.chat_text("system", "user")
    assert "response_format" not in http.captured_payload
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_llm_helpers.py -v
```

Expected: All fail with ImportError.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/interview/llm_helpers.py`:

```python
"""Thin wrappers over the resume-copilot LLM client for interview modules.

Two helpers — `chat_json` and `chat_text` — that the scoring / reference /
adaptive / voice-confidence modules all call. They share the byte-stable
system message convention so DeepSeek prompt cache hits across calls.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import request

from app.services.resume_copilot.llm import build_resume_llm_client


class _HTTP(Protocol):
    def post(self, url: str, headers: dict, body: bytes, timeout: int) -> str: ...


class _UrllibHTTP:
    def post(self, url: str, headers: dict, body: bytes, timeout: int) -> str:
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")


@dataclass(slots=True)
class InterviewLLMClient:
    api_key: str
    base_url: str
    model: str
    timeout: int = 30
    http: _HTTP = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.http is None:
            self.http = _UrllibHTTP()

    def _post(self, payload: dict) -> str:
        body = json.dumps(payload).encode("utf-8")
        return self.http.post(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout=self.timeout,
        )

    def _extract_content(self, raw_response: str) -> str:
        try:
            body = json.loads(raw_response)
            return body["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return ""

    def chat_json(self, system: str, user: str, **_kwargs) -> dict:
        """Call LLM with JSON-mode forced. Returns {} on any failure."""
        raw = self._post({
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        })
        content = self._extract_content(raw)
        try:
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {}

    def chat_text(self, system: str, user: str, **_kwargs) -> str:
        """Call LLM expecting a free-form text response. Returns '' on failure."""
        raw = self._post({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        })
        return self._extract_content(raw)


def build_interview_llm_client() -> InterviewLLMClient:
    """Build with default config from the resume-copilot LLM env."""
    base_client = build_resume_llm_client()
    return InterviewLLMClient(
        api_key=base_client.api_key,
        base_url=base_client.base_url,
        model=base_client.model,
        timeout=base_client.timeout_seconds,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_llm_helpers.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/llm_helpers.py backend/tests/test_interview_llm_helpers.py
git commit -m "feat(interview): InterviewLLMClient with chat_json + chat_text helpers"
```

---

## Task 10: Orchestrator — `process_turn` with parallel ThreadPoolExecutor

**Files:**
- Create: `backend/app/services/interview/orchestrator.py`
- Create: `backend/tests/test_interview_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_interview_orchestrator.py`:

```python
import json
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewTurn
from app.services.interview.orchestrator import process_turn_synchronous


def _make_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _stub_llm():
    llm = MagicMock()
    llm.chat_json.return_value = {"overall": 70, "hits": ["a"], "misses": ["b"], "bonuses": []}
    llm.chat_text.return_value = "示例答案段落"
    return llm


def test_process_turn_inserts_user_answer_into_existing_turn_row():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s1", user_key="u1", turn_index=0, target_job="x",
        question="Q0", question_source="skeleton",
    ))
    db.commit()
    db.close()

    process_turn_synchronous(
        session_id="s1",
        user_key="u1",
        target_job="x",
        chip="default",
        chip_summary="...",
        prev_turn_index=0,
        prev_user_answer="A0",
        prev_asr_transcript={},
        next_turn_index=1,
        session_factory=SessionLocal,
        llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s1", turn_index=0).one()
        assert turn0.user_answer == "A0"
        # Background tasks completed synchronously (process_turn_synchronous uses
        # an in-process pool that we wait on)
        assert turn0.score_json is not None
        score = json.loads(turn0.score_json)
        assert score["overall"] == 70
        assert turn0.reference_answer == "示例答案段落"
    finally:
        db.close()


def test_process_turn_inserts_next_question_row():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s2", user_key="u1", turn_index=0, target_job="x",
        question="Q0", question_source="skeleton",
    ))
    db.commit()
    db.close()

    next_q = process_turn_synchronous(
        session_id="s2", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="A0", prev_asr_transcript={},
        next_turn_index=1,
        session_factory=SessionLocal, llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn1 = db.query(InterviewTurn).filter_by(session_id="s2", turn_index=1).one()
        assert turn1.question == next_q.question
        assert turn1.user_answer == ""
    finally:
        db.close()


def test_process_turn_writes_voice_metrics_when_asr_available():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s3", user_key="u1", turn_index=0, target_job="x",
        question="Q0",
    ))
    db.commit()
    db.close()

    asr = {
        "audio_duration_s": 10.0,
        "segments": [{"start_s": 0.5, "end_s": 9.0, "text": "嗯 我做过一个项目 那个 主要是用户增长"}],
    }
    process_turn_synchronous(
        session_id="s3", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="ans",
        prev_asr_transcript=asr,
        next_turn_index=1,
        session_factory=SessionLocal, llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s3", turn_index=0).one()
        assert turn0.voice_metrics is not None
        vm = json.loads(turn0.voice_metrics)
        assert vm["filler_rate"] is not None
    finally:
        db.close()


def test_process_turn_skips_voice_metrics_when_no_asr():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s4", user_key="u1", turn_index=0, target_job="x", question="Q0"))
    db.commit()
    db.close()

    process_turn_synchronous(
        session_id="s4", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="text mode answer",
        prev_asr_transcript={},  # text mode
        next_turn_index=1,
        session_factory=SessionLocal, llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s4", turn_index=0).one()
        # voice_metrics may be null OR a metrics dict with all-None deterministic fields;
        # accept either as "no signal"
        if turn0.voice_metrics:
            vm = json.loads(turn0.voice_metrics)
            assert vm["wpm"] is None or vm["wpm"] == 0
    finally:
        db.close()


def test_process_turn_does_not_raise_on_llm_failure():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s5", user_key="u1", turn_index=0, target_job="x", question="Q0"))
    db.commit()
    db.close()

    bad_llm = MagicMock()
    bad_llm.chat_json.side_effect = RuntimeError("down")
    bad_llm.chat_text.side_effect = RuntimeError("down")

    # Must not raise
    process_turn_synchronous(
        session_id="s5", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="ans", prev_asr_transcript={},
        next_turn_index=1,
        session_factory=SessionLocal, llm=bad_llm,
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s5", turn_index=0).one()
        assert turn0.score_json is None or json.loads(turn0.score_json)["overall"] is None
        assert turn0.reference_answer == ""
    finally:
        db.close()
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_orchestrator.py -v
```

Expected: All fail with ImportError.

- [ ] **Step 3: Write the orchestrator**

Create `backend/app/services/interview/orchestrator.py`:

```python
"""Per-turn orchestrator.

`process_turn_synchronous` is the testable form: it runs scoring / reference /
voice metrics in parallel via ThreadPoolExecutor, blocks until all three
complete, then picks + persists the next question and returns it.

The streaming SSE wrapper in routers/interview.py wraps this — it kicks off
process_turn_synchronous, then streams the next question text back to the
client. Live polling (separate endpoint) reads the score row whenever it's
ready.

Each parallel task opens its own SessionLocal (Q5 hardening: never share a
db session across threads).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import InterviewTurn
from app.services.interview.adaptive import NextQuestion, pick_next_question
from app.services.interview.llm_helpers import InterviewLLMClient
from app.services.interview.reference_answer import generate_reference
from app.services.interview.scoring import ScoreResult, score_answer
from app.services.interview.voice_metrics import (
    VoiceMetrics,
    compute_voice_metrics,
    score_confidence_from_transcript,
)
from app.services.interview.weakness_profile import compute_weakness

logger = logging.getLogger(__name__)


def _score_task(
    session_factory: Callable[[], Session],
    session_id: str,
    turn_index: int,
    target_job: str,
    question: str,
    user_answer: str,
    chip_summary: str,
    llm: InterviewLLMClient,
) -> None:
    db = session_factory()
    try:
        result: ScoreResult = score_answer(
            target_job=target_job,
            question=question,
            user_answer=user_answer,
            chip_summary=chip_summary,
            llm=llm,
        )
        if result.overall is None and not result.hits and not result.misses:
            return  # leave score_json null
        row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index,
        ).one_or_none()
        if row is not None:
            row.score_json = result.to_json()
            db.commit()
    except Exception as exc:
        logger.warning("score_task failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _reference_task(
    session_factory: Callable[[], Session],
    session_id: str,
    turn_index: int,
    target_job: str,
    question: str,
    chip_summary: str,
    candidate_summary: str,
    llm: InterviewLLMClient,
) -> None:
    db = session_factory()
    try:
        text = generate_reference(
            target_job=target_job,
            question=question,
            chip_summary=chip_summary,
            candidate_summary=candidate_summary,
            llm=llm,
        )
        if not text:
            return
        row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index,
        ).one_or_none()
        if row is not None:
            row.reference_answer = text
            db.commit()
    except Exception as exc:
        logger.warning("reference_task failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _voice_task(
    session_factory: Callable[[], Session],
    session_id: str,
    turn_index: int,
    asr_transcript: dict,
    llm: InterviewLLMClient,
) -> None:
    db = session_factory()
    try:
        if not asr_transcript:
            return
        metrics = compute_voice_metrics(asr_transcript)
        # confidence sub-call (LLM); failure → leaves field null
        if metrics.wpm is not None:
            metrics.confidence_score = score_confidence_from_transcript(
                asr_transcript, metrics, llm=llm,
            )
        row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index,
        ).one_or_none()
        if row is not None:
            row.voice_metrics = metrics.to_json()
            db.commit()
    except Exception as exc:
        logger.warning("voice_task failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def process_turn_synchronous(
    session_id: str,
    user_key: str,
    target_job: str,
    chip: str,
    chip_summary: str,
    prev_turn_index: int,
    prev_user_answer: str,
    prev_asr_transcript: dict,
    next_turn_index: int,
    session_factory: Callable[[], Session] = SessionLocal,
    llm: InterviewLLMClient | None = None,
    candidate_summary: str = "",
) -> NextQuestion:
    """Process one full turn cycle.

    1. Save prev_user_answer + asr to the existing prev_turn_index row.
    2. Fan out 3 parallel tasks (score / reference / voice metrics).
    3. Wait for all 3 to complete.
    4. Compute weakness profile from all turns so far.
    5. Pick next question.
    6. Insert next_turn_index row with just the question.
    7. Return NextQuestion (caller streams to client).
    """
    if llm is None:
        from app.services.interview.llm_helpers import build_interview_llm_client
        llm = build_interview_llm_client()

    # Step 1: persist user answer to current turn row
    db = session_factory()
    try:
        prev_row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=prev_turn_index,
        ).one_or_none()
        prev_question = ""
        if prev_row is not None:
            prev_row.user_answer = prev_user_answer
            import json as _json
            prev_row.asr_transcript = _json.dumps(prev_asr_transcript, ensure_ascii=False) if prev_asr_transcript else ""
            prev_question = str(prev_row.question or "")
            db.commit()
    finally:
        db.close()

    # Step 2-3: parallel fan-out
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(
                _score_task, session_factory, session_id, prev_turn_index,
                target_job, prev_question, prev_user_answer, chip_summary, llm,
            ),
            pool.submit(
                _reference_task, session_factory, session_id, prev_turn_index,
                target_job, prev_question, chip_summary, candidate_summary, llm,
            ),
            pool.submit(
                _voice_task, session_factory, session_id, prev_turn_index,
                prev_asr_transcript, llm,
            ),
        ]
        wait(futures, timeout=30)
        # Surface any unexpected exceptions to logs (not propagated)
        for f in futures:
            try:
                f.result(timeout=0.1)
            except Exception as exc:
                logger.warning("parallel turn task raised: %s", exc)

    # Step 4: weakness profile from all turns so far
    db = session_factory()
    try:
        all_turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.session_id == session_id)
            .order_by(InterviewTurn.turn_index)
            .all()
        )
        score_jsons = [t.score_json for t in all_turns]
        weakness = compute_weakness(score_jsons)
        asked = [str(t.question or "") for t in all_turns if t.question]
    finally:
        db.close()

    # Step 5: pick next question
    next_q = pick_next_question(
        target_job=target_job,
        chip=chip,
        chip_summary=chip_summary,
        weakness=weakness,
        asked_questions=asked,
        turn_index=next_turn_index,
        llm=llm,
    )

    # Step 6: persist next turn row
    db = session_factory()
    try:
        existing = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=next_turn_index,
        ).one_or_none()
        if existing is None:
            db.add(InterviewTurn(
                session_id=session_id,
                user_key=user_key,
                turn_index=next_turn_index,
                target_job=target_job,
                question=next_q.question,
                question_source=next_q.source,
            ))
            db.commit()
    finally:
        db.close()

    return next_q
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_orchestrator.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview/orchestrator.py backend/tests/test_interview_orchestrator.py
git commit -m "feat(interview): orchestrator — parallel score/reference/voice + adaptive next-question"
```

---

## Task 11: Router — POST /turn streaming with new event types + first-turn bootstrap

**Files:**
- Modify: `backend/app/routers/interview.py`
- Create: `backend/tests/test_interview_router_turn.py`

The existing `/api/interview/turn` is sync SSE. We extend it to:
1. Use `process_turn_synchronous` to handle the just-finished turn (if any) and pick the next question.
2. Stream the next question text as `chunk` events, then a `turn_complete` event.
3. For the first turn (when `messages` is empty), skip the orchestrator and just pick the skeleton[0].

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_interview_router_turn.py`:

```python
"""Integration tests for the upgraded /api/interview/turn endpoint."""
import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import InterviewTurn


def _build_test_app():
    from app.routers import interview as interview_router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(interview_router.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def _parse_sse_events(body: str):
    """Parse SSE response body into a list of {type, ...} dicts."""
    events = []
    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"type": "raw", "value": payload})
    return events


def test_first_turn_emits_chunk_and_turn_complete_for_skeleton_question(monkeypatch):
    """When messages is empty (first turn), skeleton[0] is streamed."""
    client, SessionLocal = _build_test_app()

    response = client.post(
        "/api/interview/turn",
        json={
            "target_job": "default",
            "session_id": "test-sess-1",
            "messages": [],
        },
        headers={"X-Resume-User-Key": "u1"},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    # Expect at least: chunk (with delta) + turn_complete
    assert any(e.get("type") == "chunk" for e in events)
    complete_events = [e for e in events if e.get("type") == "turn_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["turn_index"] == 0
    assert "自我介绍" in complete_events[0]["question"]

    # Verify the row was persisted
    db = SessionLocal()
    try:
        rows = db.query(InterviewTurn).filter_by(session_id="test-sess-1").all()
        assert len(rows) == 1
        assert rows[0].question_source == "skeleton"
    finally:
        db.close()


def test_subsequent_turn_runs_orchestrator(monkeypatch):
    """When messages contains prior assistant + user pairs, process_turn fires."""
    client, SessionLocal = _build_test_app()

    # Seed: pretend turn 0 already happened
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="test-sess-2", user_key="u1", turn_index=0, target_job="default",
        question="请用 1-2 分钟做个自我介绍。", question_source="skeleton",
    ))
    db.commit()
    db.close()

    captured_calls = []

    def stub_process(**kwargs):
        captured_calls.append(kwargs)
        from app.services.interview.adaptive import NextQuestion
        return NextQuestion(question="第二题：讲一段你的项目。", source="skeleton")

    monkeypatch.setattr(
        "app.routers.interview.process_turn_synchronous",
        stub_process,
    )

    response = client.post(
        "/api/interview/turn",
        json={
            "target_job": "default",
            "session_id": "test-sess-2",
            "messages": [
                {"role": "assistant", "content": "请用 1-2 分钟做个自我介绍。"},
                {"role": "user", "content": "我叫张三，本科上交大..."},
            ],
        },
        headers={"X-Resume-User-Key": "u1"},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert any("第二题" in e.get("delta", "") for e in events if e.get("type") == "chunk")
    assert len(captured_calls) == 1
    assert captured_calls[0]["session_id"] == "test-sess-2"
    assert captured_calls[0]["prev_user_answer"] == "我叫张三，本科上交大..."


def test_turn_endpoint_records_user_key():
    client, SessionLocal = _build_test_app()
    client.post(
        "/api/interview/turn",
        json={"target_job": "default", "session_id": "uk1", "messages": []},
        headers={"X-Resume-User-Key": "owner-A"},
    )
    db = SessionLocal()
    try:
        row = db.query(InterviewTurn).filter_by(session_id="uk1").one()
        assert row.user_key == "owner-A"
    finally:
        db.close()
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_router_turn.py -v
```

Expected: All fail (router not yet updated).

- [ ] **Step 3: Replace `/turn` endpoint**

Open `backend/app/routers/interview.py`. Replace the existing `interview_turn` function (and its `safe_stream`) with the new implementation. Keep the `InterviewTurnIn` model but extend it with `session_id`:

```python
class InterviewTurnIn(BaseModel):
    target_job: str
    session_id: str = ''  # frontend UUID
    messages: list[InterviewMessage]
    asr_transcript: dict | None = None  # for the most-recent user answer (voice mode only)
```

Then replace the `interview_turn` function with:

```python
@router.post('/turn')
def interview_turn(
    body: InterviewTurnIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.adaptive import NextQuestion, pick_next_question
    from app.services.interview.orchestrator import process_turn_synchronous
    from app.services.interview.weakness_profile import WeaknessProfile
    from app.models import InterviewTurn
    from app.database import SessionLocal

    chip = body.target_job  # 1:1 for now; later: derive from a chip lookup table
    chip_summary = _load_chip_summary(db, chip)

    # Determine turn index from existing rows
    last_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == body.session_id)
        .order_by(InterviewTurn.turn_index.desc())
        .first()
    )

    is_first_turn = (last_turn is None) or not any(
        m.role == 'user' for m in body.messages
    )

    if is_first_turn:
        # Bootstrap: skeleton[0] picked offline (no LLM needed)
        next_q = pick_next_question(
            target_job=body.target_job,
            chip=chip,
            chip_summary=chip_summary,
            weakness=WeaknessProfile(),
            asked_questions=[],
            turn_index=0,
            llm=_NoopLLM(),  # never reached for skeleton index 0
        )
        next_turn_index = 0
        # Persist first turn row
        if last_turn is None:
            db.add(InterviewTurn(
                session_id=body.session_id,
                user_key=x_resume_user_key,
                turn_index=0,
                target_job=body.target_job,
                question=next_q.question,
                question_source=next_q.source,
            ))
            db.commit()
    else:
        prev_user_msg = next(
            (m for m in reversed(body.messages) if m.role == 'user'), None
        )
        prev_user_answer = prev_user_msg.content if prev_user_msg else ''
        prev_turn_index = int(last_turn.turn_index)
        next_turn_index = prev_turn_index + 1

        try:
            next_q = process_turn_synchronous(
                session_id=body.session_id,
                user_key=x_resume_user_key,
                target_job=body.target_job,
                chip=chip,
                chip_summary=chip_summary,
                prev_turn_index=prev_turn_index,
                prev_user_answer=prev_user_answer,
                prev_asr_transcript=body.asr_transcript or {},
                next_turn_index=next_turn_index,
                session_factory=SessionLocal,
            )
        except Exception as exc:
            logger.exception('process_turn failed: %s', exc)
            next_q = NextQuestion(
                question='请深入讲讲你最近完成的项目里你最自豪的一个细节。',
                source='fallback',
            )

    def event_stream():
        # Stream the next question text as chunks (so existing TTS-progress logic works)
        for ch in next_q.question:
            yield f'data: {json.dumps({"type":"chunk","delta":ch}, ensure_ascii=False)}\n\n'
        yield (
            f'data: {json.dumps({"type":"turn_complete","turn_index":next_turn_index,"question":next_q.question}, ensure_ascii=False)}\n\n'
        )

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )


class _NoopLLM:
    def chat_text(self, system, user, **_):
        raise RuntimeError('NoopLLM.chat_text should never be reached')
    def chat_json(self, system, user, **_):
        raise RuntimeError('NoopLLM.chat_json should never be reached')


def _load_chip_summary(db: Session, chip: str) -> str:
    """Load nowcoder chip summary by exact match. Empty string if not found."""
    row = (
        db.query(InterviewIntelKeyword)
        .filter(InterviewIntelKeyword.keyword == chip)
        .first()
    )
    return str(row.summary_md or '') if row else ''
```

Also add at the top of the file (next to existing imports):

```python
from app.services.interview.orchestrator import process_turn_synchronous
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_router_turn.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/interview.py backend/tests/test_interview_router_turn.py
git commit -m "feat(interview): /turn endpoint upgraded — orchestrator + new SSE event types"
```

---

## Task 12: New endpoints — GET /turns + GET /turns/latest-score

**Files:**
- Modify: `backend/app/routers/interview.py`
- Create: `backend/tests/test_interview_turns_endpoints.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_interview_turns_endpoints.py`:

```python
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import InterviewTurn


def _build_test_app():
    from app.routers import interview as interview_router
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(interview_router.router)
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def test_get_turns_returns_all_for_session():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add_all([
        InterviewTurn(session_id="s1", user_key="u1", turn_index=0, question="Q0", user_answer="A0"),
        InterviewTurn(session_id="s1", user_key="u1", turn_index=1, question="Q1", user_answer="A1"),
        InterviewTurn(session_id="other", user_key="u1", turn_index=0, question="Other"),
    ])
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s1/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    assert rows[0]["question"] == "Q0"
    assert rows[1]["question"] == "Q1"


def test_get_turns_rejects_mismatched_user_key():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s2", user_key="owner-A", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s2/turns", headers={"X-Resume-User-Key": "owner-B"})
    assert resp.status_code == 403


def test_get_turns_returns_empty_list_for_unknown_session():
    client, _ = _build_test_app()
    resp = client.get("/api/interview/sessions/nonexistent/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_latest_score_returns_most_recent_scored_turn():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    score = json.dumps({"overall": 70, "hits": [], "misses": ["量化"], "bonuses": []})
    db.add_all([
        InterviewTurn(session_id="s3", user_key="u1", turn_index=0, question="Q0", score_json=score),
        InterviewTurn(session_id="s3", user_key="u1", turn_index=1, question="Q1"),  # not scored
    ])
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s3/turns/latest-score",
        headers={"X-Resume-User-Key": "u1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["turn_index"] == 0
    assert "量化" in data["hint"]


def test_latest_score_returns_null_when_no_scored_turn():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s4", user_key="u1", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s4/turns/latest-score",
        headers={"X-Resume-User-Key": "u1"},
    )
    assert resp.status_code == 200
    assert resp.json() is None


def test_latest_score_rejects_mismatched_user_key():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s5", user_key="owner-A", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s5/turns/latest-score",
        headers={"X-Resume-User-Key": "owner-B"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_turns_endpoints.py -v
```

Expected: All fail (endpoints not yet defined).

- [ ] **Step 3: Add the two endpoints**

Append to `backend/app/routers/interview.py`:

```python
def _assert_session_owner_or_403(db: Session, session_id: str, user_key: str) -> None:
    """Reject if any turn for this session has a non-empty user_key that doesn't match.
    Empty user_key on existing turns → treated as legacy/orphan and accessible (Q5 hardening
    for accidentally created rows during dev). Demo sessions don't apply to interviews."""
    rows = (
        db.query(InterviewTurn.user_key)
        .filter(InterviewTurn.session_id == session_id)
        .distinct()
        .all()
    )
    for (existing_key,) in rows:
        existing = str(existing_key or '')
        if existing and existing != user_key:
            raise HTTPException(status_code=403, detail='SESSION_FORBIDDEN')


@router.get('/sessions/{session_id}/turns')
def get_session_turns(
    session_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    rows = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_index)
        .all()
    )
    out = []
    for r in rows:
        out.append({
            'turn_index': int(r.turn_index),
            'question': str(r.question or ''),
            'user_answer': str(r.user_answer or ''),
            'reference_answer': str(r.reference_answer or ''),
            'question_source': str(r.question_source or ''),
            'score': json.loads(r.score_json) if r.score_json else None,
            'voice_metrics': json.loads(r.voice_metrics) if r.voice_metrics else None,
            'created_at': r.created_at.isoformat() if r.created_at else '',
        })
    return out


@router.get('/sessions/{session_id}/turns/latest-score')
def get_latest_score(
    session_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    row = (
        db.query(InterviewTurn)
        .filter(
            InterviewTurn.session_id == session_id,
            InterviewTurn.score_json.isnot(None),
        )
        .order_by(InterviewTurn.turn_index.desc())
        .first()
    )
    if row is None:
        return None
    try:
        score = json.loads(row.score_json or '{}')
    except json.JSONDecodeError:
        return None
    misses = score.get('misses') or []
    if misses:
        hint = f'📌 你这次没提到 {misses[0]}'
    else:
        hits = score.get('hits') or []
        hint = f'✓ 这道答得不错，命中了 {hits[0]}' if hits else '本题已评分'
    return {'turn_index': int(row.turn_index), 'hint': hint}
```

Also import `InterviewTurn` at the top of the router file (next to the existing imports):

```python
from app.models import InterviewIntelKeyword, InterviewIntelPost, InterviewReport, InterviewTurn
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_turns_endpoints.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/interview.py backend/tests/test_interview_turns_endpoints.py
git commit -m "feat(interview): GET /sessions/{sid}/turns + /turns/latest-score with owner check"
```

---

## Task 13: Report aggregation — pull from interview_turns + weekly plan

**Files:**
- Modify: `backend/app/services/interview/report.py`
- Modify: `backend/app/routers/interview.py`
- Create: `backend/tests/test_interview_report_aggregation.py`

- [ ] **Step 1: Read existing report.py to understand current shape**

```bash
cat backend/app/services/interview/report.py
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_interview_report_aggregation.py`:

```python
import json
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewTurn
from app.services.interview.report import build_report_aggregate


def _make_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_turns(SessionLocal, session_id, user_key, count=3):
    db = SessionLocal()
    for i in range(count):
        db.add(InterviewTurn(
            session_id=session_id,
            user_key=user_key,
            turn_index=i,
            target_job="数据分析师",
            question=f"Q{i}",
            user_answer=f"A{i}",
            score_json=json.dumps({
                "overall": 60 + i * 10,
                "hits": ["量化"] if i > 0 else [],
                "misses": ["STAR 结构"],
                "bonuses": [],
            }),
        ))
    db.commit()
    db.close()


def test_build_report_aggregate_includes_turn_count_and_weakness_profile():
    SessionLocal = _make_db()
    _seed_turns(SessionLocal, "s1", "u1", count=3)

    llm = MagicMock()
    llm.chat_text.return_value = "你的整体表现尚可，**主要短板**是 STAR 结构。建议..."

    db = SessionLocal()
    try:
        result = build_report_aggregate(
            session_id="s1",
            target_job="数据分析师",
            db=db,
            llm=llm,
        )
    finally:
        db.close()

    assert result["turn_count"] == 3
    assert result["weakness_profile"]["avg_score"] == 70  # avg(60, 70, 80)
    assert "STAR 结构" in result["weakness_profile"]["weak_topics"]
    assert "STAR" in result["weekly_plan_md"]


def test_weekly_plan_falls_back_when_llm_fails():
    SessionLocal = _make_db()
    _seed_turns(SessionLocal, "s2", "u1", count=2)

    llm = MagicMock()
    llm.chat_text.side_effect = RuntimeError("network down")

    db = SessionLocal()
    try:
        result = build_report_aggregate(
            session_id="s2", target_job="x", db=db, llm=llm,
        )
    finally:
        db.close()

    assert result["weekly_plan_md"]  # non-empty (generic fallback)
    assert "建议" in result["weekly_plan_md"]


def test_build_report_aggregate_empty_session_returns_zeros():
    SessionLocal = _make_db()
    db = SessionLocal()
    try:
        result = build_report_aggregate(
            session_id="empty", target_job="x", db=db, llm=MagicMock(),
        )
    finally:
        db.close()
    assert result["turn_count"] == 0
    assert result["weakness_profile"]["avg_score"] is None
```

- [ ] **Step 3: Run failing tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_report_aggregation.py -v
```

Expected: All fail with ImportError on `build_report_aggregate`.

- [ ] **Step 4: Add `build_report_aggregate` to `report.py`**

Append to `backend/app/services/interview/report.py` (don't remove existing functions — they're still used elsewhere):

```python
import json
import logging
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.models import InterviewTurn
from app.services.interview.prompts import WEEKLY_PLAN_SYSTEM
from app.services.interview.weakness_profile import compute_weakness

logger = logging.getLogger(__name__)


_WEEKLY_PLAN_FALLBACK = (
    "本次面试反馈已生成。建议针对评分较低的题目对照范例答案重做一遍，"
    "并把每段经历都重新梳理一次量化结果与方法论。下次面试前对着镜子录音回听 2 次自我介绍。"
)


def build_report_aggregate(session_id: str, target_job: str, db: Session, llm) -> dict:
    """Aggregate one interview session's turn data into the report payload.

    Returns: {
        'turn_count': int,
        'weakness_profile': {...},
        'weekly_plan_md': str,
    }
    """
    rows = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_index)
        .all()
    )

    weakness = compute_weakness([r.score_json for r in rows])
    weakness_dict = asdict(weakness)

    weekly_plan_md = _generate_weekly_plan(target_job, weakness_dict, llm)

    return {
        'turn_count': len(rows),
        'weakness_profile': weakness_dict,
        'weekly_plan_md': weekly_plan_md,
    }


def _generate_weekly_plan(target_job: str, weakness_dict: dict, llm) -> str:
    user_payload = json.dumps({
        'target_job': target_job,
        'weakness_profile': weakness_dict,
    }, ensure_ascii=False)
    try:
        raw = llm.chat_text(system=WEEKLY_PLAN_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning('weekly plan LLM failed: %s', exc)
        return _WEEKLY_PLAN_FALLBACK
    if not isinstance(raw, str) or not raw.strip():
        return _WEEKLY_PLAN_FALLBACK
    return raw.strip()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_interview_report_aggregation.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Wire `build_report_aggregate` into the existing /report endpoint**

Find the existing `interview_report` endpoint in `backend/app/routers/interview.py`. Modify it to also call `build_report_aggregate` and persist the new fields:

Replace:

```python
    report = generate_interview_report(body.target_job, messages)
    row = InterviewReport(
        user_key=x_resume_user_key,
        target_job=body.target_job,
        transcript_json=json.dumps(messages, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        duration_seconds=body.duration_seconds,
        is_guest=1 if x_guest.strip().lower() in {'1', 'true', 'yes'} else 0,
        created_at=datetime.utcnow(),
    )
```

with:

```python
    from app.services.interview.report import build_report_aggregate
    from app.services.interview.llm_helpers import build_interview_llm_client

    report = generate_interview_report(body.target_job, messages)

    # New: aggregate from interview_turns + weekly plan
    session_id = getattr(body, 'session_id', '') or ''
    if session_id:
        try:
            llm = build_interview_llm_client()
            aggregate = build_report_aggregate(session_id, body.target_job, db, llm)
        except Exception as exc:
            logger.warning('report aggregate failed: %s', exc)
            aggregate = {'turn_count': 0, 'weakness_profile': None, 'weekly_plan_md': ''}
    else:
        aggregate = {'turn_count': 0, 'weakness_profile': None, 'weekly_plan_md': ''}

    row = InterviewReport(
        user_key=x_resume_user_key,
        target_job=body.target_job,
        transcript_json=json.dumps(messages, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        duration_seconds=body.duration_seconds,
        is_guest=1 if x_guest.strip().lower() in {'1', 'true', 'yes'} else 0,
        created_at=datetime.utcnow(),
        weakness_profile_json=json.dumps(aggregate['weakness_profile'], ensure_ascii=False) if aggregate['weakness_profile'] else None,
        weekly_plan_md=aggregate['weekly_plan_md'],
        turn_count=aggregate['turn_count'],
    )
```

Also extend `InterviewReportIn`:

```python
class InterviewReportIn(BaseModel):
    target_job: str
    session_id: str = ''
    messages: list[InterviewMessage]
    duration_seconds: int = 0
```

And extend the response from /report to include the new fields:

```python
    return {
        'id': row.id,
        'report': report,
        'turn_count': row.turn_count,
        'weakness_profile': aggregate['weakness_profile'],
        'weekly_plan_md': row.weekly_plan_md,
    }
```

Also extend `get_report` (the existing GET `/reports/{report_id}`) to include the new fields in its response:

```python
    return {
        'id': row.id,
        'target_job': row.target_job,
        'transcript': json.loads(row.transcript_json or '[]'),
        'report': json.loads(row.report_json or '{}'),
        'duration_seconds': row.duration_seconds,
        'created_at': row.created_at.isoformat() if row.created_at else '',
        'turn_count': int(row.turn_count or 0),
        'weakness_profile': json.loads(row.weakness_profile_json) if row.weakness_profile_json else None,
        'weekly_plan_md': str(row.weekly_plan_md or ''),
    }
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/interview/report.py backend/app/routers/interview.py backend/tests/test_interview_report_aggregation.py
git commit -m "feat(interview): /report aggregates from interview_turns + generates weekly plan"
```

---

## Task 14: Frontend — typed API client + new hooks

**Files:**
- Create: `resume-copilot-web/components/interview/api.ts`

- [ ] **Step 1: Write the API client module**

Create `resume-copilot-web/components/interview/api.ts`:

```typescript
// Typed API client for the upgraded interview endpoints.

const USER_KEY_STORAGE_KEY = 'jobradar.resumeCopilot.userKey';

function getUserKey(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(USER_KEY_STORAGE_KEY) || '';
}

export interface ScorePayload {
  overall: number | null;
  hits: string[];
  misses: string[];
  bonuses: string[];
}

export interface VoiceMetricsPayload {
  filler_rate: number | null;
  wpm: number | null;
  pause_count: number | null;
  response_latency_ms: number | null;
  confidence_score: number | null;
}

export interface TurnPayload {
  turn_index: number;
  question: string;
  user_answer: string;
  reference_answer: string;
  question_source: string;
  score: ScorePayload | null;
  voice_metrics: VoiceMetricsPayload | null;
  created_at: string;
}

export interface LatestScorePayload {
  turn_index: number;
  hint: string;
}

export interface InterviewReportPayload {
  id: number;
  target_job: string;
  transcript: { role: string; content: string }[];
  report: Record<string, unknown>;
  duration_seconds: number;
  created_at: string;
  turn_count: number;
  weakness_profile: {
    avg_score: number | null;
    weak_topics: string[];
    strong_topics: string[];
    gap_warnings: string[];
  } | null;
  weekly_plan_md: string;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export function getInterviewTurns(sessionId: string): Promise<TurnPayload[]> {
  return getJson<TurnPayload[]>(`/api/interview/sessions/${sessionId}/turns`);
}

export function getLatestScore(sessionId: string): Promise<LatestScorePayload | null> {
  return getJson<LatestScorePayload | null>(
    `/api/interview/sessions/${sessionId}/turns/latest-score`,
  );
}

export function getInterviewReport(reportId: number): Promise<InterviewReportPayload> {
  return getJson<InterviewReportPayload>(`/api/interview/reports/${reportId}`);
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd resume-copilot-web && npx tsc --noEmit
```

Expected: no errors mentioning the new file.

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/components/interview/api.ts
git commit -m "feat(interview-web): typed API client for turns + latest-score + report endpoints"
```

---

## Task 15: Frontend — LiveHintBar component + polling hook

**Files:**
- Create: `resume-copilot-web/components/interview/LiveHintBar.tsx`

- [ ] **Step 1: Write the LiveHintBar**

Create `resume-copilot-web/components/interview/LiveHintBar.tsx`:

```typescript
'use client';

import { useEffect, useRef, useState } from 'react';
import { getLatestScore, type LatestScorePayload } from './api';

const POLL_INTERVAL_MS = 1500;
const HINT_VISIBLE_MS = 4000;

export function LiveHintBar({
  sessionId,
  suppressed,
}: {
  sessionId: string;
  suppressed: boolean;  // hide while AI is speaking (Border Beam visible)
}) {
  const [hint, setHint] = useState<string>('');
  const [visible, setVisible] = useState(false);
  const lastShownTurnRef = useRef<number>(-1);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const result: LatestScorePayload | null = await getLatestScore(sessionId);
        if (cancelled || !result) return;
        if (result.turn_index <= lastShownTurnRef.current) return;
        lastShownTurnRef.current = result.turn_index;
        setHint(result.hint);
        setVisible(true);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
        hideTimerRef.current = setTimeout(() => setVisible(false), HINT_VISIBLE_MS);
      } catch {
        // silent — polling errors don't surface
      }
    };
    const interval = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [sessionId]);

  if (suppressed || !visible || !hint) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: 'calc(100% + 12px)',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(201, 100, 66, 0.12)',
        border: '1px solid rgba(201, 100, 66, 0.3)',
        borderRadius: 12,
        padding: '8px 16px',
        fontSize: 13,
        color: 'var(--terracotta, #c96442)',
        whiteSpace: 'nowrap',
        animation: 'live-hint-fade 4s ease-in-out',
        pointerEvents: 'none',
      }}
    >
      {hint}
      <style jsx>{`
        @keyframes live-hint-fade {
          0% { opacity: 0; transform: translateX(-50%) translateY(-4px); }
          15% { opacity: 1; transform: translateX(-50%) translateY(0); }
          85% { opacity: 1; transform: translateX(-50%) translateY(0); }
          100% { opacity: 0; transform: translateX(-50%) translateY(-4px); }
        }
      `}</style>
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd resume-copilot-web && npx tsc --noEmit
```

Expected: no errors mentioning the new file.

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/components/interview/LiveHintBar.tsx
git commit -m "feat(interview-web): LiveHintBar — 1.5s poll + 4s fade hint card"
```

---

## Task 16: Frontend — wire LiveHintBar + new SSE event handler into interview page

**Files:**
- Modify: `resume-copilot-web/app/interview/[sessionId]/page.tsx`

- [ ] **Step 1: Read current interview page to find the right insertion points**

```bash
grep -n "fetch.*interview/turn\|caption\|isThinking" resume-copilot-web/app/interview/[sessionId]/page.tsx | head -20
```

- [ ] **Step 2: Add `<LiveHintBar/>` mount**

Find the JSX section that renders the AI orb / caption banner. Inside the same `position: relative` parent that holds the Border Beam, mount `<LiveHintBar/>` so it positions itself relative to that container.

Add at the top of `page.tsx`:

```typescript
import { LiveHintBar } from '@/components/interview/LiveHintBar';
```

In the JSX (find the section with the Border Beam or caption banner — it has `position: 'relative'` styling), add as a sibling:

```tsx
<LiveHintBar sessionId={sessionId} suppressed={turnInFlight} />
```

The `turnInFlight` boolean already exists in this component (it suppresses the hint while the AI is mid-stream).

- [ ] **Step 3: Update SSE handler to recognize new event types**

Find the existing SSE response parser. The current handler treats every `data:` line as raw text to append to the caption. Replace it with this branched handler:

```typescript
function handleSSEMessage(rawLine: string, onChunk: (delta: string) => void, onTurnComplete: (idx: number, q: string) => void) {
  if (!rawLine.startsWith('data:')) return;
  const payload = rawLine.slice(5).trim();
  if (!payload) return;
  // Try JSON first (new event types). If parse fails, treat as legacy raw text.
  try {
    const event = JSON.parse(payload) as { type?: string; delta?: string; turn_index?: number; question?: string };
    if (event.type === 'chunk' && typeof event.delta === 'string') {
      onChunk(event.delta);
    } else if (event.type === 'turn_complete' && typeof event.turn_index === 'number' && typeof event.question === 'string') {
      onTurnComplete(event.turn_index, event.question);
    }
  } catch {
    // Legacy: treat the whole payload as a chunk delta
    onChunk(payload);
  }
}
```

Wire `onTurnComplete` to update local turn state (advance progress rail, switch UI to "awaiting answer" mode).

- [ ] **Step 4: Lint + build**

```bash
cd resume-copilot-web && npm run lint 2>&1 | tail -10
cd resume-copilot-web && npm run build 2>&1 | tail -20
```

Expected: 0 lint errors related to new code, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/app/interview/[sessionId]/page.tsx
git commit -m "feat(interview-web): wire LiveHintBar + branched SSE event handler in interview page"
```

---

## Task 17: Frontend — new report page

**Files:**
- Create: `resume-copilot-web/app/interview/[sessionId]/report/page.tsx`

- [ ] **Step 1: Write the report page**

Create `resume-copilot-web/app/interview/[sessionId]/report/page.tsx`:

```typescript
'use client';

import { use, useEffect, useState } from 'react';
import {
  getInterviewTurns,
  getInterviewReport,
  type InterviewReportPayload,
  type TurnPayload,
} from '@/components/interview/api';

export default function InterviewReportPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const [turns, setTurns] = useState<TurnPayload[]>([]);
  const [report, setReport] = useState<InterviewReportPayload | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const turnsResult = await getInterviewTurns(sessionId);
        if (!cancelled) setTurns(turnsResult);
        // Find report id from URL or query param
        const params = new URLSearchParams(window.location.search);
        const reportId = params.get('reportId');
        if (reportId) {
          const reportResult = await getInterviewReport(parseInt(reportId, 10));
          if (!cancelled) setReport(reportResult);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId]);

  if (error) return <main style={{ padding: 32 }}>加载失败：{error}</main>;

  return (
    <main
      style={{
        maxWidth: 880,
        margin: '0 auto',
        padding: '40px 24px',
        fontFamily: 'var(--font-fraunces, Fraunces), serif',
      }}
    >
      <h1 style={{ fontSize: 32, marginBottom: 24 }}>面试反馈</h1>

      {report?.weakness_profile && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>整体表现</h2>
          <div style={{ fontSize: 56, fontWeight: 600, color: 'var(--terracotta, #c96442)' }}>
            {report.weakness_profile.avg_score ?? '—'}
            <span style={{ fontSize: 18, opacity: 0.6 }}> /100</span>
          </div>
          {report.weakness_profile.weak_topics.length > 0 && (
            <p style={{ marginTop: 16 }}>
              <strong>重点提升：</strong>
              {report.weakness_profile.weak_topics.join('、')}
            </p>
          )}
          {report.weakness_profile.strong_topics.length > 0 && (
            <p>
              <strong>已展现的强项：</strong>
              {report.weakness_profile.strong_topics.join('、')}
            </p>
          )}
        </section>
      )}

      <section style={cardStyle}>
        <h2 style={sectionHeaderStyle}>逐题回放</h2>
        {turns.length === 0 && <p style={{ opacity: 0.6 }}>没有可显示的题目记录。</p>}
        {turns.map((t) => (
          <details key={t.turn_index} style={detailStyle}>
            <summary style={summaryStyle}>
              <span>第 {t.turn_index + 1} 题</span>
              {t.score?.overall != null && (
                <span style={{ marginLeft: 'auto', fontWeight: 600 }}>
                  {t.score.overall}/100
                </span>
              )}
            </summary>
            <div style={{ paddingTop: 16 }}>
              <p><strong>题目：</strong>{t.question}</p>
              <p><strong>你的回答：</strong>{t.user_answer || <em style={{opacity:0.5}}>（未作答）</em>}</p>

              {t.score && (
                <div style={scoreCardStyle}>
                  {t.score.hits.length > 0 && (
                    <div>
                      <strong style={{ color: '#16a34a' }}>✓ 命中</strong>
                      <div>{t.score.hits.join('、')}</div>
                    </div>
                  )}
                  {t.score.misses.length > 0 && (
                    <div>
                      <strong style={{ color: '#dc2626' }}>✗ 缺失</strong>
                      <div>{t.score.misses.join('、')}</div>
                    </div>
                  )}
                  {t.score.bonuses.length > 0 && (
                    <div>
                      <strong style={{ color: '#ca8a04' }}>★ 加分</strong>
                      <div>{t.score.bonuses.join('、')}</div>
                    </div>
                  )}
                </div>
              )}

              {t.reference_answer && (
                <div style={referenceStyle}>
                  <strong>📖 如果是面霸会怎么答</strong>
                  <p style={{ marginTop: 8 }}>{t.reference_answer}</p>
                </div>
              )}

              {t.voice_metrics && t.voice_metrics.wpm != null && (
                <div style={{ marginTop: 12, fontSize: 12, opacity: 0.7 }}>
                  语速 {t.voice_metrics.wpm} 字/分
                  {t.voice_metrics.filler_rate != null && ` · 填充词 ${t.voice_metrics.filler_rate}/分钟`}
                  {t.voice_metrics.confidence_score != null && ` · 自信度 ${t.voice_metrics.confidence_score}/100`}
                </div>
              )}
            </div>
          </details>
        ))}
      </section>

      {/* Voice averages (if any turn had voice metrics) */}
      {turns.some((t) => t.voice_metrics?.wpm != null) && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>语音表现</h2>
          {(() => {
            const voiceTurns = turns.filter((t) => t.voice_metrics?.wpm != null);
            const avgWpm = Math.round(
              voiceTurns.reduce((s, t) => s + (t.voice_metrics!.wpm ?? 0), 0) / voiceTurns.length,
            );
            return <p>平均语速 {avgWpm} 字/分（理想区间 200-260 字/分）</p>;
          })()}
        </section>
      )}

      {report?.weekly_plan_md && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>本周练习计划</h2>
          <p style={{ lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{report.weekly_plan_md}</p>
        </section>
      )}
    </main>
  );
}

const cardStyle: React.CSSProperties = {
  background: 'var(--paper, #fff)',
  borderRadius: 16,
  padding: 24,
  marginBottom: 16,
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
};
const sectionHeaderStyle: React.CSSProperties = {
  fontSize: 20,
  marginBottom: 16,
  borderBottom: '1px solid var(--border, #e5e5e5)',
  paddingBottom: 8,
};
const detailStyle: React.CSSProperties = {
  borderBottom: '1px solid var(--border, #e5e5e5)',
  padding: '12px 0',
};
const summaryStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  cursor: 'pointer',
  fontSize: 16,
  fontWeight: 500,
};
const scoreCardStyle: React.CSSProperties = {
  background: 'rgba(201, 100, 66, 0.05)',
  borderRadius: 12,
  padding: 16,
  marginTop: 12,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};
const referenceStyle: React.CSSProperties = {
  background: 'rgba(245, 158, 11, 0.08)',
  borderLeft: '3px solid #ca8a04',
  borderRadius: 8,
  padding: 16,
  marginTop: 12,
};
```

- [ ] **Step 2: Lint + build**

```bash
cd resume-copilot-web && npm run lint 2>&1 | tail -10
cd resume-copilot-web && npm run build 2>&1 | tail -20
```

Expected: 0 lint errors related to new file, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/app/interview/[sessionId]/report/page.tsx
git commit -m "feat(interview-web): new report page with per-turn breakdown + voice + weekly plan"
```

---

## Task 18: E2E fake interview test

**Files:**
- Create: `backend/tests/test_e2e_fake_interview.py`

- [ ] **Step 1: Write the E2E test**

Create `backend/tests/test_e2e_fake_interview.py`:

```python
"""End-to-end test of a 12-turn fake interview.

Mocks the LLM stack entirely, walks through 12 turns of POST /turn,
finishes with POST /report, and verifies the resulting report
contains scoring + reference + voice + weekly_plan data.
"""
import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import InterviewTurn, InterviewReport


def _build_test_app():
    from app.routers import interview as interview_router
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(interview_router.router)
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


class _FakeLLM:
    """Returns plausible answers for any LLM call."""
    def chat_json(self, system, user, **_):
        # Always returns a moderate score
        return {"overall": 65, "hits": ["项目经验"], "misses": ["量化结果"], "bonuses": []}

    def chat_text(self, system, user, **_):
        # Use the system prompt to figure out what's being asked
        if "范例答案" in system:
            return "在某次实习中，我用 STAR 结构讲清了背景行动结果，包含一个量化指标。"
        if "follow-up" in system or "下一题" in system:
            return "你说的那个项目里你具体的贡献是什么？"
        if "练习建议" in system or "整体表现" in system:
            return "你的整体表现尚可，**主要短板**是量化结果。建议针对每段经历都加上一个具体数字。"
        if "自信度" in system:
            return "70"
        return "..."


def test_full_12_turn_interview_to_report():
    client, SessionLocal = _build_test_app()
    sid = "e2e-sess"
    user_key = "e2e-user"
    target_job = "default"

    # Turn 1: bootstrap (empty messages)
    response = client.post(
        "/api/interview/turn",
        json={"target_job": target_job, "session_id": sid, "messages": []},
        headers={"X-Resume-User-Key": user_key},
    )
    assert response.status_code == 200

    # Run 11 more turns
    messages = []
    db = SessionLocal()
    first_turn = db.query(InterviewTurn).filter_by(session_id=sid, turn_index=0).one()
    messages.append({"role": "assistant", "content": str(first_turn.question)})
    db.close()

    with patch(
        "app.services.interview.orchestrator.build_interview_llm_client",
        return_value=_FakeLLM(),
    ), patch(
        "app.services.interview.report.build_interview_llm_client",
        return_value=_FakeLLM(),
    ) if False else patch.object(
        # Easier: monkey-patch the module-level client builders by attaching the fake to llm parameter directly
        # Instead we monkeypatch process_turn_synchronous's default llm via the import inside it
        # See test_interview_orchestrator for the established pattern
        __import__('app.services.interview.orchestrator', fromlist=['']),
        'build_interview_llm_client',
        lambda: _FakeLLM(),
    ):
        for i in range(1, 12):
            messages.append({"role": "user", "content": f"我的第 {i} 个回答内容..."})
            response = client.post(
                "/api/interview/turn",
                json={
                    "target_job": target_job,
                    "session_id": sid,
                    "messages": messages,
                    "asr_transcript": {
                        "audio_duration_s": 30.0,
                        "segments": [{"start_s": 0.5, "end_s": 28.0, "text": "嗯 我做过一个项目"}],
                    },
                },
                headers={"X-Resume-User-Key": user_key},
            )
            assert response.status_code == 200
            # Extract the next question from turn_complete event
            for line in response.text.split("\n"):
                if line.startswith("data:") and "turn_complete" in line:
                    payload = json.loads(line[5:].strip())
                    messages.append({"role": "assistant", "content": payload["question"]})
                    break

    # POST /report — uses the existing endpoint (we mock build_interview_llm_client here too)
    with patch(
        "app.routers.interview.build_interview_llm_client",
        return_value=_FakeLLM(),
    ) if False else patch(
        "app.services.interview.report._generate_weekly_plan",
        return_value="本周建议：针对量化结果重做 3 次自我介绍。",
    ):
        report_response = client.post(
            "/api/interview/report",
            json={
                "target_job": target_job,
                "session_id": sid,
                "messages": messages,
                "duration_seconds": 600,
            },
            headers={"X-Resume-User-Key": user_key},
        )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["turn_count"] >= 10
    assert report["weakness_profile"] is not None
    assert report["weakness_profile"]["avg_score"] is not None
    assert "量化" in report["weekly_plan_md"]

    # Verify GET /turns includes scored turns
    turns_response = client.get(
        f"/api/interview/sessions/{sid}/turns",
        headers={"X-Resume-User-Key": user_key},
    )
    assert turns_response.status_code == 200
    turns = turns_response.json()
    scored_turns = [t for t in turns if t["score"] is not None]
    assert len(scored_turns) >= 5  # at least half should have scores
```

- [ ] **Step 2: Run the E2E test**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_e2e_fake_interview.py -v
```

Expected: passes (may need 10-30s).

- [ ] **Step 3: Run full backend suite to verify no regressions**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py -q 2>&1 | tail -10
```

Expected: All tests pass (existing 250+ plus the new ones from this plan).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_e2e_fake_interview.py
git commit -m "test(interview): e2e — 12-turn fake interview through report aggregation"
```

---

## Task 19: Final lint + build + smoke

- [ ] **Step 1: Backend full test suite**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py -q 2>&1 | tail -10
```

Expected: all green.

- [ ] **Step 2: Frontend lint + build**

```bash
cd resume-copilot-web && npm run lint 2>&1 | tail -10
cd resume-copilot-web && npm run build 2>&1 | tail -20
```

Expected: 0 lint errors related to new code, build succeeds.

- [ ] **Step 3: Local smoke test (optional but recommended before VPS deploy)**

Start backend + frontend dev servers. Manually walk through:
- Open `/interview` → pick a chip → start interview
- Answer first question (voice or text)
- Verify: live hint appears within 2-3s of submitting
- Complete 3-4 turns
- Click "结束面试" → land on `/interview/[sessionId]/report`
- Verify: per-turn replay expands cleanly, voice metrics show (if voice mode), weekly plan renders

- [ ] **Step 4: Deploy to VPS using jobradar-vps-deploy skill**

(skill is auto-triggered when user asks to deploy)

---

## Self-Review

(Final review per skill checklist before handoff to subagent.)

### Spec coverage check
- ✓ Task 1 covers data model (interview_turns + InterviewReport extension)
- ✓ Task 2 covers voice_metrics deterministic features
- ✓ Task 3 covers weakness_profile aggregation
- ✓ Task 4 covers prompt files (cache-friendly system prompts)
- ✓ Task 5 covers scoring.py with Q5 hardening
- ✓ Task 6 covers reference_answer.py
- ✓ Task 7 covers confidence sub-call (LLM)
- ✓ Task 8 covers adaptive picker (skeleton + follow-up + fallback)
- ✓ Task 9 covers LLM client helpers
- ✓ Task 10 covers orchestrator with ThreadPoolExecutor parallel fan-out
- ✓ Task 11 covers /turn SSE event-type extension
- ✓ Task 12 covers GET /turns + GET /turns/latest-score with owner check
- ✓ Task 13 covers report aggregation + weekly plan
- ✓ Task 14 covers frontend typed API client
- ✓ Task 15 covers LiveHintBar component
- ✓ Task 16 covers wiring into interview page
- ✓ Task 17 covers new report page
- ✓ Task 18 covers E2E test
- ✓ Task 19 covers final verification + deploy
- All 4 features (per-Q scoring, adaptive, voice, weekly plan) have a task; UI delivery model (live hint + final report) covered by Tasks 15+17.

### Placeholder scan
- No "TBD" / "TODO" / "implement later" — all code is concrete
- No "add appropriate error handling" — Q5 hardening pattern shown explicitly in each LLM-call module
- No "tests for the above" without actual test code — every test step has runnable Python

### Type consistency
- `ScoreResult` shape consistent across Tasks 5, 10, 13
- `VoiceMetrics` shape consistent across Tasks 2, 7, 10
- `NextQuestion` consistent across Tasks 8, 10, 11
- `InterviewTurn` model fields consistent across Tasks 1, 10, 11, 12, 13, 14
- `chat_json` / `chat_text` method signatures consistent across Tasks 5, 6, 7, 8, 9, 10

Plan ready for execution.
