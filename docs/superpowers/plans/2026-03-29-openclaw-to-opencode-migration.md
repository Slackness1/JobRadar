# OpenClaw → OpenCode 架构迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 OpenClaw multi-agent 上下文包整合到 OpenCode worktree 项目内，删除 OpenClaw 特有概念，保留业务知识。

**Architecture:** 编写新的 AGENTS.md 合并爬虫规则和工作流；将 TOOLS.md/MEMORY.md 精简迁移到 docs/ 下；迁移独占的 scripts；清理上下文包目录。

**Tech Stack:** Markdown 文档迁移， git 文件管理

---

## 文件差异结论（对比已完成）

| 类别 | 结论 |
|------|------|
| playbooks/ | 10/10 文件完全相同，项目已有，无需迁移 |
| docs/plans/ | 14/14 文件完全相同，项目已有，无需迁移 |
| 顶层 docs (CRAWL_PLAN 等) | 3/3 文件完全相同，项目已有，无需迁移 |
| config/ (yaml) | 9/9 文件完全相同，项目已有 backend/config/，无需迁移 |
| scripts/ | 上下文包有 36 个独占脚本，项目中仅有 1 个，需要迁移独占脚本到项目 scripts/ |
| services/, data-model/ | 仅作参考，项目已有实际代码。不迁移 |

---

### Task 1: 编写新的 AGENTS.md

**Files:**
- Create: `AGENTS.md`（项目根目录）

将 `boundary/AGENTS.md`（295行）+ `skills/SKILL.md` 合并为一个新的 AGENTS.md，删除所有 OpenClaw 调度概念，保留业务规则。

- [ ] **Step 1: 创建 AGENTS.md**

在项目根目录创建 `AGENTS.md`，内容合并自上下文包的 `boundary/AGENTS.md` 和 `skills/SKILL.md`，具体内容：

