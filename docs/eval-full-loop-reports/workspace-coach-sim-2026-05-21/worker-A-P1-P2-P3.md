# Worker A — P1, P2, P3 (run 2026-05-21)

Backend: `http://127.0.0.1:8000` (commit on `feat/workspace-redesign-2026-05-20`).
All raw API responses saved under `/tmp/sim_worker_a/` for spot-check.

## Summary
- Total bugs found: **13** (blocker: 1, major: 7, minor: 5)
- Time spent per persona: P1 ~7 min, P2 ~5 min (incl. one retry-with-canonical-key cycle), P3 ~5 min.
- Overall verdict: **has-blockers** — pipeline runs end-to-end but a SAIF student following the persona JSON's `target_track` verbatim hits "0 recommendations" with no explanation; parser drops critical cross-major / Quantamental skills; coach drifts to unrelated items after first finalize; anti-hallucination guard does not flag student-supplied numbers; and recommendation `matched_track_label` lies about sell-side vs buy-side.

---

## Persona P1 (林思远, 公募行研, strong) — session 87

### Bug P1-1: Parser truncates 实习公司 + 组名 to just 公司 [MAJOR]
- Step: 3 (parsed-profile)
- Endpoint: `GET /api/resume-copilot/sessions/87/parsed-profile`
- Expected: companies preserved as in resume ("中信证券研究所 · 消费组", "易方达基金 · 消费 + 大健康组", "高瓴资本 · 二级研究部").
- Actual: parser dropped the 组 / 部 suffix on all three: "中信证券研究所", "易方达基金", "高瓴资本". The 消费/大健康/二级研究 distinction is exactly the info a 投研 HR uses to triage.
- Reproduction: `jq '.profile.internships[] | {company, role}' /tmp/sim_worker_a/P1_parsed.json`
- Note: For P1 (consumer / pharma research), losing "· 消费组" demotes the bullet-evidence chain from a desk-specific signal to a generic 券商 stint.

### Bug P1-2: matched_track_label is "二级买方·基本面" for clearly 卖方 jobs [MAJOR]
- Step: 7 (recommendations)
- Endpoint: `GET /api/resume-copilot/sessions/87/recommendations`
- Expected: 华泰证券 行业研究员 岗位 should be labelled as 卖方 / sell-side, not 二级买方·基本面 (buy-side).
- Actual: 13/13 returned items all carry `matched_track_label = "二级买方·基本面"` even though 12/13 are 华泰证券 sell-side analyst roles. The label appears to be just the student's preferred_track copy-pasted onto every job.
- Reproduction: `jq '.items[] | {company,job_title,matched_track_label}' /tmp/sim_worker_a/P1_recs.json`
- Note: From a student's POV, every job in the list will look mis-categorised — this destroys trust in the matched_track signal. Same lie reproduces in P3 (session 91).

### Bug P1-3: focus_id flow inconsistently lands in `clarifying` vs `awaiting_plan_approval` [MAJOR]
- Step: 9 (coach start)
- Endpoint: `POST /api/resume-copilot/sessions/87/plan/start` body `{focus_kind:"experience", focus_id:163}`
- Expected: deterministic plan status after start — either always `awaiting_plan_approval` (and require approve), or always auto-clarify when focus is given.
- Actual: For P1 the plan was already `clarifying` immediately after `/plan/start` (subsequent `/plan/approve` returned `409 PLAN_NOT_AWAITING_APPROVAL (current: clarifying)`). For P2 the same shape lands in `awaiting_plan_approval` and `/plan/approve` returns 200. Same code path, two outcomes — depending on this for the FE will lead to "thinking spinner stuck" or "approve button does nothing" bugs.
- Reproduction: see `/tmp/sim_worker_a/P1_plan_start.json` (status `awaiting_plan_approval`?) — actually P1's start response was `awaiting_plan_approval` but the next state from `/plan` is `clarifying`. Either the start transition fires twice, or the GET re-derives state differently. Either way: a state-machine determinism issue.

