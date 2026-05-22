# Round 3 Worker B — P4, P5, P6 (run 2026-05-21)

Branch: `feat/workspace-redesign-2026-05-20`
Backend: `http://127.0.0.1:8000` (dev VPS lavm-wlcndo6anm)

Session IDs: P4=115, P5=116, P6=117.
User keys (saved at `/tmp/persona_resumes/workerB_r3/P{n}_userkey.txt`):
- P4: `sim_P4_20260521r3_24268`
- P5: `sim_P5_20260521r3_11218`
- P6: `sim_P6_20260521r3_60767`

Per-turn artifacts: `/tmp/persona_resumes/workerB_r3/P{4,5,6}_{turn,chat_after_t,plan_final,recs,memory,unknown_tracks_test}*.json`. Driver + analyzer: `run_persona.py` + `analyze2.py`. Aggregated matrix JSON: `/tmp/persona_resumes/workerB_r3/analysis_v2.json`.

## Batch-3 fix matrix

| Fix | P4 | P5 | P6 | Notes |
|---|---|---|---|---|
| **#4** Access-log middleware (`/tmp/backend_dev.log` 每个请求一行 `[INFO\|WARN\|ERROR] METHOD path → status (Xms)`) | Y | Y | Y | Sentinel `curl /api/health` + `sleep 1` + `tail` confirms format: `[INFO] GET /api/health → 200 (8ms)`. 233+ rows captured during this run (parse / generate / plan/turn / recs / GET-poll). One `[ERROR] POST .../plan/turn → EXCEPTION (30048ms) OperationalError` row captured cleanly for the P6 t2 500. **Spec match: format ✓, latency ms ✓, status code ✓.** Note: query string is stripped (just `/api/health`, no `?marker=…`) — not a bug, but if anyone wanted to grep by query param later they can't. |
| **#1** Parser bullet-boundary preserved | Y | Y | Y | Every persona internship has **identical bullet count to persona JSON**: P4 招行 4/4, 中信建投 4/4; P5 CICC 5/5, 高盛 5/5; P6 九坤 4/4, 乾象 4/4. The short padding bullets (P4 「做了部门内部的一些事务性工作」, P5 「整理 daily morning note 和市场数据」, P6 「做了一些数据清洗和回测脚本的维护工作」) are all **independent entries**, not merged into the preceding bullet. The strict `Bullet boundary rule` in `parser.py:183-188` is doing its job. |
| **#3** `X-Unknown-Tracks` BE contract — URL-encoded header on unknown track input | Y | Y | Y | 同时跑了两个测:**Test 1** — 用每个 persona JSON 的 `target_track` 原文 PUT `/preferences` (`银行管培 / 综合金融`、`投行 IBD (Investment Banking Division)`、`量化私募 / 对冲基金 (中频策略 + alpha 因子)`)。3 个都 canonicalize 成功 → `X-Unknown-Tracks` 空 (正确,不该报). **Test 2** — P4 用了 worker B 老 driver 的 alternative list `['银行管培','国有大行总行管培','券商综合金融']`,其中 `券商综合金融` 没 alias 命中 → 响应 header `X-Unknown-Tracks=%E5%88%B8%E5%95%86%E7%BB%BC%E5%90%88%E9%87%91%E8%9E%8D` (URL-encoded), decode = `券商综合金融`。**契约满足**:命中时单值,逗号分隔(`','.join(quote(t,safe=''))` per impl), 学生 / FE 可以 `decodeURIComponent` 回原文。 |
| **#2** Coach min-turn floor (≥ 2 user_clarification before inline write) | Y | Y | Y | **核心验证 ✓**。 P4 t1 学生一口气塞 (4 部门 + 12 访谈 + 8 画像 + Top 5 + return offer + VP 汇报) — `focus_uc_count=1` → assistant 返 floor 原文「听起来核心 evidence 已经有了。 在我写成 draft 之前, 再给我一个具体细节 — 比如你这段经历里最关键的一个动作 / 数字 / 角色, 让我落笔有底。」 (`plan_turn.py:524-528` 字面命中);item status 维持 `clarifying`, 无 draft。 P5 同样 t1 floor → t2 (uc=2) 才 write draft。 P6 同样 t1 floor。 floor message 一字不差 = `plan_turn.py:524-528`,**fix #2 没有被 LLM 绕过**。 |

