# CHANGELOG

> 最近 shipped 工作的轻量摘要。最新在上，按周分组。详细 entry 在 commit message 里。

## 2026-W21 (May 17-18) · MiMo backfill + SAIF 召回 + 6-metric + interview/eval 多 provider

- **🎯 6-metric 试点级硬化 sprint (2026-05-18, D-18)** —— 把推荐+简历改写共 6 个 metric 全部 push 到试点水平。
  - **推荐侧 ②③** — LLM rerank prompt 强制 SUT 输出 tier_label ∈ {强匹配/可迁移/有差距} 三档 + strengths 必须 2-4 条引用简历具体事实 (实习公司/项目/技能);新 `_track_kind_to_tier_label` 把 4 分支映射到 3 档 + 红线优先;新 `_compute_priority_letter` 算 A/B/C/D 投递分层;前端 HFPill 角标显示 priority_letter (绿/橙/灰/红) + tier_label。
  - **简历侧 ④⑤⑥** — chat.py 复用 plan-mode 的 `audit_draft` + `tag_extractor.extract_tags` + `EvidenceTag` schema (不搬整套状态机);新 `_profile_to_evidence_list` 把整份简历转 Evidence 池;`_filter_audit_risks_against_original` 差量过滤 leadership/tech (chat.py 是 rewrite 不是从空白起);chat.py system prompt 加严禁角色升级 + 成果声明编造;RewriteOption 新字段 `audit_risks` + `warning_severity`,UI 选项 B 半硬警告。
  - **离线评估** — `scripts/offline_test_resume_rewrite.py`:8 SAIF 简历 × 2 bullets × 2 options = 32 改写。**v3 (final): Evidence 100% / Severe overclaim 0% / Actionability 100%**;priority 分布 (n=80): A 86.2% / B 11.2% / C 2.5% / D 0%。
  - **30 新 unit tests** (`test_recommendation_priority_tier.py` + `test_chat_audit_integration.py`) 全绿。

- **🎯 SAIF 投研召回 sprint (2026-05-17, D-17)** —— 用户截图反馈"选投研+上海推 AI 工程师 / 合规 / 营销"问题完整修复。
  - **taxonomy 加 4 helper** — `_UMBRELLA_EXPANSION` (投研→4 canonical) + `expand_track_to_canonicals` + `aliases_for_canonical` + `recall_keywords_for_canonical`;`TRANSFERABLE_FOR_UMBRELLA` 跳板;`is_ambiguous_source` (1:N source 不当作错位)。
  - **召回硬过滤** — `_filter_candidate_jobs` 加 track 维度,双层 (typed ∪ transferable ∪ NULL+alias) ∧ (location ∨ company_type),分级 fallback。候选池从 91k 缩到 ~2235。
  - **打分权重再平衡** — track 4→18;`_classify_track_match` 4 分支 + `_track_mismatch_penalty=15` + risks 角标。
  - **红线词扩** — +13 个 stem (HRBP / 产品运营 / 服务经理 / 业务运营)。
  - **离线 harness** — N=8 + rerank:96.2% hit / 0% bad。

- **🎯 MiMo v2.5 canonical backfill sprint (2026-05-18, D-16)** —— Job.canonical_track 覆盖率 29.9% → **46.2%** (57,927/125,367),余 53.8% 是 MiMo 判"无金融相关性"的真噪声。
- **securities source-aware title 二级路由** — 修 sell-side / buy-side / IBD 三种 securities source 的 canonical 错位。
- **公募 6 家爬虫修复** — Beisen Zhiye SSR → SPA 适配。
- **hedge_funds +鸣石投资** — 量化 SAIF 校招扩 +7 个岗。
- **dev/prod VPS 拆分**(自 2026-05-17) — dev `lavm-wlcndo6anm` 不跑 systemd / prod `myvps` 域名 jobcopilot.top。

### Interview + eval 改进 (本地 6 commit)
- **interview/interest_decider 加维度 1b 迁移性追问** — 跨经历桥接 (量化→信用 / 期权→FICC) + A2 augmented_chip_summary 选公司差异化 inject;answer<80字 advance 等 hard rule。
- **interview/report 反编造守卫** — overall_comment + improvements 必须引用学生原话 + 可执行 action;JSON 转义用「」防双引号崩溃。
- **interview/scoring Phase A** — scoring_system.md + report.py prompt 加强要求引用原话。
- **eval/clients 多 judge provider** — `EVAL_JUDGE_PROVIDER=mimo|qwen|glm|deepseek`,429 专门 retry。
- **eval/judge Phase C** — 新 metric `judge_feedback_specificity`,评 SUT 报告是否引用原话+给可执行 action。
- **eval/runner real fixtures** — 5 真实公募 JD × 学生配对,`--real-only` flag 单跑真实数据。

