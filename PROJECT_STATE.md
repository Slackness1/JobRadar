# PROJECT_STATE

> 项目当前快照。每次大段工作结束时更新。**Last updated: 2026-05-18.**

## Modules

| Module | Status | Notes |
|---|---|---|
| Crawlers (10 tier blocks) | ✅ stable | 9 daily blocks + Tata API。`foreign_ibs` ~4.5min 最慢。Job 落库时 `before_insert` 自动派生 `canonical_track`。 |
| Sites monitor (`/sites`, `/api/sites`) | ✅ stable | 已嵌入 `/system-health`,2/8s 自适应轮询。 |
| Coverage dashboard (`/coverage`) | ✅ stable | 13 tracks,每条 yaml 带 `canonical_tracks: [...]` 映射 8 canonical;`/api/coverage` response surface 该字段。golden-spiral starmap 默认视图。 |
| Admin pages (`/review-queue`, `/system-health`) | ✅ stable | Wireframe 变体 C,HiFi terracotta 作用域隔离。 |
| Resume Copilot pipeline | ✅ stable | Parse(inferred_tracks 自动 canonicalize) → preferences (8 canonical picker + 老值 union) → recommendation + LLM rerank → chat rewrites。 |
| Resume Copilot demo session | ✅ stable | `DEMO_SESSION_ID=1`,lifespan 启动时强制重建。 |
| Mock interview (text + voice) | ✅ stable | DashScope cosyvoice-v2 + paraformer-realtime-v2。Lingmou 数字人 dormant。 |
| Adaptive interview picker | ✅ stable | Skeleton + LLM follow-up + recall + hard-rule + interest_decider (followup mean 2.40→3.00)。每个并行任务独立 SessionLocal (Q5-hardened)。 |
| 5 ContextProviders fan-in | ✅ stable | sensitive_topic → tencent_track → student_memory → podcast → **track_knowledge** (Phase D 新加),按序短路。 |
| Taxonomy module (`app.services.taxonomy/`) | ✅ stable | 8 canonical + 65+ aliases + 22 红线词 + source_map (1:1 source→canonical) + tracks.yaml (8 canonical knowledge data) + TrackKnowledgeProvider。142 unit tests。 |
| `Job.canonical_track` + `Track.canonical_track` | ✅ stable | SQLAlchemy `before_insert` 自动派生 Job;Track DB 9 行 backfill;Alembic 0004/0005;`/api/tracks` surface。Job 99113 行 backfill 29592 (29.9%)。 |
| Eval harness Phase 1+1.5 (投研 v1) | ✅ stable | 5 students × 5 JDs × 5 answers + judge.py 4 metric × MiMo + multi_turn simulator 接 interest_decider。JD fixtures 带 canonical_track,judge prompt enumerate 8 canonical。baseline.json checked in。 |
| Knowledge pack (Tencent skill) | ✅ stable | 9 tables,8/8 verbatim quotes 验过,5 output constraints,8 sensitive topics。 |
| Account system (alpha-1 内测) | ✅ stable | 4 表 + 6 endpoints + bcrypt + QQ SMTP + AuthModal。4/5 邀请码可用。 |
| XHS crawler (`tools/xhs_post_comment_crawler/`) | ✅ usable | 新 A 账号 web_session 已注入。B 账号冷藏。smoke pass。`env -u ALL_PROXY` 跑。 |
| Alembic migrations | 🟡 partial | Strangler-fig 与 `schema_patch.py` 共存。新 schema 走 Alembic only。当前 head `0005_job_canonical_track`。 |

## In flight

(空) — 6-metric 试点级硬化 sprint 收官 (D-19):推荐侧 tier_label 三档强约束 + priority_letter A/B/C/D;简历侧 chat.py 接 audit_draft 5 维 (复用 plan-mode 算法);Evidence 100% / Overclaim 0% / Actionability 100%;30 新 unit tests。**MiMo backfill 收官 (D-17)**:canonical 覆盖 29.9% → 46.2%。等用户指派下一段。

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
