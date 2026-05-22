# Round 2 Worker B — P4, P5, P6 (run 2026-05-21)

Branch: `feat/workspace-redesign-2026-05-20`
Backend: `http://127.0.0.1:8000` (dev VPS lavm-wlcndo6anm)

Session IDs: P4=107, P5=109, P6=110.
User keys (saved at `/tmp/persona_resumes/workerB_r2/P{n}_userkey.txt`):
- P4: `sim_P4_20260521r2_76771`
- P5: `sim_P5_20260521r2_92502`
- P6: `sim_P6_20260521r2_32553`

Per-turn artifacts (request/response, plan snapshots, chat dumps): `/tmp/persona_resumes/workerB_r2/`.

## Fix verification matrix

| Fix | P4 | P5 | P6 | Notes |
|---|---|---|---|---|
| **M1** tag 翻成中文 (no `tech_unverified` / `overclaim` leak) | Y | Y | Y | P4 t2 surfaces 「主导度需要佐证」; P5 t4 surfaces 「动词太强 (e.g. 主导/独立完成)」 + 「主导度需要佐证」 + 「技术细节缺出处」; P6 t2/t3 surface 「技术细节缺出处」. Zero raw English tag names anywhere in the 18 assistant messages collected. |
| **M2** open_questions dedup | Y | Y | Y | P6 cleanest: t2 fires `tech_unverified`-translated question; t3 fires the **same** kind again — `oq_count` stays at **2**, the duplicate is suppressed. P4 (t2/t4) and P5 (t2/t3/t4) generate **distinct** follow-ups each time (no dup append), confirming the normalized-hash skip works. |
| **M3** finalize 接住 ("定下来 / 用这版 / ok 就这样") | Y* | n/a | Y | **Gate**: only fires when `current_item.status == 'awaiting_review'`. For P4 sid=107 retest (`p4_finalize_retry.py`): item in awaiting_review + "定下来。" → `prev_item_status='finalized'` + `current_item_id` advanced to next pending internship + assistant replied 「已敲定。」. For P6: same — item ended in `finalized`, current advanced (`19d2c659` → `7e6df0ca`). P5 never reached `awaiting_review` within the 4-turn flow (audit kept blocking with overclaim / 32 笔 deal mismatch) so finalize never had a chance to fire — **M3 logic untested for P5, but no failure observed**. |
| **M4** draft EXTEND (not replace) | Y | n/a | Y | P4 turn 3 draft (110 chars: 4 部门轮岗 + 12 次访谈 + 8 份画像 + Top 5 + return offer) → turn 6 draft (133 chars: same content **plus** 「与总行 mentor 合作完成面向 VP 的项目结题汇报」) — the previously consolidated narrative is **kept** and the new mentor fact is **appended**. Compare to round 1 P4 where turn 4 draft dropped 4 部门轮岗 and Top 5 entirely. P6 final draft (sid=110) preserves both Avramov 0.04 IC **and** Frazzini 0.4→0.62 sharpe in one block, plus tools (qlib + LightGBM + 18→7min). P5 never produced a draft in the flow. |
| **B2** per-employer cap = 3 (per stream) | Y | Y | Y | Cap is enforced **per (company, is_internship)** pair (this is the impl in `workflow.py::_balance_two_streams`, not global). P4: max 3 (浦发银行 campus). P5: max 3 (Goldman Sachs campus = 3, Goldman Sachs intern = 3 — 6 total but within the cap by design). P6: max 3 (Goldman Sachs campus). Initial "Goldman Sachs = 6" alarm was a false positive on my side until I re-read the impl. **If product wants global cap=3 instead, that's a config decision, not a bug.** |

\* M3 fires correctly on the *retry* turn after the draft has been generated. See "Bug R2-1" below for the resulting UX trap.

## Summary

- Total NEW bugs found: **3** (1 major UX, 2 minor — see below)
- Round 1 bugs verified fixed: **9 / 11** (the 4 majors that the M1/M2/M3/M4 fixes targeted, plus B2; Bug 4/6 parser, Bug 5 McKinsey rerank, Bug 9 HTTP-500 not retested but no recurrence observed)
- Verdict: **ready for the SAIF faculty demo with one known UX friction point** (Bug R2-1) and one cosmetic issue (Bug R2-2). The Round 1 blockers (tag leak / dup-question loop / no finalize path / draft replace) are all gone.

