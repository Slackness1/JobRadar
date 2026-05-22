# Worker A independent review - workspace coach/chat

Date: 2026-05-22
Runtime: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3004`
Worktree: `/home/chuanbo/projects/JobRadar`
Branch observed: `feat/workspace-redesign-2026-05-20`

Scope: P1 / P2 / P5, with emphasis on normal chat continuity and coach closed loop. Recommendation was smoke only.

## Executive Summary

Coach mode is not yet reliably closed-loop. P1 hit a real `500` during a plan turn after reaching `awaiting_review`; P5 lost/contradicted focus and ended after 6 turns still `clarifying` with no draft; all three personas ended with `final_anchors=0`. Normal chat is improved for P1, but P2/P5 still show continuity or memory-capture issues. Recommendation smoke passed for all three personas.

## BLOCKER

1. **P1 coach plan turn returns 500 after draft/awaiting_review**
   - Session: `122`
   - Step: `step4`, `plan_turn4`
   - Request: `POST /api/resume-copilot/sessions/122/plan/turn`
   - Status: `500 Internal Server Error`
   - Context: P1 reached `awaiting_review` on turn 3 and generated a draft, then the next plan turn failed. This breaks the coach closed loop and leaves the user unable to continue normally.
   - Evidence: `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P1/report.json`

2. **P5 coach loses focus and gets stuck in "will write later" behavior**
   - Session: `128`
   - Expected focus item: `高盛 (Goldman Sachs) · Global Markets Division (GBM) · 暑期项目`
   - Final status: `clarifying`
   - Final draft: `null`
   - Turns taken: `6`
   - Final anchors: `0`
   - Chat history shows the assistant repeatedly says the current item is `中金IBD`, while the plan focus is Goldman GBM:
     - `id=695`: "当前正在改写的是中金IBD的经历..."
     - `id=697`: "当前正在改写的是中金IBD经历..."
     - `id=705`: "如果够，我直接撰写..."
   - This directly violates "coach should show/keep focus item" and reproduces "准备写但不写".
   - Evidence: `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P5_chat_history.json`, `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P5/report.json`

## MAJOR

1. **Coach evidence/anchor progress is inconsistent across all personas**
   - P1: evidence count `1 -> 4`, draft exists, final status `awaiting_review`, but `final_anchors=0`.
   - P2: evidence count `1 -> 7`, draft exists, final status falls back to `clarifying`, `final_anchors=0`.
   - P5: evidence count `1 -> 7`, no draft, final status `clarifying`, `final_anchors=0`.
   - The evidence array grows, but `anchors_filled` remains `0` every turn. This makes the progress/closure signal unreliable.

2. **Finalize path was not successfully validated**
   - All three personas hit `422` on `plan_finalize_attempt`.
   - Request used: `POST /api/resume-copilot/sessions/{id}/plan/actions`
   - Payload action: `finalize_item`
   - Response says valid actions are `ask`, `write`, `drop`, `replan`, `ready_to_write`, `finalize`, `block`.
   - This looks like eval script/API contract drift, but the practical result is the same: this run did not prove the flow can finalize.

3. **Normal chat continuity still has failures for P2/P5**
   - P2: `t4_repeat_dedupe` failed. T4 repeated the T1 fact but inserted `3` new memories; assertion expected `<=1`.
   - P5: preference capture failed. `preference_captured` actual was `0`.
   - P1 passed all step3 assertions, but T4 used a simulator fallback message, so its dedupe pass is less meaningful.

4. **Fallback simulator messages are written into user-visible chat and the assistant responds to them**
   - P1 chat: user message `"(fallback) T4_repeat_T1_fact_dedupe_test — 模拟消息生成失败 ()"` was stored and answered.
   - P2 chat: user message `"(fallback) T5_second_preference_plus_open_question — 模拟消息生成失败 ()"` was stored and answered.
   - P5 chat: both step3 and coach contain fallback user messages.
   - This pollutes continuity evaluation and can make memory/chat behavior look worse or better than real user input.

5. **Internal/generic audit wording leaks into user-facing assistant text**
   - P5 assistant ids `699` and `703` include a generic example: `50MW 电站 / 100 万欧元`, unrelated to IBD/GBM.
   - Rewrite option warning fields also expose internal-style text such as `draft contains '2300' not in evidence`.
   - This is not raw tag leakage like `verb_subject`, but it is still backend/audit-template leakage into the user experience.

## MINOR

1. **Runtime latency and observability are weak**
   - Step1 upload wall times: P1 `94.31s`, P2 `188.02s`, P5 `86.61s`.
   - Step3 chat wall times: P1 `123.15s`, P2 `154.88s`, P5 `201.28s`.
   - Step5 recommendation smoke wall times: P1 `120.72s`, P2 `127.29s`, P5 `77.05s`.
   - Scripts generally print only at the end, so long waits have little progress visibility.

2. **P2 coach status oscillates after draft**
   - P2 reached `awaiting_review` on turns 3 and 5, but ended `clarifying` on turn 6 while still having a draft.
   - Final assistant asks "可以直接定稿?", but the run does not transition to finalized.

## Persona Notes

### P1

- Session: `122`
- Step1: parsed/confirmed internships `3/3`; direction analysis passed.
- Step3: memory `4 -> 11`; deltas `[4, 0, 2, 0, 1]`; all step3 assertions passed.
- Step4: focus id `98ead0a4-2f00-4c6e-ac59-4d5335a35a8a`; status `pending -> awaiting_review`; evidence `1 -> 4`; draft exists; `final_anchors=0`; `plan_turn4` returned `500`; finalize attempt returned `422`.
- Chat history pairing: final GET returned `17` messages: one system message, then user/assistant pairs throughout.
- Recommendation smoke: initial `20`, reject `200`, after `20`, rejected job absent from regenerated top results.

### P2

- Session: `125`
- Step1: parsed/confirmed internships `2/2`; direction analysis passed.
- Step3: memory `3 -> 11`; deltas `[1, 2, 2, 3, 0]`; `t4_repeat_dedupe` failed.
- Step4: focus id `d126255f-c4f5-4a63-9a37-14503648c0b7`; status `pending -> clarifying`; evidence `1 -> 7`; draft exists; `final_anchors=0`; finalize attempt returned `422`.
- Chat history pairing: final GET returned `23` messages: one system message, then user/assistant pairs throughout.
- Recommendation smoke: initial `20`, reject `200`, after `20`, rejected job absent from regenerated top results.

### P5

- Session: `128`
- Step1: parsed/confirmed internships `2/2`; direction analysis passed.
- Step3: memory `3 -> 9`; deltas `[2, 2, 0, 2, 0]`; preference capture failed with actual `0`.
- Step4: focus id `2359b137-2669-46ad-a5aa-817b9c15bfb3`; status `pending -> clarifying`; evidence `1 -> 7`; no draft; `final_anchors=0`; finalize attempt returned `422`.
- Chat history pairing: final GET returned `23` messages: one system message, then user/assistant pairs throughout.
- Recommendation smoke: initial `13`, reject `200`, after `13`, rejected job absent from regenerated top results.

## HTTP 500 / 422 / 409

- `500`: Yes, P1 `step4.plan_turn4`, `POST /api/resume-copilot/sessions/122/plan/turn`.
- `422`: Yes, all three personas on `step4.plan_finalize_attempt` due invalid action `finalize_item`.
- `409`: None observed in these reports.

Status counts after all executed steps:

| Persona | 200 | 202 | 204 | 422 | 500 | 409 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 | 50 | 3 | 1 | 1 | 1 | 0 |
| P2 | 47 | 3 | 1 | 1 | 0 | 0 |
| P5 | 46 | 3 | 1 | 1 | 0 | 0 |

## Commands Run

All commands were run from `/home/chuanbo/projects/JobRadar/backend`:

```bash
WORKSPACE_PERSONA=P1 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P1 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P1 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
WORKSPACE_PERSONA=P1 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step5_recommend_and_reject.py

WORKSPACE_PERSONA=P2 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P2 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P2 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
WORKSPACE_PERSONA=P2 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step5_recommend_and_reject.py

WORKSPACE_PERSONA=P5 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P5 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P5 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
WORKSPACE_PERSONA=P5 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step5_recommend_and_reject.py
```

Final chat history GETs:

```bash
curl -H 'X-Resume-User-Key: eval_workspace_P1_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/122/chat
curl -H 'X-Resume-User-Key: eval_workspace_P2_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/125/chat
curl -H 'X-Resume-User-Key: eval_workspace_P5_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/128/chat
```

## Raw Output Paths

Backend reports:

- `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P1/report.json`
- `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P2/report.json`
- `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P5/report.json`

Copied raw logs and chat histories:

- `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P1_*`
- `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P2_*`
- `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P5_*`

## Residual Risks

- This was API/script-based validation, not visual frontend validation at `http://127.0.0.1:3004`.
- The simulator generated fallback user messages in several turns, so some chat/coach findings are polluted by non-realistic user input.
- Because finalize attempts used an invalid action name, this run cannot distinguish between "finalize is broken" and "eval script is stale"; it only proves this eval path did not validate finalization.
- Existing worktree had many pre-existing modifications; I did not modify business code or revert anything.
