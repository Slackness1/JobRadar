# 小红书 知识库补充计划 — 2026-05-19

**背景**:Podcast 知识库重建解决"行业 trend + 长篇 anecdote"那一层信号(stage 0-5 在 `podcast-rebuild-plan-2026-05-19.md`)。但模拟面试还差另一块:**学生原话级**的实习经验 / 面经回忆 / 选 offer 决策 — 这块用音频找不到,只能去小红书。

XHS-crawler 代码本机已就位(`tools/xhs_post_comment_crawler/`,Playwright 持久 profile + 真实浏览器爬,**不**走逆向签名),用户提供的登录 cookie(web_session/a1/webId/gid 4 个关键全有)已落 `backend/data/_secrets/saif_a_session_snapshot.json`,可直接 `xhs-crawler` import 复用。

---

## 信号差异 — 跟 Podcast / 牛客面经如何互补

| 来源 | 强项 | 弱项 |
|---|---|---|
| **Podcast(长音频)** | 高质量行业 macro / 资深 mentor 视角 / 跨年纵深 | 单集 1-2 小时,信息密度低;少"今天碰到 X"这种鲜活原话 |
| **牛客面经** | 面试题原题集中(2223 条已入库) | 答题/反馈/选 offer 决策几乎没有 |
| **XHS 帖子+评论** | **学生第一人称鲜活原话**:实习日记 / 面试回忆 / 选 offer / 同班同学闲聊 / 真实薪酬 | 营销号噪声大,需要 LLM 二筛 |

XHS 补的就是 **"投行三人间住宿什么样" / "我面信用研究遇到的真题" / "公募 vs 券商 自营选哪个" / "高金 MF 暑期实习如何投"** 这类话题 — 给模拟面试 follow-up + 给评分 reference 注入鲜活学生侧 corpus,**不直接给用户看**。

---

## 目标(SAIF 试点验收)

- ✅ ≥ 300 条 typed insights 入库(role / resume / interview / company / industry 5 类,同 podcast 5 桶)
- ✅ 70% 以上命中 finance 关键词(用 `term_dict.json` 反查)
- ✅ `XhsContextProvider` 上线后,模拟面试评分 reference 引用率提升(meta-judge 验)
- ✅ Cookie 失效自动 detect + 提示重登(不会静默挂)

---

## 数据源 + 爬取策略

### 关键词清单(分 3 组)

```yaml
# group_1_role (按 8 canonical 投研子轨)
- "公募 行业研究 实习"
- "卖方 行业研究 面试"
- "量化研究员 校招"
- "信用研究 实习"
- "FICC 投资经理"
- "IBD 行业组 实习日记"
- "PE/VC 投资 实习"
- "二级 行研 vs 量化"

# group_2_company (SAIF 学生最常去 的雇主 — 跟 5 个 real JD 对得上)
- "嘉实基金 实习"
- "景顺长城 校招"
- "华夏基金 行研"
- "富国基金 面试"
- "南方/易方达 暑期"
- "中信证券 研究所"
- "中金 IBD"
- "华泰证券 研究"

# group_3_school_lifecycle (高金语境)
- "SAIF MF 求职"
- "高金 暑期实习"
- "上交大 高金 公募"
- "高金 校招 选 offer"
```

### 抓取规则(避免营销号)

- `--min-likes 30 --min-comments 8`:低互动直接过滤
- 帖子作者 fans > 100k 的直接 drop(大概率商单 / 营销号)
- 评论保留:只留 like ≥ 2 的(过滤"路过""学习了""mark")
- 每帖最多取 30 条评论(避免 long-tail 噪声)

### 反爬 + 风控

- 单关键词限制 max_notes ≤ 30
- 跑批之间 sleep 5-15s(随机)
- 同关键词 query 一次跑完不重试
- 撞 captcha 立即停,人工重登一次

---

## 阶段拆分(5 阶段)

### Stage 0 · session 导入 + 关键词清单 fixture(~30min)

