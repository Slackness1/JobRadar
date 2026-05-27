# TASKS

> 当前 sprint + 短期 backlog。完成项搬到 `CHANGELOG.md`。日常工作日志见 `ACTIVITY.md`。**Last updated: 2026-05-27.**

## 收官 ✅ (2026-05-27, W22)

- **投研 + AI 跨域 demo (Tasks 1-19 + 2 真实学生闭环)** — 7 个 XHS bucket (含跨域 AI 应用) → 27 sub_cat 三维 taxonomy (Opus 4.7 合成) → 10 投研 + 10 AI demo 公司 → 7 persona (5 模拟 + 2 真实学生) × 84 真实 JD 端到端匹配, advice-style narrative + DB真岗/XHS合成 source 标注。区分力 5/6 通过 (含跨域 AI vs 投研 0 leak)。总成本 $6.13 (预算 $10)。docs/eval/2026-05-27-投研-AI跨域-demo-final-report.md (v2) 飞书 docx 已交付老师 + 用户。
- **P_self persona review 收口** — user 全字段 review 完毕, flow_padding_internship (PVSyst 测试数据) 拆到独立 P_self_demo_cases.json 隔离, hidden_highlights / wants_to_avoid / inferred_roles 全部按 user 反馈修正 (没重跑 demo, user 明确说后续再触发)。

## 收官 ✅ (2026-05-26, W22)

- **Resume Copilot HiFi 三页一比一复刻 (P0a-P2)** — Sessions 页 + IntelDrawer 4-tab + CoachPane/RewritePane 中栏 takeover + ConfirmProfile 整页。在 `resume-copilot` 分支干完后合到 main。
- **13 canonical 赛道重构** — 从 10 扩到 13,新增 4 个细分赛道 + Alembic 备份 + rule-based backfill 脚本。994 unit tests pass。
- **推荐叙事 Phase 5-8** — back-office 拦截 / industry-tags / LLM 个性化叙事 / 平台 tab mini narrative。
- **金融爬虫扩展 +12 家** — 中信证券 / 鹏华 / Deutsche Bank / Barclays / Citadel 等;新增 3 个细分 track。
- **元文档体系重构** — 废弃 HANDOFF.md;新建 ACTIVITY.md;CLAUDE.md 加冷启动路径 + 对话风格规范;CLAUDE.md P1 分层落地(4 个 service 子目录)。

## 收官 ✅ (2026-05-18, W21)

- **6-metric 试点级硬化** — 推荐侧 tier_label 三档 + priority_letter A/B/C/D;简历侧 chat.py 接 audit_draft。Evidence 100% / Overclaim 0% / Actionability 100%。
- **SAIF 投研召回 sprint** — 候选池 91k → 2235;track 权重 4→18;离线 harness 96.2% hit。
- **MiMo backfill** — Job.canonical_track 覆盖率 29.9% → 46.2%。
- **模拟面试评分接入 ContextProvider** — scoring.py 加 db/user_key/profile/preferences 参数。

## Active sprint — 真实闭环验证 + SAIF demo 准备

### 🔴 P0 (本次正在跑) — 上游记忆→面试 真实链路检验

- [ ] **跑通：简历上传 → chat 修改 → 模拟面试**，验证上游写入的记忆是否真的被面试的出题 / 评分读到、有没有改变 LLM 行为
- [ ] 输出对照报告：同一假学生 fixture，跑两遍模拟面试 —— 一次 user_key 是新的（无上游记忆），一次走完整链路后用（有上游记忆），看出题 + 反馈差异

### 🟡 P1 (依赖 P0 发现，下一步)

- [ ] **接通：模拟面试→学生档案 的写入** —— 当前断在这里：面试算出来的弱点只写在 `interview_reports` 表，没存进 `account_memory`，所以"做完面试 → 系统记下来 → 下次面试调用"这个闭环根本不存在。预计半天～一天。改完后"同一学生连做两次面试，第二次反馈引用第一次"才成立。
- [ ] **系统内"热展示"形态选型**：3 个候选 —— (A) 同一学生网页上连做 2 次面试，反馈引用上次  (B) 面试页侧边露 "AI 当下用了什么" 小窗  (C) 反馈下加 "看看不带历史版本" 切换按钮。A 是最直观演示，B 是产品长期卖点，C 是 A 的快捷补充。等 P0/P1 跑通后定。

### 🟢 P2 (W22 收官后新加)

- [ ] **部署 W22 全量工作到 prod VPS** —— HiFi 三页 + 13 赛道目前只在 dev,jobcopilot.top 仍是旧版。跑 `jobradar-vps-deploy` skill。
- [ ] **观察元文档体系是否真的被各会话执行** —— 1-2 周后检查 ACTIVITY.md 是否被并行会话按规则追加,如有漏写考虑加 pre-commit hook 提醒。

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
