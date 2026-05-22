# Worker B Independent Review - Workspace Coach/Chat

Date: 2026-05-22
Runtime: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3004`
Worktree: `/home/chuanbo/projects/JobRadar`
Branch: `feat/workspace-redesign-2026-05-20`
Personas: P3, P4, P7

## Summary

Backend and frontend were reachable (`/docs` and frontend root both returned 200). Upload/generate succeeded for all three personas, and step3 chat produced a visible assistant response for every turn. The main failure is coach/plan closure: all three personas ended with `final_anchors=0`, the finalize attempt returned 422 for all three, and P4 never produced a draft after 6 turns.

Recommendation was checked as GET-only smoke to avoid mutating/rejecting jobs: P3 returned 20 items, P4 returned 14, P7 returned 13; all three recommendation smoke calls returned 200.

## BLOCKER

1. Coach/plan mode does not complete a closed loop across P3/P4/P7.

   Evidence:
   - P3 step4: `turns_taken=5`, `final_anchors=0`, final focus status `awaiting_review`, has draft, but `plan_turn6` returned 500 and finalize returned 422.
   - P4 step4: `turns_taken=6`, `final_anchors=0`, final focus status `clarifying`, no draft after 7 evidence entries, finalize returned 422.
   - P7 step4: `turns_taken=6`, `final_anchors=0`, final focus status `clarifying`, has draft but reverts to clarification, finalize returned 422.

   Impact: a user can answer multiple rounds, sometimes even get a draft, but the plan/checklist does not reach a stable completed/finalized state. This fails the "闭环" requirement.

2. Plan action schema mismatch blocks finalization.

   Evidence: all three personas hit `plan_finalize_attempt=422` with `INVALID_ACTION`, because the eval called `finalize_item` while the API accepts `ask`, `write`, `drop`, `replan`, `ready_to_write`, `finalize`, or `block`.

   Impact: even when P3/P7 have drafts, the final action path used by the current eval/runtime cannot finalize. This may be an eval/runtime contract drift, but from the runtime behavior it is still a hard closure failure.

3. P3 plan turn crashed with HTTP 500.

   Evidence: P3 `plan_turn6` returned `500 Internal Server Error`. P4/P7 did not hit 500.

   Impact: coach mode can server-error after several successful turns. This is user-visible risk if the same path is reachable from the UI.

## MAJOR

1. Coach repeats clarification after the user has already answered.

   Evidence:
   - P4 asked "主导度需要佐证" on turn2, marked it answered on turn3, then asked the same "主导度需要佐证" again in turn6 alongside another question.
   - P7 asked "主导度需要佐证 / 技术细节缺出处" on turn2, marked it answered, later asked unrelated or already covered questions while preserving old answered questions in the stack.
   - P3 generated a draft by turn3, then later asked "这段经历里你本人最核心的动作是什么?" even though prior answers already included concrete actions and metrics.

   Impact: the coach feels stuck in clarification rather than moving through STAR-like collection into write/review/finalize.

2. Focus item is not clear enough.

   Evidence: all three focus items are titled only `internship #1`; the target company exists in the eval metadata, but the plan item title/subject does not expose it. This makes the selected focus ambiguous in report/UI-level state.

   Impact: user and evaluator cannot easily confirm whether the coach is deep-diving the intended internship without inspecting evidence text.

3. Checklist/anchor progress is not observable.

   Evidence: `anchors` and `progress` are null on initial/final focus items for P3/P4/P7, and the evaluator reports `final_anchors=0` for all three despite evidence accumulation and drafts in P3/P7.

   Impact: plan progress cannot be reliably shown as advancing. If the product UI relies on the same fields, users will not see clear checklist movement.

4. P4 gets stuck in "preparing to write but not writing".

   Evidence: P4 collected 7 evidence entries over 6 turns, repeatedly said it needed one more detail before writing, but final focus has `has_draft=false` and status remains `clarifying`.

   Impact: this directly matches the risk "准备写但不写".

## MINOR

1. Step3 chat rail visibility is OK, but continuity is uneven.

   Evidence: every step3 turn in P3/P4/P7 has non-empty assistant content. However, P3 repeatedly revisits whether the added "消费/化工" details belong to the resume, and P7 alternates between smart-advisor and Ant/anti-fraud rewrite framing across turns. P4 is the most continuous.

2. Preference capture in chat is partial.

   Evidence: P3 and P7 T3 preference turns had `memory_delta=0`; P3/P7 only captured preference-like growth later in T5. Assertions still passed because total memory increased and at least one preference was captured by the end.

3. Residual concurrency risk observed.

   Evidence: during the first P3 upload run, a separate `P1_step3_chat_5_turns.py` process was also running on the same runtime. I did not touch it. No SQLite lock surfaced in my P3/P4/P7 runs, but it is a residual risk for shared runtime evals.

## Persona Results

| Persona | step1 | step3 chat | step4 coach | Recommendation smoke |
| --- | --- | --- | --- | --- |
| P3 | session 123, direction OK, 144.71s | 5/5 assistant replies visible; memory 3 -> 8 | draft exists, status `awaiting_review`, `final_anchors=0`, `plan_turn6=500`, finalize 422 | 200, 20 items |
| P4 | session 127, direction OK, 177.16s | 5/5 assistant replies visible; memory 3 -> 11 | no draft after 6 turns, status `clarifying`, `final_anchors=0`, finalize 422 | 200, 14 items |
| P7 | session 130, direction OK, 230.41s | 5/5 assistant replies visible; memory 3 -> 5 | draft exists, status back to `clarifying`, `final_anchors=0`, finalize 422 | 200, 13 items |

## Raw Outputs

Primary reports:
`/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P3/report.json`
`/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P4/report.json`
`/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P7/report.json`

Copied/extracted raw files:
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P3_step1_upload.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P3_step3_chat_5_turns.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P3_step4_plan_mode.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P4_step1_upload.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P4_step3_chat_5_turns.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P4_step4_plan_mode.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P7_step1_upload.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P7_step3_chat_5_turns.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P7_step4_plan_mode.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P3_chat_pairs.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P4_chat_pairs.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P7_chat_pairs.txt`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P3_recommendations_smoke.json`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P4_recommendations_smoke.json`
`/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P7_recommendations_smoke.json`

## Commands Run

```bash
cd /home/chuanbo/projects/JobRadar/backend
WORKSPACE_PERSONA=P3 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P3 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P3 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
WORKSPACE_PERSONA=P4 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P4 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P4 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
WORKSPACE_PERSONA=P7 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P7 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P7 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
```

GET-only recommendation smoke:

```bash
curl -H 'X-Resume-User-Key: eval_workspace_P3_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/123/recommendations
curl -H 'X-Resume-User-Key: eval_workspace_P4_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/127/recommendations
curl -H 'X-Resume-User-Key: eval_workspace_P7_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/130/recommendations
```

## 500 / 422 / 409

P3: one 500 (`plan_turn6`), one 422 (`plan_finalize_attempt`), no 409.

P4: no 500, one 422 (`plan_finalize_attempt`), no 409.

P7: no 500, one 422 (`plan_finalize_attempt`), no 409.