```markdown
# JobRadar — Project Rules

## Project Scope
- JobRadar 是一个岗位聚合与智能匹配系统
- 合法采集公开岗位信息 → 标准化 → 数据库 → 前端检索/筛选/分析
- 相关主路径：
  - `backend/` — 后端服务、爬虫、配置、数据库
  - `frontend/` — 前端 UI
  - `docs/` — 爬虫文档与站点 playbook
  - `scripts/` — 可复用脚本
  - `config.yaml` — 评分与赛道配置

## Source of Truth
1. 后端模型与数据库约束
2. 当前可运行的 crawler 代码
3. 当前 config 文件
4. docs/ 与 playbooks
5. config.yaml
6. 对话中的临时表述

## Core Crawling Principles
- 仅使用合法、公开、可访问的岗位数据来源
- 优先官方招聘站 > 公开 ATS/平台页 > 转载站/镜像站
- 尊重 robots/站点条款/登录边界/速率限制
- 不绕过验证码、登录封禁、风控
- 优先结构化、稳定、低脆弱度的数据源
- 新建提取逻辑前，先复用已有 crawler 与 config

## Preferred Extraction Order
1. 公开 job flow 中直接暴露的 JSON / API
2. 页面内嵌的 hydration payload、JSON-LD、初始化状态
3. 稳定 HTML 解析
4. 仅在前面不足时再使用 Playwright

## ATS / Framework Detector-First Rule
优先识别站点底层 ATS 或前端框架，再路由到对应 adapter：
- URL pattern / script src / DOM 特征 / network host / 页面文案

优先识别家族：Greenhouse / Lever / Workday / SmartRecruiters / Taleo / iCIMS / Moka / 北森 / 自建 SPA

一旦识别出家族，复用对应 adapter。修复面向家族沉淀，不只修单站点。

## Layered Crawl Escalation (Layer 0-4)
- **Layer 0** — 静态探测：职位关键词、ATS 特征、job link pattern、初始化 JSON
- **Layer 1** — 接口探测：XHR/fetch/GraphQL、JSON 响应、分页参数
- **Layer 2** — 轻量浏览器交互：等待 hydrate、滚动、点 load more、切 tab
- **Layer 3** — 重型页面抓取：逐项点详情、多轮滚动、复杂 DOM 抽取
- **Layer 4** — 保底链路：收集 detail 链接逐页解析，或标记"疑似有岗但列表解析失败"

少岗位官网优先兜底：
- 扫内嵌数据：__NEXT_DATA__ / __NUXT__ / window.__INITIAL_STATE__ / application/ld+json
- 收集所有疑似职位链接
- 多阶段等待+滚动，不只依赖 networkidle
- 检查 iframe / shadow DOM
- 用页面文案做 sanity check

## Six-Step Standard Crawl Workflow
1. **探测（Discovery）**：识别 ATS/框架/job signal，确认招聘主页/列表页/detail 链接模式/初始化数据线索
2. **优先 API**：发现稳定公开接口时直接抓
3. **混合模式**：Playwright 建会话拿 token/参数，再切回 requests 批抓
4. **页面高召回**：滚动/切 tab/点 load more/扫内嵌 JSON/收 detail 链接
5. **结果校验**：completeness score + 真假 0 判断
6. **失败归因**：标准标签、保留证据、进入 fallback 优先队列

## Zero-Result Validation
每次抓取必须对 0 岗位做真假判断：
- **confirmed zero** — 无信号/无链接/无指纹，确认无岗位
- **suspect zero** — 有信号矛盾时标记为可疑

标红条件（必须进入重试队列）：
- 页面自报有岗位但抽取为 0
- 发现 detail 链接但列表为 0
- 历史平均有岗位突然为 0
- detail URL 数量远多于列表结果

## Standard Failure Tags
- `NO_JOB_SIGNAL`
- `JOB_SIGNAL_BUT_ZERO_EXTRACTED`
- `HYDRATION_TIMEOUT`
- `NEEDS_INTERACTION`
- `DETAIL_LINKS_FOUND_LIST_FAILED`
- `API_FOUND_AUTH_REQUIRED`
- `BLOCKED_OR_EMPTY_RESPONSE`
- `ATS_DETECTED_BUT_ADAPTER_MISSING`
- `PAGE_CLAIMS_OPENINGS_BUT_ZERO`
- `IFRAME_CONTENT_NOT_PARSED`
- `SHADOW_DOM_NOT_PARSED`

## Lightweight Evidence Collection
每次抓取至少保留：final URL / 页面标题 / 前 10 XHR URL / ATS 指纹 / job/detail 链接 / 关键文本片段 / DOM 计数前后 / HTML 片段 / 截图 / 失败标签

## Documentation Update Rules
- 站点/ATS/平台规则 → `docs/site_playbooks/`
- 高层工作流/总体说明 → `docs/`
- 工具/路径/命令约定 → `docs/tools-and-paths.md`
- 长期决策 → `docs/decisions.md`

## Existing Crawler Families
新增逻辑前优先检查：
- `backend/app/services/crawler.py` — 通用 Playwright
- `backend/app/services/moka_crawler.py` — Moka 家族
- `backend/app/services/haitou_crawler.py` — 海投网
- `backend/app/services/securities_crawler.py` — 券商聚合
- `backend/app/services/securities_playwright_crawler.py` — 券商 Playwright
- `backend/app/services/bank_crawler/` — 银行专用
- `backend/app/services/energy_crawler.py` — 能源
- `backend/app/services/legacy_crawlers/` — 历史参考

## Config-First Behavior
优先扩展配置，不硬编码。重点配置：
- `backend/config/targets_v3.yaml`
- `backend/config/securities_campus.yaml`
- `backend/config/mbb_big4_config.yaml`
- `backend/config/tiered_internet_companies.yaml`

## Site Playbooks Index
详见 `docs/site_playbooks/_index.md`，当前已覆盖：
- banks / securities / moka / workday / greenhouse / lever / custom_sites / 51job_campus

## Data Handling
- 区分原始、过程态、标准化数据
- 保留来源 URL、抓取时间、source identifier
- 合并时避免重复岗位
- 缺失/模糊/可疑结果明确标注，不静默假设

## Failure Reporting
明确指出失败阶段：target discovery / config selection / listing discovery / pagination / detail extraction / normalization / database write / legal boundary

## Guardrails
- 先小样本验证，再放大
- 能复用缓存时优先复用
- 调 crawler 时做确定性小改动
- 站点变化后先更新 docs/config
```

- [ ] **Step 2: 验证 AGENTS.md 无 OpenClaw 残留**

```bash
grep -i "openclaw\|project-a\|project-b\|main.*schedule\|bank_queue\|executor contract\|feishu.*trigger\|SOUL\|HEARTBEAT\|IDENTITY\|memory/.*\.md" AGENTS.md
```