详细每-turn breakdown:

```
P4:  t1 uc=1 status=clarifying msg="听起来核心 evidence..." (floor)
     t2 uc=2 status=clarifying msg="主导度需要佐证..." (audit)
     t3 uc=3 status=clarifying msg=同 (M2 dedup,  oq_count 保持 2)
     t4 uc=4 status=clarifying msg=同 (M2 dedup)
     [item never reaches awaiting_review — see Bug R3-B1 below]

P5:  t1 uc=1 status=clarifying msg=floor
     t2 uc=2 status=awaiting_review draft写了 (84 字符,  跨境并购 project)
     t3 "定下来" → "已敲定。" → 推进到下一个 pending item (project - bullet #1)
     t4 uc=1 on new item → 又 floor (符合设计)

P6:  t1 uc=1 status=clarifying msg=floor
     t2 → 500 (SQLite locked,  三并行碰撞 — 见 Bug R3-B2)
     t3 uc=2 status=clarifying msg="技术细节缺出处..." (audit 接管)
     t4 uc=3 status=awaiting_review draft 写了 (173 字符,  含 Avramov + 18→7min + PM quote)
     [P6 "差不多就这样吧, 定下来。" 发在 t2 上时 item 还在 clarifying — 被吞,
      finalize 永远没机会跑]
```

## Round 1 / Round 2 regression check

| Item | Status | Evidence |
|---|---|---|
| **M1** 中文 audit hint, 无 `tech_unverified` / `overclaim` / `leadership_unverified` 等 raw token | PASS | 跨 P4/P5/P6 的 **22 条 assistant message** 全文 grep TAGS=[tech_unverified, overclaim, leadership_unverified, no_evidence, fabricated_number, audit_kind, no_data]:**0 hits**。 P4 t2 surfaces 「主导度需要佐证」, P6 t3 surfaces 「技术细节缺出处」 — 都是中文版本。 |
| **M2** 同一 question 不重复 append open_questions | PASS | P4 最干净:t2 / t3 / t4 都触发同一 「主导度需要佐证」 question,`oq_count` 始终保持 **2** (即 floor message + 1 audit question),hash-dedup 工作正常。P6 同样:t3 触发 「技术细节缺出处」, t4 没再 append (oq_count = 2 稳定)。 |
| **M3** "定下来 / 用这版" 在 status=awaiting_review 时真 finalize | PASS (P5) / N/A (P4 P6) | P5 t3:item 在 awaiting_review (t2 写完 draft) → 学生 「差不多就这样吧, 定下来。」 → assistant 「已敲定。」 + `current_item_id` 从 project 推进到 `project - bullet #1`。 R2 polish 措辞 (t2 assistant 末尾) 一字不差:「看这版可以的话再回一句"就这样 / 定下来",  我就入档; 想改就直接告诉我改哪里。」 — **2-step 信号清晰传达** ✓. **P4 / P6** item 永远没到 awaiting_review (P4 因 leadership_unverified audit 一直 clarify, P6 t2 500 + audit), finalize 路径未被触发但**也没观察到失败**, M3 逻辑 untested on these two but no failure。 |
| **M4** draft EXTEND vs replace | PASS (P6) / N/A (P4 P5 cross-item) | P6 终态 draft (t4, 173 字) 同时含 5 个 fact:① 提交 12 入库 4 sharpe>0.8 ② Avramov 2023 IC 0.04 ③ backtest 18→7 min ④ 内部研报《限价单持续性与短期反转》 ⑤ PM 评审会引用 — 全部 来自 t1 单条 + t3 audit 后,**前一轮 fact 没被替换**。 P4 没 draft 产出。 P5 t2 draft 是 project (反垄断) 而不是中金 IBD focus,不构成 extend test (focus 在 t2 跳了 item)。 |
| **B2** P5 推荐 distribution, per-canonical-company ≤ 3 | PASS (per-stream, same as R2 finding) | P5 recs total = 13,  by (company, is_internship):Goldman Sachs (False)=3, Goldman Sachs (True)=3, 中金公司(True)=2, 蚂蚁(True)=2, 其余 ≤1. **per-stream cap = 3 holds**。  **若 product 要 global cap=3** (e.g. Goldman Sachs 总共只能 3), 当前 6 还是 over — 同 Round 2 结论。 P4 同 19 条, 招行 (True)=3 + 招行 (False)=1 = 4 global, 也 per-stream OK 但 global over。 P6 recs 没拿到 (`status=running` 一直没 settle,见 Bug R3-B3 below)。 |

