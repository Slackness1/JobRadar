# Mock Interview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone mock interview feature — user types a target job, conducts a conversational interview with LLM follow-ups, and gets a structured feedback report at the end.

**Architecture:** Client-side conversation state (React + LocalStorage) proxied through FastAPI streaming endpoints to DeepSeek. Only the final report is persisted to SQLite. The Next.js `/api/*` rewrite passes streaming responses through transparently.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js 16 App Router + Tailwind CSS 4 (frontend), DeepSeek streaming API via urllib SSE, SQLite via existing `schema_patch.py`.

---

## File Map

### Backend (new / modified)
| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/models.py` | Add `InterviewReport` ORM model |
| Modify | `backend/app/services/schema_patch.py` | Add `interview_reports` DDL |
| Create | `backend/app/services/interview/__init__.py` | Package marker |
| Create | `backend/app/services/interview/llm.py` | System prompt builder + SSE streaming generator |
| Create | `backend/app/services/interview/report.py` | Report LLM call + JSON parsing |
| Create | `backend/app/routers/interview.py` | 4 endpoints: /turn /report /reports /reports/{id} |
| Modify | `backend/app/main.py` | Register interview router |
| Create | `backend/tests/test_interview_service.py` | Unit tests for prompt + report parsing |

### Frontend (new)
| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `resume-copilot-web/components/interview/types.ts` | TS types for messages, report |
| Create | `resume-copilot-web/components/interview/api.ts` | fetch helpers + SSE streaming helper |
| Create | `resume-copilot-web/components/interview/InterviewChat.tsx` | Chat bubble stream + typing indicator |
| Create | `resume-copilot-web/components/interview/InterviewReport.tsx` | Score ring + dimension bars + highlights |
| Create | `resume-copilot-web/app/interview/page.tsx` | Setup page (job input) |
| Create | `resume-copilot-web/app/interview/[sessionId]/page.tsx` | Main interview + report page |

---

## Task 1: DB Model + Schema Patch

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/schema_patch.py`

- [ ] **Step 1: Add `InterviewReport` model to `models.py`**

Append at the end of `backend/app/models.py`:

```python
class InterviewReport(Base):
    __tablename__ = 'interview_reports'

    id = Column(Integer, primary_key=True, index=True)
    user_key = Column(Text, nullable=False, index=True)
    target_job = Column(Text, nullable=False)
    transcript_json = Column(Text, default='[]')
    report_json = Column(Text, default='{}')
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Add DDL to `schema_patch.py`**

At the end of `ensure_compatible_schema()` function (just before `conn.commit()` or the final `pass`), add:

```python
        interview_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_reports'")
        ).fetchone()
        if not interview_exists:
            conn.execute(text(
                """
                CREATE TABLE interview_reports (
                    id INTEGER PRIMARY KEY,
                    user_key TEXT NOT NULL,
                    target_job TEXT NOT NULL,
                    transcript_json TEXT DEFAULT '[]',
                    report_json TEXT DEFAULT '{}',
                    duration_seconds INTEGER DEFAULT 0,
                    created_at DATETIME
                )
                """
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_interview_reports_user_key ON interview_reports (user_key)"
            ))
```

- [ ] **Step 3: Verify table is created on startup**

```bash
cd backend
PYTHONPATH=. .venv/bin/python -c "
from app.services.schema_patch import ensure_compatible_schema
from app.database import engine
ensure_compatible_schema(engine)
from sqlalchemy import inspect
insp = inspect(engine)
assert 'interview_reports' in insp.get_table_names(), 'Table not created'
print('OK: interview_reports table exists')
"
```

Expected: `OK: interview_reports table exists`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models.py backend/app/services/schema_patch.py
git commit -m "feat(interview): add InterviewReport model and schema patch"
```

---

## Task 2: LLM Service — Streaming Turn + Report Generation

**Files:**
- Create: `backend/app/services/interview/__init__.py`
- Create: `backend/app/services/interview/llm.py`
- Create: `backend/app/services/interview/report.py`
- Create: `backend/tests/test_interview_service.py`

- [ ] **Step 1: Create package marker**

```bash
touch backend/app/services/interview/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_interview_service.py`:

```python
import json
import pytest

from app.services.interview.llm import build_interview_system_prompt, INTERVIEW_END_MARKER
from app.services.interview.report import parse_report_json


def test_system_prompt_contains_target_job():
    prompt = build_interview_system_prompt("蚂蚁集团数据分析师")
    assert "蚂蚁集团数据分析师" in prompt


def test_system_prompt_contains_end_marker():
    prompt = build_interview_system_prompt("test job")
    assert INTERVIEW_END_MARKER in prompt


def test_system_prompt_mentions_behavioral_questions():
    prompt = build_interview_system_prompt("test job")
    assert "行为" in prompt


def test_parse_report_json_valid():
    raw = json.dumps({
        "overall_score": 78,
        "dimensions": [
            {"name": "表达清晰度", "score": 80, "comment": "清晰"},
            {"name": "逻辑结构", "score": 75, "comment": "较好"},
            {"name": "岗位匹配度", "score": 82, "comment": "匹配"},
            {"name": "抗压表现", "score": 70, "comment": "一般"},
        ],
        "highlights": ["亮点1"],
        "improvements": ["改进1"],
        "overall_comment": "总体不错",
    })
    result = parse_report_json(raw)
    assert result["overall_score"] == 78
    assert len(result["dimensions"]) == 4
    assert result["highlights"] == ["亮点1"]


def test_parse_report_json_clamps_score():
    raw = json.dumps({"overall_score": 150, "dimensions": [], "highlights": [], "improvements": [], "overall_comment": ""})
    result = parse_report_json(raw)
    assert result["overall_score"] == 100


def test_parse_report_json_handles_missing_fields():
    raw = json.dumps({})
    result = parse_report_json(raw)
    assert "overall_score" in result
    assert "dimensions" in result
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/test_interview_service.py -v 2>&1 | tail -15
```

