# Worker B — P4, P5, P6 (run 2026-05-21)

Branch: `feat/workspace-redesign-2026-05-20`
Backend: `http://127.0.0.1:8000` (dev VPS lavm-wlcndo6anm)

## Summary

- Total bugs found: **11** (blocker: 0, major: 4, minor: 7)
- Time per persona: P4 ≈ 12 min, P5 ≈ 9 min, P6 ≈ 11 min
- Overall verdict: **has-blockers-for-finalize-but-flow-runs** — upload → parse → confirm → recommend → coach kickoff → archive all work end-to-end and reliably surface a usable draft after 1-2 turns. But coach turn engine has a **recurring failure mode**: when internal pipeline flags fire (`tech_unverified`, `leadership_unverified`), the user-facing message leaks the raw flag name and the loop refuses to advance even when the student provides the requested numbers. That alone will sink the SAIF faculty demo if not fixed.

Session IDs: P4=86, P5=90, P6=92. user_keys persisted under `/tmp/persona_resumes/workerB/p{4,5,6}_userkey.txt`.

---

## Persona P4 (夏文清 — 招行 + 中信建投, 银行管培方向)

Run: upload 202 → parse OK after ~9s → confirm 200 → prefs 200 → generate 202 → feedback completed at ~81s → recs OK (10 银行管培 items, all on-track) → memory archive seeded 3 experiences → coach started with `focus_id=167` (招商银行) → 7 turns → archive draft 201.

### Bug 1: Coach leaks internal pipeline flag `tech_unverified` to the user [MAJOR]
- **Step**: P4 turn 3 / `POST /plan/turn`
- **Endpoint**: `/api/resume-copilot/sessions/86/plan/turn`
- **Expected**: Coach asks a natural-language question grounded in what's missing.
- **Actual**: Assistant message verbatim: `我准备写的版本里有 tech_unverified，需要先补一下出处。能给我一个能直接引用的具体数字或事实吗？` — `tech_unverified` is clearly a backend tag name that escaped the prompt template.
- **Reproduction**: Send a turn referencing soft outcome (e.g. "客户访谈是个亮点") without explicit citation source; the next assistant message contains the raw flag.
- **Note**: The same bug recurs as `leadership_unverified` on P4 turn 7 and again as `tech_unverified` on P5 turns 2-4. Bug is template-level, not data-specific.

### Bug 2: Coach refuses to advance after the student provides the requested numbers [MAJOR]
- **Step**: P4 turn 3 → student gave "12 次访谈 / 8 份画像 / 一份转产品团队" — coach still asks the same `tech_unverified / 出处` question on turn 4.
- **Expected**: After concrete numbers + source ("招行实习期间立项"), draft should advance or coach should ask a *different* question.
- **Actual**: `open_questions` array keeps the same question; only after the user explicitly *complains* ("我觉得 12 次访谈和 8 份画像已经是具体数字了呀？") does the draft update — and then it **replaces** the previous content instead of appending. Student is stuck guessing what the model wants.
- **Reproduction**: see saved request/response in `/tmp/persona_resumes/workerB/p4_turn{3,4}.json`.

### Bug 3: Draft overwrites prior consolidated content when the student adds detail [MAJOR]
- **Step**: P4 turn 1 draft = `"在50人的总行管培批次中，于2个月内轮岗4个部门……Top 5实习生并获得return offer。"` (good consolidated draft). Turn 4 draft = `"在私人银行条线完成12次高净值客户……作为客群洞察参考。"` — entire rotation / Top 5 / return offer narrative deleted.
- **Expected**: Add the new evidence on top of the existing draft (merge), not replace.
- **Actual**: New draft drops 4-部门轮岗 and Top 5 storyline; explicit user request "能把 4 部门轮岗 + Top 5 + return offer 和这段客户访谈放在一段里整体讲吗？" was acknowledged but turn 5 draft still didn't merge. Turn 6 even resets and asks "这段经历里你本人最核心的动作是什么?" — coherence break.
- **Note**: this destroys the value of multi-turn coach for any persona who wants iterative buildup.

