# Workspace Coach Real User Simulation Plan

Date: 2026-05-21
Branch: `feat/workspace-redesign-2026-05-20`

## Goal

Use persona resumes to simulate real student behavior across the resume copilot workspace:

1. Upload resume.
2. Confirm parsed profile plus track and city preference.
3. Enter workspace.
4. Start coach mode and choose a specific experience.
5. Answer several coach questions in the persona's voice.
6. Verify draft generation, review card, and archive/write-to-memory behavior.
7. Record bugs that a student would actually hit, not only unit-test failures.

## Data Gate

Current environment findings:

- Primary PDF dataset: `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/pdfs`
- Primary persona JSON dataset: `/home/chuanbo/projects/JobRadar/backend/tests/eval/personas/workspace_2026_05_20`
- Available complete samples in the current worktree: `P1` through `P8`, each with `.pdf` and `.json`.
- Also found a copied dataset at `/tmp/saif_personas_2026_05_20/`; do not use it as source of truth unless the primary repo paths disappear.
- Not found in the current worktree: `P9.pdf` and `P9.json`.
- Found `P9.json` only in the separate `/home/ubuntu/projects/JobRadar/...` worktree, without a matching PDF.
- Not found: a host-mounted `Downloads` / `下载` directory under `/home/chuanbo`, `/home/ubuntu`, or `/mnt`.

Before execution, workers must treat P9 as blocked unless a new path is provided or the file appears.

## Runtime Gate

Expected local services:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3004`

Preflight checks:

- `GET /api/health` returns `{"status":"ok"}`.
- Frontend port `3004` is listening.
- No long-running foreground tool session is left open.

## API Flow

Use a unique `X-Resume-User-Key` per persona run, for example:

```text
sim_P1_20260521_<timestamp>
```

Core endpoints:

1. Upload PDF
   - `POST /api/resume-copilot/sessions`
   - multipart field: `file=@P?.pdf`
   - headers: `X-Resume-User-Key`
   - expected: `202`, returns `session_id`.

2. Poll session until parsed profile is ready
   - `GET /api/resume-copilot/sessions/{session_id}`
   - then `GET /api/resume-copilot/sessions/{session_id}/parsed-profile`
   - expected: parsed profile exists and resembles persona JSON.

3. Confirm profile
   - `PUT /api/resume-copilot/sessions/{session_id}/confirmed-profile`
   - body: `{ "profile": <parsed profile with optional persona correction> }`
   - expected: `200`; archive seeding should not blank or hide experiences.

4. Save preferences
   - `PUT /api/resume-copilot/sessions/{session_id}/preferences`
   - body: `{ "preferences": { preferred_tracks, preferred_locations, ... } }`
   - source: persona `scenario_config.target_track`; default cities `["北京", "上海"]` unless persona implies otherwise.

5. Generate workspace recommendations
   - `POST /api/resume-copilot/sessions/{session_id}/generate`
   - poll session, recommendations, feedback, and direction-analysis until completed or timeout.

6. Start coach
   - optional cleanup: `DELETE /api/resume-copilot/sessions/{session_id}/plan`
   - `POST /api/resume-copilot/sessions/{session_id}/plan/start`
   - if testing a specific archive item, pass `focus_id`; otherwise use the first coachable plan item.
   - `POST /api/resume-copilot/sessions/{session_id}/plan/approve`

7. Coach turns
   - `POST /api/resume-copilot/sessions/{session_id}/plan/turn`
   - body: `{ "content": "<persona answer>" }`
   - run 3-6 turns or until item reaches `awaiting_review` with draft.

8. Verify conversation
   - `GET /api/resume-copilot/sessions/{session_id}/chat`
   - expected: every user turn has an assistant reply; no silent thinking state.

9. Archive draft
   - `POST /api/resume-copilot/sessions/{session_id}/memory`
   - body should match the frontend `PlanDraftCard` payload shape.
   - expected: `201`; subsequent `GET /memory` shows the new entry.

## Browser Flow

API execution catches backend logic bugs quickly. At least two persona runs should also use the frontend UI on `3004` to catch interaction bugs:

- Upload file through the visible upload control.
- Confirm page should show resume preview, track chips, and city chips.
- Coach composer should show the active coached experience title.
- Thinking indicator should use the terracotta orb and integer timer.
- Progress chips should begin empty or reflect only coach-collected answers, not parsed resume defaults.
- After draft generation, the review card should appear without requiring an extra user message.
- Archive panel should show the newly added item after入档.

## Persona Worker Split

Use subagents during execution, not only exploration:

- Worker A: P1, P2, P3
- Worker B: P4, P5, P6
- Worker C: P7, P8, and P9 if found

Each worker should simulate student answers from its persona JSON:

- `persona_voice`: controls message length, tone, hesitation, and specificity.
- `flow_padding_internship`: tells which experience/bullet is meant to be strengthened.
- `hidden_highlights`: provides details the student can reveal during coach.
- `avoid_emphasize`: constrains what not to overstate and what to emphasize.

Workers must not change production code. They may create result logs under:

```text
docs/eval-full-loop-reports/workspace-coach-sim-2026-05-21/
```

## Pass Criteria

For each persona:

- Upload succeeds.
- Parsed profile can be confirmed.
- Preferences are saved with intended track/cities.
- Recommendations generation completes or fails with a clear, recorded reason.
- Coach plan starts and has a valid `current_item_id`.
- Coach asks grounded follow-up questions about the selected experience.
- Each `/plan/turn` returns non-500 status.
- Chat history contains the full user/assistant exchange.
- A draft appears when evidence is enough.
- Archive write succeeds and memory list includes the new entry.

## Bug Report Format

Each bug should include:

- Persona ID.
- Step.
- Endpoint or UI location.
- Expected behavior.
- Actual behavior.
- HTTP status / response body / screenshot path if available.
- Reproduction commands or browser steps.
- Severity: blocker, major, minor.

## Known Risks Before Execution

- P9 is currently missing in this environment.
- Host `Downloads` / `下载` is not visible from the current WSL filesystem.
- Recommendation generation may be slower than coach-only flow because it can invoke LLM/reranking.
- Running many personas against the same dev DB will create persistent sessions and memory rows; each run must use a unique `X-Resume-User-Key`.