### Bug P1-4: After finalize, `current_item_id` jumps to `self_intro` (item 0) instead of next bullet [MAJOR]
- Step: 9 (coach turns 3+)
- Endpoint: `POST /api/resume-copilot/sessions/87/plan/actions` action=`finalize` then `POST /plan/turn`
- Expected: after finalising `internship #1`, coach should advance to the next pending child (e.g. `internship #1 - bullet #1`) or to `internship #2`. Student's mental model is "we're done with this experience, let's keep going".
- Actual: `current_item_id` reset to the very first pending item (`self_intro` for P1). Then the AI sent: *"我准备写的版本里有 overclaim，需要先补一下出处。能给我一个能直接引用的具体数字或事实吗？"* — referencing a draft that never existed for self_intro and confusing the student.
- Reproduction: `cat /tmp/sim_worker_a/P1_turn3.json | jq '.current_item_id, .items[] | {kind,title,status}'`
- Note: This contradicts the new spec "学生只想加厚某段，不想跑完全简历". Anchor should stay on the experience or progress to its sub-bullets, not snap back to item 0.

### Bug P1-5: Coach draft has empty `risk_flags` despite student introducing numbers not in the profile [MAJOR]
- Step: 9 (turn 2)
- Endpoint: `POST /api/resume-copilot/sessions/87/plan/turn`
- Expected: per `CLAUDE.md` non-negotiable rule "_detect_fabricated_numbers() in 'improved' bullet" — if the draft text contains numbers not anchored in the original profile, `risk_flags` should surface a warning.
- Actual: student introduced "约 200 个 SKU" and "12 家经销商" in the chat reply. Original profile bullet had "5 家经销商" only. Draft adopted both numbers verbatim. `risk_flags: []`.
- Reproduction: see `/tmp/sim_worker_a/P1_turn2.json` `.items[*].draft`.
- Note: The fabrication-warning may only trigger on profile-source rewrite, not on coach-generated drafts seeded from chat. This is a behavioural gap students will absolutely exploit.

---

## Persona P2 (顾天瑜, 卖方研究 TMT, strong) — session 89

### Bug P2-1 [BLOCKER]: 0 recommendations when student uses persona-spec target_track string [BLOCKER]
- Step: 4–7 (preferences → recommendations)
- Endpoint: `PUT /sessions/89/preferences` body `{preferred_tracks:["卖方研究 TMT (sell-side research)"]}` (verbatim from persona JSON `scenario_config.target_track`).
- Expected: recommendations matching TMT sell-side jobs (e.g. 东吴证券 TMT 研究助理 / 华泰策略).
- Actual: `recommendations: 0`. Agent trace silently degrades to *"很抱歉，当前候选池中没有找到匹配你背景的卖方研究TMT岗位"* — no warning that the track string is unknown, and Tavily fallback search yields nothing.
- Reproduction: `jq '.items|length, .agent_trace[].message' /tmp/sim_worker_a/P2_recs.json` → 0 items.
- Root cause: canonical track keys (per `TrackPickerModal.tsx`) are `卖方研究·S&T`, not the longer string in the persona JSON. Re-saving prefs with `["卖方研究·S&T"]` returned 13 items immediately (see `/tmp/sim_worker_a/P2_recs2.json`).
- Note: This is a BLOCKER because (a) any external persona / faculty file using natural-language track names will hit the same wall, (b) the failure mode (empty list + "建议你关注券商官网") looks like the product has no jobs for this student, not like a config mismatch. At minimum the backend should normalise input strings, or return a clear "unknown_track_key" error from `PUT /preferences`.

### Bug P2-2: `inferred_tracks` says "二级买方·基本面" for an obviously 卖方 candidate [MAJOR]
- Step: 3 (parsed-profile)
- Endpoint: `GET /sessions/89/parsed-profile`
- Expected: P2's resume headline literally says "目标卖方研究首席助理" + 2 sell-side internships (中金 / 中信建投). Inferred track should include 卖方研究·S&T.
- Actual: `inferred_tracks = ["二级买方·基本面", "半导体/通信设备"]` — contradicts the candidate's own headline.
- Reproduction: `jq '.profile.inferred_tracks' /tmp/sim_worker_a/P2_parsed.json`
- Note: Combined with bug P2-1, the system pre-fills the wrong default direction. A student who trusts the confirm-page chip will save the wrong preference and end up at the 0-rec dead-end.

### Bug P2-3: `skills.technical` returns phantom "C" not in the resume [MINOR]
- Step: 3
- Endpoint: `GET /sessions/89/parsed-profile`
- Expected: per persona JSON: Python (pandas/matplotlib), SQL 基础, Wind API 高级用法, 财务三张表勾稽, DCF/相对估值/PEG.
- Actual: `["Python","C","SQL"]`. Drops 5 of 5 finance-specific tech skills (the things a TMT 卖方 lead wants to verify) and hallucinates `"C"` (P2 has zero C exposure).
- Reproduction: `jq '.profile.skills.technical' /tmp/sim_worker_a/P2_parsed.json`
- Note: Same phantom `"C"` shows up in P3. Likely a parser default-list leakage.

