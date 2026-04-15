# JobRadar Agent Handbook

## Project Overview
- JobRadar 是岗位聚合与智能匹配系统。
- 主链路：合法采集公开岗位信息 -> 标准化 -> 数据库存储 -> 前端检索/筛选/分析。
- 关键目录：
  - `backend/`：FastAPI、SQLAlchemy、crawler、配置、数据库逻辑
  - `frontend/`：Vite + React + TypeScript 前端
  - `docs/`：站点 playbooks、决策、流程说明
  - `scripts/`：可复用脚本入口
  - `config.yaml`：评分与赛道配置

## Default Working Mode
- 默认在当前 WSL2 工作目录直接开发和验证。
- 适用于新 feature、bugfix、前后端联调、测试、文档更新。
- 影子环境不是默认前提。
- 只有在你需要隔离另一套已运行中的前后端、数据库快照或登录态时，才使用 shadow runtime。

## Source Of Truth
1. 后端模型与数据库约束
2. 当前可运行的 backend/frontend 代码
3. 当前 config 文件与 YAML 配置
4. `docs/` 与 site playbooks
5. 对话中的临时补充说明

## Workspace Rules Sources
- 当前仓库存在根目录 `AGENTS.md`，这是 repo 级主要 agent 指令入口。
- 当前仓库没有 `.cursor/rules/`、`.cursorrules`、`.github/copilot-instructions.md`。
- `.opencode/commands/` 存在，但只是 skill 快捷入口，不是每轮自动注入的第二套规则。
- 如果 `AGENTS.md` 与历史 memory/plan 文档冲突，以当前代码和本文件为准。

## Repo Map
- `backend/app/main.py`：FastAPI 入口与 router 注册
- `backend/app/routers/`：HTTP API 层
- `backend/app/services/`：业务逻辑与 crawler 实现
- `backend/app/models.py`：数据库模型
- `backend/app/schemas.py`、`backend/app/schemas_job_intel.py`：输入输出 schema
- `backend/app/database.py`：DB session 和依赖注入
- `backend/tests/`：pytest 测试
- `backend/config/`：站点与 crawler 配置
- `frontend/src/pages/`：页面组件
- `frontend/src/components/`：复用 UI 组件
- `frontend/src/api/index.ts`：前端 API 请求封装

## Build / Run / Lint / Test Commands

### Docker
- 启动：`docker compose up --build -d`
- 停止：`docker compose down`

### Backend Local Development
- 安装依赖：`pip install -r backend/requirements.txt`
- 安装 Playwright Chromium：`python3 -m playwright install chromium`
- 本地运行：`cd backend && python3 -m uvicorn app.main:app --reload`
- crawler 调试：`cd backend && python3 -m app.services.crawler`

### Backend Tests
- 全量：`cd backend && PYTHONPATH=. pytest -q`
- 单文件：`cd backend && PYTHONPATH=. pytest tests/test_haitou_crawler.py -v`
- 单用例：`cd backend && PYTHONPATH=. pytest tests/test_haitou_crawler.py::test_parse_time_range -v`
- 如果测试导入 `from app...`，优先保持 `PYTHONPATH=.` 的调用方式。

### Frontend Local Development
- 安装依赖：`cd frontend && npm ci`
- 本地开发：`cd frontend && npm run dev`
- 构建：`cd frontend && npm run build`
- Lint：`cd frontend && npm run lint`

### Frontend Tests
- 当前仓库没有已验证的前端测试脚本。
- 不要假设存在 `npm test`、Vitest、Jest 或 Playwright 前端测试命令。
- 如果后续新增前端测试工具，更新本文件与相关 docs。

## Backend Code Style
- import 顺序保持三组：标准库、第三方、本地 `app.*`，组间空一行。
- 函数、变量使用 `snake_case`。
- 类、Pydantic schema、SQLAlchemy model 使用 `PascalCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 私有辅助函数使用 `_name` 前缀。
- Router 保持薄：参数解析、响应模型、`HTTPException` 放在 `routers/`。
- 业务逻辑、抓取逻辑、导入导出逻辑优先放在 `services/`。
- 新逻辑优先复用现有 service，不要在 router 中堆积复杂分支。
- 保持与现有类型风格兼容；新代码优先显式类型，但不要为了统一风格做大规模无关重构。
- 对 DB 写操作保持明确的事务边界；失败时考虑 rollback 或状态回写。
- Service 层优先抛明确异常；Router 层将请求级错误转成 `HTTPException`。
- 不要静默吞错，尤其是 crawler、导入、任务队列、导出链路。

## Frontend Code Style
- React 组件、页面组件使用 `PascalCase`。
- 变量、函数、hooks、state 使用 `camelCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 优先使用显式 `interface` 或类型别名描述 API 数据与组件状态。
- `useState` 尽量带明确类型，避免无边界扩散 `any`。
- 类型导入优先使用 `import type`。
- 第三方依赖放在 import 前部，本地模块放后部。
- API 调用优先复用 `frontend/src/api/index.ts`，不要在页面里散落重复的 axios 请求。
- 对用户可见的错误优先用 antd `message` 反馈。
- 保持现有格式风格：单引号、分号、2 空格缩进。
- 遵循当前 ESLint 和 TS strict 配置，不额外引入新的 formatter 或状态管理方案，除非任务明确要求。

