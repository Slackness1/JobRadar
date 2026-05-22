# Workspace Coach/Chat Independent Review - 2026-05-22

Runtime: `/home/chuanbo/projects/JobRadar`, branch `feat/workspace-redesign-2026-05-20`, backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:3004`.

Data source: Feishu `00_personas-saif` P1-P8 PDF/JSON. SHA256 matched repo fixtures exactly. No business code was changed.

## Verdict

Coach mode is better than the earlier "thinking disappears and no reply" failure: all P1-P8 runs produced visible assistant chat replies after plan turns. But it is **not demo-safe as a closed-loop experience** yet.

Main problem: the system can collect evidence and sometimes draft, but still gets stuck in clarification, crashes on later turns, or promises "reply 定下来 and I will archive" without actually proving archive/writeback. Chat rewrite is mostly usable, but memory continuity and audit wording still leak rough edges.

## BLOCKER

1. **Coach can crash after a draft exists**
   - P1 `plan_turn4` returned HTTP 500 after the item had reached `awaiting_review`.
   - P3 `plan_turn6` also returned HTTP 500 after a draft path.
   - User impact: a student can answer multiple rounds, see the coach nearly finish, then hit a server error.

2. **Some personas never get a draft even after 6 turns + repeated finalize**
   - P4: 6 coach turns plus two `就这样，定下来` probes, still `clarifying`, no draft.
   - P5: same failure, no draft.
   - User impact: this reproduces the "evidence 够了为什么不开始写" complaint.

3. **P5 coach focus and audit wording are polluted**
   - P5 is IBD/GBM, but assistant text references unrelated redline examples: `50MW 电站 / 100 万欧元`.
   - Root clue: `plan_turn.py` user-facing `implausible_scale` translation hardcodes the P8 example.
   - User impact: a finance student sees an irrelevant energy-project warning and loses trust immediately.

## MAJOR

1. **Finalize only works after a draft exists**
   - P1/P3/P6/P8 finalized on first `就这样，定下来`.
   - P2/P7 generated draft on first finalize phrase, then finalized on the second.
   - P4/P5 never produced draft, even after repeated finalize intent.

2. **"我就入档" is not proven by backend behavior**
   - Assistant draft text says: `再回一句"就这样 / 定下来", 我就入档`.
   - Probe shows the plan item becomes `finalized`, but no explicit memory write endpoint is called by `/plan/turn`.
   - This should be either real auto-archive or the wording should say "我就敲定这一版，之后点入档保存".

3. **Coach focus title is too generic in plan state**
   - Plan items are titled `internship #1`, not company/role.
   - Frontend kickoff may show this generic title, making it hard for the student to know which experience is being coached.

4. **Chat memory continuity has holes**
   - P2 repeated-fact dedupe failed: repeated T1 fact created 3 new memories.
   - P5 preference capture failed.
   - P6 chat memory growth and preference capture both failed in Worker C.

5. **Eval harness has stale finalize action**
   - Built-in `step4_plan_mode.py` calls `finalize_item`, but API accepts `finalize`.
   - This caused expected 422s in every worker report and should be fixed before using the harness as a release gate.

## MINOR

1. Playwright UI screenshots were not captured because neither Python nor Node Playwright is installed in this runtime.
2. Recommendation smoke passed enough for this run: recommendation GETs returned non-empty items and did not block coach/chat testing.
3. P8 redline was not reinforced in the exercised path. PVSyst/50MW/100万欧元 remained low-confidence parser seed, not a finalized coach draft. However, the redline item was not explicitly risk-flagged in memory.

## Files

- Worker reports:
  - `worker-A.md`
  - `worker-B.md`
  - `worker-C.md`
- Machine-readable summaries:
  - `persona-run-matrix.json`
  - `coach-turn-diff.json`
  - `chat-rewrite-audit.json`
- Raw runtime output:
  - `/tmp/jobradar_workspace_coach_eval_2026_05_22/raw/`

## Recommended Fix Order

1. Fix P1/P3 500s on plan turns after `awaiting_review`.
2. Make repeated finalize intent in `clarifying` actually write a draft for P4/P5 or return one precise missing fact.
3. Remove hardcoded `50MW / 100 万欧元` from generic user-facing audit copy; keep it only in logs/tests or make it context-specific.
4. Align plan finalize wording with behavior: either auto-archive on finalize or stop promising archive.
5. Replace generic `internship #1` titles with company/role titles in plan items.
6. Update eval harness action from `finalize_item` to `finalize`, and derive anchors from `evidence[].tags` like the frontend does.
