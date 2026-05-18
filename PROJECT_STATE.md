# PROJECT_STATE

> 项目当前快照。每次大段工作结束时更新。**Last updated: 2026-05-16 深夜.**

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

(空) — Taxonomy sprint 收官,等用户指派下一段。详见 `HANDOFF.md` "下次会话最适合接的几件事"。

## Recent shipped (last 2 weeks)

详见 `CHANGELOG.md`。亮点:**taxonomy 项目级铺线 sprint 7 commit 全 ship** (A/B/C/D-0/D/E/F);account 系统 alpha-1 上线;低质量红线;XHS crawler;eval Phase 1+1.5;interest_decider;hybrid follow-up。

## Known blockers / debt

| 优先级 | 问题 | 位置 |
|---|---|---|
| 🟡 | `_build_session_out` N+1(每次 1.6s 轮询跑 5 次 `.first()`) | `backend/app/routers/resume_copilot.py:57-61` |
| 🟡 | `recommend_jobs_for_profile` 全表 `query(Job).all()` 无 prefilter | `backend/app/services/resume_copilot/recommendation.py:439` |
| 🟡 | 推荐 enrichment snapshot 无 14 天 TTL | `recommendation.py:393-395` |
| 🟢 | ~~Job.canonical_track 覆盖率 29.9%~~ → **2026-05-18 已解决**:VPS DB 跑 alembic 0004/0005 + MiMo v2.5 backfill 74,750 rows = **46.2% coverage** (57,927/125,367)。余 53.8% NULL 是 MiMo 判"无金融相关性"的真噪声(互联网/消费/制造非 SAIF 池),不再 actionable。详见 `backend/scripts/mimo_backfill_canonical.py` + D-16。 | — |
| 🟡 | SUT 推荐 tier_label 太保守(multi-turn baseline 从不给 '强匹配');SUT follow-up 偶发跨经历跳跃 | `backend/app/services/resume_copilot/recommendation.py` LLM rerank prompt |
| 🟢 | chat.py rewrite 未按 user canonical track 调改写口径(Phase E stretch 留 backlog) | `backend/app/services/resume_copilot/chat.py` |
| 🟢 | Tencent 知识包用的是 transcript 范例数据,未接 `tencent-recruit-pack/scripts/fetch_recruit_jds.py` 抓真实 JD | `backend/app/services/knowledge_pack/` |
| 🟢 | `HANDOFF_NEXT_SESSION.md` (root) / `backend/data/jobradar.db.bak.20260428` / `docs/decisions.md` (lowercase) 三个 stale — 待 user 确认删/保留 | root + backend/data + docs |

## Production runtime

- VPS `myvps` (122.51.18.237) 跑 systemd unit `jobradar.service`,main 分支。
- Daily crawl 08:00 / tier crawl 09:00 / digest 09:35(Asia/Shanghai)。
- 详见 `CLAUDE.md` "Production runtime" 段 + `docs/deployment-and-data.md`。
