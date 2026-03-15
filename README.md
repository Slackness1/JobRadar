# JobRadar

> **From job aggregation to job intelligence**
>
> 一个围绕「目标公司 + 目标赛道」的求职决策系统，而不是通用岗位搬运器。

**English Version:** [README_EN.md](./README_EN.md)

---

## Hero 区

**项目定位（一句话）**  
JobRadar 把碎片化岗位信息转成可执行的投递策略：先发现、再筛选、再评分、再结合外部情报做决策。

**Tagline**  
From job aggregation to job intelligence.

**Demo（占位）**

```text
[Demo GIF Placeholder]
路径建议：docs/demo.gif
```

---

## Why this exists

传统聚合平台能帮你“看到岗位”，但很难帮你“做决策”。

主要问题：
- 只给线索，不给完整决策链路（岗位质量、时效、成功率、外部信号）
- 平台内投递入口不一定是最优入口（很多情况要回到官网/校招官网）
- 盲抓全网岗位噪声高，目标赛道用户真正关心的是**重点公司的持续跟踪**

所以 JobRadar 的核心思路不是“抓更多”，而是：
- 围绕重点公司做持续监控
- 对岗位做优先级评分
- 将面经/讨论/舆情等外部情报纳入判断
- 输出每天可执行的投递建议

---

## What makes JobRadar different

1. **公司级重爬（Company-level Recrawl）**  
   不是无差别重跑全站，而是把重点公司加入重爬队列，做定向更新。

2. **岗位评分（Job Scoring）**  
   基于关键词、赛道匹配、地点、时效等维度做加权排序，先投“更值得投”的岗位。

3. **外部情报整合（Intelligence Enrichment）**  
   把面经、讨论、薪酬/强度等非结构化信息转成可参考信号。

4. **每日报告（Daily Briefing）**  
   输出「新增岗位 + 重点变化 + 推荐动作」的日报，减少重复筛选成本。

---

## Core workflow

```text
发现公司/岗位线索
   → 字段清洗与去重
   → 官网/校招入口补录
   → 岗位评分与优先级排序
   → 外部情报整合
   → 每日投递日报
```

对应闭环：

`discover -> clean -> target -> score -> enrich -> decide -> apply`

---

## Screenshots / Demo

### 1) 岗位列表（Dashboard）
```text
[截图占位符]
建议路径：docs/screenshots/dashboard.png
```

用于查看岗位池、快速筛选和定位优先处理岗位。

### 2) 岗位详情 / 情报页（Job Intel）
```text
[截图占位符]
建议路径：docs/screenshots/job_intel.png
```

用于补充岗位外部信号，辅助“是否投、何时投”的决策。

### 3) 公司重爬（Company Expand / Recrawl）
```text
[截图占位符]
建议路径：docs/screenshots/company_expand.png
```

用于标记重点公司并纳入后续重爬队列。

### 4) 岗位评分（Scoring）
```text
[截图占位符]
建议路径：docs/screenshots/scoring_detail.png
```

### 5) 每日报告（Daily Briefing）
```text
[截图占位符]
建议路径：docs/screenshots/daily_briefing.png
```

---

## Feature matrix

| 能力模块 | 说明 | 当前状态 |
|---|---|---|
| 多源岗位发现 | 从聚合来源获取岗位线索 | ✅ 已支持 |
| 字段清洗与去重 | 标准化字段，减少重复和脏数据 | ✅ 已支持 |
| 公司级重爬队列 | 重点公司定向更新 | ✅ 已支持 |
| 官网/校招入口补录 | 补全真实投递入口 | ✅ 已支持 |
| 岗位评分引擎 | 多维度加权优先级 | ✅ 已支持 |
| 外部情报整合 | 面经/讨论/舆情信号补强 | 🟡 进行中 |
| 每日报告生成 | 输出可执行投递摘要 | 🟡 进行中 |
| 自动化调度与告警 | 定时 + 异常通知 | 🔜 规划中 |

---

## Quick Start

### 方式 1：Docker（推荐）
```bash
docker compose up --build -d
```

启动后访问：
- Frontend: http://localhost:5173
- Backend: http://localhost:8001
- API Docs: http://localhost:8001/docs

### 方式 2：本地前后端开发

后端（FastAPI）：
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

前端（Vite）：
```bash
cd frontend
npm install
npm run dev
```

---

## Architecture

```text
Frontend (React + TS)
        |
Backend API (FastAPI)
        |
Database (SQLite)
        |
Crawler Layer (multi-source)
        |
Enrichment Layer (intel / scoring)
        |
Reporting Layer (daily briefing)
```

模块说明：
- **Frontend**：岗位工作台、筛选、详情、操作入口
- **Backend**：数据管理、任务编排、API 输出
- **DB**：岗位、公司、评分、日志等核心实体
- **Crawler**：多来源抓取与公司定向重爬
- **Enrichment**：评分与外部情报融合
- **Reporting**：日报与摘要输出

---

## Roadmap

- [ ] 完善官网/校招入口自动发现能力
- [ ] 增强公司归并与岗位去重准确率
- [ ] 扩展评分特征（技能画像、时效权重、历史反馈）
- [ ] 补齐岗位评分 / 日报页面截图与说明
- [ ] 强化外部情报聚合（更多平台、结构化摘要）
- [ ] 支持更细粒度的投递状态与跟进提醒
- [ ] 增加调度可观测性（失败告警、任务看板）

---

## Tech Stack

- Frontend: React + TypeScript + Ant Design + Vite
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
- Crawling: Python + Playwright / requests
- Deployment: Docker Compose

---

## License

待补充（建议使用 MIT）。
