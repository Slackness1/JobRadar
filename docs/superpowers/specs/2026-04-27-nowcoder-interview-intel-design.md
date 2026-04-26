# Nowcoder Interview Intel — Design

**Status**: approved 2026-04-27
**Owner**: Mock Interview module

## Goal

让 `/interview/{sessionId}` 的 AI 面试官在出题时能引用「这家岗位最近真实问过什么题」，而不是凭空生成。覆盖范围限定为 `/interview` 入口页的 17 个固定 chip 岗位（见 §1.1）；自由 textarea 输入沿用现状（无外部上下文）。

## Non-goals

- 不覆盖自由 textarea 输入的长尾岗位
- 不引入 Playwright 或浏览器自动化
- 不改 `JobIntelSnapshot` 表（它的 PK 是 `job_id`，与本特性的 chip 字符串维度正交）
- 不改 `/interview` 入口页 UI、`/interview/{sessionId}` 页 UI、设备检查页 UI
- 不引入新的告警通道（沿用现有 `/api/scheduler` 观测）

## Background

- POC 脚本 `/tmp/nc_scrape.py` 已验证：牛客 `/search/all?query=...` 返回 SSR HTML 含 `/discuss/{pid}` 链接；详情页 `/discuss/{pid}` 的 `<meta name="description">` 直接含结构化字段（公司/时间/岗位/问题），最新格式（带 emoji 模板）一行 regex 即可解析
- 当前面试 system prompt 仅含 `target_job` + 6 条规则，无外部上下文，注入扩展点干净
- 后端运行环境：FastAPI + SQLite (WAL, busy_timeout=5000) + APScheduler，VPS 上 systemd 长跑
- 现有 LLM client：`build_resume_llm_client()`，模型已切到 `deepseek-v4-flash`

## Architecture

```
APScheduler (09:00 Asia/Shanghai, 在 daily_crawl 08:00 之后)
   │
   ↓ nowcoder_intel_refresh job
   │
   ├─→ scraper.py          (search + fetch_post, urllib only)
   │
   ├─→ summarizer.py       (LLM: posts → markdown summary)
   │
   ├─→ SQLite (2 new tables: interview_intel_keywords, interview_intel_posts)
   │
   └─→ /api/scheduler 暴露 last_run / last_status / counts / last_error

POST /api/interview/turn
   │
   ↓ build_interview_system_prompt(target_job)
   │
   └─→ intel_provider.get_intel_for_target_job(db, target_job)
       ├─ 命中且 summary 非空 → 拼接到 system prompt 末尾
       └─ 任何失败 → 返回 None → 退回纯 LLM prompt（行为同现状）
```

**模块边界**：
- `scraper`、`summarizer`、`intel_provider` 三个组件互不依赖
- scraper 不依赖 LLM；summarizer 不依赖网络
- 整个特性对面试模块的注入点只有一个函数：`build_interview_system_prompt()`
- 任何失败链路都退回到现有行为，不会让用户感知到"变差"

### 1.1 Chip 关键词集合

来源：`resume-copilot-web/app/interview/page.tsx` 的 `PRESETS`，共 3 组 17 个：

- 互联网：`产品经理 / 数据分析师 / 前端开发 / 后端开发 / 算法工程师 / 运营`
- 金融：`券商研究员 / 投行分析师 / 量化研究员 / 风控分析师 / 商业银行管培生`
- 咨询/快消/央企：`MBB 战略咨询 / 宝洁市场营销 / 联合利华管培生 / 中金财富管理 / 中国银行总行`

## Components

新建路径 `backend/app/services/interview/nowcoder/`：

| 文件 | 职责 | 关键接口 |
|---|---|---|
| `nowcoder_keywords.yaml` | chip → 牛客搜索词映射；可手动调整 | （配置） |
| `scraper.py` | 搜索 + 单帖详情解析；纯 stdlib (`urllib`) | `search(query, limit) -> list[PostMeta]`<br>`fetch_post(pid) -> PostDetail` |
| `summarizer.py` | N 条 post → ≤400 字 markdown 摘要 | `summarize_keyword(keyword, posts) -> str` |
| `refresh_job.py` | nightly orchestrator，串起 scrape + summarize + DB upsert | `run_refresh(db) -> RefreshStats` |
| `intel_provider.py` | 面试启动时只读 DB；substring 匹配 | `get_intel_for_target_job(db, target_job) -> str \| None` |