```bash
# 用 import_session_snapshot 把用户给的 cookie 灌进 profile
.venv/bin/python -c "
from xhs_post_comment_crawler.session import import_session_snapshot
from pathlib import Path
import_session_snapshot('saif_a', Path('backend/data/_secrets/saif_a_session_snapshot.json'))
"

# 验证(headless True 进去看一眼是否登录态保留)
xhs-crawler whoami --profile saif_a
```

输出:keyword YAML 清单 → `tools/xhs_post_comment_crawler/keywords/saif_finance_v1.yaml`

### Stage 1 · 批量爬取(~5-10h 异步,可隔夜)

```bash
DASHSCOPE_API_KEY=... xhs-crawler search-fetch-batch \
    --keywords-file keywords/saif_finance_v1.yaml \
    --profile saif_a \
    --max-notes 30 --min-likes 30 --min-comments 8 \
    --output-dir backend/data/xhs/raw/
```

- 24 个 keyword × 30 帖 ≈ **720 候选帖子**
- 实际去重 + 过滤后 ≈ **400-500 有效帖**
- 评论平均 30 条 → ≈ 15k 条 raw 评论文本
- 跑批中间撞 captcha 时:停 → 重新 `xhs-crawler login --profile saif_a` 手动一次 → 续跑(crawler 自带断点续支持)

输出文件结构:
```
backend/data/xhs/raw/
├── saif_finance_v1_20260519/
│   ├── search_results.json
│   ├── notes/<note_id>/{note.json, comments.json, meta.json}
│   ├── notes.csv
│   ├── comments.csv
│   └── report.md   # crawler 自带浅分析
```

### Stage 2 · 噪声清洗(~30min,纯文本)

```bash
.venv/bin/python scripts/xhs_pass1_filter.py \
    --input backend/data/xhs/raw/saif_finance_v1_20260519/ \
    --output backend/data/xhs/_processed/notes_clean.jsonl
```

规则(纯 heuristic,**不**调 LLM):
- drop 作者 fans > 100k
- drop 帖子里出现 "私信""+vx""推荐课程""免费领""转账""扫码" 任一
- drop 标题含 "广告"/"商单"/"赞助" 字样
- drop 评论 like < 2
- drop 长度 < 30 字的评论

### Stage 3 · LLM 抽取 typed insight(~1-2h)

```bash
MIMO_API_KEY=... .venv/bin/python scripts/xhs_pass2_extract.py \
    --input backend/data/xhs/_processed/notes_clean.jsonl \
    --output backend/data/xhs/_processed/insights.jsonl
```

- **完全复用** podcast 的 pass3 prompt(改 source label 从 podcast → xhs, 输出 schema 不变)
- 每帖产 2-5 条 insight,400 帖 ≈ **800-2000 条原始 insight**(过 dedup 后留 300-600)
- mimo-v2.5-pro,content-filter 时 DeepSeek 兜底

### Stage 4 · dedup + embedding + 入库(~30min)

```bash
.venv/bin/python scripts/xhs_pass3_dedup.py             # difflib 0.85 阈值
.venv/bin/python -m app.services.xhs.ingest             # 入 xhs_notes + xhs_insights 表
```

**新建 2 张表**(镜像 podcast 结构,字段微调):
- `xhs_notes`:note_id / title / author_handle / like_count / comment_count / topic_one_liner / summary_500 / embedding
- `xhs_insights`:同 PodcastInsight schema,加 `source_note_id`(替代 source_eid)

→ 等价于把 PodcastContextProvider 复制一份变 XhsContextProvider,RAG 调度上是 sibling。

### Stage 5 · 接 Provider + eval(~30min)

```bash
# 新 XhsContextProvider 注册到 ContextRegistry,bootstrap_llm_context() 增 1 行
# env LLM_CONTEXT_PROVIDERS=podcast,xhs 启用两个 RAG 源

# 跑 v6 baseline 验证 feedback_specificity 没退步,有 xhs 引文出现
.venv/bin/python -m tests.eval.runner --real-only --combos 5 --output v6
```

---

## 时间表