Expected: ImportError / ModuleNotFoundError (files don't exist yet).

- [ ] **Step 4: Create `backend/app/services/interview/llm.py`**

```python
import json
from typing import Iterator
from urllib import request as urllib_request

from app.services.resume_copilot.llm import build_resume_llm_client

INTERVIEW_END_MARKER = '[INTERVIEW_END]'

_TURN_LIMIT = 14


def build_interview_system_prompt(target_job: str) -> str:
    return f"""你是一位专业的校招面试官，正在对一名应届生进行一对一面试。
目标岗位：{target_job}

## 面试规则
1. 前 3 轮出行为类问题（如"介绍一个你主导过的项目"、"描述一次你解决团队冲突的经历"）
2. 第 4 轮起穿插岗位专项问题，根据目标岗位选择技术或业务方向题
3. 根据候选人的回答决定：深挖追问 还是 切换下一题
4. 每次只问一个问题，语气专业但不刻板，不提前评价候选人表现
5. 累计对话达到 {_TURN_LIMIT} 轮后，给出一句简短的收尾语，并在消息末尾追加标记：{INTERVIEW_END_MARKER}
6. 如候选人主动说"结束面试"，立即收尾并追加 {INTERVIEW_END_MARKER}

## 开场
第一条消息：用一句话介绍自己的面试官身份，然后直接提出第一个行为类问题。"""


def stream_interview_turn(target_job: str, messages: list[dict]) -> Iterator[str]:
    """Yields raw SSE lines proxied from the LLM streaming response."""
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'stream': True,
        'messages': [
            {'role': 'system', 'content': build_interview_system_prompt(target_job)},
            *messages,
        ],
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
    with urllib_request.urlopen(req, timeout=client.timeout_seconds) as response:
        for raw_line in response:
            line = raw_line.decode('utf-8').rstrip('\n')
            if line:
                yield line + '\n'
```

- [ ] **Step 5: Create `backend/app/services/interview/report.py`**

```python
import json
from urllib import request as urllib_request

from app.services.resume_copilot.llm import build_resume_llm_client

_REPORT_SYSTEM_PROMPT = """你是一位专业的面试评估官。根据以下面试记录，给出结构化的反馈报告。

严格返回 JSON，格式如下：
{
  "overall_score": <0-100整数>,
  "dimensions": [
    {"name": "表达清晰度", "score": <0-100>, "comment": "<一句话评价>"},
    {"name": "逻辑结构",   "score": <0-100>, "comment": "<一句话评价>"},
    {"name": "岗位匹配度", "score": <0-100>, "comment": "<一句话评价>"},
    {"name": "抗压表现",   "score": <0-100>, "comment": "<一句话评价>"}
  ],
  "highlights": ["<亮点1>", "<亮点2>"],
  "improvements": ["<改进点1>", "<改进点2>"],
  "overall_comment": "<2-3句总体评价>"
}"""


def generate_interview_report(target_job: str, messages: list[dict]) -> dict:
    transcript = '\n'.join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}"
        for m in messages
    )
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': _REPORT_SYSTEM_PROMPT},
            {'role': 'user', 'content': f'目标岗位：{target_job}\n\n面试记录：\n{transcript}'},
        ],
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
    with urllib_request.urlopen(req, timeout=client.timeout_seconds) as response:
        body = json.loads(response.read().decode('utf-8'))
    raw = body['choices'][0]['message']['content']
    return parse_report_json(raw)


def parse_report_json(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        data = {}

    overall = data.get('overall_score', 0)
    if not isinstance(overall, (int, float)):
        overall = 0
    overall = max(0, min(100, int(overall)))

    dimensions = data.get('dimensions', [])
    if not isinstance(dimensions, list):
        dimensions = []
    normalized_dims = []
    for d in dimensions:
        if not isinstance(d, dict):
            continue
        score = d.get('score', 0)
        if not isinstance(score, (int, float)):
            score = 0
        normalized_dims.append({
            'name': str(d.get('name', '')),
            'score': max(0, min(100, int(score))),
            'comment': str(d.get('comment', '')),
        })

    return {
        'overall_score': overall,
        'dimensions': normalized_dims,
        'highlights': [str(h) for h in data.get('highlights', []) if h],
        'improvements': [str(i) for i in data.get('improvements', []) if i],
        'overall_comment': str(data.get('overall_comment', '')),
    }
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/test_interview_service.py -v 2>&1 | tail -15
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/interview/ backend/tests/test_interview_service.py
git commit -m "feat(interview): add LLM streaming turn + report generation service"
```

---

## Task 3: Backend Router

**Files:**
- Create: `backend/app/routers/interview.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/routers/interview.py`**

```python
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InterviewReport
from app.services.interview.llm import stream_interview_turn
from app.services.interview.report import generate_interview_report

router = APIRouter(prefix='/api/interview', tags=['interview'])


class InterviewMessage(BaseModel):
    role: str
    content: str


class InterviewTurnIn(BaseModel):
    target_job: str
    messages: list[InterviewMessage]


class InterviewReportIn(BaseModel):
    target_job: str
    messages: list[InterviewMessage]
    duration_seconds: int = 0


@router.post('/turn')
def interview_turn(
    body: InterviewTurnIn,
    x_resume_user_key: str = Header(default=''),
):
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]
    return StreamingResponse(
        stream_interview_turn(body.target_job, messages),
        media_type='text/event-stream',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )


@router.post('/report')
def interview_report(
    body: InterviewReportIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]
    report = generate_interview_report(body.target_job, messages)
    row = InterviewReport(
        user_key=x_resume_user_key,
        target_job=body.target_job,
        transcript_json=json.dumps(messages, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        duration_seconds=body.duration_seconds,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'report': report}


@router.get('/reports')
def list_reports(
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    if not x_resume_user_key:
        return []
    rows = (
        db.query(InterviewReport)
        .filter(InterviewReport.user_key == x_resume_user_key)
        .order_by(InterviewReport.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            'id': r.id,
            'target_job': r.target_job,
            'duration_seconds': r.duration_seconds,
            'overall_score': json.loads(r.report_json or '{}').get('overall_score', 0),
            'created_at': r.created_at.isoformat() if r.created_at else '',
        }
        for r in rows
    ]


@router.get('/reports/{report_id}')
def get_report(
    report_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    row = db.query(InterviewReport).filter(InterviewReport.id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Report not found')
    if row.user_key != x_resume_user_key:
        raise HTTPException(status_code=403, detail='Forbidden')
    return {
        'id': row.id,
        'target_job': row.target_job,
        'transcript': json.loads(row.transcript_json or '[]'),
        'report': json.loads(row.report_json or '{}'),
        'duration_seconds': row.duration_seconds,
        'created_at': row.created_at.isoformat() if row.created_at else '',
    }
```

- [ ] **Step 2: Register router in `backend/app/main.py`**

Add import alongside the other routers (around line 22):
```python
from app.routers import interview
```

Add include_router after line 88:
```python
app.include_router(interview.router)
```

- [ ] **Step 3: Smoke-test the router starts without errors**

```bash
cd backend
PYTHONPATH=. .venv/bin/python -c "
from app.main import app
routes = [r.path for r in app.routes]
assert any('/api/interview/turn' in r for r in routes), 'Route not registered'
assert any('/api/interview/report' in r for r in routes), 'Route not registered'
print('OK:', [r for r in routes if 'interview' in r])
"
```

Expected: prints the 4 interview routes.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/interview.py backend/app/main.py
git commit -m "feat(interview): add interview router with turn/report/reports endpoints"
```

---

## Task 4: Frontend Types + API Helpers

**Files:**
- Create: `resume-copilot-web/components/interview/types.ts`
- Create: `resume-copilot-web/components/interview/api.ts`

- [ ] **Step 1: Create `resume-copilot-web/components/interview/types.ts`**

```typescript
export type InterviewRole = 'user' | 'assistant';

export interface InterviewMessage {
  role: InterviewRole;
  content: string;
}

export interface ReportDimension {
  name: string;
  score: number;
  comment: string;
}

export interface InterviewReport {
  overall_score: number;
  dimensions: ReportDimension[];
  highlights: string[];
  improvements: string[];
  overall_comment: string;
}

export interface InterviewReportRow {
  id: number;
  target_job: string;
  duration_seconds: number;
  overall_score: number;
  created_at: string;
}

export interface SavedReport {
  id: number;
  target_job: string;
  transcript: InterviewMessage[];
  report: InterviewReport;
  duration_seconds: number;
  created_at: string;
}

export type InterviewState =
  | 'interviewing'
  | 'wrapping_up'
  | 'generating_report'
  | 'report_ready';
```

- [ ] **Step 2: Create `resume-copilot-web/components/interview/api.ts`**

```typescript
import type { InterviewMessage, InterviewReport, InterviewReportRow, SavedReport } from './types';

const USER_KEY_STORAGE_KEY = 'jobradar.resumeCopilot.userKey';

function getUserKey(): string {
  if (typeof window === 'undefined') return '';
  let key = window.localStorage.getItem(USER_KEY_STORAGE_KEY) || '';
  if (!key) {
    key = crypto.randomUUID();
    window.localStorage.setItem(USER_KEY_STORAGE_KEY, key);
  }
  return key;
}

/** Stream a single interview turn. Calls onToken for each text delta, onDone when stream ends. */
export async function streamInterviewTurn(
  targetJob: string,
  messages: InterviewMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
): Promise<void> {
  const response = await fetch('/api/interview/turn', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Resume-User-Key': getUserKey(),
    },
    body: JSON.stringify({ target_job: targetJob, messages }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    for (const line of chunk.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const data = trimmed.slice(5).trim();
      if (data === '[DONE]') continue;
      try {
        const event = JSON.parse(data);
        const token: string = event?.choices?.[0]?.delta?.content ?? '';
        if (token) onToken(token);
      } catch {
        // skip malformed SSE lines
      }
    }
  }
  onDone();
}

export async function saveInterviewReport(
  targetJob: string,
  messages: InterviewMessage[],
  durationSeconds: number,
): Promise<{ id: number; report: InterviewReport }> {
  const res = await fetch('/api/interview/report', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Resume-User-Key': getUserKey(),
    },
    body: JSON.stringify({ target_job: targetJob, messages, duration_seconds: durationSeconds }),
  });
  if (!res.ok) throw new Error(`Report failed: ${res.status}`);
  return res.json();
}

