# Round 2 Worker A — P1, P2, P3 (run 2026-05-21)

Backend: `http://127.0.0.1:8000` (healthy, dev VPS host=lavm-wlcndo6anm). All raw API responses in `/tmp/sim_worker_a_r2/`.

Sessions / user-keys:
- P1 → session 96, `sim_P1_20260521r2_7563249a` (中信证券 internship as focus)
- P2 → session 102, `sim_P2_20260521r2_<rand>` (CICC TMT internship as focus)
- P3 → session 105, `sim_P3_20260521r2_<rand>` (国海富兰克林 internship as focus)

## Fix verification matrix

| Fix | P1 | P2 | P3 | Notes |
|---|---|---|---|---|
| B4 parser skills + no phantom "C" | ✓ | ✓ | ✓ | P1 keeps Wind/Bloomberg/DCF/VAR/VECM/财务三张表勾稽; P2 keeps Wind API/DCF/PEG; P3 keeps LSTM+Transformer+GRU+PyTorch. None contain a phantom "C". |
| B3 canonicalize track | ✓ (n/a in flow, only canonical key used) | ✓ | ✓ | P2 sent `"卖方研究 TMT (sell-side research)"` → BE persisted `["卖方研究·S&T"]`, 200 OK, 15 recs returned (was 0 in R1). P3 sent `"私募 / 资管基本面研究"` → persisted `["二级买方·基本面"]`, 15 recs. Verified `x-unknown-tracks: this-is-bogus-track-xyz` header URL-encoded when a bogus track is mixed in. |
| M3 finalize intent | ✓ (intent) | ✓ (intent) | ✓ (intent) | "就这样,定下来。" / "ok 可以了" / "差不多就这样吧, 定下来。" all correctly flip the focused item from `awaiting_review` → `finalized` and the AI replies "已敲定。". **BUT** the next-item routing is still broken — see Bug R2-1. |
| M1 tag translated (no raw English tag in chat) | ✓ | ✓ | ✓ | Grepped chat for `overclaim` / `tech_unverified` / `vague_verb` / `student_introduced_number` → 0 hits across all 3 personas. AI follow-ups are Chinese, targeted (e.g. P3 turn 2: "你提到的20人团队和50亿投决是在国海富兰克林基金实习期间发生的吗？能否具体说明你的角色和项目场景？"). |
| M5 student-introduced-number | ✓ | ✓ | ✓ | P1 200 SKU + 15% → both flagged `student_introduced_number` (blocking=false); P2 54% + 87% → both flagged; P3 15% → flagged. Vague verb (`帮助`) also surfaces correctly. |
| M2 open_questions dedup | ✓ | ✓ | ✓ | P2 coach re-asked the SAME generic "本人最核心的动作是什么?" question in chat after Turn 3, but `open_questions[]` stayed at length 1 (already answered, not duplicated). P3 has 2 entries because they're genuinely different topics (20人团队 vs LSTM/15%). No spurious duplicates anywhere. |
| M4 draft EXTEND | n/a (one round to draft) | ✓ | ✓ | P2 Turn 2 draft: "搭建半导体设备国产化率跟踪数据库..." → Turn 4 draft kept that narrative AND added "该数据库被3位首席复用，将行业研判准确率从54%提升至87%。". P3 Turn 1 draft fused both the 装机量跟踪表 anchor AND the LSTM/Transformer addition — fixes Round 1 P3-5 ("drops half the student's content"). |

## Summary
- Total NEW bugs found: **2** (1 MAJOR, 1 MINOR).
- Round 1 bugs verified fixed: **9 / 13** (B3, B4 across all 3 personas, M1, M2, M4, M5, P1-3 plan_status determinism, P2-2 inferred_tracks now correct, P3-1 inferred_tracks Chinese, P3-3 basic_info no "None", P3-4 recommendation_status flips to completed, P3-5 draft EXTEND).
- Round 1 bugs that REPRO (4): P1-1 (`组/部` suffix on company still stripped), P1-2 / P2-2-partial / P3-1-recs (matched_track_label still echoes student preference), P1-4 (current_item_id snaps to self_intro after finalize), P1-5 / P3-6 — the fabrication check is now done as `student_introduced_number` flag (NEW name, NEW location) so the *spirit* is fixed; previous bugs P1-5 / P3-6 are closed.
- Verdict for SAIF demo: **major-fixes-shipped-but-1-blocker-and-1-major-remain**. B3 BLOCKER from R1 is fully fixed (no more 0-rec dead-end for natural-language tracks); coach now has anti-fabrication; finalize-on-"就这样" works. But: (a) "我们做完中信这段了" → coach replies "OK, 下一项是 self_intro" is a confusing UX regression (R2-1), and (b) `matched_track_label` is still a no-op echo, so all jobs look mis-categorised regardless of company / role family.

## New bugs (only NEW ones, don't re-list Round 1)

