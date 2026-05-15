# DECISIONS

> 架构 / 技术决策与"为什么这么做"。**只追加**，不重写历史。每条格式：编号 · 日期 · 标题 / 决策 / 备选 / 为什么 / 位置。

> 2026-03 时期的业务决策（爬虫合并、咨询公司分层、5 scoring tracks、爬虫四层持久化）放在 `docs/decisions.md` (lowercase) — frozen snapshot，不再维护。本文件从 2026-04 架构期开始。

---

## D-01 · 2026-04-28 · SQLite WAL + busy_timeout=5000

**决策**：在 SQLAlchemy engine 的 `@event.listens_for('connect')` hook 里 `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`。
**备选**：保留默认 rollback journal，在 app 层加 retry。
**为什么**：上线一周内出现 daily crawler 写 + 1.6s frontend poll 读 = `database is locked`。WAL 消掉读写竞争，busy_timeout 吸收残余写写竞争。10 行改动 vs 全栈 retry 包装。
**位置**：`backend/app/database.py`

## D-02 · 2026-04-28 · Alembic 走 strangler-fig，`schema_patch.py` 不动

**决策**：所有新 schema 改动只走 Alembic（`backend/alembic/versions/`）。`app/services/schema_patch.py` 继续在 lifespan 启动时跑，但**冻结**到现有 patch，不再加新东西。
**备选**：一次切换 — 删掉 `schema_patch.py`，把当前 schema 塞进一个 baseline migration。
**为什么**：VPS DB 有 8+ 个 `.bak` 文件是手动 schema-stress 的证据，一次切换的 prod 回归风险高于"两套并存一个月"。新 migration 用 `inspector.get_table_names()` 做 idempotency 检查，重跑安全。
**位置**：`backend/alembic/versions/`

## D-03 · 2026-05-01 · DashScope 替换 Aliyun NLS（语音栈）

**决策**：TTS = `cosyvoice-v2` 音色 `longyingtian`（CosyVoice WebSocket duplex）。ASR = `paraformer-realtime-v2`（`/api/interview/asr` WS proxy）。Lingmou 数字人代码保留但 **dormant**。
**备选**：留在 Aliyun NLS。
**为什么**：NLS 账号/配额阻塞 + ASR partial 延迟更慢。DashScope token 复用 Resume Copilot 已有账号。Lingmou 代码留着是因为以后回切"真实数字人头像"不想从零写 V3 签名 + ROA path。
**位置**：`backend/app/services/interview/voice/`，commits `4615a9e` / `7d2f8d2`

## D-04 · 2026-05-13 · Per-page scoped HiFi terracotta 主题

**决策**：每个 HiFi 风格的 admin 页（sites / coverage / review / health）有独立 `*-theme.css`，CSS scope 是 `[data-theme="<page>"]`。`resume-copilot-web` 三套设计系统并存：Workspace（root tokens）/ HiFi（`.hf` scope）/ Interview（`[data-theme="interview"]` scope）。
**备选**：单一全局主题 + 每页 cascade 覆盖。
**为什么**：admin 页里 AntD 组件和 HiFi 组件并存。全局 terracotta 会污染 AntD 的对比度。Scope 隔离是不打架 AntD 最便宜的方案。
**位置**：`frontend/src/styles/{sites,coverage,review,health}-theme.css`、`resume-copilot-web/components/hifi/hifi-tokens.css`、`resume-copilot-web/app/interview/interview-theme.css`

## D-05 · 2026-05-14 · ContextProvider 注册有序 + early-terminate

**决策**：4 个 provider 按序注册：`sensitive_topic` → `tencent_track` → `student_memory` → `podcast`。每个 `fetch()` 返回 `str | tuple[str, terminate: bool]`。`SensitiveTopicProvider` 在 `block`/`warn` severity 命中时返回 `terminate=True`，registry 短路掉后续。
**备选**：所有 provider 并行跑，concat 输出，让 LLM 自己解决冲突。
**为什么**：薪酬 / 通过率 / offer 承诺类话题带强制 guardrail 模板，**不能**叠加其它 context（会稀释 guardrail）。有序 + 短路把这个契约显式化、可测。并行 concat 把决策权交给 LLM，安全话题不能这么干。
**位置**：`backend/app/services/llm_context/registry.py`、`backend/app/services/knowledge_pack/sensitive_provider.py`

## D-06 · 2026-05-14 · Knowledge pack = DB tables，不是运行时读 MD

