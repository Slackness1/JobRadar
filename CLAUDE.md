# CLAUDE.md

> 新会话**先读这个**。然后看 `PROJECT_STATE.md`（当前状态）/ `TASKS.md`（接什么干）/ `HANDOFF.md`（上次留到哪）/ `DECISIONS.md`（为什么是现在的样子）。

## What this project is

**JobRadar** — 中文求职 / 校招市场的岗位追踪工具。**三个 runtime**：

| Runtime | Root | Port | Purpose |
|---|---|---|---|
| Backend API | `backend/` | 8000 dev / 8002 docker | FastAPI + SQLite，所有数据 + AI 逻辑 |
| Job browser (admin) | `frontend/` | 5173 | Vite + React，岗位检索 / 评分 / 站点监控 / 覆盖度 |
| Resume Copilot Web (public) | `resume-copilot-web/` | 3001 | Next.js，简历上传 → parse → recommend + mock interview |

`frontend` 和 `resume-copilot-web` 都把 `/api/*` 代理到同一个 backend。它们**不**一起跑。

## Commands

```bash
# Backend
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
cd backend && PYTHONPATH=. .venv/bin/pytest tests/                   # all
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_X.py -x       # single
cd backend && PYTHONPATH=. .venv/bin/alembic revision --autogenerate -m "<name>"
cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head

# Frontend (Vite admin)
cd frontend && npm run dev          # 5173
cd frontend && npm run lint && npm run build && npm test

# Resume Copilot Web (Next.js)
cd resume-copilot-web && npm run dev   # 3001
cd resume-copilot-web && npm run lint  # 必须 0 errors 才能 ship
cd resume-copilot-web && npm run build

# Docker (backend + admin)
docker compose up --build              # backend :8001, frontend :5173
```

## Architecture (1 段话每个领域 — 深入看 `docs/architecture.md`)

- **`backend/app/main.py` lifespan**：建表 → `ensure_compatible_schema()`（legacy DDL patcher） → `alembic upgrade head` → seed YAML → `ensure_demo_session(db)` → APScheduler 启 daily-crawl 08:00 / tier-crawl 09:00 / digest 09:35（Asia/Shanghai） + hourly guest cleanup。
- **Resume Copilot pipeline** (`backend/app/services/resume_copilot/`)：`workflow.py`（async parse + generate via `BackgroundTasks`），`parser.py`（LLM extract + heuristic fallback），`recommendation.py`（rule_score → 可选 snapshot boost → LLM rerank），`quick_enrichment.py`（top-N 并行 web search），`chat.py`（rewrite 严契约 — 见 `DECISIONS.md`），`demo_session.py`（`DEMO_SESSION_ID = 1`）。
- **Mock Interview** (`backend/app/services/interview/`)：`orchestrator.py`（per-turn 三路并行 fan-out），`adaptive.py`（skeleton 6 题 + LLM follow-up + recall），`voice/{tts,asr}.py`（DashScope cosyvoice-v2 + paraformer-realtime-v2）。4 个 ContextProvider 通过 `app/services/llm_context/` 接入。
- **Knowledge pack** (`backend/app/services/knowledge_pack/`)：Tencent skill 9 张表，CLI ingest，verbatim quote 验过。
- **Crawlers** — `app/services/{insurance,bank,securities,funds,pe_vc,hedge_funds,foreign_ibs,internet,state_owned,consumer_foreign}_*_crawler.py`。**所有 quirk + 诊断方法论 + handler primitive 在 `docs/crawlers-notes.md`**。
- **Frontend admin** (`frontend/`)：Vite + React 19 + AntD 6。HiFi-styled 页（`/sites` / `/coverage` / `/review-queue` / `/system-health`）用 scoped `[data-theme="<page>"]` CSS，**不**用 AntD。
- **Resume Copilot Web** (`resume-copilot-web/`)：Next.js 16 App Router。**三套设计系统并存** — 见下文 "Design system rules"。

## Non-negotiable rules

### Git / shipping
- **从不**：force-push / `reset --hard` / `--no-verify` / `--no-gpg-sign` / 未授意 commit。
- **总是**：新 commit。已推 commit 不 `--amend`。Hook 失败 → 修 → re-stage → 新 commit。
- Frontend 改动 `npm run lint` + `npm run build` 必须过才算 done；backend `pytest tests/` 必须保持绿。
- **绝不** rollback 不相关工作来"清理"，留着别动。

### Backend conventions
- **新 schema 改动只走 Alembic**。`app/services/schema_patch.py` 是 legacy，启动时还在跑只为安全过渡，新表/列只往 `backend/alembic/versions/` 加。新 migration 用 `inspector.get_table_names()` 做 idempotency 检查。
- **SQLite engine WAL + busy_timeout=5000** 在 `backend/app/database.py` 的 `@event.listens_for(engine, 'connect')` hook 里，**不要**绕开 — 没 WAL 的话 daily crawl + poller 会 deadlock。
- **Demo session read-only**：`_assert_not_demo(session)` 检查 `session.user_key == '__demo__'`，挂在每个 write endpoint 上。新 write endpoint **必须**加这个守卫。
- **每个并行任务自己开 `SessionLocal`**。绝不跨线程共享 SQLAlchemy session。
- **语音栈是 DashScope，不是 Aliyun NLS**。TTS = `cosyvoice-v2` 音色 `longyingtian`；ASR = `paraformer-realtime-v2`。`voice/avatar.py` Lingmou 数字人代码 dormant — 不要 wire 进去之前看 `DECISIONS.md` D-03。