Expected: 无匹配结果

- [ ] **Step 3: 提交**

```bash
git add AGENTS.md
git commit -m "docs: add AGENTS.md with merged crawling rules and workflows"
```

---

### Task 2: 迁移 TOOLS.md → docs/tools-and-paths.md

**Files:**
- Create: `docs/tools-and-paths.md`
- Reference: `~/.config/opencode/project-a-context/boundary/TOOLS.md`

将 TOOLS.md 迁移到 docs/ 下，保留路径和命令参考，删除 OpenClaw 概念（安全审查 skills、memory 规则等）。

- [ ] **Step 1: 创建 docs/tools-and-paths.md**

内容从 TOOLS.md（184行）提取，保留以下部分并更新路径：

```markdown
# JobRadar Tools and Path Conventions

## Workspace Root
- 项目根目录：本 worktree 根目录
- 关键子路径：
  - `backend/app/services/` — crawler 实现
  - `backend/config/` — crawler target config
  - `backend/data/jobs.db` — SQLite 岗位数据库
  - `docs/` — 爬虫文档与站点 playbooks
  - `scripts/` — 可复用脚本

## Preferred Implementation Order
1. 优先扩展 `backend/app/services/` 里的现有 crawler
2. 再更新 `backend/config/` 中的 config
3. 再补 `docs/` 文档
4. 需要重复执行时，补 `scripts/` 入口
5. 只有确认无法复用时，才新建 crawler 文件

## Existing Crawler Implementation Hints
- 通用 Playwright：`backend/app/services/crawler.py`
- MOKA 家族：`backend/app/services/moka_crawler.py`
- Haitou 家族：`backend/app/services/haitou_crawler.py`
- 券商聚合：`backend/app/services/securities_crawler.py`
- 券商 Playwright：`backend/app/services/securities_playwright_crawler.py`
- 银行专用：`backend/app/services/bank_crawler/`
- 能源：`backend/app/services/energy_crawler.py`
- 补爬/一次性：`backend/app/services/legacy_crawlers/`

## Config-First Targets
- `backend/config/targets_v3.yaml`
- `backend/config/securities_campus.yaml`
- `backend/config/mbb_big4_config.yaml`
- `backend/config/tiered_internet_companies.yaml`

## Standard Data / Logging Conventions
- 原始/临时抓取：`data/tmp/`
- 截图：`data/screenshots/`
- 报告：`data/`
- 导出：`data/exports/`
- 备份：`data/backups/`

Crawl 报告尽量包含：target name / site family / ATS / config used / crawler path / extraction method / result count / failure notes / timestamp

## Database Handling
- 模型：`backend/app/models/`
- DB 连接：`backend/app/database.py`
- SQLite：`backend/data/jobs.db`
- 后端 schema 已存在时不另起存储结构

## Reusable Scripts
- `scripts/run_bank_crawl.py` — 银行爬取
- `scripts/merge_jobs.py` — 合并岗位数据
- `scripts/jobradar_paths.py` — 路径管理
- 重复流程优先补成脚本入口

## Environment Commands
- backend venv: `source backend/venv/bin/activate`（如存在）
- backend run: `cd backend && python3 -m uvicorn app.main:app --reload`
- Playwright: `python3 -m playwright install chromium`
- main crawl debug: `cd backend && python3 -m app.services.crawler`
- bank crawl: `python3 scripts/run_bank_crawl.py`
- merge: `python3 scripts/merge_jobs.py`
- proxy test: `python3 scripts/test_proxy.py`

## Securities Crawler Notes
- 券商 HTTPS 必须使用代理（http://127.0.0.1:7890），否则 ERR_EMPTY_RESPONSE
- 券商多 JS 渲染，静态 HTML 无法获取岗位数据
- 选择器脆弱，优先 config-first
- 运行前先验证代理：`python3 scripts/test_proxy.py`
```

- [ ] **Step 2: 提交**

```bash
git add docs/tools-and-paths.md
git commit -m "docs: migrate TOOLS.md to docs/tools-and-paths.md"
```

---

### Task 3: 迁移 MEMORY.md → docs/decisions.md

**Files:**
- Create: `docs/decisions.md`
- Reference: `~/.config/opencode/project-a-context/boundary/MEMORY.md`

将 MEMORY.md（406行）精简为关键决策记录。删除 OpenClaw agent 概念（"project-a"、"三层模型"等）。

