# Round 3 端到端验证 — 合并报告 (2026-05-21)

> 第三批 4 个 fix (#1/#2/#3/#4) 复跑 8 个 SAIF MF persona。 3 个并行 subagent。

## Top-line

**P8 红线 PASSED — 三轮里第一次。** Worker C 实测 4 轮学生 push 编造数字, 系统全程拒绝, draft 无入档。

## Round 3 fix verification

| Fix | Worker A (P1-3) | Worker B (P4-6) | Worker C (P7-8) |
|---|---|---|---|
| #4 access log middleware | ✓ | ✓ (233+ rows, 1 EXCEPTION 行 cleanly 捕获) | n/a (但每个 request 都有 log 证) |
| #1 parser bullet boundary | ✓ (P1: 4/5/4, P2: 4/4, P3: 4/4) | ✓ (招行/中信建投/CICC/高盛/九坤/乾象 都精确匹配) | ✓ (P7 4+4, P8 4+3) |
| #3 X-Unknown-Tracks header | ✓ (URL-encoded) | ✓ (Chinese bogus → decode OK) | ✓ |
| #2 coach min-turn floor | ✓ (turn 1 = ask, P1 t2 才 awaiting_review) | ✓ ("Floor cannot be bypassed by LLM") | ✓ (+ B1 联动 = 红线 PASSED) |

**全 12 维 verified PASS。**

## Round 1/2 regression check (R3 视角)

| Fix | Verified hold | Notes |
|---|---|---|
| B1 plausibility coach + chat path | ✓ | P8 红线 4 turn 全程拒收 |
| B2 per-employer cap + 中金 alias | ✓ | P7 蚂蚁 ≤ 3, CICC 归一 |
| B3 canonicalize tracks | ✓ | P2 verbatim 工作 |
| B4 parser skills (no phantom C, LightGBM 等) | ✓ | All persona |
| M1 中文 tag | ✓ | 22 个 assistant 消息 0 个 English tag |
| M2 question dedup | ✓ | P4 t2/t3/t4 同问 oq_count=2 |
| M3 finalize "定下来" 接住 | ✓ | P5 t3 advances next pending |
| M4 draft EXTEND | ✓ | P6 final draft 含 5 facts 全保留 |
| M5 student-introduced-number | ✓ | (single tested by C) |
| R2 polish | ✓ | "再回一句就这样我就入档" wording 显示 |

## R3 找到的 new bugs + 本轮立即修

| # | 严重度 | 描述 | 修了? |
|---|---|---|---|
| R3-B1 | **MAJOR UX** | "定下来"在 clarifying 状态下连说 N 次被 audit gate ignored | ✓ **fixed**: prior_user_finalize ≥ 1 + status=clarifying → 强 write + audit risks 转 non-blocking 挂 draft, 走 awaiting_review |
| R3-C/track-key | MINOR | `matched_track_label/key` 被 job_title / HTML 标签污染 | ✓ **fixed**: 只接受 ∈ CANONICAL_FINANCE_TRACKS 的结果, 其它回 student preference 或空 |
| R3-A/None | MINOR | P3 basic_info phone="None" 字符串 | ✓ **fixed**: `_BASIC_INFO_NULLISH` 过滤 "none/null/n/a/-/无/不详/未提供" 等 |
| R3-C/skill case | MINOR | pytorch + PyTorch 同时存在; tools long string + split parts 并存 | ✓ **fixed**: `_clean_skill_items` 加 case-insensitive dedup + split 自然解决 long string |
| R3-2 / R3-B2 | TRANSIENT | SQLite locked 并发 (3-way worker), busy_timeout 实际已经 30s | 不做 (prod 单用户不触发, agent_trace 写法需要更深的 refactor) |
| Bug 4/6 (R1 + R2) | MINOR | parser 公司 `· 子组` 后缀进 role 字段 | 不做 (FE 显示 fallback 已 OK) |

## 累计 fix 统计

- Round 1: 9 条 (B1 / B2 / B3 / B4 / M1 / M2 / M3 / M4 / M5)
- Round 2 (含 polish): 7 条
- Round 3 batch: 4 条 (#1 / #2 / #3 / #4)
- Round 3 patches: 4 条 (R3-B1 / R3-C track / R3-A None / R3-C skill case)
- **合计 24 条端到端修复**

测试: **201 个 pytest 全过** (plan + parser + recommendation 三个领域)。
后端 `http://127.0.0.1:8000` + 前端 `http://127.0.0.1:3004` 双双在线 ✅。
