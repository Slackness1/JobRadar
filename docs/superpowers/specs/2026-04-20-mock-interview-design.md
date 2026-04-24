# Mock Interview Feature — Design Spec

**Date:** 2026-04-20  
**Branch:** feature/mock-interview  
**Status:** Approved, ready for implementation

---

## Overview

A standalone mock interview feature in the Resume Copilot web app. Users type a target job, conduct a conversational interview with an LLM acting as interviewer (with follow-up questions), and receive a structured feedback report at the end.

---

## User Flow

```
/interview (setup)
  → user types target job (freeform, e.g. "蚂蚁集团数据分析师")
  → click 开始面试

/interview/[sessionId] (conversation)
  → LLM opens with first behavioral question
  → user answers → LLM follows up or pivots to next topic
  → after 10-14 turns LLM sends closing message (contains [INTERVIEW_END])
  → OR user clicks "结束面试" at any time

report panel (inline, no page change)
  → report generation spinner
  → structured report card slides in
  → options: 重新面试 | 查看历史报告
```

---

## Architecture

### Frontend (`resume-copilot-web/`)

| Path | Purpose |
|------|---------|
| `app/interview/page.tsx` | Setup page — job input + start |
| `app/interview/[sessionId]/page.tsx` | Conversation + report page |
| `components/interview/InterviewChat.tsx` | Chat bubble UI + streaming |
| `components/interview/InterviewReport.tsx` | Report card with scores |
| `components/interview/api.ts` | API helpers for /turn and /report |

State machine (client-side):
```
setup → interviewing → wrapping_up → generating_report → report_ready
```

Session ID is a `crypto.randomUUID()` generated on setup. Conversation state is persisted to `localStorage` keyed by sessionId so a page refresh restores the chat.

### Backend (`backend/app/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/interview/turn` | POST | Streaming: receives `{target_job, messages[]}` → streams LLM next turn |
| `/api/interview/report` | POST | Receives `{target_job, messages[], duration_seconds}` → generates report JSON → saves to DB → returns report |
| `/api/interview/reports` | GET | Lists saved reports for the user (by `X-Resume-User-Key` header) |
| `/api/interview/reports/{id}` | GET | Returns a single report |

New router: `backend/app/routers/interview.py`  
New service: `backend/app/services/interview/`

### Database

New table added via `schema_patch.py`:

```sql
CREATE TABLE IF NOT EXISTS interview_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    target_job TEXT NOT NULL,
    transcript_json TEXT,       -- [{role, content}] full conversation
    report_json TEXT,           -- structured feedback JSON
    duration_seconds INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## LLM Design

### `/api/interview/turn` — Conversation

System prompt injected once, then full `messages[]` passed each turn:

```
你是一位专业的校招面试官，正在对一名应届生进行面试。
目标岗位：{target_job}

行为规则：
1. 前 3 轮出行为类问题（如"介绍一下你负责过的项目"、"讲一个你解决冲突的经历"）
2. 第 4 轮起穿插岗位专项问题，根据岗位方向选题
3. 根据候选人的回答决定：深挖追问 or 切换下一题
4. 累计对话达到 10-14 轮后，给出收尾语并在消息末尾附加标记 [INTERVIEW_END]
5. 每次只问一个问题，语气专业但不刻板
6. 不要评价候选人回答好坏，面试结束前保持中立
```

Streaming via SSE. Frontend detects `[INTERVIEW_END]` in streamed text to auto-trigger report.

### `/api/interview/report` — Report Generation

Full transcript sent in one shot. Required output (JSON):

```json
{
  "overall_score": 78,
  "dimensions": [
    { "name": "表达清晰度", "score": 80, "comment": "..." },
    { "name": "逻辑结构",   "score": 75, "comment": "..." },
    { "name": "岗位匹配度", "score": 82, "comment": "..." },
    { "name": "抗压表现",   "score": 70, "comment": "..." }
  ],
  "highlights": ["亮点1", "亮点2"],
  "improvements": ["改进点1", "改进点2"],
  "overall_comment": "综合评价..."
}
```

---

## Frontend UI

### Setup Page `/interview`

- Centered card, `resume-paper-shadow`, same tokens as main app
- Single `<textarea>` input (placeholder: "例如：蚂蚁集团数据分析师、互联网产品经理…")
- "开始面试" primary button
- `user_key` from `getOrCreateUserKey()` (shared with Resume Copilot)

### Interview Page `/interview/[sessionId]`

Two-column layout:

**Left rail (narrow):**
- Target job label
- Round counter (第 N 轮)
- Timer (elapsed)
- "结束面试" button

**Right main area:**
- Chat bubble stream
  - Interviewer messages: dark card (`bg-[#0b0d12]`, white text) — same as `AgentThinkingPanel`
  - User messages: soft blue (`var(--soft-blue)`)
  - Interviewer typing: `SPINNER_FRAMES` at 120ms + "面试官思考中…"
- Bottom: `<textarea>` + send button
  - `Enter` → send, `Shift+Enter` → newline

### Report Panel (inline, replaces chat area)

Slides in after report generates:
- Overall score: circular progress ring
- Four dimensions: labeled score bars
- Highlights / Improvements: two-column list
- Overall comment paragraph
- Buttons: "重新面试" | "历史报告"

Styling: all existing CSS tokens (`var(--primary)`, `var(--ink)`, `var(--border)`, etc.), no new design system.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `/turn` stream interrupted | "网络错误，重新发送" inline error; prior messages preserved |
| `/report` generation fails | Retry button shown; transcript still in LocalStorage |
| LLM never sends `[INTERVIEW_END]` | "结束面试" button always available as manual trigger |
| Page refresh mid-interview | Chat restored from LocalStorage via sessionId |
| Report already exists for sessionId | GET from DB, skip re-generation |

---

## Out of Scope (this iteration)

- Voice input
- Linking to a Resume Copilot session / using resume context
- Report export (PDF, share link)
- Interview templates / question banks
- Scoring rubric customization

---

## Implementation Order

1. DB schema patch (`InterviewReport` table)
2. Backend service: `interview/llm.py` (prompt builder + streaming call)
3. Backend router: `/turn`, `/report`, `/reports`, `/reports/{id}`
4. Frontend API helpers (`components/interview/api.ts`)
5. Setup page (`/interview`)
6. Interview conversation page + streaming chat UI
7. Report display component
8. LocalStorage restore logic
9. Wire up "结束面试" manual trigger
10. Lint + build verification
