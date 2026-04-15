# JobRadar OpenCode Start

## Read Order
1. `AGENTS.md` — repo 级主规则、命令、代码风格、crawler 规范
2. `docs/tools-and-paths.md` — 常用路径、脚本、运行命令
3. `docs/decisions.md` — 长期决策与历史约束

## Default Mode
- 默认在当前 WSL2 工作目录直接开发。
- 新 feature、bugfix、前后端联调、测试，优先走本地工作区，不默认使用 shadow runtime。
- 详细规则以 `AGENTS.md` 为准，不要再从旧 memory 或迁移文档推断行为。

## Key Paths
- Backend app: `backend/app/`
- Backend tests: `backend/tests/`
- Frontend app: `frontend/src/`
- Crawler config: `backend/config/`
- Site playbooks: `docs/site_playbooks/`

## Optional Shadow Runtime
- 只有当你需要隔离另一套已运行中的前后端、数据库快照或登录态时，才使用 shadow runtime。
- 后端影子端口：`8010`
- 前端影子端口：`5174`
- 刷新影子副本：`~/bin/jobrador-shadow-refresh`

## WSL2 Network Notes
- 如果在 WSL2 里直接运行 `opencode` 时卡住不返回，优先怀疑 OpenAI 访问需要走 Windows 本机代理。
- 推荐启动方式：`./scripts/opencode-wsl.sh`
- 该脚本会自动读取 WSL 默认网关，并尝试连接 `7890` 端口的 Windows 代理；成功后会导出 `HTTP_PROXY` 和 `HTTPS_PROXY`。
- 需要切回智谱模型时，编辑 `~/.config/opencode/opencode.json` 中的 `model` 和 `small_model`。
