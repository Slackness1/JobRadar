# 🎯 JobRadar

🤖 面向「目标公司 + 目标赛道」的岗位情报与投递决策系统，聚焦岗位发现、公司重爬、岗位评分、外部情报整合与每日报告输出。

[功能特性](#-功能特性) · [核心流程](#-核心流程) · [截图占位](#-截图--demo) · [快速开始](#-快速开始) · [架构设计](#-架构设计) · [路线图](#-路线图)

简体中文 | [English](./README_EN.md)

---

## ✨ 功能特性

- **多源岗位发现**：从多个来源收集岗位与公司线索
- **字段清洗与去重**：统一字段格式，降低重复与脏数据干扰
- **公司级重爬队列**：围绕重点公司做定向更新，而不是盲目全量抓取
- **官网/校招入口补录**：补全真实投递入口，提升投递有效性
- **岗位加权评分**：结合关键词、赛道匹配、地点、时效等维度排序
- **外部情报整合**：融合面经、讨论、舆情等信号，辅助投递决策
- **每日报告输出**：形成「新增岗位 + 变化要点 + 建议动作」日报

---

## ❓ Why this exists

传统聚合平台擅长“展示岗位”，但不擅长“支持决策”。

JobRadar 的出发点是：
- 目标赛道用户通常关注的是少量重点公司，而不是全网噪声
- 平台内投递入口不一定是最优路径，很多场景需回到官网/校招官网
- 真正影响投递决策的，除了 JD，还包括时效、质量、成功率与外部信号

所以 JobRadar 不追求“抓得最多”，而追求“投得更准”。

---

## 🚀 What makes JobRadar different

1. **公司级重爬**：按公司粒度持续跟踪，聚焦重点目标
2. **岗位评分**：多维加权优先级，先投更值得投的岗位
3. **外部情报**：把非结构化讨论转为可行动信号
4. **每日报告**：每天给出明确的下一步动作建议

---

## 🔄 核心流程

```text
发现公司/岗位线索
  → 字段清洗与去重
  → 官网/校招入口补录
  → 岗位评分与优先级排序
  → 外部情报整合
  → 每日投递日报
```

闭环：`discover -> clean -> target -> score -> enrich -> decide -> apply`

---

## 🖼 截图 / Demo

### 1) 岗位列表（Dashboard）
```text
[截图占位符]
建议路径：docs/screenshots/dashboard.png
```

### 2) 岗位详情 / 情报页（Job Intel）
```text
[截图占位符]
建议路径：docs/screenshots/job_intel.png
```

### 3) 公司重爬（Company Expand / Recrawl）
```text
[截图占位符]
建议路径：docs/screenshots/company_expand.png
```

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

### Demo（占位）
```text
[Demo GIF Placeholder]
建议路径：docs/demo.gif
```

---

## 📊 Feature Matrix

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

## ⚡ 快速开始

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

## 🧱 架构设计

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

## 🗺 路线图

- [ ] 完善官网/校招入口自动发现能力
- [ ] 增强公司归并与岗位去重准确率
- [ ] 扩展评分特征（技能画像、时效权重、历史反馈）
- [ ] 补齐岗位评分 / 日报页面截图与说明
- [ ] 强化外部情报聚合（更多平台、结构化摘要）
- [ ] 支持更细粒度的投递状态与跟进提醒
- [ ] 增加调度可观测性（失败告警、任务看板）

---

## 🧰 技术栈

- Frontend: React + TypeScript + Ant Design + Vite
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
- Crawling: Python + Playwright / requests
- Deployment: Docker Compose

---

## 📄 License

待补充（建议使用 MIT）。