**改动到现有文件**：
- `backend/app/models.py`：追加两个模型类（不改现有）
- `backend/app/services/interview/llm.py`：在 `build_interview_system_prompt(target_job)` 内加一次 `intel_provider` 调用并拼接
- `backend/app/main.py`：lifespan 内注册 `nowcoder_intel_refresh` 到现有 APScheduler
- `backend/app/routers/scheduler.py`：在状态响应里加新 job metadata
- `backend/data/jobradar.db` 通过 `ensure_compatible_schema()` 自动建新表

### 关键词映射 (yaml 形状)

```yaml
- chip: "产品经理"
  query: "产品经理面经"
- chip: "数据分析师"
  query: "数据分析面经"
- chip: "MBB 战略咨询"
  query: "战略咨询面经"
# ... 17 行
```

实现时为每个 chip 给出一个具体 query 字符串（不让代码自动加"面经"后缀，避免对"商业银行管培生"这种已经很长的词产生噪音）。

## Data Model

```python
class InterviewIntelKeyword(Base):
    __tablename__ = "interview_intel_keywords"
    keyword = Column(String, primary_key=True)   # 等于 chip 文本，例 "产品经理"
    summary_md = Column(Text, nullable=True)     # NULL = 当前周期摘要失败
    source_count = Column(Integer, default=0)
    generated_at = Column(DateTime, nullable=True)

class InterviewIntelPost(Base):
    __tablename__ = "interview_intel_posts"
    pid = Column(String, primary_key=True)       # 牛客 post id
    keyword = Column(String, primary_key=True)   # 复合 PK；同一 pid 可出现在多个 keyword 下
    title = Column(String)
    company = Column(String, nullable=True)
    interview_date = Column(String, nullable=True)  # 牛客原文是字符串如 "26-4-14"，不强转日期
    position = Column(String, nullable=True)
    questions_text = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    parse_status = Column(String)                # "ok" | "partial" | "failed"
```

**为什么不复用 `JobIntelSnapshot`**：它的语义键是 `job_id`（FK 到 Job 表里的具体职位行），而本特性的语义键是 chip 字符串。硬塞会要求为每个 chip 造一个伪 Job 行，污染情报表语义。

**复合 PK 而非全局唯一 pid**：同一帖子可能在多个 keyword 搜索结果里出现，让每个 keyword 各存一份冗余更简单。总量 ~170 行，冗余可忽略。

## Data Flow

### Nightly refresh (cron 09:00 Asia/Shanghai)

```
run_refresh(db)
   │
   ├─ 加载 nowcoder_keywords.yaml → list[(chip, query)]
   │
   ↓ for each (chip, query):
   │
   ├─ scraper.search(query, limit=10)
   │   失败 → 记 keyword-level error, continue 下个 chip
   │
   ├─ for each PostMeta:
   │   ├─ DB 查 (pid, chip)：fetched_at 在 24h 内 → skip
   │   ├─ scraper.fetch_post(pid)
   │   │   单帖失败 → upsert with parse_status="failed", continue
   │   ├─ time.sleep(uniform(0.4, 1.0))    # 礼貌
   │   └─ upsert InterviewIntelPost
   │
   ├─ 收集本 keyword 下所有 parse_status="ok" 的 posts (含本次和 24h 内的旧帖)
   │   summarizer.summarize_keyword(chip, posts)
   │   返回 markdown 段落 ≤ 400 字
   │   失败 → summary_md=NULL（posts 已落表，下次 refresh 只补摘要不重爬）
   │
   └─ upsert InterviewIntelKeyword(keyword, summary_md, source_count, generated_at)
```

总耗时估算：17 chip × (1 search + 10 detail × 0.7s + 1 LLM call ~3s) ≈ **3 分钟**。

### Interview start injection (per-turn)