### LLM / context
- **ContextProvider 顺序有讲究**。`SensitiveTopicProvider` first；命中时返 `(block, terminate=True)`，registry 短路掉后续。**不要**改顺序之前看 `DECISIONS.md` D-05。
- **知识包的 verbatim quote 不能被改写**。Ingest 时 `_verify_verbatim`（带 smart-quote 归一化）已经 substring 验过；prompt / 输出里也不能改写。
- **Resume rewrite 不能编造数字**。`_detect_fabricated_numbers()` 在 `improved` bullet 出现 profile 里没的数字时加 warning — **不要**剥掉这个 warning，让它显式露出。

### Frontend conventions
- **三套设计系统并存，严格隔离**。Token 全部 scope 到 parent class / data-attr，**绝不**让一套渗到另一套：
  - **Workspace** (`/resume-copilot`)：sky-blue，token 在 `app/globals.css`，无 scope（root default）
  - **HiFi** (`/`、`/upload`、`<DemoBanner/>`)：terracotta `#c96442` on parchment `#f5f4ed`，Fraunces serif，token 在 `components/hifi/hifi-tokens.css`，**scope `.hf`**
  - **Interview** (`/interview/*`)：同 terracotta 调色板，token 在 `app/interview/interview-theme.css`，**scope `[data-theme="interview"]`**（`app/interview/layout.tsx` wrap）
- **Frontend admin 的 HiFi 页用 `[data-theme="<page>"]` scope**（看 `coverage-theme.css` / `sites-theme.css` / `review-theme.css` / `health-theme.css`）。新 HiFi-styled admin 页照这个模式。
- **Border Beam** 是共用的"AI thinking"效果 — `.border-beam` 在 `app/globals.css`。放在 `position: relative` 父元素的**最后一个 child**，让它在兄弟之上 paint。

### Crawlers — 操作铁律
- **标 "工程不可行" 之前必须跑 ≥1 个备选引擎**（curl_cffi / Playwright Firefox / 加 `Sec-Fetch-*` 的直 requests / 找 RSC payload）— 详见 `DECISIONS.md` D-10。
- **加新 finance source 要同时改 crawler 和 `coverage_truth.yaml` 的 `source_match`** — 一个 commit。
- 改 crawler 之前看 `docs/crawlers-notes.md` 的 site quirk —— 字节 5,590 ceiling / 阿里 batchId 季度更新 / Workday `limit ≤ 20` 等。

## Production runtime (摘要)

- VPS `myvps` (122.51.18.237) 跑 systemd unit `jobradar.service`，分支 `main`，bind `127.0.0.1:8000`。
- APScheduler `daily_crawl` 0 8 * * * Asia/Shanghai。验证：`curl http://127.0.0.1:8000/api/scheduler`。
- VPS 时区 = CST (UTC+8)；SQLite 存 naive UTC，查询用 `datetime(col, 'localtime')`，**不要**手动 -8h。
- VPS 工作目录 `/home/ubuntu/opencode-worktrees/jobrador-edit/backend`。新 VPS DB 第一次部署后 `alembic stamp head` 一次再让 lifespan upgrade。
- Logs：`sudo journalctl -u jobradar --since "08:00"`
- Weekly DB backup：WSL cron 每周日 03:00 跑 `~/bin/backup_jobradar_db.sh`，sqlite3 `.backup` API + gzip + rsync。

详见 `docs/deployment-and-data.md`。

## Environment setup

`backend/.env.local`（最小集）：

```
RESUME_COPILOT_BASE_URL=https://api.deepseek.com/v1
RESUME_COPILOT_API_KEY=sk-...
RESUME_COPILOT_MODEL_NAME=deepseek-chat
TAVILY_API_KEY=tvly-...
FIRECRAWL_API_KEY=fc-...
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_TTS_MODEL=cosyvoice-v2
DASHSCOPE_TTS_VOICE=longyingtian
DASHSCOPE_ASR_MODEL=paraformer-realtime-v2
```

完整 key 列表 + crawler / aliyun / scheduler 可选项在 `backend/app/config.py`。`resume-copilot-web/.env.local` 只在 backend 不在 8002 时设 `RESUME_COPILOT_BACKEND_URL`。

## Pointers — 找东西去这里

| 想看... | 去 |
|---|---|
| 当前模块状态 / 在做什么 / 阻塞 | `PROJECT_STATE.md` |
| 接下来干什么（active sprint + backlog） | `TASKS.md` |
| 上一段会话留到哪儿 | `HANDOFF.md` |
| 某决策为什么这么做（架构层） | `DECISIONS.md` |
| 2026-03 业务期决策（爬虫合并 / 咨询分层 / scoring tracks） | `docs/decisions.md` (legacy snapshot) |
| 最近 shipped 工作 | `CHANGELOG.md` |
| 历史进度档案（~47KB） | `docs/PROGRESS.md` |
| Crawler quirk / 诊断方法论 / handler primitive | `docs/crawlers-notes.md` |
| Crawler 各 tier 覆盖度报告 | `docs/crawler-coverage-{internet,banks,securities,state-owned,consumer-foreign}-2026-05.md` |
| Eval harness 设计（投研 v1） | `docs/eval-touyan-v1-design.md` |
| 生产 VPS / systemd / DB backup 细节 | `docs/deployment-and-data.md` |
| 架构深入（per-router / per-service） | `docs/architecture.md` |
| Job intel 系统设计 | `docs/JOB_INTEL_SYSTEM_DESIGN.md` |
| Interview Subagent ABC + ExperienceRecaller 设计原文 | `docs/interview-subagent-design-2026-05-13.md` |
| 统一 Memory + Plan Mode 设计原文 | `docs/unified-memory-and-plan-mode-2026-05-13.md` |
| OpenCode agent handbook（Claude Code 不用读，用其它 agent 时看） | `AGENTS.md` |
