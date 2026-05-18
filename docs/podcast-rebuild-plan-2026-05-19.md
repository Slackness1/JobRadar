# Podcast 知识库重建计划 — 2026-05-19

**背景**:之前的 988 条 podcast insights 已删,所有中间产物(transcripts / episode_summaries / submissions.jsonl)都丢失。只剩设计文档 + 4 个 pass 脚本 + 热词系统(term_dict.json)。本次重建按苹果播客来源走,目标恢复 ~800-1500 条 finance-recruiting 相关 insights 进 RAG 库。

---

## 目标

填上"模拟面试 5 层 context stack"的第 5 层(podcast insights),让 SUT 在评分 / 出题 / 给反馈时能引用 **行业洞察 + 岗位真实情况** —— 不再是空泛的"DeepSeek 套壳"。

数据基线(SAIF 试点验收):
- ✅ ≥ 800 条 typed insights 入库(role_insight / resume_tip / interview_qa / company_anecdote / industry_trend 5 类)
- ✅ 80% 以上 insight 命中 finance role / company / sector(用 term_dict 词典反查)
- ✅ Provider 接入后实测:对面试反馈引用率提升(by Sonnet meta-judge)

---

## 数据源(已确认)

| Apple Podcast | ID | 范围 | 主筛 |
|---|---|---|---|
| 大力如山 | 1648308335 | 全集 | **手动过滤掉明显不相关**(育儿/八卦/非金融),保留金融/职业相关 |
| 就业研究所 | 1748496863 | 全集 | 几乎全相关,默认全收 |

---

## 阶段拆分(6 阶段)

### Stage 0 · 改造 transcribe 脚本支持 Apple Podcast(~1.5h)

现状:`scripts/transcribe_xiaoyu.py` 只吃小宇宙(regex 锁定 `media.xyzcdn.net` + 24 位 hex episode id),要替换 URL 解析逻辑:

- 输入:`https://podcasts.apple.com/cn/podcast/{slug}/id{podcast_id}` 或 episode URL
- 提取 podcast_id → 调 `https://itunes.apple.com/lookup?id={id}&entity=podcast` 拿 `feedUrl`(RSS XML 链接)
- 解析 RSS,遍历 `<item>`,每个 item 抓 `<title>` / `<enclosure url="...">` / `<itunes:duration>`
- episode_id 用 RSS guid(或 audio URL 的 hash 兜底)
- 其他 ASR submit / poll / save 都不变

新脚本:`scripts/transcribe_apple.py`(保留 xiaoyu 版以备用),用法:
```
python scripts/transcribe_apple.py <podcast_url_or_id> [--exclude-pattern <regex>]
```

`--exclude-pattern` 用于大力如山的人工筛(eg `--exclude-pattern "育儿|生活|八卦"`)

### Stage 1 · 下载 + ASR 转录(~3-4h,自动跑)

```
DASHSCOPE_API_KEY=... python scripts/transcribe_apple.py \
    "https://podcasts.apple.com/cn/podcast/.../id1648308335" \
    --exclude-pattern "育儿|生活|八卦|宠物"
DASHSCOPE_API_KEY=... python scripts/transcribe_apple.py \
    "https://podcasts.apple.com/cn/podcast/.../id1748496863"
```

- 假设 2 个 podcast 合共 ~80-120 集 × 平均 45min = 4500min
- DashScope Paraformer-v2 ~$0.005/min → **~$22**
- ThreadPoolExecutor(max_workers=4) 异步并行,polling 8s 一次
- 可断点续(submissions.jsonl 记 task_id)
- 输出:`backend/data/podcasts/transcripts/{eid}.{json,txt}` + `_meta/{eid}.meta.json`

### Stage 2 · ASR 纠错(~5min,纯文本处理)

```
python scripts/podcast_pass1_correct.py
```

- 用 term_dict.json 22 个 ASR 修正(穆迪/IBD/PR/信评/承做 等)
- 读 `transcripts_raw/` → 写 `transcripts/`(idempotent)

### Stage 3 · 摘要 + Insights 抽取(~2-3h,LLM 跑)

```
MIMO_API_KEY=... python scripts/podcast_pass2_summarize.py    # episode 级摘要
MIMO_API_KEY=... python scripts/podcast_pass3_extract.py     # 5 类 typed insights
```

