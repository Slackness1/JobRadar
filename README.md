# JobRadar - 多源岗位抓取与管理

一个可配置“站点节点（source node）”的岗位抓取与管理项目，支持本地 Docker 启动、岗位筛选、前端总览与后端 API 调用。

## 1. 项目目标

- 抓取多个目标站点的岗位数据
- 统一存储与筛选岗位
- 在前端页面集中查看与维护投递状态
- 支持后续按你自己的站点节点持续扩展

## 2. 快速启动（Docker）

```bash
docker compose up --build -d
```

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8001`
- API 文档：`http://localhost:8001/docs`

停止服务：

```bash
docker compose down
```

## 3. 站点节点配置思路

请把抓取目标抽象成“站点节点”，每个节点定义如下信息：

1. 入口地址（Base URL / Entry URL）
2. 鉴权方式（无鉴权 / Token / Cookie）
3. 分页策略（页码参数、下一页链接、滚动加载）
4. 字段映射（岗位标题、公司、地点、发布日期、详情链接）
5. 岗位标签（例如 campus / internship / custom）

示例（概念性，不限定具体实现字段名）：

```yaml
nodes:
  - key: source_a
    base_url: https://jobs.example-a.com
    auth_mode: token
    entry_path: /campus
    max_pages: 20
    enabled: true

  - key: source_b
    base_url: https://careers.example-b.com
    auth_mode: none
    entry_path: /positions
    max_pages: 30
    enabled: true
```

## 4. 本地脚本说明

- `auto_login_scraper.py`：自动登录抓取脚本（适用于需要登录态的节点）
- 导出抓取脚本：通用参数化抓取并导出 CSV
- `filter_jobs.py` / `filter_jobs_v2.py`：岗位筛选器
- `format_csv.py`：CSV 字段整理

说明：脚本文件名属于历史兼容命名，不影响你将目标站点替换成自己的节点。

## 5. 常见使用流程

1. 启动 Docker 服务
2. 配置你的站点节点参数
3. 触发抓取（前端或脚本）
4. 在岗位总览中筛选与标注申请状态
5. 导出结果做后续跟踪

## 6. GitHub 个人开发者范式（默认标准）

### 6.1 分支命名规范

- `main`（永远保持可运行、可发布）
- `feat/<name>`
- `fix/<name>`
- `refactor/<name>`
- `docs/<name>`
- `chore/<name>`

示例：

- `feat/github-login`
- `fix/payment-timeout`
- `refactor/api-client`
- `docs/readme-install`
- `chore/upgrade-eslint`

使用 Issue 编号时，推荐：

- `feat/12-github-login`
- `fix/27-timeout-retry`

### 6.2 Commit 规范

格式：

`type(scope): summary`

常用类型：

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`
- `build`
- `ci`
- `style`

示例：

- `feat(auth): add GitHub OAuth login`
- `fix(api): retry on 504 timeout`
- `docs(readme): add local setup guide`
- `refactor(user): split service and controller`
- `test(auth): add login callback tests`
- `chore(deps): upgrade vite to latest version`

### 6.3 PR 规范

- PR 标题建议沿用 commit 风格
- 一个 PR 只做一件事
- PR 尽量小
- 做到一半可先开 Draft PR
- PR 描述必须写清楚测试方式
- 合并默认使用 Squash merge

### 6.4 Issue 使用规则

Issue 仅保留三类：

1. Bug
2. Feature
3. Task

原则：

- 每个可追踪工作尽量有一个 Issue
- 一个 branch 对应一个 issue
- PR 描述里写 `Closes #xx`

### 6.5 Changelog 维护规则

仅在合并到 `main` 且值得记录的改动后更新。

记录四类内容：

1. Added
2. Changed
3. Fixed
4. Removed

## 7. 输出字段（示例）

| 字段 | 说明 |
|------|------|
| job_id | 岗位 ID |
| company | 公司 |
| department | 部门/主体 |
| job_title | 岗位名称 |
| location | 地点 |
| publish_date | 发布时间 |
| deadline | 截止时间 |
| detail_url | 详情链接 |
| job_stage | 岗位阶段标签 |
| scraped_at | 抓取时间 |

## 8. 维护建议

- 新增站点时，优先复用已有抓取/映射流程
- 先做小步提交，再做 PR 汇总
- 不要在 `main` 直接开发