**决策**：9 张表（`knowledge_employer / knowledge_track / knowledge_file / track_resume_rubric / track_interview_rubric / interviewer_quote / track_example_bank / output_constraint / sensitive_topic`）。CLI `backend/scripts/ingest_tencent_pack.py` 从 `tencent-recruit-pack/` 的 MD 入库。
**备选**：请求时 lazy 读 MD 拼 prompt。
**为什么**：per-employer / per-track 过滤是常态，DB index 便宜。Ingest 时跑 `_verify_verbatim`（带 smart-quote 归一化）— dev 期间确实抓住过 LLM 偷偷改写 quote 的情况。`KnowledgeFile.content_hash` dedup 让重跑 idempotent。
**位置**：`backend/app/services/knowledge_pack/`

## D-07 · 2026-05-14 · ExperienceRecaller 是 async subagent，sync orchestrator 通过 `asyncio.run` 桥接

**决策**：`ExperienceRecaller` 实现成 async (`Subagent[InT, OutT]` ABC)，但在 sync 的 `process_turn_synchronous` 里通过 `asyncio.run()` 调（`_recall_experiences()` 内）。
**备选**：(a) 把 orchestrator 改全 async；(b) 把 recaller 写 plain sync。
**为什么**：orchestrator 是 sync 因为 FastAPI `BackgroundTasks` 回调是 sync + 已有 fan-out 用 `ThreadPoolExecutor`。Recaller 写 async-shaped 是为了和将来其它 subagent 的 ABC 对齐（其它 agent 真要并行 LLM fan-out）。`asyncio.run` 是最便宜的桥 — recaller 只做纯 SQL + 1 次 LLM call，没有嵌套 loop 风险。
**位置**：`backend/app/services/interview/orchestrator.py:_recall_experiences`、`backend/app/services/interview/subagents/recaller.py`

## D-08 · 2026-05-14 · 把 `tencent-recruit-pack/` vendor 进 repo

**决策**：Tencent skill pack 的源 MD 放在 repo 内 `tencent-recruit-pack/`，不做 sibling skill repo。
**备选**：保持 skill repo，ingest 时 clone。
**为什么**：user 确认是单学院部署 — 没有授权 / 脱敏顾虑。Vendor 进来去掉一个 moving dependency，让 ingest CLI 在 fresh clone 上能直接跑。
**位置**：`tencent-recruit-pack/`

## D-09 · 2026-05-15 · Eval harness 范围 = 4 metric × 投研一个方向（Phase 1）

**决策**：第一版 eval harness 只覆盖 4 个 metric（Track Relevance / Fit Explanation Quality / Evidence Groundedness / Follow-up Quality）× 15 个 fixture（5 students / 5 JDs / 5 interview answers），全部投研方向。Trace 是 Phase 2，hard guardrail 是 Phase 3。
**备选**：8 metric × 全方向；或者 trace-first。
**为什么**：user 说要把更大的提议精简。最高 ROI 是"我改了 prompt 之后有没有让别的 case 退步"的回归检测 — 这个需要 fixtures + diff，**不**需要 trace。单方向（投研）让 LLM judge 对 rubric 期待能写得很具体；之后加 互联网 / 咨询 是 copy-paste schema。
**位置**：`docs/eval-touyan-v1-design.md`

## D-10 · 2026-05-09 · Crawler "工程不可行"判定要至少 1 个备选引擎实测

**决策**：在给某家 crawler 标 "工程不可行 / 反爬不可绕" 之前，至少要用 1 个备选引擎跑过 — 候选：`curl_cffi.requests` (impersonate=chrome120/safari17_2) / Playwright Firefox / 直 `requests` 加全 `Sec-Fetch-*` headers / 找 RSC payload 或 `window.__NEXT_DATA__` 等 SSR 数据源。≥2 个备选都拿不到再判工程不可行。
**备选**：信第一次 Chromium 失败的诊断。
**为什么**：2026-05-09 LVMH 反例 — Phase 5 当时定为 "Chromium HTTP/2 fingerprint 被 CDN 拒，工程不可行"。subagent 用 `curl_cffi.requests.get(impersonate='chrome120')` 一次过 200 / 1.38MB HTML。真因是 Prismic CMS `offersUrl: "$undefined"`（上游内容真空），不是反爬。要分清 (a) 上游真空 vs (b) 反爬不可绕 vs (c) 选择器/接口漂 — 三种处理方式不同。
**位置**：详见 `docs/crawlers-notes.md` "诊断方法论"
