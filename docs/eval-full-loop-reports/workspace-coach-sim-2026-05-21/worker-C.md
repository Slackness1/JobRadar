# Worker C Real User Simulation Report

Date: 2026-05-21
Worker: C
Personas: P7, P8, P9 gate check
Backend: `http://127.0.0.1:8000`
Raw response logs: `/tmp/jobradar_workerC_20260521T205751`

## Preflight

- `GET /api/health`: `200 {"status":"ok"}`
- P7/P8 source files:
  - PDFs: `backend/scripts/_out/eval_workspace_2026_05_20/pdfs/P7.pdf`, `P8.pdf`
  - JSON: `backend/tests/eval/personas/workspace_2026_05_20/P7.json`, `P8.json`
- P9 source gate:
  - Current worktree: missing `backend/tests/eval/personas/workspace_2026_05_20/P9.json`
  - Current worktree: missing `backend/scripts/_out/eval_workspace_2026_05_20/pdfs/P9.pdf`
  - Separate `/home/ubuntu/projects/JobRadar` worktree: `P9.json` exists, `P9.pdf` missing
  - Decision: `P9 blocked`; no cross-worktree copy/write performed.

## P7

- Persona: `workspace_P7_2026_05_20`
- User key: `sim_workerC_P7_20260521T205751`
- Session: `94`
- Result: `completed_no_draft`

### Flow Summary

1. Upload `P7.pdf`
   - `POST /api/resume-copilot/sessions`
   - Status: `202`
   - Response: `session_id=94`, `status=parsing_profile`, `page_count=1`, `file_size_bytes=88805`
2. Poll parse
   - Final session status: `awaiting_user_confirmation`
   - Parsed profile check:
     - Name: `蒋睿哲`
     - Internships: `2/2`
     - Projects: `1/1`
   - No persona JSON correction was needed.
3. Confirm profile
   - `PUT /confirmed-profile`: `200`
4. Save preferences
   - `PUT /preferences`: `200`
   - Requested track: `FinTech 数据 / 算法 (金融科技数据岗)`
   - Saved canonical track: `金融科技`
   - Locations: `["北京", "上海"]`
   - Roles: `["FinTech 算法工程师", "数据科学家", "风控算法岗"]`
5. Generate recommendations
   - `POST /generate`: `202`
   - Final session: `status=completed`, `recommendation_status=completed`, `feedback_status=completed`, `has_direction_analysis=true`, `has_feedback=false`
   - Recommendations: `20`
   - Top matches include Ant Group algorithm/data roles; top item `job_id=d28adc7aa611`, final score `98`
   - Direction analysis count: `4`
6. Coach focus
   - Focus memory id: `197`
   - Focus row: `某券商 · 金融科技部 · 智能投顾组 · 数据 / 算法实习生 (2024-06 - 2024-12)`
   - `POST /plan/start` with `{"focus_kind":"experience","focus_id":197}` returned current item `internship #1`, correctly anchored on the target internship.
   - `POST /plan/approve`: `200`
7. Coach turns
   - Ran 6 persona-voice turns about converting "做了一些数据维护工作" into an AB-test/data-pipeline bullet.
   - Every `/plan/turn` returned `200`.
   - Chat history contains 6 user turns and 6 assistant replies.
   - All assistant replies were fallback messages:
     - `系统暂时无法生成详细问题（transport: The read operation timed out），请直接告诉我这条经历的核心数字和你的角色。`
   - Final plan remained `clarifying`; no item reached `awaiting_review`; no draft was generated.
8. Archive attempt
   - Skipped because no draft/awaiting_review item existed, so the frontend `PlanDraftCard` archive shape could not be exercised.
   - Final memory counts: `experience=3`, other categories `0`.

### Bugs

1. P7 / Feedback polling
   - Endpoint: `GET /api/resume-copilot/sessions/94/feedback`
   - Expected: frontend API has a feedback getter, and the plan says feedback should be pollable.
   - Actual: `404 {"detail":"Not Found"}`
   - Severity: major
   - Repro:
     ```bash
     curl -H 'X-Resume-User-Key: sim_workerC_P7_20260521T205751' \
       http://127.0.0.1:8000/api/resume-copilot/sessions/94/feedback
     ```