## Crawler Principles
- 仅使用合法、公开、可访问的岗位数据来源。
- 优先官方招聘站 > 公开 ATS/平台页 > 转载站或镜像站。
- 尊重 robots、站点条款、登录边界、速率限制。
- 不绕过验证码、登录封禁、风控。
- 新建提取逻辑前，先复用已有 crawler 与 config。

## Preferred Extraction Order
1. 公开 job flow 中直接暴露的 JSON 或 API
2. 页面内嵌 hydration payload、JSON-LD、初始化状态
3. 稳定 HTML 解析
4. 仅在前面不足时再使用 Playwright

## ATS / Framework Detector-First Rule
- 优先识别站点底层 ATS 或前端框架，再路由到对应 adapter。
- 识别线索包括 URL pattern、script src、DOM 特征、network host、页面文案。
- 优先识别家族：Greenhouse、Lever、Workday、SmartRecruiters、Taleo、iCIMS、Moka、北森、自建 SPA。
- 一旦识别出家族，修复应面向家族沉淀，不只修单站点。

## Layered Crawl Escalation
- Layer 0：静态探测职位关键词、ATS 特征、job link pattern、初始化 JSON。
- Layer 1：接口探测 XHR/fetch/GraphQL、JSON 响应、分页参数。
- Layer 2：轻量浏览器交互，等待 hydrate、滚动、点 load more、切 tab。
- Layer 3：重型页面抓取，逐项点详情、多轮滚动、复杂 DOM 抽取。
- Layer 4：保底链路，收集 detail 链接逐页解析，或标记“疑似有岗但列表解析失败”。

## Zero-Result Validation
- 每次抓取必须判断 0 岗位是真 0 还是可疑 0。
- `confirmed zero`：无信号、无链接、无指纹，确认无岗位。
- `suspect zero`：有信号矛盾但抽取为 0，必须进入重试或排查队列。
- 以下情况必须标红：页面自报有岗位但抽取为 0；发现 detail 链接但列表为 0；历史平均有岗位突然为 0；detail URL 远多于列表结果。

## Failure Tags And Evidence
- 标准失败标签：`NO_JOB_SIGNAL`、`JOB_SIGNAL_BUT_ZERO_EXTRACTED`、`HYDRATION_TIMEOUT`、`NEEDS_INTERACTION`、`DETAIL_LINKS_FOUND_LIST_FAILED`、`API_FOUND_AUTH_REQUIRED`、`BLOCKED_OR_EMPTY_RESPONSE`、`ATS_DETECTED_BUT_ADAPTER_MISSING`、`PAGE_CLAIMS_OPENINGS_BUT_ZERO`、`IFRAME_CONTENT_NOT_PARSED`、`SHADOW_DOM_NOT_PARSED`。
- 每次抓取至少保留：final URL、页面标题、前 10 个 XHR URL、ATS 指纹、job/detail 链接、关键文本片段、DOM 计数前后、HTML 片段、截图、失败标签。

## Existing Crawler Families
- 通用 Playwright：`backend/app/services/crawler.py`
- Moka：`backend/app/services/moka_crawler.py`
- Haitou：`backend/app/services/haitou_crawler.py`
- 券商聚合：`backend/app/services/securities_crawler.py`
- 银行专用：`backend/app/services/bank_crawler/`
- 能源：`backend/app/services/energy_crawler.py`
- 历史参考：`backend/app/services/legacy_crawlers/`

## Config-First Behavior
- 优先扩展配置，不硬编码站点规则。
- 重点配置：`backend/config/targets_v3.yaml`、`backend/config/securities_campus.yaml`、`backend/config/mbb_big4_config.yaml`、`backend/config/tiered_internet_companies.yaml`。
- 只有确认无法复用现有 crawler family 和配置时，才新建 crawler 文件。

## Documentation Update Rules
- 站点、ATS、平台规则更新到 `docs/site_playbooks/`。
- 高层工作流或通用说明更新到 `docs/`。
- 工具、路径、命令约定更新到 `docs/tools-and-paths.md`。
- 长期决策更新到 `docs/decisions.md`。
- 如果开发流程变化，例如新增前端测试或新的验证命令，同步更新本文件。

## Extended Reference Docs
- 系统结构与模块地图：`docs/architecture.md`
- 部署、数据库和数据边界：`docs/deployment-and-data.md`
- 做 feature 开发或跨模块改动时，优先看 `docs/architecture.md`。
- 做部署、数据库、导入导出、运行时状态相关工作时，优先看 `docs/deployment-and-data.md`。

## Verification Before Completion
- 没有运行相关验证命令，就不要声称“已完成”或“已通过”。
- Backend 改动至少运行相关 pytest；优先跑受影响文件或具体用例。
- Frontend 改动至少运行 `cd frontend && npm run lint` 与 `cd frontend && npm run build`。
- 文档改动至少自查路径、命令、文件名、目录结构是否真实存在。
- 不要虚构测试结果，不要根据“应该可以”来做完成声明。

## Git And Change Discipline
- 不要在 `main` 直接开发。
- 分支命名优先使用：`feat/...`、`fix/...`、`refactor/...`、`docs/...`、`chore/...`。
- Commit message 优先使用 `type(scope): summary`。
- 一个 PR 尽量只做一件事，描述里写清测试方式。
- 保持小步修改，优先最小正确变更，不做与任务无关的大重构。
- 如果发现工作区有其他人留下的改动，不要擅自回滚；仅处理当前任务相关部分。