- mimo-v2.5-pro(content-filter 时 DeepSeek 兜底)
- 每集大致产 8-15 条 insight,80-120 集 ≈ **640-1800 条**(目标 ≥ 800)
- 成本估 ~$10
- 输出:`_processed/episode_summaries.jsonl` + `_processed/insights.jsonl`

### Stage 4 · 去重 + 入库(~30min)

```
python scripts/podcast_pass35_dedup.py            # canonical normalize + dedup
python -m app.services.podcasts.ingest            # 入 podcast_episodes + podcast_insights 表
```

- pass3.5 用 difflib(threshold 0.85)合并近重复 → 留 corroboration list("N 嘉宾说过这个")
- ingest 把 episodes + insights + 1024-dim DashScope embedding 入库
- embedding 成本 ~$1

### Stage 5 · 验证 + 接 Provider(~30min)

- SQL count 验证 `podcast_insights` ≥ 800
- 抽样 10 条用 `app.services.podcasts.retrieve.search()` 验证 RAG 召回
- 启 `PodcastContextProvider`(已有,只需开 env `LLM_CONTEXT_PROVIDERS=podcast`)
- 跑一次 mock interview eval(v5 baseline)看 feedback_specificity 是否再涨

---

## 时间表

总时长 ~7-9 小时 自动跑 + ~2h 主动操作,可隔夜跑。

```
T+0     Stage 0(改脚本)          ←  人工 1.5h
T+1.5h  Stage 1 启动(ASR 异步)
T+5h    Stage 1 完成 + Stage 2 跑(5min)
T+5.1h  Stage 3 启动(LLM 抽取 2-3h)
T+7.5h  Stage 3 完 + Stage 4(30min)
T+8h    Stage 5 验证 + 接入
```

## 成本

| 项 | $ |
|---|---|
| DashScope Paraformer ASR | ~22 |
| mimo + DeepSeek fallback LLM(pass 2+3) | ~10 |
| DashScope text-embedding-v3 | ~1 |
| **合计** | **~$33** |

---

## 风险 + 兜底

| 风险 | 概率 | 兜底 |
|---|---|---|
| 苹果 podcast RSS 解析挂(格式变化) | 低 | 已有备用 — 用 `feedparser` lib 解析(更鲁棒) |
| DashScope ASR 大批量限流 | 中 | 自动重试已在,最坏跑 2 晚分批 |
| mimo content-filter 拒一些 episode | 中 | 已有 DeepSeek 兜底逻辑 |
| 大力如山有效集数太少(过滤后) | 中 | 加 1 个相关 podcast 兜底(eg "对冲基金故事" / "一席") |
| 入库后 RAG 召回质量不高 | 低 | 看 v5 eval,如果 insight 引用率 < 5%,调 embedding 文本组合公式 |

---

## 验收标准

跑完 Stage 5 后必须满足:
- [ ] `podcast_insights` 表 ≥ 800 行
- [ ] `podcast_episodes` 表 ≥ 60 行(每集 ~10 insight 反推)
- [ ] 抽样 5 个查询(eg "投行实习核心能力"),每个 retrieve top-5 至少 3 条相关
- [ ] PodcastContextProvider 注册到 LLM Context Registry,启动 backend 不挂
- [ ] v5 baseline 跑 25 配对,feedback_specificity mean ≥ 2.0(跟 v3 持平不退步)

---

## 不做(明确划清)

- 不爬其它 podcast(只动这 2 个)
- 不重写 pass1-3.5 脚本 — 沿用现有
- 不动 RAG provider 实现(已有,只是没数据)
- 不并行多账号 ASR(单 key 串行够用)

---

## 资料

- 老 VPS 上的设计决策记录:`DECISIONS.md` D-05 (provider 顺序)+ D-06(知识包 DB tables)
- 热词字典:`backend/data/podcasts/_processed/term_dict.json`(22 ASR + 19 公司 + 角色 + 缩写,Pass 0 hand-curated)
- 4 个 pass 脚本:`scripts/podcast_pass{1_correct,2_summarize,3_extract,35_dedup}.py`
- RAG 入库:`backend/app/services/podcasts/{embed,ingest,retrieve,provider}.py`
- 入库后访问:`PodcastContextProvider`(已注册,需 env 启用)
