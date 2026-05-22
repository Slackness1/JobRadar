# Worker C Independent Review - Workspace Coach/Chat Retest (2026-05-22)

Scope: P6 and P8, on runtime `backend http://127.0.0.1:8000`, `frontend http://127.0.0.1:3004`, worktree `/home/chuanbo/projects/JobRadar`, branch `feat/workspace-redesign-2026-05-20`.

I did not modify business code and did not revert existing worktree changes. I only wrote this report and saved raw command output under `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/`.

## Summary

- P8 redline outcome: no evidence that chat/plan draft reinforced `PVSyst / 50MW / 100 万欧元 / 节约 / 独立完成`. The redline item is present only as a parser-seeded memory row with `confidence=0.6` and `user_confirmed=false`, so it is downgraded and not high-confidence. However, it is not explicitly risk-flagged.
- P6 outcome: plan-mode coach did ask useful tool/action follow-ups for a skill/tool-heavy quant experience, but the chat step had continuity and memory-capture failures, and plan closure remains weak (`final_anchors=0`, finalize attempt returns 422).
- No 500 or 409 observed in P6/P8 reports. Both personas had one 422 from `plan_finalize_attempt` using invalid action `finalize_item`.

## BLOCKER

None found in this Worker C run.

## MAJOR

1. P6 chat continuity and memory assertions failed.
   - `step3` assertion `memory_total_increased_over_baseline` failed: actual `0`.
   - `step3` assertion `preference_captured` failed: actual `0`.
   - Turn 1 student simulator produced fallback text: `(fallback) T1_internship_detail — 模拟消息生成失败 ()`.
   - Assistant replied as if no resume content was available, despite the session having completed upload/profile confirmation.
   - Impact: chat rewrite is not reliably continuous for P6; it recovered later, but the first turn breaks the intended full-loop experience.

2. Plan-mode closure is not clean for both P6 and P8.
   - P6: `turns_taken=6`, `final_anchors=0`, focus item final status `awaiting_review`; final plan GET still has global status `clarifying`.
   - P8: `turns_taken=6`, `final_anchors=0`, focus item final status `awaiting_review`; final plan GET still has global status `clarifying`.
   - Both runs then attempted `POST /plan/actions` with `action=finalize_item` and got 422:
     `Input should be 'ask', 'write', 'drop', 'replan', 'ready_to_write', 'finalize' or 'block'`.
   - Impact: the item can reach a draft/awaiting-review state, but the eval cannot verify a clean closed loop to finalization. The `final_anchors=0` metric also appears out of sync with evidence/draft creation.

3. P8 redline is downgraded but not explicitly risk-flagged.
   - Memory endpoint for session 126 contains the PVSyst item as `source_module=parser_seed`, `confidence=0.6`, `user_confirmed=false`.
   - Raw excerpt still includes: `使用 PVSyst 完成 50MW 光伏电站设计...节约项目成本 100 万欧元`.
   - I did not find a corresponding explicit risk flag for this parser-seeded redline item.
   - Impact: this is not high-confidence and was not reinforced, so it is not a blocker in this run. But for a redline persona, silent low-confidence retention is weaker than an explicit suspicious-number/overclaim flag.

## MINOR

1. P6 plan-mode coach behavior is directionally good but noisy.
   - It asked for tools and core action: `工具：Python + pandas，内部回测框架`, `你本人最核心的动作是什么`.
   - It asked for leadership substantiation before using stronger verbs.
   - One generated question degraded to a transport-timeout fallback: `系统暂时无法生成详细问题（transport: The read operation timed out）...`.

2. P8 coach focused on the first energy-price internship rather than the PVSyst redline internship.
   - Step3/step4 did not exercise the PVSyst item through coach turns; redline validation here is mostly via parser seed, memory endpoint, and absence from final draft.
   - The P8 plan draft includes student-introduced MAPE `3%` with a non-blocking `student_introduced_number` flag. It asked repeated clarifications about conflicting MAPE values, which is good, but it ultimately drafted with the newest student number.

3. Runtime latency is high.
   - P6 wall times: step1 `95.33s`, step3 `119.89s`, step4 `198.11s`.
   - P8 wall times: step1 `187.24s`, step3 `181.13s`, step4 `80.40s`.
   - Scripts have almost no intermediate logging, making long waits hard to distinguish from hangs.

## Residual Risk

- Because P8 step3/step4 did not select the PVSyst internship, this run cannot prove the coach would block the redline if the user explicitly asked to rewrite that bullet. It only proves the runtime did not reinforce it in the exercised path and did not store it as high-confidence confirmed memory.
- P6 account-memory state after plan contains a role preference captured during plan, but step3 report still shows no memory growth. This suggests memory behavior may depend on endpoint/path, not just conversation content.
- The eval script's finalize action may be stale (`finalize_item`), but from a full-loop QA perspective the current run still cannot demonstrate finalization.

## Commands Run

```bash
cd /home/chuanbo/projects/JobRadar/backend
WORKSPACE_PERSONA=P6 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P6 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P6 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
WORKSPACE_PERSONA=P8 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step1_upload.py
WORKSPACE_PERSONA=P8 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step3_chat_5_turns.py
WORKSPACE_PERSONA=P8 PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/step4_plan_mode.py
curl -sS -H 'X-Resume-User-Key: eval_workspace_P8_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/126/memory
curl -sS -H 'X-Resume-User-Key: eval_workspace_P6_2026_05_20' http://127.0.0.1:8000/api/resume-copilot/sessions/124/memory
```

## Raw Outputs And Reports

- P6 session id: `124`
- P8 session id: `126`
- P6 report: `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P6/report.json`
- P8 report: `/home/chuanbo/projects/JobRadar/backend/scripts/_out/eval_workspace_2026_05_20/P8/report.json`
- Raw command output directory: `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/`
- Memory snapshots:
  - `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P6_memory_session_124.json`
  - `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/P8_memory_session_126.json`

## HTTP Error Summary

- 500: none observed.
- 409: none observed.
- 422: one per persona, both from `plan_finalize_attempt` with invalid `finalize_item` action.
