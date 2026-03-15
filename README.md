# JobRadar

<p align="center">
  <a href="#english">English</a> | <a href="#中文">中文</a>
</p>

---

## English

> JobRadar is a focused job-intelligence workflow for targeted career tracks.

JobRadar is not just a generic job scraper. It is designed for people who:
- focus on specific career tracks,
- care about a shortlist of target companies,
- and need better application decisions, not just more listings.

### Demo

![JobRadar Demo](./docs/demo.gif)

### Screenshots & walkthrough

<p align="center">
  <img src="./docs/screenshots/dashboard.png" alt="Job dashboard" width="31%" />
  <img src="./docs/screenshots/job_intel.png" alt="Job intel" width="31%" />
  <img src="./docs/screenshots/company_expand.png" alt="Company expand" width="31%" />
</p>

- **Dashboard**: browse discovered jobs, filter by conditions, and decide where to focus first.
- **Job Intel**: enrich a job with extra signals (discussion/interview-related context) to improve decision quality.
- **Company Expand**: mark target companies and prepare follow-up recrawls for continuous tracking.

### What it does
- Multi-source job discovery
- Data cleaning and deduplication
- Company-level recrawl queue
- Weighted job scoring
- Job intelligence integration (interview notes / discussion signals)
- Daily application briefing

### Typical workflow
`discover -> clean -> target -> score -> enrich -> decide -> apply`

### Tech stack
- Frontend: React + TypeScript + Ant Design + Vite
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
- Crawling: Python + Playwright / requests
- Deployment: Docker Compose

### Quick start
```bash
docker compose up --build -d
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8001
- API Docs: http://localhost:8001/docs

### Project structure
```text
JobRadar/
├── frontend/
├── backend/
│   ├── app/
│   ├── data/
│   └── reports/
├── docs/
├── docker-compose.yml
└── config.yaml
```

---

## 中文

> JobRadar 是一个面向目标赛道求职的岗位情报与投递决策系统。

JobRadar 不只是“抓岗位”，而是帮助你完成从发现到投递决策的完整闭环。

它主要面向这类场景：
- 目标赛道明确（如数据分析、风控、AI 产品等）
- 长期关注少数重点公司
- 需要基于信息质量做投递优先级判断

### 演示

![JobRadar 演示](./docs/demo.gif)

### 截图与功能讲解

<p align="center">
  <img src="./docs/screenshots/dashboard.png" alt="岗位总览" width="31%" />
  <img src="./docs/screenshots/job_intel.png" alt="岗位情报" width="31%" />
  <img src="./docs/screenshots/company_expand.png" alt="公司展开" width="31%" />
</p>

- **岗位总览（Dashboard）**：查看岗位池，按条件筛选并快速定位优先投递项。
- **岗位情报（Job Intel）**：为岗位补充面经/讨论等外部信号，提升决策质量。
- **公司展开（Company Expand）**：标记重点公司并加入后续重爬队列，持续跟踪新岗位。

### 核心能力
- 多源岗位发现
- 字段清洗与去重
- 公司级重爬队列
- 岗位加权评分
- 岗位外部情报整合
- 每日投递简报

### 典型流程
`发现岗位 -> 清洗去重 -> 锁定公司 -> 评分排序 -> 情报补强 -> 决策投递`

### 技术栈
- 前端：React + TypeScript + Ant Design + Vite
- 后端：FastAPI + SQLAlchemy
- 数据库：SQLite
- 爬虫：Python + Playwright / requests
- 部署：Docker Compose

### 快速启动
```bash
docker compose up --build -d
```

- 前端：http://localhost:5173
- 后端：http://localhost:8001
- API 文档：http://localhost:8001/docs

### 目录结构
```text
JobRadar/
├── frontend/
├── backend/
│   ├── app/
│   ├── data/
│   └── reports/
├── docs/
├── docker-compose.yml
└── config.yaml
```
