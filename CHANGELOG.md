# CHANGELOG

> 最近 shipped 工作的轻量摘要。最新在上，按周分组。详细 entry 在 commit message 里。

## 2026-W20 (May 11-17)

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