### Bug P2-4: `role` field pollution — department name concatenated [MINOR]
- Step: 3
- Endpoint: `GET /sessions/89/parsed-profile`
- Expected: `role = "研究实习生"`.
- Actual: `role = "研究部 · TMT 组 · 研究实习生"` for both internships. The department is already part of `company`. This will look ugly on the rendered profile chip.
- Reproduction: `jq '.profile.internships[].role' /tmp/sim_worker_a/P2_parsed.json`

---

## Persona P3 (陈昊, 跨专业 / 私募基本面, mid) — session 91

### Bug P3-1: `inferred_tracks` returned in English, no canonical keys [MAJOR]
- Step: 3
- Endpoint: `GET /sessions/91/parsed-profile`
- Expected: Chinese canonical keys aligned with `TrackPickerModal` (e.g. `二级买方·基本面`, `量化`).
- Actual: `["Finance","量化","Asset Management","Private Equity"]`. 3 of 4 are English, none of which match any TRACKS key, so they will not pre-select anything on the confirm page.
- Reproduction: `jq '.profile.inferred_tracks' /tmp/sim_worker_a/P3_parsed.json`
- Note: P1 returned Chinese, P3 returned a mix. Parser language stability is non-deterministic per resume.

### Bug P3-2: Phantom `"C"` again, drops LSTM/Transformer hidden highlight [MAJOR]
- Step: 3
- Endpoint: `GET /sessions/91/parsed-profile`
- Expected: per persona JSON skills.technical includes "时序模型 (LSTM/Transformer/GRU) 实战经验" — explicitly listed in `hidden_highlights` as the "稀缺技能 for 量化私募 + Quantamental".
- Actual: `["Python","C","SQL","PostgreSQL","PyTorch"]`. PyTorch is kept (good) but LSTM/Transformer/GRU dropped, and again the phantom `"C"`.
- Reproduction: `jq '.profile.skills.technical' /tmp/sim_worker_a/P3_parsed.json`
- Note: For a cross-major student whose entire differentiation pitch is "I do Quantamental", losing the model names from the parsed profile means the downstream recommender can't see the differentiator.

### Bug P3-3: Basic-info fields populated with literal string "None" [MINOR]
- Step: 3
- Endpoint: `GET /sessions/91/parsed-profile`
- Expected: optional fields (phone, github, linkedin, website) omitted or `null`.
- Actual: `"phone":"None","github":"None","linkedin":"None","website":"None"` (string).
- Reproduction: `jq '.profile.basic_info' /tmp/sim_worker_a/P3_parsed.json`
- Note: UI will render "电话: None" — embarrassing. Comparable persona P1 / P2 returns omit these keys cleanly.

### Bug P3-4: Recommendations status reports `running` even after items are returned [MINOR]
- Step: 7
- Endpoint: `GET /sessions/91` vs `GET /sessions/91/recommendations`
- Expected: session-level `recommendation_status` flips to `completed` before items are served.
- Actual: 15 polls of `/sessions/91` all returned `rec=running fb=running` even though `/recommendations` already returned 20 items.
- Reproduction: `/tmp/sim_worker_a/P3_recs.json` has 20 items; same-time session GET still shows `running`.
- Note: FE that uses session status as a gate will keep the spinner spinning indefinitely.

### Bug P3-5: Draft drops half the student's content [MAJOR]
- Step: 9 (turn 2)
- Endpoint: `POST /sessions/91/plan/turn`
- Expected: when student answers with two anchored facts ("装机量月度跟踪表 18 个月 4 公司" + "Python 清洗脚本节省 2h/周"), draft should fuse both or at least preserve the more concrete one.
- Actual: draft kept only the Python/script half; the 装机量跟踪 (which is anchored in the original profile bullet "搭建动力电池装机量月度跟踪表, 数据来源含工信部 + 上险数据") was dropped.
- Reproduction: `/tmp/sim_worker_a/P3_turn2.json` `.items[?].draft.text`.
- Note: For mid-tier students this is the single most damaging bug — they bring concrete material, the coach throws half away.