## 2026-W20 (May 11-17) · 后半周大爆发

(2026-05-16 这一天连发 19+ commits,本周差不多干完了 SAIF 内测前的所有 alpha 准备)

- **🎯 taxonomy 项目级铺线 sprint 收官 (2026-05-16 深夜)** —— 6 phase 全 ship,8 canonical 贯穿 backend model + parser + provider + scoring,frontend picker,eval fixtures + judge prompt,DB jobs + tracks 全模块。**142 unit tests pass**。7 commits (`A 631e13b` / `F 2c39590` / `B 1de7f81` / `C 36cd29c` / `D-0 ce11b15` / `D 991342c` / `E 697cb37`)。关键产出:
  - **Phase B (`1de7f81`)** — Alembic 0005 加 `Job.canonical_track` Text + index;**SQLAlchemy `before_insert` event listener** 集中派生,避免改 20+ Job() 调用点;99113 行 backfill (29592 hit / 29.9% — 余下主要是 tatawangshen/legacy catchall 无信号 source);新 source_map.py 复用 Phase F coverage_truth.yaml 1:1 source 映射。
  - **Phase C (`36cd29c`)** — parser inferred_tracks (LLM + heuristic 两路) 跑 canonicalize;前端 TRACK_OPTIONS 改 8 canonical + 老值 union 渲染保留向后兼容。
  - **Phase D-0 (`ce11b15`)** — `tracks.yaml` 写满 8 canonical knowledge data (typical_employers / roles / high_quality_signals / low_quality_signals / star_examples / followup_templates)。
  - **Phase D (`991342c`)** — 5th ContextProvider `TrackKnowledgeProvider` 在 taxonomy/provider.py,优先级 preferences > inferred > target_job > user_question,返 ~600-1000 chars 紧凑 block (top-5 雇主 + top-5 信号 + 1 STAR + 2 followup),注册 bootstrap 第 5 位。
  - **Phase E (`697cb37`)** — 5 JD fixture + judge.py system prompt 引用 8 canonical + judge payload 含 jd_canonical_track。