- [ ] **Step 1: 创建 docs/decisions.md**

从 MEMORY.md 提取关键业务决策，精简为：

```markdown
# JobRadar Key Decisions

## 2026-03-12: JobRadar + job-crawler 项目合并
数据从 220 条增长到 16,685 条（75 倍增长），覆盖 30+ 家公司。
合并策略：脚本→legacy_crawlers/，数据→legacy/，配置→config/，job_id 去重。

## 2026-03-22: 爬虫知识沉淀结构
四层持久化：AGENTS.md（总规则）/ docs/tools-and-paths.md（路径命令）/ docs/site_playbooks/（站点经验）/ config.yaml（业务配置）。

## 2026-03-23: 两阶段爬取流程（Discovery → Extraction）
Discovery 只找入口，Extraction 只提数据。不允许未确认入口前直接大规模提取。

## 2026-03-23: 真假 0 判断 + completeness score
每次爬取对 0 结果做真假判断，计算 completeness score，可疑 0 进入重试队列。

## 2026-03-23: ATS detector + adapter 模式
先识别站点底层 ATS/框架，再路由到对应 adapter。修复面向家族沉淀。

## 2026-03-23: 轻量证据 + 标准失败标签
每次抓取保留轻量证据，使用标准 FailureReason 标签（11 种枚举）。

## 2026-03-23: 分层探测与分层升级（Layer 0-4）
0 层静态→1 层接口→2 层轻量交互→3 层重型→4 层保底。按层升级不跳层。

## 2026-03-23: 六步标准爬取流程
探测→API→混合模式→页面高召回→结果校验→失败归因。

## 2026-03-25: 咨询公司目标池分层
- Tier S: McKinsey, BCG, Bain
- Tier A: Oliver Wyman, Strategy&, Roland Berger, Kearney, LEK, EY-Parthenon
- Tier A-: Deloitte, PwC, EY, KPMG, Accenture, IBM Consulting
- Tier B: Capgemini, Protiviti, BearingPoint, ZS, OC&C, BDA
默认目标范围：Tier B 及以上。

## Tech Stack
- 前端：React 19 + TypeScript + Ant Design + Vite
- 后端：FastAPI + SQLAlchemy + SQLite + APScheduler
- 爬虫：Playwright + Requests + 配置化框架

## 5 Scoring Tracks
1. 数据分析/挖掘 (1.0)
2. 科技/数字化咨询 (0.9)
3. AI产品经理 (1.0)
4. 投研/市场研究 (0.95)
5. 电力市场/交易/算法 (0.85)

## Core Tables
jobs / tracks / keyword_groups / keywords / job_scores / crawl_logs / company_recrawl_queue / job_intel_tasks / job_intel_records / job_intel_snapshots / job_intel_comments
```

- [ ] **Step 2: 提交**

```bash
git add docs/decisions.md
git commit -m "docs: add key decisions from project history"
```

---

### Task 4: 迁移 memory/ 日志 → docs/memory/

**Files:**
- Create: `docs/memory/` 目录（14 个日志文件）

将上下文包 memory/ 下的 14 个日志文件复制到 docs/memory/。这些是历史运行记录，保留作为参考。

- [ ] **Step 1: 创建目录并复制文件**

```bash
mkdir -p docs/memory
cp /home/ubuntu/.config/opencode/project-a-context/memory/*.md docs/memory/
```

- [ ] **Step 2: 确认文件数量**

```bash
ls docs/memory/ | wc -l
```

Expected: 14

- [ ] **Step 3: 提交**

```bash
git add docs/memory/
git commit -m "docs: preserve historical memory logs in docs/memory/"
```

---

### Task 5: 迁移独占 scripts

**Files:**
- Copy: 36 个脚本文件到 `scripts/`

上下文包有 36 个项目 scripts/ 中不存在的脚本。复制到项目 scripts/ 中。唯一重叠的 `test_securities_simple.py` 保留项目版本（多两行 sys.path 设置）。

- [ ] **Step 1: 复制独占脚本**

```bash
# 获取上下文包中存在但项目中不存在的脚本
for f in /home/ubuntu/.config/opencode/project-a-context/scripts/*; do
  basename=$(basename "$f")
  if [ ! -f "scripts/$basename" ]; then
    cp "$f" "scripts/$basename"
  fi
done
```

