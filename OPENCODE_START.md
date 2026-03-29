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
- Config reference: `docs/config-reference/`

## Crawling Rules
- Always Discovery first, then Extraction
- Prefer API / embedded payload → HTML → Playwright
- Validate zero results (confirmed zero vs suspect zero)
- Collect lightweight evidence on every crawl
- See `AGENTS.md` for full rules

## Shadow Runtime
- 后端影子端口：8010（`~/bin/jobrador-shadow-backend`）
- 前端影子端口：5174（`~/bin/jobrador-shadow-frontend`，代理到 8010）
- 数据库和登录态是快照，不会回写 live
- 刷新影子副本：`~/bin/jobrador-shadow-refresh`
