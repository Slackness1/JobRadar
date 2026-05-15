# PROJECT_STATE

> 项目当前快照。每次大段工作结束时更新。**Last updated: 2026-05-15.**

## Modules

| Module | Status | Notes |
|---|---|---|
| Crawlers (10 tier blocks) | ✅ stable | 9 daily blocks + Tata API。`foreign_ibs` ~4.5min 最慢。 |
| Sites monitor (`/sites`, `/api/sites`) | ✅ stable | 已嵌入 `/system-health`，2/8s 自适应轮询。 |
| Coverage dashboard (`/coverage`) | ✅ stable | 13 tracks，golden-spiral starmap 默认视图。 |
| Admin pages (`/review-queue`, `/system-health`) | ✅ stable | Wireframe 变体 C，HiFi terracotta 作用域隔离。 |
| Resume Copilot pipeline | ✅ stable | Parse → preferences → recommendation + LLM rerank → chat rewrites。 |
| Resume Copilot demo session | ✅ stable | `DEMO_SESSION_ID=1`，lifespan 启动时强制重建。 |
| Mock interview (text + voice) | ✅ stable | DashScope cosyvoice-v2 + paraformer-realtime-v2。Lingmou 数字人 dormant。 |
| Adaptive interview picker | ✅ stable | Skeleton + LLM follow-up + recall。每个并行任务独立 SessionLocal (Q5-hardened)。 |
| 4 ContextProviders fan-in | ✅ stable | sensitive_topic → tencent_track → student_memory → podcast，按序短路。 |
| Knowledge pack (Tencent skill) | ✅ stable | 9 tables，8/8 verbatim quotes 验过，5 output constraints，8 sensitive topics。 |
| Alembic migrations | 🟡 partial | Strangler-fig 与 `schema_patch.py` 共存。新 schema 走 Alembic only。 |

## In flight

- **Eval harness Phase 1 (投研 v1)** — 设计文档已落 `docs/eval-touyan-v1-design.md`。代码 0 行未写。下一步见 `TASKS.md` 的 "Active sprint"。
- **Meta-doc skeleton** — 本批次正在创建（PROJECT_STATE / TASKS / HANDOFF / DECISIONS / CHANGELOG + slim CLAUDE.md）。

## Recent shipped (last 2 weeks)

详见 `CHANGELOG.md`。亮点：Tencent 知识包入库 + 4 Provider 接入 + adaptive picker recall；mock interview 切到 DashScope 语音栈。

## Known blockers / debt

| 优先级 | 问题 | 位置 |
|---|---|---|
| 🟡 | `_build_session_out` N+1（每次 1.6s 轮询跑 5 次 `.first()`） | `backend/app/routers/resume_copilot.py:57-61` |
| 🟡 | `recommend_jobs_for_profile` 全表 `query(Job).all()` 无 prefilter | `backend/app/services/resume_copilot/recommendation.py:439` |
| 🟡 | 推荐 enrichment snapshot 无 14 天 TTL（任何 snapshot 都按新鲜对待） | `recommendation.py:393-395` |
| 🟢 | Tencent 知识包用的是 transcript 范例数据，未接 `tencent-recruit-pack/scripts/fetch_recruit_jds.py` 抓真实 JD | `backend/app/services/knowledge_pack/` |
| 🟢 | `HANDOFF_NEXT_SESSION.md` (root) 已陈旧，`HANDOFF.md` 取代之 — 待 user 确认删除 | root |
| 🟢 | `docs/decisions.md` (lowercase) 是 2026-03 业务历史决策，新 `DECISIONS.md` 只盖架构 — 老文件保留为 legacy snapshot | docs |

## Production runtime

- VPS `myvps` (122.51.18.237) 跑 systemd unit `jobradar.service`，main 分支。
- Daily crawl 08:00 / tier crawl 09:00 / digest 09:35（Asia/Shanghai）。
- 详见 `CLAUDE.md` "Production runtime" 段 + `docs/deployment-and-data.md`。