## New bugs

### Bug R3-B1 [MAJOR — regression of R2-1, amplified]:学生 "定下来" 在 item 卡 `clarifying` 时**完全被吞**, 学生连续 3 turn 没人理

- **场景**: P4 turn 5 / 6 / 7 / 8 — 学生先后说 「另外我们当时是和一位总行 mentor 合作完成 VP 结题汇报...」 / 「差不多就这样吧, 定下来。」 / 「再回一句就这样, 我就入档。」
- **实际**: assistant 三次返**完全相同**的 「这一版我想再确认一下「主导度需要佐证」 — "主导 / 牵头"需要具体例子: 你怎么定方向 / 推进谁 / 拍板什么? 给我一两个细节我才好往上加。」
- **根因**: `plan_turn.py:412-414` 的 `_is_finalize_intent` 只在 `status == AWAITING_REVIEW` 时 fire。 P4 的 internship item 因 `leadership_unverified` audit 始终在 `clarifying` (uc_count 已经到 4 但 audit 不放行), 所以 finalize 从来没被识别。 学生从用户视角看就是「我说了三次定下来, AI 像没听见」。
- **R2 对比**: R2-1 是「需要说两次定下来」 (中间被吃一次)。 R3 这版**更严重** — 说 3 次都没用, 因为 item 根本进不了 awaiting_review。 audit gate 比 floor gate 更黏。
- **建议**: 在 finalize intent 检测到时, 即便 item 在 `clarifying`,也允许一种 "我知道还有 audit, 但学生明确要 ship" 的逃生口。 e.g. 显式提示 "审核还有一项没补完 (主导度需要佐证),要不要我把这一版按现状入档 (留 risk_flag) 还是再补一句具体细节?"  — 至少把 audit 状态告诉学生, 别让学生原地循环。
- **复现**: 见 `/tmp/persona_resumes/workerB_r3/P4_chat_after_t4.json` msg index 5-8 + `P4_plan_final.json` (`internship #1` 终态 `status=clarifying`, `uc_count=4`)。

### Bug R3-B2 [TRANSIENT / ENV — SQLite lock under 3-way parallel coach load]:HTTP 500 OperationalError on P6 t2

