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