```
T+0     Stage 0(session 导入 + keyword)   ←  人工 0.5h
T+0.5h  Stage 1 启动(异步爬,中间偶尔人工 captcha)
T+10h   Stage 1 完(隔夜)
T+10.5h Stage 2 跑(30min)
T+11h   Stage 3 启动(LLM 1-2h)
T+12.5h Stage 4(30min)
T+13h   Stage 5 验证 + 接入
```

## 成本

| 项 | $ |
|---|---|
| Crawler 自身 | 0(本地 Playwright) |
| LLM 抽取(mimo + DeepSeek fallback) | ~10 |
| DashScope text-embedding-v3 | ~2 |
| **合计** | **~$12** |

---

## 风险 + 兜底

| 风险 | 概率 | 兜底 |
|---|---|---|
| Cookie 失效(预期 1-2 周一次) | 高 | 启动前自动 ping `/explore` 检查 200/403;403 → 提示 `xhs-crawler login --profile saif_a` 手动重登(扫码 30s)|
| 撞 captcha 频繁(IP 风控) | 中 | 单次 max_notes 限 30,关键词间 sleep 5-15s 随机;真撞了切到第 2 个 ISP(咖啡馆 WiFi)|
| 营销号噪声穿过 heuristic | 中 | Stage 3 prompt 加"明显商单/课程推广跳过"指令,LLM 二筛 |
| 站点结构变(comments 抓不到) | 低 | crawler README 已注 `--max-scroll-rounds` 调大;实在不行 author.py 单帖 fallback |
| 平台合规质疑 | 低 | 内部使用,**不**对外曝 raw 原文(只灌入 RAG 当 reference);output_summaries/ 保留 attribution |

---

## 验收标准

跑完 Stage 5 后必须满足:
- [ ] `xhs_insights` 表 ≥ 300 行
- [ ] `xhs_notes` 表 ≥ 200 行(过滤后)
- [ ] 抽样 5 个查询(eg "嘉实行研实习"),retrieve top-5 至少 3 条相关
- [ ] `XhsContextProvider` 注册到 LLM Context Registry,启动 backend 不挂
- [ ] v6 baseline 跑 5 配对,feedback_specificity mean ≥ 2.0(跟 v4 持平不退步)
- [ ] 评分 reference block 出现 xhs 来源引文(grep `[xhs:` 标记)

---

## 不做(明确划清)

- **不**做 captcha 自动绕过(纯手工触发时重登)
- **不**爬 XHS 其它内容(笔记之外的视频/直播不动)
- **不**对外公开 raw 帖子内容(internal RAG only,合规边界)
- **不**复用 podcast 的 5 张表 — 新建 2 张 xhs 表保持 source 隔离

---

## 跟 Podcast 计划的协同顺序

**强烈建议先做 podcast(已写计划)再做 xhs**,理由:
1. Podcast pipeline 跑通后,pass3 抽取 prompt 是稳定的 — XHS 直接复用省 1.5h prompt 调试
2. 数据库 schema 一次性沉淀 typed_insight 这套 contract,xhs 镜像更省事
3. v5 (podcast 加入) + v6 (xhs 加入) 两次 baseline 能分别量化各 source 的边际贡献

但 podcast 卡在 Stage 1 ASR 阶段时,xhs Stage 0-1 可以并行启动(异步爬不耗 LLM token,不冲突)。

---

## 资料

- Crawler 源码:`tools/xhs_post_comment_crawler/` (~2611 行 Python,Playwright + typer CLI)
- Session 凭据:`backend/data/_secrets/saif_a_session_snapshot.json`(16 cookies 含 4 关键)
- 关键词热词:`backend/data/podcasts/_processed/term_dict.json`(复用)
- 跟 podcast 共用的 pass3 prompt:`scripts/podcast_pass3_extract.py`
- 历史经验:`docs/xhs_post_comment_crawler/xhs_spider_comparison.md`(为什么选 Playwright + persistent profile 而不是 MediaCrawler)
- 类型/Provider 设计模式参考:`backend/app/services/podcasts/{ingest,retrieve,provider}.py`