- **场景**: 三个 persona 在同一 backend 上同时跑 `plan/turn`。 P5 t2 和 P6 t1 在差不多同一时刻 commit。 P6 t2 抢锁失败 30 s 后 timeout → 500。
- **stack**: `sqlite3.OperationalError: database is locked` → `plan_turn.py:406 db.flush()` 上面 (insert ResumeCopilotMessage)。 access log 捕捉为单行 `[ERROR] POST /api/resume-copilot/sessions/117/plan/turn → EXCEPTION (30048ms) OperationalError` — middleware 还是工作的 ✓。
- **影响**: P6 turn 2 (本来是 Frazzini quality factor sharpe 0.4 → 0.62 那段 fact) 没入 evidence ledger。 后续 t3 / t4 还是能 recover (focus 仍在 九坤 item), 但 Frazzini 的 evidence 没进 draft (P6 t4 draft 只含 Avramov, 没含 Frazzini)。
- **为什么没在 R2 出**: R2 也是 3 并行,但 LLM 完成时间错开了一些; R3 的 plan/turn 平均 17-25s, 凑巧 commit 撞在了一起。
- **判断**: 这是**测试环境下的并行假象**, **不是产品 bug** (生产是单用户单 session,不会 3 并行); 但 backend SQLite WAL + busy_timeout 应该护住, 没护住 → backend 配置或 plan_turn flush 顺序值得 Worker A/C 看下。  另: SQLite `busy_timeout=5000` 默认值,这里 30s 才超时 — 说明 anyio threadpool 也在外层 wait, busy_timeout 实际只 control SQLite 内部 retry。
- **建议**: 若 R3 后期还要做多-persona 并行 eval,加 `--max-concurrency 1` 串行跑;或把 plan/turn 的 ResumeCopilotMessage insert / plan UPDATE / flush 合到一个 transaction,缩短锁窗口。 但**生产用户不受影响**, 优先级 LOW。

### Bug R3-B3 [MINOR — recommendation status stuck running]:P6 session 117 recs 一直 `status=running`, 永远没 ready

- **场景**: P6 generate 阶段成功完成 (feedback_status=None → ready), 但事后单独 fetch `/recommendations` 始终拿到 `status=running, items=[]`。 等了 2+ 分钟未变。
- **可能原因**: P6 的 t2 500 把 SQLite lock 时机弄乱了, recommend job 卡在某个 lock-acquire 阶段; 或 generator 自己 commit 失败但状态没回滚成 `failed`。
- **影响**: B2 check on P6 不可做 — 没有 recs 数据。 P4 / P5 OK。
- **建议**: backend 重启或下次跑前清掉 P6 session。 product-side 应该 health check: 若 status=running 超过 N 秒,要么 retry 要么 mark failed,**绝对不能永远 running** (FE 永远 spinner)。  优先级 MEDIUM。

## Round 1 / Round 2 bugs that REPRO