```
build_interview_system_prompt(target_job, db_session=None)
   │
   ├─ if db_session is None: 只用 base_prompt（兼容测试 / 无 DB 调用）
   │
   ├─ intel = intel_provider.get_intel_for_target_job(db, target_job)
   │
   │  匹配规则（按优先级）:
   │  1. 精确匹配：target_job == keyword
   │  2. substring：keyword in target_job
   │     例: "产品经理" ⊂ "字节跳动产品经理实习" → 命中
   │  3. 都不命中 → None
   │
   ├─ if intel and intel.summary_md:
   │     prompt = base_prompt
   │            + "\n\n## 最近公开面经的高频考察方向\n"
   │            + intel.summary_md
   │            + f"\n\n（以上方向参考了 {intel.source_count} 条来自牛客网的公开面经，作为出题灵感，不要直接复述）"
   │
   └─ else: prompt = base_prompt   # 退回当前行为
```

## Error Handling

| 失败点 | 处理 | 用户感知 |
|---|---|---|
| 单帖 detail 解析失败 | `parse_status="failed"` 落表，continue | 无 |
| 单 keyword 0 搜索结果 | `posts=[], summary_md=NULL, source_count=0` | 该 chip 退回纯 LLM prompt |
| 牛客 5xx / timeout | 重试 1 次（间隔 5s），仍失败则跳本 keyword | 无 |
| 牛客 429 | 立即终止整个 refresh job，`last_error="rate_limited"`，下次 cron 自然重试 | 已有 cache 继续用，新数据等 24h |
| LLM summarize 失败 | `summary_md=NULL`，posts 仍落表 | chip 退回纯 LLM prompt |
| Scheduler job 进程崩溃 | APScheduler 自带恢复；状态在 `/api/scheduler` 可见 | 你 curl 时能看到 |
| `intel_provider` 查询时 DB 出错 | 静默 try/except → 返回 None | 退回纯 LLM prompt |

**核心原则**：任何失败链路都让面试启动至少不变差。从不阻塞用户。

## Observability

`GET /api/scheduler` 响应里新增 key：

```json
{
  "daily_crawl": { "...": "..." },
  "nowcoder_intel_refresh": {
    "last_run": "2026-04-27T09:03:14+08:00",
    "last_status": "ok",
    "keywords_total": 17,
    "keywords_ok": 16,
    "keywords_failed": 1,
    "posts_fetched": 142,
    "last_error": null
  }
}
```

`last_status` ∈ {"ok", "partial", "failed", "rate_limited"}。

## Politeness / Legal

- UA：桌面 Chrome 字符串
- `Accept-Language: zh-CN,zh;q=0.9`
- 请求间隔：每个 detail 后 sleep `uniform(0.4, 1.0)`s
- 不并发：单线程串行
- 429 立即停 24h
- system prompt 内告知 LLM "灵感参考了 N 条公开面经"，让 LLM 在被问到时能自然带出来源

不在面试报告页加显式来源 banner（用户决定）。

## Testing

| 模块 | 测试方式 | 打真实牛客 |
|---|---|---|
| `scraper.py` | mock `urlopen`，喂 POC 已验证的 HTML 样本，验 regex 解析 | 否 |
| `scraper.py` 集成 | 1 个 `@pytest.mark.integration` 真打牛客（CI skip） | 是（手动） |
| `summarizer.py` | mock LLM client，验 prompt 结构 + 返回处理 | 否 |
| `refresh_job.py` | mock scraper + summarizer，验 DB upsert / 24h 去重 / keyword-level 失败 continue | 否 |
| `intel_provider.py` | seed 一行 keyword 到 DB，验精确匹配 / substring 匹配 / 空 summary 降级 | 否 |
| `build_interview_system_prompt` 注入 | mock `intel_provider`，验命中 / 未命中两条路径 | 否 |

不测：APScheduler cron 触发本身（daily_crawl 已在跑，模式可信）；牛客 SSR HTML 长期稳定性（依赖手动集成测发现回归）。

## Open Questions

无。所有关键决策在 brainstorming 阶段已敲定。

## Out of Scope (Future Work)

- 自由文本 textarea 路径的面经覆盖（option B from Q2）
- 面经摘要按公司维度切片（"字节考察 X，腾讯考察 Y"）
- 面试报告页底部加显式来源 banner（option C from Q6）
- 牛客 `gw-c.nowcoder.com` JSON 网关接入（覆盖老格式帖子）
- 多平台扩展（看准网 / 应届生 BBS）
