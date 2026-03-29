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
- 模型：`backend/app/models/`（或 `backend/app/models.py`）
- DB 连接：`backend/app/database.py`
- SQLite：`backend/data/jobradar.db`
- 后端 schema 已存在时不另起存储结构

## Reusable Scripts
- `scripts/run_bank_crawl.py` — 银行爬取
- `scripts/merge_jobs.py` — 合并岗位数据
- `scripts/jobradar_paths.py` — 路径管理
- 重复流程优先补成脚本入口

## Environment Commands
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

## Shadow Runtime
- 后端影子端口：8010（`~/bin/jobrador-shadow-backend`）
- 前端影子端口：5174（`~/bin/jobrador-shadow-frontend`，代理到 8010）
- 数据库和登录态是快照，不会回写 live