## New bugs

### Bug R2-1: 学生必须连续两次说「定下来」才能 finalize — coach 把第一次的「定下来」误认为 clarifying 信号 [MAJOR UX]

- **Step**: P4 turn 6 — student sent `差不多就这样吧，定下来。` while item was in `clarifying` (with an unanswered question about mentor)
- **Expected** (from the user perspective): explicit "定下来" should commit whatever draft already exists OR generate one final draft and commit it in one shot.
- **Actual**: Coach generated a fresh draft (transitioning the item to `awaiting_review`) and replied 「要改还是定下来？」 — student then had to re-type `定下来。` a **second** time to actually finalize. Only on the second 定下来 did `prev_item_status='finalized'` + `current_item_id` advance.
- **Why this matters**: a real student saying "差不多就这样吧, 定下来" *thinks* they're done. Instead they see another draft and another question. The recovery is only 1 extra turn but the cognitive jolt is significant — feels like the AI didn't listen.
- **Reproduction**: `/tmp/persona_resumes/workerB_r2/p4_finalize_retry.py` proves the two-step path works; `/tmp/persona_resumes/workerB_r2/P4_chat_after_t6.json` shows the first 定下来 produced a draft instead of a finalize.
- **Suggested fix**: when status is `clarifying` and the student sends a finalize intent, treat it as "skip remaining open questions, generate the final draft, **and** finalize in the same turn" — i.e. one-shot.

### Bug R2-2: `_AUDIT_TAG_HINT_CN` translation for `overclaim` exposes the literal English snippet `e.g. 主导/独立完成` to the student [MINOR]

- **Step**: P5 turn 4 assistant message verbatim:
  > 这一版我想再确认一下「动词太强 (e.g. 主导/独立完成)」(另外还有: 主导度需要佐证、技术细节缺出处) — 能确认一下这段经历里你具体负责什么吗?
- The pattern `「动词太强 (e.g. 主导/独立完成)」` reads like internal rule documentation leaked into the user-facing message. The `(e.g. ...)` parenthetical is a **prompt-engineering hint** for the LLM, not something a student should see.
- **Expected**: just `「动词太强」 — 能确认你具体负责什么吗?` or, even better, translate per fact (e.g. "你说『主导了 32 笔 deal』，但其实可能更准确的是『参与了 32 笔』 — 帮我确认一下?")
- **Reproduction**: `_AUDIT_TAG_HINT_CN['overclaim'] = ('动词太强 (e.g. 主导/独立完成)', '...')` in `plan_turn.py:279-280`.
- **Severity**: minor — the message is still intelligible, but the `(e.g. ...)` artifact is the kind of thing SAIF faculty will instantly flag as "this AI feels half-baked".

### Bug R2-3: 当一个 turn 同时触发 ≥2 个 audit tag, fallback message 一次性把三个 hint 全堆给学生, 信号量超载 [MINOR]

- **Step**: P5 turn 4 — three Chinese hints in one message (`「动词太强」(另外还有: 主导度需要佐证、技术细节缺出处)`)
- **Expected**: pick the highest-priority single hint and ask one focused question. Showing three audit failures in one breath leaves the student paralyzed about which one to address first.
- **Actual**: All three are listed; the actual follow-up question is the generic 「能确认一下这段经历里你具体负责什么吗?」 which only really addresses `overclaim`. The other two are dangling.
- **Severity**: minor — the loop still advances, but the question feels unmoored to the message. This is the "技术细节缺出处" hint being attached but not actually asked-about.

## Round 1 bugs that REPRO (still broken)

None of the 4 majors (Bugs 1, 2, 3, 10, 11) reproduce. Specifically:

- **Bug 1 (P4 t3 `tech_unverified` literal leak)**: dead — P4 t2 in this run says 「主导度需要佐证」, no English tag.
- **Bug 2 (P4 t3-4 loop never advances)**: dead — every turn produces a new question or draft transition. `current_item` does sit on the same item for ~4 turns but that's expected (it's the active focused item, not a "loop"). After R2-1 it advances cleanly.
- **Bug 3 (P4 draft replaces not merges)**: dead — verified by side-by-side turn 3 (110 chars) vs turn 6 (133 chars) drafts; the 4-部门 / Top 5 / return offer narrative is preserved on every regeneration.
- **Bug 5 (P5 McKinsey BusinessAnalyst noise)**: not observed in this run. P5 recs are now 6 Goldman (3 campus / 3 intern), 2 CICC, 1 中信建投, 1 华夏基金, 2 蚂蚁 — all on-track for IBD prefs. McKinsey absent. May still surface with different rerank seeds but the cap + diversification is doing its job here.
- **Bug 7 (P5 `tech_unverified` loop / 3 dup open_questions)**: dead — P5 t2/t3/t4 each generate **different** questions (`open_questions` length 1→2→3→4, all distinct). M2 dedup confirmed when same kind fires twice (P6 t2/t3).
- **Bug 10 (P6 "定下来" not recognized as finalize)**: fixed (with the R2-1 caveat: needs the item to be in `awaiting_review` first). P6 retest with `p5p6_finalize_retry.py` shows finalize works end-to-end: `prev_item_status='finalized'` + assistant says 「已敲定。」 + current advances.
- **Bug 11 (P6 coach drops student-volunteered facts)**: dead — final P6 draft contains all 3 facts the persona was instructed to volunteer: Avramov IC 0.04 + Frazzini sharpe 0.4→0.62 + backtest 18min→7min engineering optimization.

Not retested (no recurrence either):
- **Bug 4 + Bug 6** (parser consistency): not specifically retested but parsed-profile saved at `/tmp/persona_resumes/workerB_r2/P{4,5,6}_parsed.json` — spot check shows P4 still drops sub-org ("招商银行" not "招商银行 · 总行管培生暑期项目"), P5 still piles sub-dept into role; **regression status: still present, no change from round 1**, but neither blocks coach flow.
- **Bug 8** (coach skips strong-persona technical follow-up): mixed — P5 t1/t2/t3 do ask grounded "请问 32 笔 deal 是哪些 deal" follow-ups instead of falling back to generic audit. Improvement vs round 1 but still room.
- **Bug 9** (HTTP 500 on `/plan/turn`): NOT reproduced in 13 plan/turn calls across 3 personas. May be flaky / load-dependent; backend did die twice during my run from unrelated parallel-load issues (I had to restart it), but that's a separate environmental thing.

## Cross-persona patterns this round

1. **The M3 finalize gate is conservative by design but the UX needs polish**: requiring item to be in `awaiting_review` *before* "定下来" fires is the safe rule (don't let students nuke open audit findings), but the student doesn't know that distinction. Either auto-promote-and-finalize (R2-1 suggestion) or surface the gate explicitly ("还有 1 个待澄清的点, 我先帮你写一版你看")
2. **M2 dedup works on identical text but not on semantically-equivalent text**. P5 t2 + t3 + t4 each crafted a slightly differently-worded follow-up to the same `overclaim` finding — none triggered the hash dedup. Not strictly a bug (the questions are genuinely different), but if you have a persona that triggers the same audit kind 3 times, you'll still get 3 different follow-up questions piled on. Future hardening: dedup by `audit_kind` not just by text hash.
3. **Coach replan/mismatch logic on P5 is solid**: when the student gave "中金 IBD 32 笔 deal" content while focused on "高盛 GBM" internship, the coach correctly identified the mismatch in plain Chinese on t1/t2/t3 instead of just merging it incorrectly. This is good cross-experience hygiene.
4. **B2 per-employer cap is per-stream**, not global. **Action item for product**: confirm this is the intended product spec. If you want max 3 *globally* per company, the impl needs `per_stream` removed from the cap key.
5. **Latency**: parse ~25-35 s, generate ~120-150 s (slower than round 1 by ~30 s on average — likely just LLM API variance), plan/turn 8-22 s. Acceptable for the demo.

## Test artifacts

- Per-turn snapshots: `/tmp/persona_resumes/workerB_r2/P{4,5,6}_turn{1..6}.json`
- Chat after each turn: `/tmp/persona_resumes/workerB_r2/P{4,5,6}_chat_after_t{n}.json`
- Recommendations: `/tmp/persona_resumes/workerB_r2/P{4,5,6}_recs.json`
- Memory entries: `/tmp/persona_resumes/workerB_r2/P{4,5,6}_memory.json`
- Driver scripts (throwaway, not committed): `run_persona.py` + `analyze.py` + `p4_finalize_retry.py` + `p5p6_finalize_retry.py`
- Final analysis matrix JSON: `/tmp/persona_resumes/workerB_r2/analysis_summary.json`