- [ ] **Step 2: 确认新增文件**

```bash
ls scripts/ | wc -l
```

Expected: 37（原 1 个 + 新增 36 个）

- [ ] **Step 3: 提交**

```bash
git add scripts/
git commit -m "scripts: migrate context bundle scripts into project"
```

---

### Task 6: 迁移 config 参考 → docs/config-reference/

**Files:**
- Create: `docs/config-reference/`（9 个 yaml 文件副本）

config/ 中的 9 个 yaml 已存在于 `backend/config/`（完全相同）。在 docs/config-reference/ 创建副本作为参考文档，方便不启动后端也能查看配置。

- [ ] **Step 1: 创建目录并复制**

```bash
mkdir -p docs/config-reference
cp /home/ubuntu/.config/opencode/project-a-context/config/*.yaml docs/config-reference/
```

- [ ] **Step 2: 提交**

```bash
git add docs/config-reference/
git commit -m "docs: add config reference copies for easy access"
```

---

### Task 7: 更新 OPENCODE_START.md

**Files:**
- Modify: `OPENCODE_START.md`

更新 OPENCODE_START.md 反映新结构，移除对上下文包的依赖。

- [ ] **Step 1: 重写 OPENCODE_START.md**

```markdown
# JobRadar — OpenCode Workspace

## Quick Start
1. Read `AGENTS.md` — project rules and crawling workflows
2. Read `docs/tools-and-paths.md` — paths, commands, conventions
3. Read `docs/decisions.md` — key project decisions

## Key Locations
- Crawler code: `backend/app/services/`
- Crawler config: `backend/config/`
- Site playbooks: `docs/site_playbooks/`
- Scoring config: `config.yaml`
- Historical logs: `docs/memory/`

## Crawling Rules
- Always Discovery first, then Extraction
- Prefer API / embedded payload → HTML → Playwright
- Validate zero results (confirmed zero vs suspect zero)
- Collect lightweight evidence on every crawl
- See `AGENTS.md` for full rules
```

- [ ] **Step 2: 提交**

```bash
git add OPENCODE_START.md
git commit -m "docs: update OPENCODE_START.md for new structure"
```

---

### Task 8: 清理上下文包目录

**Files:**
- Delete: `.project-a-context/` (worktree 内的副本)

删除 worktree 内的上下文包副本。`~/.config/opencode/project-a-context/` 保留（用户可能仍需要）。

- [ ] **Step 1: 删除 worktree 内的上下文包副本**

```bash
rm -rf .project-a-context/
```

- [ ] **Step 2: 确认删除**

```bash
ls .project-a-context/ 2>&1
```

Expected: "No such file or directory"

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "chore: remove .project-a-context bundle (migrated to project docs)"
```

---

### Task 9: 最终验证

- [ ] **Step 1: 确认 AGENTS.md 无 OpenClaw 残留**

```bash
grep -in "openclaw\|project-a\|project-b\|\.openclaw\|SOUL\.md\|HEARTBEAT\|IDENTITY\.md\|executor contract\|bank_queue" AGENTS.md
```

Expected: 无输出

- [ ] **Step 2: 确认文件结构完整**

```bash
echo "=== Root ===" && ls AGENTS.md OPENCODE_START.md config.yaml
echo "=== docs ===" && ls docs/decisions.md docs/tools-and-paths.md
echo "=== docs/memory ===" && ls docs/memory/ | wc -l
echo "=== docs/config-reference ===" && ls docs/config-reference/ | wc -l
echo "=== docs/site_playbooks ===" && ls docs/site_playbooks/ | wc -l
echo "=== scripts ===" && ls scripts/ | wc -l
echo "=== .project-a-context ===" && ls .project-a-context/ 2>&1
```

Expected:
- AGENTS.md, OPENCODE_START.md, config.yaml 存在
- docs/decisions.md, docs/tools-and-paths.md 存在
- docs/memory/ 有 14 个文件
- docs/config-reference/ 有 9 个文件
- docs/site_playbooks/ 有 10 个文件
- scripts/ 有 37 个文件
- .project-a-context/ 不存在

- [ ] **Step 3: 确认前后端不受影响**

```bash
ls backend/app/services/crawler.py backend/app/models/ backend/config/targets_v3.yaml
```

Expected: 所有文件存在

- [ ] **Step 4: 最终提交**

```bash
git status
git log --oneline -10
```
