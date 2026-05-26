# PROJECT_STATE

> 项目当前快照。每次大段工作结束时更新。**Last updated: 2026-05-26.**

## Modules

| Module | Status | Last verified | Notes |
|---|---|---|---|
| Crawlers (10 tier blocks + 12 新源) | ✅ stable | 2026-05-26 | 9 daily blocks + Tata API + 中信证券 / 鹏华 / Deutsche Bank / Barclays / Citadel 等 12 家 W22 新接。`foreign_ibs` ~4.5min 最慢。 |
| Coverage dashboard (`/coverage`) | ✅ stable | 2026-05-26 | 13 coverage tracks (W22 新增 insurance_am / securities_am / bank_wealth);yaml `canonical_tracks` 映射 13 canonical;starmap 默认视图。 |
| Sites monitor (`/sites`) | ✅ stable | 2026-05-19 | 已嵌入 `/system-health`,2/8s 自适应轮询。 |
| Admin pages (`/review-queue`, `/system-health`) | ✅ stable | 2026-05-19 | HiFi terracotta 作用域隔离。 |
| Resume Copilot pipeline | ✅ stable | 2026-05-26 | Parse → preferences (**13 canonical** picker) → recommendation V4 + LLM rerank + 个性化叙事 (Phase 7-8) + industry-tags (Phase 6) → chat rewrites with 编造数字守卫。 |
| Resume Copilot UI (HiFi 三页) | ✅ stable | 2026-05-26 | W22 新增:Sessions 页 (登录首屏选简历) / ConfirmProfile 整页 (替代浮层) / IntelDrawer 420px 4-tab / CoachPane + RewritePane 中栏 takeover。 |
| Resume Copilot demo session | ✅ stable | 2026-05-18 | `DEMO_SESSION_ID=1`,lifespan 启动时强制重建。 |
| Mock interview (text + voice) | ✅ stable | 2026-05-18 | DashScope cosyvoice-v2 + paraformer-realtime-v2。Lingmou 数字人 dormant。 |
| Adaptive interview picker | ✅ stable | 2026-05-18 | Skeleton + LLM follow-up + recall + interest_decider (followup mean 2.40→3.00)。每个并行任务独立 SessionLocal。 |
| 5 ContextProviders fan-in | ✅ stable | 2026-05-18 | sensitive_topic → tencent_track → student_memory → podcast → track_knowledge,按序短路。 |
| Taxonomy module (`app.services.taxonomy/`) | ✅ stable | 2026-05-26 | **13 canonical** (W22 从 10 扩出) + 280+ aliases + 22 红线词 + source_map + tracks.yaml 13 条 knowledge + TrackKnowledgeProvider。994 unit tests。 |
| `Job.canonical_track` 派生 + backfill | ✅ stable | 2026-05-26 | SQLAlchemy `before_insert` 自动派生;v2 重构有 `canonical_track_pre_v2` 备份列;rule-based backfill 脚本拆 4 个 ambiguous 池。MiMo 总覆盖率 46.2%。 |
| Eval harness Phase 1+1.5 (投研 v1) | ✅ stable | 2026-05-18 | 5 students × 5 JDs × 5 answers + judge.py 4 metric × MiMo + multi_turn simulator。JD fixtures + judge prompt 已升级 **13 canonical**。 |
| Knowledge pack (Tencent skill) | ✅ stable | 2026-05-16 | 9 tables,8/8 verbatim quotes 验过,5 output constraints,8 sensitive topics。 |
| Account system (alpha-1 内测) | ✅ stable | 2026-05-15 | 4 表 + 6 endpoints + bcrypt + QQ SMTP + AuthModal。 |
| XHS crawler | 🟡 deprecated | 2026-05-26 | 2026-05-26 决策:爬取弃用,改 API 替代。详见 `WORKTREE_STATUS.md`。 |
| Alembic migrations | 🟡 partial | 2026-05-26 | Strangler-fig 与 `schema_patch.py` 共存。新 schema 走 Alembic only。当前 head `f1a8e3c7b2d5`(13 canonical v2)。 |

## In flight

**等用户指派**。最近收官:W22 HiFi 三页一比一复刻 (Sessions/Confirm/Coach/Intel/Rewrite) + 13 canonical 赛道重构 + 推荐叙事 Phase 5-8 + 12 家金融爬虫扩展。

**待部署**:今天合并的 W22 全部工作**尚未推到 prod VPS**(jobcopilot.top 仍是旧版),需跑 `jobradar-vps-deploy` skill。

## Recent shipped (last 2 weeks)

详见 `CHANGELOG.md`。亮点:**taxonomy 项目级铺线 sprint 7 commit 全 ship** (A/B/C/D-0/D/E/F);account 系统 alpha-1 上线;低质量红线;XHS crawler;eval Phase 1+1.5;interest_decider;hybrid follow-up。

## Known blockers / debt

| 优先级 | 问题 | 位置 |
|---|---|---|
| 🟡 | `_build_session_out` N+1(每次 1.6s 轮询跑 5 次 `.first()`) | `backend/app/routers/resume_copilot.py:57-61` |
| ✅ | ~~`recommend_jobs_for_profile` 全表 `query(Job).all()` 无 prefilter~~ — 已修(D-18: track-aware prefilter + 双层 NULL fallback + 可迁移 OR + 分级 fallback) | `recommendation.py:530-619` |
| 🟡 | 推荐 enrichment snapshot 无 14 天 TTL | `recommendation.py:393-395` |
| ✅ | ~~Job.canonical_track 覆盖率 29.9%~~ → **2026-05-18 已解决**:MiMo v2.5 backfill 74,750 rows = **46.2% coverage** (D-17)。余 53.8% NULL 是 MiMo 判"无金融相关性"的真噪声,不再 actionable。 | `backend/scripts/mimo_backfill_canonical.py` |
| ✅ | ~~SUT 推荐 tier_label 太保守~~ — 已修(D-19: 三档白名单强约束 + rule 兜底);follow-up 跨经历跳跃问题独立留 backlog | rerank prompt 严约束 |
| 🟢 | chat.py rewrite 未按 user canonical track 调改写口径 — 仍为 Phase E stretch backlog;但 audit_draft 已接 (D-19) | `chat.py` |
| 🟢 | Tencent 知识包用的是 transcript 范例数据,未接 `tencent-recruit-pack/scripts/fetch_recruit_jds.py` 抓真实 JD | `backend/app/services/knowledge_pack/` |
| 🟢 | `HANDOFF_NEXT_SESSION.md` (root) / `backend/data/jobradar.db.bak.20260428` / `docs/decisions.md` (lowercase) 三个 stale — 待 user 确认删/保留 | root + backend/data + docs |

## Runtimes (dev + prod 自 2026-05-17 拆分)

- **Dev VPS** `lavm-wlcndo6anm` (公网 `1.161.52.206`,4 CPU / 15Gi / 99G):开发 / migration / LLM backfill / smoke。**不**跑 systemd。
- **Prod VPS** `myvps` (公网 `122.51.18.237`):systemd `jobradar.service`,main 分支,域名 jobcopilot.top。Daily crawl 08:00 / tier crawl 09:00 / digest 09:35(Asia/Shanghai)。
- dev → prod 同步走 `jobradar-vps-deploy` skill;dev DB 改动不会自动到 prod。
- 详见 `CLAUDE.md` "Runtimes" 段 + `docs/deployment-and-data.md`。