2. P7 / Coach cannot produce draft when LLM transport times out
   - Endpoint: `POST /api/resume-copilot/sessions/94/plan/turn`
   - Expected: after 3-6 rich, grounded student answers, coach should ask useful follow-ups or write a draft for review.
   - Actual: each turn returns `200` but repeats the transport-timeout fallback question; evidence accumulates, item stays `clarifying`, and `PlanDraftCard` never appears.
   - Severity: major
   - Repro summary:
     ```bash
     curl -X POST -H 'Content-Type: application/json' \
       -H 'X-Resume-User-Key: sim_workerC_P7_20260521T205751' \
       'http://127.0.0.1:8000/api/resume-copilot/sessions/94/plan/turn?target_item_id=6c19da80-4e96-437d-b373-58854b3915da' \
       -d '{"content":"数据规模大概是 1.2 亿条标签记录，AB 测试样本 6 万用户。新算法点击率提升 7.3%，加仓转化率提升 4.1%。"}'
     ```

## P8

- Persona: `workspace_P8_2026_05_20`
- User key: `sim_workerC_P8_20260521T205751`
- Session: `95`
- Result: `failed_parse_timeout`

### Flow Summary

1. Upload `P8.pdf`
   - `POST /api/resume-copilot/sessions`
   - Status: `202`
   - Response: `session_id=95`, `status=parsing_profile`, `page_count=2`, `file_size_bytes=93529`
2. Poll parse
   - Polled 90 times.
   - Last response remained:
     - `status=parsing_profile`
     - `has_parsed_profile=false`
     - `error_message=""`
     - `recommendation_status=pending`
   - Because parsed profile never became available, the real user flow could not proceed to confirmation, preferences, recommendation generation, coach, draft, or archive.

### Bugs

1. P8 / Upload accepted but parsing never resolves or fails
   - Endpoint: `GET /api/resume-copilot/sessions/95`
   - Expected: parser should either create a parsed profile or mark the session failed with a visible error.
   - Actual: session stayed in `parsing_profile` for the full polling window with empty `error_message`.
   - Severity: blocker
   - Repro:
     ```bash
     curl -F 'file=@backend/scripts/_out/eval_workspace_2026_05_20/pdfs/P8.pdf;type=application/pdf' \
       -H 'X-Resume-User-Key: sim_workerC_P8_20260521T205751' \
       http://127.0.0.1:8000/api/resume-copilot/sessions

     curl -H 'X-Resume-User-Key: sim_workerC_P8_20260521T205751' \
       http://127.0.0.1:8000/api/resume-copilot/sessions/95
     ```

## P9

- Result: `blocked`
- Reason: current `/home/chuanbo/projects/JobRadar` worktree has neither `P9.json` nor `P9.pdf`; separate `/home/ubuntu/projects/JobRadar` only has `P9.json` and no PDF.
- Action: no copy/write across worktrees; no session created.

## Command Summary

Backend start used for this run:

```bash
cd /home/chuanbo/projects/JobRadar/backend
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Simulation used API calls matching the plan:

```bash
POST   /api/resume-copilot/sessions
GET    /api/resume-copilot/sessions/{session_id}
GET    /api/resume-copilot/sessions/{session_id}/parsed-profile
PUT    /api/resume-copilot/sessions/{session_id}/confirmed-profile
PUT    /api/resume-copilot/sessions/{session_id}/preferences
POST   /api/resume-copilot/sessions/{session_id}/generate
GET    /api/resume-copilot/sessions/{session_id}/recommendations
GET    /api/resume-copilot/sessions/{session_id}/direction-analysis
GET    /api/resume-copilot/sessions/{session_id}/feedback
DELETE /api/resume-copilot/sessions/{session_id}/plan
POST   /api/resume-copilot/sessions/{session_id}/plan/start
POST   /api/resume-copilot/sessions/{session_id}/plan/approve
POST   /api/resume-copilot/sessions/{session_id}/plan/turn
GET    /api/resume-copilot/sessions/{session_id}/chat
POST   /api/resume-copilot/sessions/{session_id}/memory
```