export async function listInterviewReports(): Promise<InterviewReportRow[]> {
  const res = await fetch('/api/interview/reports', {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getInterviewReport(id: number): Promise<SavedReport> {
  const res = await fetch(`/api/interview/reports/${id}`, {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!res.ok) throw new Error(`Not found: ${id}`);
  return res.json();
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd resume-copilot-web
npx tsc --noEmit 2>&1 | grep -E "interview|error" | head -20
```

Expected: no errors in interview files.

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/interview/
git commit -m "feat(interview): add frontend types and API streaming helpers"
```

---

## Task 5: Setup Page

**Files:**
- Create: `resume-copilot-web/app/interview/page.tsx`

- [ ] **Step 1: Create the setup page**

Create `resume-copilot-web/app/interview/page.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function InterviewSetupPage() {
  const router = useRouter();
  const [targetJob, setTargetJob] = useState('');
  const [error, setError] = useState('');

  function handleStart() {
    const trimmed = targetJob.trim();
    if (!trimmed) {
      setError('请填写目标岗位');
      return;
    }
    const sessionId = crypto.randomUUID();
    // Store target job so the session page can read it
    sessionStorage.setItem(`interview.${sessionId}.job`, trimmed);
    router.push(`/interview/${sessionId}`);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4">
      <div className="resume-paper-shadow w-full max-w-lg rounded-[24px] bg-[var(--paper)] px-8 py-10">
        <h1 className="mb-1 text-[22px] font-semibold text-[var(--ink)]">模拟面试</h1>
        <p className="mb-8 text-[14px] text-[var(--muted)]">
          输入你的目标岗位，AI 面试官将进行真实对话式面试，并在结束后给出详细反馈。
        </p>

        <label className="mb-2 block text-[13px] font-medium text-[var(--ink)]">
          目标岗位
        </label>
        <textarea
          className="w-full resize-none rounded-[14px] border border-[var(--border)] bg-[var(--soft)] px-4 py-3 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none"
          rows={2}
          placeholder="例如：蚂蚁集团数据分析师、互联网产品经理、券商研究员…"
          value={targetJob}
          onChange={(e) => { setTargetJob(e.target.value); setError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleStart(); } }}
        />
        {error && <p className="mt-1.5 text-[13px] text-red-500">{error}</p>}

        <button
          onClick={handleStart}
          className="mt-5 w-full rounded-[12px] bg-[var(--primary)] py-3 text-[15px] font-semibold text-white transition-opacity hover:opacity-90 active:opacity-80"
        >
          开始面试
        </button>

        <p className="mt-4 text-center text-[12px] text-[var(--muted)]">
          面试约 10–14 轮，结束后生成详细报告
        </p>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Lint check**

```bash
cd resume-copilot-web && npm run lint 2>&1 | grep -E "interview|error" | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/app/interview/
git commit -m "feat(interview): add setup page with job input"
```

---

## Task 6: InterviewChat Component

**Files:**
- Create: `resume-copilot-web/components/interview/InterviewChat.tsx`

- [ ] **Step 1: Create `InterviewChat.tsx`**

```tsx
'use client';

import { useEffect, useRef, useState } from 'react';

const SPINNER_FRAMES = ['·', '✢', '✳', '✶', '✻', '✽'] as const;

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  messages: Message[];
  streamingContent: string;   // partial content being streamed in
  isStreaming: boolean;
  disabled: boolean;
  onSend: (content: string) => void;
}

export function InterviewChat({ messages, streamingContent, isStreaming, disabled, onSend }: Props) {
  const [input, setInput] = useState('');
  const [frameIdx, setFrameIdx] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingContent]);

  // Spinner animation
  useEffect(() => {
    if (!isStreaming) return;
    const timer = setInterval(() => setFrameIdx((i) => (i + 1) % SPINNER_FRAMES.length), 120);
    return () => clearInterval(timer);
  }, [isStreaming]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || disabled || isStreaming) return;
    setInput('');
    onSend(trimmed);
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-[16px] px-4 py-3 text-[14px] leading-relaxed whitespace-pre-wrap ${
                msg.role === 'assistant'
                  ? 'bg-[#0b0d12] text-white/90'
                  : 'bg-[var(--soft-blue)] text-[var(--ink)]'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* Streaming message */}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-[16px] bg-[#0b0d12] px-4 py-3 text-[14px] leading-relaxed text-white/90 whitespace-pre-wrap">
              {streamingContent || (
                <span className="flex items-center gap-2 text-white/40">
                  <span className="font-mono text-[15px]">{SPINNER_FRAMES[frameIdx]}</span>
                  面试官思考中…
                </span>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        <div className="flex gap-2">
          <textarea
            className="flex-1 resize-none rounded-[12px] border border-[var(--border)] bg-[var(--soft)] px-4 py-2.5 text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none"
            rows={2}
            placeholder="输入你的回答… (Enter 发送，Shift+Enter 换行)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || isStreaming}
          />
          <button
            onClick={handleSend}
            disabled={disabled || isStreaming || !input.trim()}
            className="self-end rounded-[10px] bg-[var(--primary)] px-4 py-2.5 text-[13px] font-semibold text-white disabled:opacity-40 hover:opacity-90"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Lint check**

```bash
cd resume-copilot-web && npm run lint 2>&1 | grep -E "InterviewChat|error TS" | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/components/interview/InterviewChat.tsx
git commit -m "feat(interview): add InterviewChat component with streaming bubble UI"
```

---

## Task 7: InterviewReport Component

**Files:**
- Create: `resume-copilot-web/components/interview/InterviewReport.tsx`

- [ ] **Step 1: Create `InterviewReport.tsx`**

```tsx
'use client';

import type { InterviewReport } from './types';

interface Props {
  report: InterviewReport;
  targetJob: string;
  durationSeconds: number;
  onRestart: () => void;
}

function ScoreRing({ score }: { score: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = score >= 80 ? '#4ade80' : score >= 60 ? 'var(--primary)' : '#f97316';

  return (
    <div className="relative flex items-center justify-center">
      <svg width={96} height={96} className="-rotate-90">
        <circle cx={48} cy={48} r={r} fill="none" stroke="var(--border)" strokeWidth={7} />
        <circle
          cx={48} cy={48} r={r} fill="none"
          stroke={color} strokeWidth={7}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-[22px] font-bold text-[var(--ink)]">{score}</span>
    </div>
  );
}

function DimensionBar({ name, score, comment }: { name: string; score: number; comment: string }) {
  const color = score >= 80 ? '#4ade80' : score >= 60 ? 'var(--primary)' : '#f97316';
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[13px] font-medium text-[var(--ink)]">{name}</span>
        <span className="text-[13px] font-semibold" style={{ color }}>{score}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--border)]">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      {comment && <p className="mt-1 text-[12px] text-[var(--muted)]">{comment}</p>}
    </div>
  );
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}分${s.toString().padStart(2, '0')}秒`;
}

export function InterviewReport({ report, targetJob, durationSeconds, onRestart }: Props) {
  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
      <div className="mx-auto w-full max-w-xl space-y-5">
        {/* Header */}
        <div className="rounded-[20px] bg-[var(--paper)] resume-paper-shadow px-6 py-5">
          <p className="mb-1 text-[12px] font-semibold uppercase tracking-widest text-[var(--muted)]">
            面试报告
          </p>
          <h2 className="text-[18px] font-semibold text-[var(--ink)]">{targetJob}</h2>
          <p className="text-[13px] text-[var(--muted)]">面试时长：{formatDuration(durationSeconds)}</p>
        </div>

        {/* Score */}
        <div className="rounded-[20px] bg-[var(--paper)] resume-paper-shadow px-6 py-5">
          <p className="mb-4 text-[13px] font-semibold text-[var(--muted)]">综合评分</p>
          <div className="flex items-center gap-6">
            <ScoreRing score={report.overall_score} />
            <p className="flex-1 text-[14px] leading-relaxed text-[var(--ink)]">
              {report.overall_comment}
            </p>
          </div>
        </div>

        {/* Dimensions */}
        {report.dimensions.length > 0 && (
          <div className="rounded-[20px] bg-[var(--paper)] resume-paper-shadow px-6 py-5">
            <p className="mb-4 text-[13px] font-semibold text-[var(--muted)]">各维度评分</p>
            {report.dimensions.map((d) => (
              <DimensionBar key={d.name} {...d} />
            ))}
          </div>
        )}

        {/* Highlights + Improvements */}
        <div className="grid grid-cols-2 gap-4">
          {report.highlights.length > 0 && (
            <div className="rounded-[20px] bg-[var(--accent-soft)] px-5 py-4">
              <p className="mb-2 text-[12px] font-semibold text-[var(--accent)]">✦ 亮点</p>
              <ul className="space-y-1">
                {report.highlights.map((h, i) => (
                  <li key={i} className="text-[13px] text-[var(--ink)]">· {h}</li>
                ))}
              </ul>
            </div>
          )}
          {report.improvements.length > 0 && (
            <div className="rounded-[20px] bg-[var(--warning-soft)] px-5 py-4">
              <p className="mb-2 text-[12px] font-semibold text-amber-600">⚡ 改进方向</p>
              <ul className="space-y-1">
                {report.improvements.map((imp, i) => (
                  <li key={i} className="text-[13px] text-[var(--ink)]">· {imp}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Actions */}
        <button
          onClick={onRestart}
          className="w-full rounded-[12px] border border-[var(--border)] bg-[var(--paper)] py-3 text-[14px] font-medium text-[var(--ink)] hover:bg-[var(--soft)] transition-colors"
        >
          重新面试
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Lint check**

```bash
cd resume-copilot-web && npm run lint 2>&1 | grep -E "InterviewReport|error TS" | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/components/interview/InterviewReport.tsx
git commit -m "feat(interview): add InterviewReport component with score ring and dimension bars"
```

---

## Task 8: Interview Session Page (main page)

**Files:**
- Create: `resume-copilot-web/app/interview/[sessionId]/page.tsx`

- [ ] **Step 1: Create the session page**

Create `resume-copilot-web/app/interview/[sessionId]/page.tsx`:

```tsx
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import type { InterviewMessage, InterviewReport as InterviewReportType, InterviewState } from '@/components/interview/types';
import { streamInterviewTurn, saveInterviewReport } from '@/components/interview/api';
import { InterviewChat } from '@/components/interview/InterviewChat';
import { InterviewReport } from '@/components/interview/InterviewReport';

const INTERVIEW_END_MARKER = '[INTERVIEW_END]';
const LS_PREFIX = 'interview.';

function loadSession(sessionId: string): { messages: InterviewMessage[]; targetJob: string } | null {
  try {
    const raw = localStorage.getItem(`${LS_PREFIX}${sessionId}`);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

function saveSession(sessionId: string, messages: InterviewMessage[], targetJob: string) {
  try {
    localStorage.setItem(`${LS_PREFIX}${sessionId}`, JSON.stringify({ messages, targetJob }));
  } catch { /* ignore */ }
}

export default function InterviewSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();

  const [targetJob, setTargetJob] = useState('');
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [streamingContent, setStreamingContent] = useState('');
  const [state, setState] = useState<InterviewState>('interviewing');
  const [report, setReport] = useState<InterviewReportType | null>(null);
  const [reportError, setReportError] = useState('');
  const [round, setRound] = useState(0);
  const startTimeRef = useRef<number>(Date.now());

  // Restore or initialize session
  useEffect(() => {
    const saved = loadSession(sessionId);
    if (saved) {
      setTargetJob(saved.targetJob);
      setMessages(saved.messages);
      // If messages exist, session was already in progress — don't auto-start
      return;
    }
    // First visit: read target job from sessionStorage
    const job = sessionStorage.getItem(`interview.${sessionId}.job`) || '';
    if (!job) { router.push('/interview'); return; }
    setTargetJob(job);
    sessionStorage.removeItem(`interview.${sessionId}.job`);
    // Auto-start with empty messages → LLM opens the interview
    startTurn(job, []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const startTurn = useCallback(async (job: string, msgs: InterviewMessage[]) => {
    setState('interviewing');
    setStreamingContent('');
    let accumulated = '';

    try {
      await streamInterviewTurn(
        job,
        msgs,
        (token) => {
          accumulated += token;
          setStreamingContent(accumulated);
        },
        () => {
          const hasEnd = accumulated.includes(INTERVIEW_END_MARKER);
          const clean = accumulated.replace(INTERVIEW_END_MARKER, '').trim();
          const newMsg: InterviewMessage = { role: 'assistant', content: clean };
          const updatedMsgs = [...msgs, newMsg];
          setMessages(updatedMsgs);
          setStreamingContent('');
          setRound((r) => r + 1);
          saveSession(sessionId, updatedMsgs, job);
          if (hasEnd) triggerReport(job, updatedMsgs);
        },
      );
    } catch {
      setStreamingContent('');
      setMessages((prev) => [...prev, { role: 'assistant', content: '⚠️ 网络错误，请重新发送。' }]);
    }
  }, [sessionId]);

  function handleSend(content: string) {
    const userMsg: InterviewMessage = { role: 'user', content };
    const updatedMsgs = [...messages, userMsg];
    setMessages(updatedMsgs);
    saveSession(sessionId, updatedMsgs, targetJob);
    startTurn(targetJob, updatedMsgs);
  }

  function handleEndInterview() {
    if (state !== 'interviewing') return;
    triggerReport(targetJob, messages);
  }

  async function triggerReport(job: string, msgs: InterviewMessage[]) {
    setState('generating_report');
    setReportError('');
    const duration = Math.floor((Date.now() - startTimeRef.current) / 1000);
    try {
      const { report: r } = await saveInterviewReport(job, msgs, duration);
      setReport(r);
      setState('report_ready');
    } catch {
      setReportError('报告生成失败，请重试。');
      setState('interviewing');
    }
  }

  const isStreaming = state === 'interviewing' && streamingContent !== '' || streamingContent !== '';
  const isDisabled = state !== 'interviewing';

  if (state === 'report_ready' && report) {
    const duration = Math.floor((Date.now() - startTimeRef.current) / 1000);
    return (
      <main className="flex min-h-screen flex-col bg-[var(--background)]">
        <div className="border-b border-[var(--border)] bg-[var(--paper)] px-6 py-4">
          <h1 className="text-[16px] font-semibold text-[var(--ink)]">面试完成 · {targetJob}</h1>
        </div>
        <InterviewReport
          report={report}
          targetJob={targetJob}
          durationSeconds={duration}
          onRestart={() => router.push('/interview')}
        />
      </main>
    );
  }

  return (
    <main className="flex h-screen flex-col bg-[var(--background)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--paper)] px-6 py-3">
        <div>
          <h1 className="text-[15px] font-semibold text-[var(--ink)]">{targetJob || '模拟面试'}</h1>
          <p className="text-[12px] text-[var(--muted)]">第 {round} 轮</p>
        </div>
        <div className="flex items-center gap-3">
          {state === 'generating_report' && (
            <span className="text-[13px] text-[var(--muted)]">生成报告中…</span>
          )}
          {reportError && (
            <button
              onClick={() => triggerReport(targetJob, messages)}
              className="text-[13px] text-red-500 underline"
            >
              {reportError} 重试
            </button>
          )}
          <button
            onClick={handleEndInterview}
            disabled={state !== 'interviewing' || messages.length < 2}
            className="rounded-[10px] border border-[var(--border)] px-3 py-1.5 text-[13px] text-[var(--muted)] hover:bg-[var(--soft)] disabled:opacity-30 transition-colors"
          >
            结束面试
          </button>
        </div>
      </div>

      {/* Chat */}
      <InterviewChat
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={!!streamingContent}
        disabled={isDisabled}
        onSend={handleSend}
      />
    </main>
  );
}
```

- [ ] **Step 2: Lint check**

```bash
cd resume-copilot-web && npm run lint 2>&1 | grep -E "\[sessionId\]|error" | head -15
```

Expected: no errors.

- [ ] **Step 3: Full build check**

```bash
cd resume-copilot-web && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` with no errors.

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/app/interview/
git commit -m "feat(interview): add session page with streaming chat, end interview, and report flow"
```

---

## Task 9: End-to-End Smoke Test

- [ ] **Step 1: Start backend (port 8002)**

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

- [ ] **Step 2: Start frontend (port 3001)**

```bash
cd resume-copilot-web
RESUME_COPILOT_BACKEND_URL=http://127.0.0.1:8002 npm run dev -- --hostname 127.0.0.1
```

- [ ] **Step 3: Golden path test**

Open `http://127.0.0.1:3001/interview`:
1. Type "蚂蚁集团数据分析师" → click 开始面试
2. Verify redirects to `/interview/[uuid]`
3. Verify first interviewer message streams in
4. Send 2 answers; verify follow-up questions appear
5. Click "结束面试" → verify report generates and displays
6. Verify score ring renders, dimensions show

- [ ] **Step 4: Refresh restore test**

During an active interview (after 2 messages), refresh the page. Verify conversation restores from LocalStorage.

- [ ] **Step 5: Backend unit tests**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/test_interview_service.py -v
```

Expected: `6 passed`.

- [ ] **Step 6: Final lint + build**

```bash
cd resume-copilot-web
npm run lint && npm run build
```

Expected: 0 errors.

- [ ] **Step 7: Commit if any fixes made during testing**

```bash
git add -p   # stage only relevant changes
git commit -m "fix(interview): smoke test fixes"
```