### Bug P3-6: Anti-hallucination silent on "约 15%" + "约 2 小时/周" (cross-major case) [MAJOR]
- Step: 9 (turn 2)
- Endpoint: `POST /sessions/91/plan/turn`
- Expected: per `CLAUDE.md` rule, fabricated numbers should surface `risk_flags`. P3 is the highest-risk persona per task prompt ("AI hallucinates numbers not in profile — esp. relevant for P3").
- Actual: `risk_flags: []`. Draft contains "敏感度提升约15%" and "节省mentor约2小时/周" — neither is in the parsed profile.
- Reproduction: `/tmp/sim_worker_a/P3_turn2.json`.
- Note: Same gap as P1-5. Strongly recommend treating coach-generated drafts the same way as resume-rewrite drafts for the fabrication check.

---

## Cross-persona patterns

1. **Parser is not finance-finance-aware.** It drops 组 / 部 / 子板块 from company names (P1), the actual technical skill catalogue (P2 + P3), and the differentiating model-architecture words (P3). For a 招聘 product this is the wrong direction: the words it keeps are the boilerplate, the words it drops are the JD-match signal.

2. **`matched_track_label` is currently a no-op echo of the student's preferred_track** (observed P1 + P3). It should reflect the rule-engine's actual track classification of each job, otherwise students cannot tell which jobs are aligned vs aspirational.

3. **Plan/coach state machine is non-deterministic.** Same `focus_id` flow lands P1 in `clarifying` and P2 in `awaiting_plan_approval` (Bug P1-3). After finalize, current_item snaps to item-0 instead of advancing (Bug P1-4). FE will need to defensively re-derive UI state on every poll.

4. **Coach has no anti-fabrication check** (P1-5, P3-6). Any number the student says in chat is laundered into the draft and persisted to `account_memory` with `confidence=0.9` and zero risk flags. For 严肃 finance recruiting this is the bug that will burn the SAIF pilot first.

5. **Track-key contract drift.** Persona JSON, `inferred_tracks` from parser, `TRACKS[].key` from TrackPickerModal, and the rule engine's recognised keys are four different vocabularies. P2-1 (0 recs) is the visible blocker; the silent danger is many small mismatches across the codebase.

6. **`linked_field_paths` empty on coach archive.** FE archive payload doesn't carry the bullet path, so the post-coach "🔄 内容已变" badge can never fire. (See archived entry id 173 in P1.)

---

## Suggestions for fixes (prioritized)

1. **[BLOCKER]** `PUT /preferences` should validate `preferred_tracks` against the canonical TRACKS list and either normalise (`"卖方研究 TMT (sell-side)"` → `"卖方研究·S&T"`) or 400 with `unknown_track_key`. No more silent "0 jobs" dead-end.
2. **[MAJOR]** Plug `_detect_fabricated_numbers()` into the coach draft generator so student-introduced numbers also surface `risk_flags`.
3. **[MAJOR]** Compute `matched_track_label` from the job's classification, not from `preferences.preferred_tracks`.
4. **[MAJOR]** Parser: stop dropping skill atoms (LSTM/Transformer/财务三张表勾稽/Wind API); stop emitting phantom `"C"`; preserve `组` / `部` suffix in company.
5. **[MAJOR]** After `finalize`, advance `current_item_id` to the next pending sibling/child within the same parent before falling back to item-0.
6. **[MAJOR]** Make plan-start state transition deterministic (always `awaiting_plan_approval` when `focus_id` given, or always `clarifying` — pick one and stick).
7. **[MAJOR]** Coach prompt: don't drop half the student's content when fusing the draft (P3-5).
8. **[MINOR]** `parsed-profile`: emit `null` (or omit) for missing phone/github/linkedin/website instead of literal string `"None"`.
9. **[MINOR]** `inferred_tracks` should always be Chinese canonical keys, not language-mixed.
10. **[MINOR]** Strip department prefix from `role` field once it's already in `company`.
11. **[MINOR]** Add `linked_field_paths` to the coach-archive `POST /memory` payload so resync badge works.
12. **[MINOR]** Sync `session.recommendation_status` to `completed` before /recommendations becomes readable.
13. **[MINOR]** `MEMORY_VALIDATION_ERROR` on coach-archive: the error payload is human-unfriendly ("ExperiencePayload\nbehavioral_hook\nField required"). Convert to "缺少 behavioral_hook 字段，请先在草稿里写完整 STAR" so FE can surface it.