### Bug R2-1: After M3 finalize, `current_item_id` jumps to `self_intro` instead of next sibling/parent [MAJOR]
- Persona: P1 (session 96), P2 (session 102), P3 (session 105) — reproduces on all three
- Step: 9 (plan/turn with finalize intent)
- Endpoint: `POST /api/resume-copilot/sessions/{id}/plan/turn` body `{"content":"就这样,定下来。"}`
- Expected: after a student finalizes the focused parent-level internship item, `current_item_id` should advance to:
  - the first pending child bullet of that same internship (e.g. `internship #1 - bullet #1`), OR
  - the next sibling parent (e.g. `internship #2`)
- Actual: `current_item_id` snaps to the *first pending item in the template* — which is always `self_intro` (item ordinal 0). Items already finalized are skipped, but the template order, not the cursor position, drives the next pick. So a student who finalises 易方达 hears "已敲定。" and then on next turn the AI grills them about 自我介绍, with no UI cue why.
- Reproduction:
  - P1: `jq '{cur: .current_item_id, prev_status: (.items|map(select(.id=="e37db52a-3459-4447-a8f2-f1f90812d38c"))[0].status), next_pending_kind: (.items|map(select(.status=="pending"))[0].kind)}' /tmp/sim_worker_a_r2/P1_turn2_finalize.json` → `{cur: "1fe...", prev_status: "finalized", next_pending_kind: "self_intro"}`
  - P2: `/tmp/sim_worker_a_r2/P2_turn5_finalize.json` — same shape
  - P3: `/tmp/sim_worker_a_r2/P3_turn5_finalize.json` — same shape
- Note: This is Round 1 P1-4 still alive. The "M3 finalize intent" fix correctly handles the *intent detection* and the *item status transition* (`awaiting_review` → `finalized`), but the post-finalize cursor walker still uses template order. For a student doing the "我只想加厚这一段" flow (per the new spec in CLAUDE.md), the AI then immediately asks about self_intro is a UX dead-end.
- Severity: MAJOR. From the student's POV: "我刚定下来中信证券这段, AI 现在让我聊自我介绍, 它是不是忘了我刚才的进度?" — directly contradicts the SAIF "可证伪反馈" promise.

### Bug R2-2: `matched_track_label` still echoes student's preferred_track for clearly-mismatched jobs [MAJOR]
- Persona: all 3 (P1 + P2 + P3)
- Step: 7 (recommendations after generate)
- Endpoint: `GET /sessions/{id}/recommendations`
- Expected: `matched_track_label` should reflect the *job's* classification, not the *student's* preference. A 衍复投资 机器学习工程师 (infra) job should be `量化` or `工程`, not `二级买方·基本面`.
- Actual: 100% of returned items carry `matched_track_label` exactly equal to the student's saved `preferred_tracks[0]`.
  - P1 (pref = 二级买方·基本面): 17 items all `"二级买方·基本面"`, including 华泰证券 行业研究员-金融周期 (clearly 卖方).
  - P2 (pref = 卖方研究·S&T): top 3 are all 高盛 GSET DevOps / Sydney Compliance Equities — labelled `"卖方研究·S&T"` regardless. These are S&T-adjacent infra jobs at best.
  - P3 (pref = 二级买方·基本面): top 3 are 衍复投资 机器学习工程师 / 性能工程师 + 兴业银行 经济与金融研究院 行业研究助理 — all labelled `"二级买方·基本面"` even for ML infra roles.
- Reproduction: `jq '[.items[:3] | .[] | {company,job_title,matched_track_label}]' /tmp/sim_worker_a_r2/P{1,2,3}_recs.json`
- Note: This is Round 1 P1-2 / P3-1-derivative still alive. The label is currently FE garnish but it's load-bearing because the demo answers "is this job a fit for my track?". If every job answers "yes, exactly your track" the signal collapses. This was flagged R1; no movement.
- Severity: MAJOR. Recommend computing `matched_track_label` from the rule-engine's actual track classification per-job (already available in `matched_track_key`), not from prefs.

### Bug R2-3: `skills.technical` contains free-text annotation fragments as separate "skills" [MINOR]
- Persona: P1 (also reproduces softer on P2/P3 via "SQL基础" type artifacts).
- Step: 3 (parsed-profile)
- Endpoint: `GET /sessions/96/parsed-profile`
- Expected: each entry in `skills.technical` is an atomic skill name (e.g. `"Python"`, `"Bloomberg Terminal"`).
- Actual: P1 has these as standalone skill entries:
  - `"3 年实战经验"` (loose duration string, no anchor to which skill)
  - `"熟练窗口函数"` (description fragment of SQL skill, listed as own skill)
  - `"Bloomberg + Wind + Choice 高级用法"` AND separately `"Wind"`, `"Bloomberg"`, `"Choice"` — duplication
- And `skills.tools` has a literal `"Bloomberg Terminal / Wind 资讯 (高级函数 + Wind API) / Choice 金融终端 / Tushare / AKShare / Tableau /"` slash-joined dump alongside the same atomized entries.
- Reproduction: `jq '.profile.skills' /tmp/sim_worker_a_r2/P1_parsed.json`
- Note: The B4 fix successfully atomized the model-architecture names, but it now over-shoots — it's emitting BOTH the atomized form AND the original phrase AND meta-fragments. FE will render "技能: 3 年实战经验" which reads as nonsense.
- Severity: MINOR. Cosmetic but visible on resume confirm chip.

