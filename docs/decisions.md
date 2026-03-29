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

## Data Scale History
| 时间点 | 岗位量 | 关键增量 |
|--------|--------|---------|
| 03-11 早期 | ~4,785 | 腾讯/美团/字节 |
| 03-12 合并后 | ~16,685 | 75倍增长 |
| 03-17 银行专项 | ~22,560 | 6家银行 |
| 03-22 券商专项 | +500 | 16家券商 |
| 03-23 能源专项 | +746 | 50家能源公司 |