- **taxonomy Phase F 落地 (2026-05-16 晚)** — `coverage_truth.yaml` 13 条每条加 `canonical_tracks: [...]` (允许 1:N,e.g. hedge_funds = [量化, 二级买方·基本面]); Track DB 加 `canonical_track` Text 列 + Alembic `0004_track_canonical_track` + 9 行 backfill (other_foreign 留 NULL,跨业态太杂)。`/api/coverage` + `/api/tracks` 都 surface 新字段。**additive 不破坏** —— dashboard 计算逻辑/keyword scoring 0 改动。82 unit tests pass (66 旧 + 16 新 wiring 契约)。
- **taxonomy module Phase A 落地 (2026-05-16)** — `app/services/taxonomy/` 抽出 8 canonical tracks + 65+ aliases + 22 红线词 patterns,从 `recommendation.py` 解耦。66 unit tests pass。下游 phase B-F (crawler ingest / parser canonicalize / preferences UI / 5th ContextProvider / scoring 重命名) 已规划。
- **8 canonical 金融赛道总览 doc** — `docs/finance-tracks-2026-overview.md` (~250 行) 写满 8 个赛道 × 平台 × 岗位 + ★ 评级 (★★★ 香饽饽 / ✗ 低质量) + 红线清单 + JobRadar 接入建议。数据混源:个人通识 + 4 次 web search + 1 次 XHS crawl(n=8 帖,46 评论)。
- **低质量岗位红线落地** — `_LOW_QUALITY_ROLE_PATTERNS` (22 词:柜员/客户经理/渠道销售类) + 命中 `final_score -50` + risk note。在真实 91465 jobs 表上扫描:命中 4251 (4.6%),top 50 零命中,bottom 50 全命中。误杀率 ≈ 0%。
- **前端 UI risk warning** — 推荐卡 enrichment badge 下加 risks 渲染,含"低质量"红底 🚫,其它琥珀底 ⚠️。
- **XHS crawler 验证 + 注入 session** — 用户提供 3 套 cookie (旧 A 已封 / 新 A 可用 / B 冷藏),用户新 A 的 web_session 已注入 `tools/xhs_post_comment_crawler/profiles/default/`。smoke-test:搜"校招" → 20 结果,抓 18 评论。
- **token trace 排雷 phase D** — `LLM_CTX_TRACE=1` 开关 + `fetch_blocks` 结构化日志。实测当前 chat 用 600 tokens (<2% context),5th provider 加 1000-1500 仍 <5%。**D-05 担心的"budget 撑满"被证伪**,5th provider 安全。
- **账号系统 alpha-1 内测** — 4 张新表 (invite_codes / users / email_verifications / user_sessions) + 6 endpoints + bcrypt + QQ SMTP (`smtp.qq.com:465` SSL) + AuthModal (登录+邀请码注册+verify 三步) + 自动签 30 天 token。5 个邀请码,1 个已用。
- **interview hybrid follow-up 决策 (interest_decider)** — 替代旧的"`prev_score.overall < 60`" 系统视角。新 `interest_decider.py` LLM 按真实面试官 4 维度判断 (业务相关 / 候选人钩子 / 可挖细节 / 不看分数)。加 hard rule:反问环节强制 advance + cap=3 + 答案<80字 advance。eval baseline 验证 followup mean **2.40 → 3.00**,case 05 反问 bug `0 → 3` 修了。
- **judge calibration 看 SUT tier_label** — `judge_track_relevance` 重写,SUT 推 gap+tier='有差距' → 1 分(合理);SUT 推 gap+tier='强匹配' → 0 分(真 bug)。0 分案例从 **11 → 3**,1 分从 **2 → 13**。
- **Multi-turn simulator (Phase 1.5)** — `tests/eval/multi_turn.py` 接 `interest_decider`,跑完整 19-turn 模拟面试。2 fixture mean=2.50。interest_decider 行为完全按业务对齐 (e.g., "光伏项目与 JD 大消费板块缺乏业务关联" → advance)。
- **Meta-doc 重组 (2026-05-15)** — slim 了 CLAUDE.md（320→~180 行），新增 root 级 `PROJECT_STATE.md` / `TASKS.md` / `HANDOFF.md` / `DECISIONS.md` / `CHANGELOG.md`，eval 设计落 `docs/eval-touyan-v1-design.md`，crawler 细节搬到 `docs/crawlers-notes.md`。
- 把 `tencent-recruit-pack/` 整个 vendor 进 repo（单学院部署，无授权顾虑）。
- 4 ContextProviders 接入 interview orchestrator：`sensitive_topic` / `tencent_track` / `student_memory` / `podcast`，按序注册 + sensitive 命中时短路。
- ExperienceRecaller subagent 接入 adaptive picker：sync orchestrator 通过 `asyncio.run` 桥接，failure 不致命（`is_usable` false → 降级为不带 recall 的 follow-up）。
- Tencent 知识包入库 pipeline：9 张新表 + idempotent CLI `backend/scripts/ingest_tencent_pack.py`。结果：2 employers / 5 tracks / 5 files / 29 resume rubrics / 11 interview rubrics / 8 verbatim quotes (8/8 verified) / 1 transcript example / 5 output constraints / 8 sensitive topics。
- Adaptive interview picker：skeleton + LLM follow-up + generic fallback。Q5-hardened — 每个并行任务独立 SessionLocal，绝不跨线程共享 db。
- Scoring service：rubric LLM call + reference answer + transcript-derived confidence (0-100)。所有相关 system prompt 走 cache-friendly 形态。

## 2026-W19 (May 4-10)

- Mock interview 语音栈切到 DashScope：TTS = `cosyvoice-v2` 音色 `longyingtian`，ASR = `paraformer-realtime-v2`。Lingmou 数字人代码 dormant 但保留。
- Interview SSE 单 read socket timeout 从 30s → 120s（reasoning 模型 token 间停顿可 >30s，原值会断流）。
- Phase 9 + 10 finance crawlers：hedge_funds + foreign_ibs（Citi+MS 走 Workday `searchText` 服务端过滤，避开 2000 个全球岗位的全 pagination）。
- Coverage dashboard：13 tracks，公司星图设为默认视图（替换排行榜默认）。
- Crawler 诊断方法论确立（D-10）— 标 "工程不可行" 前要跑 ≥1 个备选引擎实测。

## 2026-W18 (Apr 27 - May 3)

- Alembic migrations 引入；`schema_patch.py` 作为 strangler-fig 保留。
- SQLite engine：WAL + `busy_timeout=5000`（D-01）。
- Sites monitor 并入 `/system-health`；`/sites` 路由 + endpoints 保留以支持 direct linking。
- Demo session（`DEMO_SESSION_ID=1`）— 预置 recommendation + 3 chat 消息。`_assert_not_demo` 守卫挂在每个 write endpoint 上。

## 2026-W17 及以前

详见 `git log` 与 `docs/PROGRESS.md` (~47KB 历史进度档案)。
