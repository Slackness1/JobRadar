# TASKS

> 当前 sprint + 短期 backlog。完成项搬到 `CHANGELOG.md`。**Last updated: 2026-05-18 深夜.**

## 收官 ✅ (2026-05-16 深夜)

**Taxonomy 项目级铺线 sprint 全部完成** —— 6 phase 全 ship,8 canonical 贯穿 backend model + parser + provider + scoring,frontend picker,eval fixtures + judge prompt,DB jobs + tracks 全模块。142 unit tests pass。

## 收官 ✅ (2026-05-18)

**模拟面试评分接入 ContextProvider + personalization directive (C')** —— scoring.py 新增可选 db/user_key/profile/preferences 参数；总是 append directive；orchestrator 透传 user_key。10/10 scoring test pass。**已 push (`efb0ffe`)**。配套 demo: `backend/scripts/demo_abc_scoring_touyan.py` 一键复跑 4 版对照（投研嘉实场景）。

## Active sprint — 真实闭环验证 + SAIF demo 准备

### 🔴 P0 (本次正在跑) — 上游记忆→面试 真实链路检验

- [ ] **跑通：简历上传 → chat 修改 → 模拟面试**，验证上游写入的记忆是否真的被面试的出题 / 评分读到、有没有改变 LLM 行为
- [ ] 输出对照报告：同一假学生 fixture，跑两遍模拟面试 —— 一次 user_key 是新的（无上游记忆），一次走完整链路后用（有上游记忆），看出题 + 反馈差异

### 🟡 P1 (依赖 P0 发现，下一步)

- [ ] **接通：模拟面试→学生档案 的写入** —— 当前断在这里：面试算出来的弱点只写在 `interview_reports` 表，没存进 `account_memory`，所以"做完面试 → 系统记下来 → 下次面试调用"这个闭环根本不存在。预计半天～一天。改完后"同一学生连做两次面试，第二次反馈引用第一次"才成立。
- [ ] **系统内"热展示"形态选型**：3 个候选 —— (A) 同一学生网页上连做 2 次面试，反馈引用上次  (B) 面试页侧边露 "AI 当下用了什么" 小窗  (C) 反馈下加 "看看不带历史版本" 切换按钮。A 是最直观演示，B 是产品长期卖点，C 是 A 的快捷补充。等 P0/P1 跑通后定。

详见 `HANDOFF.md` "下次会话建议接什么"。

## ✅ Taxonomy sprint 已完成(7 commits)

- [x] ✅ **Phase A** (`631e13b`) — taxonomy module 抽出,recommendation.py 改 import。
- [x] ✅ **Phase F** (`2c39590`) — coverage_truth.yaml + Track DB 加 canonical_tracks。additive。
- [x] ✅ **Phase B** (`1de7f81`) — Alembic 0005 加 `Job.canonical_track` + `before_insert` 自动派生 + 29592 行 backfill (29.9%)。新 source_map.py。
- [x] ✅ **Phase C** (`36cd29c`) — parser inferred_tracks 跑 canonicalize + 前端 TRACK_OPTIONS 8 canonical + 老值 union 向后兼容。
- [x] ✅ **Phase D-0** (`ce11b15`) — `tracks.yaml` 8 canonical 的 knowledge data。
- [x] ✅ **Phase D** (`991342c`) — 5th ContextProvider `TrackKnowledgeProvider` (taxonomy/provider.py),注册 bootstrap 第 5 位。
- [x] ✅ **Phase E** (`697cb37`) — JD fixtures + judge.py 引用 8 canonical。chat.py rewrite 口径调整未做(backlog)。

## Backlog · 高优先级 (Eval / Recommendation / 性能)

- [ ] 🐛 **SUT 推荐 tier_label 太保守** (multi-turn baseline 发现) — SUT 在 25 个 (student,jd) 里**从不给** tier='强匹配',即使候选人完美对口。调 SUT recommendation prompt 允许更自信。
- [ ] 🐛 **SUT follow-up 偶发跨经历跳跃 / hallucinate** (multi-turn baseline) — 24 turn 里 1 次跳到另一段实习,1 次凭空提没说过的 entity。在 follow-up generation prompt 加"禁止跨经历 + 禁止编造 entity"强约束。
- [ ] 📏 **multi_turn judge prompt 对 transferability 偏严** — SUT 问"X 项目方法论能否搬到 Y 行业"被判 0。calibrate prompt 区分"跳到另一段经历" vs "在当前项目内做 transferability 假设性追问"。
- [ ] 🔧 **`_parse_score` LLM reasoning unescaped 直引号** — multi_turn 1 个 case judge JSON 里用了 `"无缝迁移"` 没 escape 致 raw_decode 失败。要么 prompt 强制中文引号,要么 fallback yaml.safe_load。
- [ ] **N+1 fix** — `_build_session_out` 5 次 `.first()` → 单 `joinedload` 或加 `has_*` 列
- [ ] **Recommendation prefilter** — `recommend_jobs_for_profile` 在 scoring 前按 `preferred_tracks/locations/job_family` prefilter,硬上限 N×10
- [ ] **eval harness Phase 2** — `llm_eval_trace` 表 + 4 Provider 写 trace + recommendation rerank 写 trace

## Backlog · 中优先级

- [ ] **跑 2 次 baseline 测 judge 稳定性** — judge 是 stochastic LLM,单次 ±1 分噪声。看分布决定 pytest 的 1 分 tolerance 合不合适。
- [ ] **扩到第二个方向** — 互联网 / 咨询 / 央企 之一,加 `fixtures/internet_v1/` 验证 schema 复用性。
- [ ] **eval Phase 3** — `eval_diff.py`,对比两次 baseline,红色 highlight 退步项
- [ ] **Tencent 真实 JD 接入** — 跑 `tencent-recruit-pack/scripts/fetch_recruit_jds.py` 把抓到的 JD 入 knowledge_pack
- [ ] **`quick_enrichment` 并行化** — 当前每个 top-N job 串行,改 `asyncio.gather` per-job
- [ ] **Snapshot TTL** — `recommendation.py` 加 14 天 TTL,过期 snapshot 不应用 boost

## Backlog · 低优先级

- [ ] Frontend polling 加 max-duration cap (5 min) + 3 次连续失败时 retry banner
- [ ] `agent_trace_json` 上限 50 events,re-generate 时 reset
- [ ] 删除 stale 文件:`HANDOFF_NEXT_SESSION.md`、`backend/data/jobradar.db.bak.20260428`(确认 user OK 后)
- [ ] 把 `docs/decisions.md` (lowercase) 标记为 legacy 并加跳转
- [ ] `_canonicalize_track` 升级到 trie / regex 编译 — 当前 50+ alias 线性遍历,千级 job 表跑无感,但 D 接入后频次会大涨

## Backlog · 看心情

- [ ] Recommendation 输出加 `rule_score` vs `enhanced_score` 双 score 区分 (当前 collapse)
- [ ] LLM JSON response 用 Pydantic `model_validate` 包一层 (当前 `_coerce_ai_recommendation_item` 只补 missing 字段)
- [ ] 写 4 个 ContextProvider 单测
- [ ] XHS crawler 多账号轮换 + 节流脚本(用户 B 账号冷藏,后续要长期爬需要新号)