## Round 1 bugs that REPRO (still broken)

- **Bug P1-1 (parser truncates company suffix)**: P1's three internships still came back as `"中信证券研究所"`, `"易方达基金"`, `"高瓴资本"` — the `· 消费组` / `· 消费+大健康组` / `· 二级研究部` distinguishing tail is gone. (Hidden by R2-3 surfacing more skill atoms, so easy to miss.) `jq '.profile.internships[].company' /tmp/sim_worker_a_r2/P1_parsed.json`. **Not in today's fix list — surfacing again as still-broken.**
- **Bug P1-2 / P3-1-recs (matched_track_label echo)**: see R2-2 above. Same root cause as Round 1 — label still derived from `preferences.preferred_tracks[0]`, not from per-job classification.
- **Bug P1-4 (current_item_id snaps to item-0)**: see R2-1 above. The status transition works (finalize fires correctly via "就这样") but the cursor advance logic still picks template-first not next-sibling.
- **Bug P2-4 (role field has dept prefix)**: P2's parsed profile now shows `role: "研究实习生"` cleanly — APPEARS FIXED. `jq '.profile.internships[].role' /tmp/sim_worker_a_r2/P2_parsed.json` returns `"研究实习生"` for both. Closed.

## Bugs from Round 1 that ARE fully verified fixed (for the record)

| R1 bug | Status | Evidence |
|---|---|---|
| P1-3 plan_status non-deterministic | fixed | Across P1/P2/P3 the start → `awaiting_plan_approval` → approve → `clarifying` flow is consistent. P1 used to land in `clarifying` from start; now it correctly lands in `awaiting_plan_approval`. |
| P1-5 / P3-6 no fabrication warning | fixed (renamed flag) | Same intent, new mechanism: `risk_flags[].kind = "student_introduced_number"` fires on '200', '15%', '54%', '87%' across all 3 personas. |
| P2-1 [BLOCKER] 0 recs on natural-language track | fixed | P2 PUT prefs with `"卖方研究 TMT (sell-side research)"` (verbatim from persona JSON) → 200 OK, persisted as `["卖方研究·S&T"]`, generate returns 15 recs. P3 same flow with `"私募 / 资管基本面研究"` → 15 recs. |
| P2-2 inferred_tracks wrong direction | fixed | P2 now `["卖方研究·S&T", "二级买方·基本面"]` with sell-side first. |
| P2-3 phantom "C" | fixed | No phantom "C" anywhere in P1/P2/P3 (validated via `jq 'any(. == "C")'`). |
| P3-1 inferred_tracks mixed language | fixed | P3 now `["二级买方·基本面", "量化"]` — all Chinese. |
| P3-2 drops LSTM/Transformer | fixed | P3 has all of `LSTM`, `Transformer`, `GRU`, `PyTorch`, `时序模型`. |
| P3-3 basic_info literal "None" | fixed | P3 `basic_info` has only `name/email/location/headline` keys — no phone/github/linkedin/website fields at all (cleanly omitted). |
| P3-4 recommendation_status stuck running | fixed | All 3 sessions now report `recommendation_status: "completed"` once items are ready. |
| P3-5 draft drops half the student's content | fixed | P3 Turn 1: input mentions both 装机量跟踪表 (in profile) AND LSTM/Transformer + 15% (new). Resulting draft preserves both anchors: `"独立搭建动力电池装机量月度跟踪表（覆盖18个月数据），并应用LSTM+Transformer模型进行预测，将预测准确率提升15%。"` |

## Spot-check evidence files (for QA replay)

```
/tmp/sim_worker_a_r2/
├── P1_parsed.json          # B4: skills.technical, internships, inferred_tracks
├── P1_recs.json            # R2-2: matched_track_label = "二级买方·基本面" on 卖方 jobs
├── P1_turn1.json           # M5: 200 / 15% flagged as student_introduced_number
├── P1_turn2_finalize.json  # R2-1: current_item_id → self_intro after finalize
├── P2_parsed.json          # B4: no phantom "C", Wind API kept; inferred_tracks 卖方研究·S&T first
├── P2_prefs.json           # B3: "卖方研究 TMT (sell-side research)" → "卖方研究·S&T"
├── P2_prefs_h2.txt         # B3: x-unknown-tracks: this-is-bogus-track-xyz header
├── P2_recs.json            # 15 items (was 0 in R1)
├── P2_turn4.json           # M4: draft EXTEND keeps prior narrative; M5: 54%/87% flagged
├── P2_turn5_finalize.json  # R2-1: same self_intro snap on "ok 可以了" intent
├── P3_parsed.json          # B4: LSTM+Transformer+GRU+PyTorch kept; basic_info no "None"; inferred_tracks all-Chinese
├── P3_recs.json            # R2-2: ML infra jobs labelled "二级买方·基本面"
├── P3_turn1.json           # M4+M5+P3-5 fix: fused 装机量+LSTM narrative, 15% flagged
└── P3_turn5_finalize.json  # R2-1: "差不多就这样吧, 定下来。" intent works, then self_intro snap
```