### Bug 4: Parser merges sub-organization into top-level company field [MINOR]
- **Step**: `GET /parsed-profile` for P4
- **Expected**: Persona JSON has `"company": "招商银行 · 总行管培生暑期项目"` and `"company": "中信建投证券 · 投资银行部 · 综合金融组"`.
- **Actual**: Parsed `company` = `"招商银行"` and `"中信建投证券"` — sub-org / department stripped. (Persona JSON's structure is the ground truth, parser dropped specificity that coach later needed to understand "总行" vs "分行" distinction.)
- **Note**: For P5 the parser does the opposite — see Bug 6.

---

## Persona P5 (魏文骏 — 中金 IBD + 高盛 GBM, 投行 IBD 方向)

Run: upload 202 → parse OK after ~30s (slower due to 2-page PDF) → confirm 200 → prefs 200 → generate 202 → feedback completed at ~115s → recs OK (18 items, mostly IBD/quant/strategy with some McKinsey consulting noise) → coach started with `focus_id=183` (高盛 GBM) → 4 turns → archive 201.

### Bug 5: Recommendations include 3 McKinsey consulting jobs despite preferred_tracks = ["投行 IBD","内资头部投行","外资投行 IBD"] [MINOR]
- **Step**: `GET /recommendations` for P5
- **Expected**: All 18 items should be IBD or IBD-adjacent (PE, equity capital markets, M&A).
- **Actual**: Positions 6-9 are McKinsey BusinessAnalyst / DataScientist / Capabilities & Insights — pure management consulting, off-track for a candidate who explicitly excluded "buy-side research sense" and wants顶级投行 IBD only.
- **Note**: not catastrophic (IBD jobs lead the list, McKinsey items are middle-of-pack), but a student would notice and lose trust.

### Bug 6: Parser stuffs department + sub-group + role into `role` field [MINOR]
- **Step**: `GET /parsed-profile` for P5
- **Actual**: `company="中国国际金融股份有限公司 (CICC)"`, `role="投资银行部 · 大型企业组 · Summer Analyst"`; `company="高盛 (Goldman Sachs)"`, `role="Global Markets Division (GBM) · 暑期项目 · Summer Analyst"`. The persona JSON splits these — sub-department should arguably be its own field or appended to `company`.
- **Note**: this is the inverse of Bug 4 (P4 lost sub-org info; P5 piled it all into `role`). Parser is inconsistent across persona resumes; ML extractor or post-processor is non-deterministic on this dimension.

### Bug 7: `tech_unverified` loop persists across 3 consecutive turns [MAJOR]
- **Step**: P5 turns 2, 3, 4 — `open_questions` array on turn 4 contains 3 identical copies of the same `tech_unverified` open question.
- **Expected**: After student supplies "covered period 2018-2024, sample 240 deals, 38 未通过" the assistant should either generate a new draft or open_questions should rotate.
- **Actual**: open_questions keeps appending duplicates of the *same* templated question. Same root cause as Bug 1+2 but exposed more cleanly here because P5 numerics are extremely dense.

### Bug 8: Coach skips technical follow-up suitable for strong persona [MINOR]
- **Step**: P5 turn 2 — student delivers thesis + 240-deal regression + alpha 11% + sharpe 0.9 + "but buy-side concern is stub capacity"
- **Expected**: Grounded follow-up like "12% spread how do you handle execution cost?", "how robust is it across announce-period regimes?", "what is the basis between deal types?"
- **Actual**: Coach falls back to the generic `tech_unverified` template. For a `student_tier="strong"` persona this is wasted opportunity.

---

## Persona P6 (韩怀宇 — 九坤 + 乾象, 量化私募方向)

Run: upload 202 → parse OK after ~21s → confirm 200 → prefs 200 → generate 202 → feedback completed at ~125s (slowest of the three) → recs OK (20 items, all 量化 / 量化研究 / DS — track honored well) → coach started with `focus_id=192` (乾象) → 3 turns → archive 201. Additionally: `DELETE /plan` then re-start with `focus_id=191` (九坤) worked → `current_item_id` resolved to internship #1 correctly.

### Bug 9: `POST /plan/turn` returned HTTP 500 once on a routine turn, succeeded on replay [MAJOR]
- **Step**: P6 turn 2 (content = `"差不多就这样吧，定下来。"`)
- **First call**: HTTP 500 with empty/non-JSON body (the curl wrapper captured the 500 status from `-w "\nHTTP_STATUS:%{http_code}\n"` but the body was empty; reproducing immediately returned HTTP 200).
- **Note**: looks like a race/transient. Real students may hit it under concurrent dev-DB load. Worth replaying logs at `12:16` to find the trace. Also: when the call did finally succeed, it triggered a **silent replan** — item UUIDs changed entirely (new `6e864e72…` for self_intro etc), and the previously `awaiting_review` internship #2 reset to `clarifying` with the same generic "你本人最核心的动作是什么?" question. **Replans should be visible to the user.**

### Bug 10: "定下来 / 差不多就这样" finalize intent not recognized [MAJOR]
- **Step**: P6 turn 2 — student typed an explicit confirm signal ("差不多就这样吧，定下来。") matching the language the coach itself used earlier ("要改还是定下来？").
- **Expected**: Item moves to `done` / `finalized`, plan advances to next item, current_item_id moves on.
- **Actual**: Coach interprets it as another clarification turn, resets the item to `clarifying`, asks the generic "本人最核心的动作是什么?" question. This means there is **no working "accept draft" path through the API** today — every "confirm" just looks like more chat input.
- **Note**: critical because students will say "ok" / "就这样" / "可以" all the time. Without finalize, no item ever closes and the plan cannot iterate through self_intro → education → internship → project → skills.

### Bug 11: Coach selectively drops user-provided detail when updating the draft [MINOR]
- **Step**: P6 turn 3 — student said: (a) 复现 Avramov 2023 低 idiosyncratic vol 因子 IC 0.04, (b) Frazzini quality factor sharpe 0.4→0.62, (c) backtest framework 部分性能优化也是我做的.
- **Updated draft**: kept (b), dropped (a) and (c) entirely. Hidden_highlights[0] (backtest 18min→7min performance work) is exactly what (c) was hinting at — coach failed to bridge.
- **Note**: incentive misalignment: student volunteers 3 facts but only 1 lands. Persona instructions explicitly say "想突出 alpha 产出 + 工程能力双优"; current behavior loses the engineering pillar.

---

## Cross-persona patterns

1. **The `*_unverified` flag leakage (Bugs 1, 7, also seen in P4 as `leadership_unverified`)** is the single most damaging pattern: a tag intended for internal pipeline routing surfaces as user text, and the loop containing it never breaks even when the user explicitly satisfies the request. Across all three personas this is the moment where a real student would either give up or aggressively complain to the SAIF career office.

2. **Draft-merge regression (Bugs 3, 11)**: when a student adds a *new* fact via turn N, the draft regenerated at turn N+1 tends to focus on the *new* fact only and drop the previously consolidated narrative. This is the opposite of what coach mode is supposed to do (incremental buildup).

3. **No working "accept / finalize / 定下来" intent (Bug 10)**: there is currently no observable path through the chat API by which an item reaches `done` and the plan advances. Worker C / A should confirm independently. If true this is a **flow-blocker** for any demo that walks past the first item.

4. **Parser inconsistency on company / sub-org (Bugs 4, 6)**: P4 loses sub-org info, P5 piles it all into role. Need a deterministic post-processor or schema for "company / department / sub-group / role".

5. **Recommendation track-fit is good but not perfect** (Bug 5 on P5; P4 and P6 were on-track): for personas with very narrow preferred_tracks, the LLM rerank lets ~15% off-track items in.

6. **`POST /plan/turn` latency**: cold path 5-12 s per turn, acceptable. Generate latency 80-125 s, slow but OK if UI shows a real spinner with stage hints.

7. **Coach kickoff card**: after `plan/approve`, no assistant kickoff message appears in `GET /chat` — the student has to talk first. The system msg from feedback is fine, but a per-item "AI 已就绪 — 现在轮到你说" kickoff is missing on the chat thread; UI presumably renders it client-side. API consumers don't see it.

8. **Memory write + read round-trip is reliable**: `POST /memory` 201, `GET /memory` shows the new entry in `entries.experience` with `source_module: "manual_api"`. No dupes, no broken linked_field_paths.

---

## Suggestions for fixes (priority order)

1. **Sanitize internal tag names out of the user-facing prompt**. Either translate `tech_unverified / leadership_unverified` into Chinese natural language before injecting into the question, or strip the suffix entirely. (Bug 1, 7, recurrence in P4.)

2. **Add explicit "finalize" intent classification on `/plan/turn`**: regex / LLM-classifier hit for "定下来 / 就这样 / 可以 / ok / accept / 用这版" → transition item to `done` and bump `current_item_id` to the next pending item. (Bug 10.)

3. **Fix draft merge semantics**: when new user evidence arrives, the draft prompt should be "extend the prior draft with this new fact" rather than "rewrite from this new fact only". Pass the prior `draft.text` into the regeneration prompt as a hard anchor. (Bug 3, 11.)

4. **Break the open_questions loop**: if the same question text is already present in `open_questions` with an `answered_at` since the prior turn, do not re-append; instead either escalate to a different question or finalize the draft with a `risk_flags` entry the UI can show. (Bug 2, 7.)

5. **Make replan events visible**: when the coach decides to replan (item UUIDs change), emit a user-facing message "我重新整理了一下计划，回到了 ……" so the student understands why their previous progress reset. (Bug 9 second half.)

6. **Tighten the recommendation rerank for narrow `preferred_tracks`**: McKinsey BusinessAnalyst should not appear when prefs are `["投行 IBD","内资头部投行","外资投行 IBD"]`. Consider a hard filter on `matched_track ⊂ preferred_tracks` for the top-10 slice. (Bug 5.)

7. **Parser company-vs-role disambiguation**: post-process to detect "·" / " · " separators in raw OCR text and split sub-org consistently. Either always append to `company` or always put in a new `department` field, but be consistent. (Bug 4, 6.)