None of the R1 majors (Bugs 1, 2, 3, 7, 8, 10, 11) reproduce in this round. R2-2 (`(e.g. 主导/独立完成)` parenthetical leak in `_AUDIT_TAG_HINT_CN`) and R2-3 (multi-hint pileup) — **not observed** in this run because no turn triggered ≥ 2 audit tags simultaneously. R2-1 (need two "定下来") evolved into the worse R3-B1 above (now it's "even 3 times doesn't work" when blocked by audit, not just floor).

**Bug 4 / Bug 6 (parser sub-org drop)**: still present, unchanged from R2. P4 company = `招商银行` (drops `· 总行管培生暑期项目`); P5 `中国国际金融股份有限公司 (CICC)` (drops `· 投资银行部 · 大型企业组`, pile dept into role); P6 `九坤投资` (drops `· 中频策略组`). **Status: same as R2 — no change, no block on coach flow**, but the dropped detail does cost down-stream context (e.g. role specificity in mock interview prompt).

**Bug 9 (HTTP 500 on `/plan/turn`)**: 1 occurrence on P6 t2, see Bug R3-B2 — root cause is SQLite lock from concurrent test load, NOT a regression of the inline error path.

## Cross-persona patterns this round

1. **#2 min-turn floor 是真有效**, but 给 P4 / P6 这种学生想一口气把整段倾倒的 (P4: 5 个 fact, P6: 4 个 metric) 体感稍有 friction — 学生一口气说完 6 件事, AI 说 「再给我一个具体细节」 — 学生**意图被识别为 evidence 单薄**, 实际是 LLM 没把 6 件事算成 6 条独立 user_clarification。 Floor 的 `user_clarification_count` 实际是按 evidence 行计数 (1 turn = 1 evidence), 不是 fact 计数。 这是设计取舍, 但对 dense-message persona (P5 那种 punchy / P4 那种 narrative) 有点不公。  **建议**: floor 计数考虑 evidence text 长度 + 信息密度 (e.g. > 100 字 + ≥ 3 数字 = 1.5 票), 让 dense 学生少绕一轮。 优先级 LOW (R2 没人投诉, 这次也没卡死)。

2. **Audit gate (e.g. `leadership_unverified` / `tech_unverified`) 比 finalize gate 更黏**。 P4 因 audit 永远不进 awaiting_review,「定下来」永远不识别。 这是新观察到的 UX trap (R3-B1)。

3. **Multi-persona parallel load 会触发 SQLite lock**。 R2 没见过这个, R3 见到 1 次 (P6 t2)。  说明 plan/turn 写路径在并行下不够 robust; 单 prod 用户不受影响, 但 multi-tenant 长期是潜在隐患。

4. **每条 audit / floor message 都被 append 到 open_questions**, 哪怕 `oq_count` 因 dedup 没涨, **但 open_questions 列表里这条 question 是 hashable 单条**。 FE 如果 render `open_questions` list 给学生看,学生会看到「现在还有 2 个待澄清的问题」 — 但其实只有 1 个真问题,另 1 个是 floor message 那种 nudge — 这两个体感很不一样, FE 应该区分 (e.g. floor question 不算 question 算 system_hint)。 **优先级 LOW** (不是 bug, 是 modeling choice)。

5. **B2 per-stream cap = 3** — Round 2 已结论, Round 3 复现:per (company, is_internship) ≤ 3 holds, but global Goldman = 6 / 招行 = 4 still happens。 同 Round 2 action item:product 决策 per-stream vs global, 当前是 per-stream by design。

## Test artifacts

- Per-turn snapshots: `/tmp/persona_resumes/workerB_r3/P{4,5,6}_turn{1..4}.json`
- Chat after each turn: `/tmp/persona_resumes/workerB_r3/P{4,5,6}_chat_after_t{n}.json`
- Recommendations: `/tmp/persona_resumes/workerB_r3/P{4,5}_recs_v2.json` (P5 settled; P6 stuck running)
- Memory entries: `/tmp/persona_resumes/workerB_r3/P{4,5,6}_memory.json`
- Unknown-tracks header tests: `/tmp/persona_resumes/workerB_r3/P{4,5,6}_unknown_tracks_test.json`
- Parsed-profile vs persona JSON diff (fix #1): `/tmp/persona_resumes/workerB_r3/P{4,5,6}_parsed.json` + analyzer `analysis_v2.json`
- Driver / analyzer: `/tmp/persona_resumes/workerB_r3/run_persona.py` + `analyze2.py`
- Final analysis JSON: `/tmp/persona_resumes/workerB_r3/analysis_v2.json`

## Verdict

- **Batch-3 fixes #1, #2, #3, #4 all PASS on P4/P5/P6** — parser bullet boundary preserved, min-turn floor protects t1 from premature write (literal floor message 命中), X-Unknown-Tracks header URL-encoded contract holds, access log middleware logs every request with correct format.
- **R1 / R2 majors stay fixed** (M1 zero leaks, M2 dedup at 2, M3 finalize works on P5, M4 extend works on P6).
- **1 new MAJOR UX bug** (R3-B1): finalize intent ignored when item stuck in `clarifying` by audit gate — student says 「定下来」 3 times in a row to no effect on P4。 Need an audit-aware finalize escape hatch before the SAIF demo.
- **1 new env / load bug** (R3-B2): 3-way parallel SQLite lock → 1 plan/turn 500. Not a prod risk, but worth a look.
- **1 new minor** (R3-B3): P6 `recommendations` stuck `status=running` after a 500 — FE will spin forever. Need timeout / retry / fail-state.
