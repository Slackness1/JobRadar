# Phase G — 推荐链路 v2 升级 (27 sub_cat 知识库 + 岗位 enrich + 推荐改造)

**版本**: v1
**生成日期**: 2026-05-27
**作者**: Claude (网站设计-devvpstmux session) + user 协同 brainstorm
**前置**: `docs/superpowers/specs/2026-05-26-investment-research-taxonomy-discovery-design.md` (demo 阶段, 已 ship)
**关联交付**: `docs/taxonomy-投研-final-v1.md` (27 sub_cat × 3 维 taxonomy 已锁定)
**目标 sprint**: 12.5-15.5 天 (~2.5-3 周)
**预算**: $50-60 LLM + crawl (~3-4% of 本周 $1,479 配额)

---

## 1. 目标 (单一)

**让学生在第一屏推荐岗位环节不再失去耐心。**

具体到现象层:
- 第一屏推荐不再混入底薪销售 / 中后台行政 / 客服 / 中介岗
- 推荐岗位 100% 是 SAIF MF 学生该看到的赛道头部公司
- 推荐理由从模板 ("您的金融背景与此岗位匹配") 升级到"对真人的建议" (引用知识库 verbatim + 学生 hidden_highlight + 差距分析)
- 学生 preferred sub_cat 头部公司无 active 岗位时, 显式 fallback 卡片告诉学生"X 公司本季暂未开放, 通常 [季节] 集中开放, 关注招聘官号"

**不在 scope 内 (留 Phase H)**:
- 真实学生 case study 闭环 (钦奕阳 / 张志杰 onboarding)
- 简历链路改造 (用 sub_cat 做语义增强 + 差距建议)
- 模拟面试链路改造 (用 sub_cat 出题 + 评分 + 追问)

---

## 2. Architecture — 6 工序流水线

```
工序 3a · XHS 补爬到 27 sub_cat baseline (Pro medium, 1 天, $1.5-2)
   │  ↓ taxonomy_xhs_posts 表 (27 sub_cat × ≥30 帖 / ≥10 公司)
   │
工序 0 · 公司 ground truth 清单 (Opus 一次, 0.5 天, ~$2)
   │  ↓ ground_truth_companies_v1.json (180-200 家公司, 27 sub_cat 全覆盖)
   │
工序 3b · 27 sub_cat 知识库 synthesis (Opus hybrid, 1 天, $32)
   │  ↓ docs/sub_cat_knowledge/*.md + knowledge_subcategories 表 (15 字段)
   │
   ├── 工序 1 · audit + 补爬缺失公司岗位 (3-5 天, $2-5) ──┐
   │                                                          │
   └── 工序 2 · quality_label 7 等级 backfill (Pro med, 1天, $6-8) ──┘
                                                                       │
工序 4 · sub_cat enrich Multi-pass C (Pro high, 2 天, $8-12) ◄─────────┘
   │  ↓ jobs 表 7 列新字段, ground truth 池 5-8k 岗位 sub_cat 100%
   │
工序 5 · 推荐链路 v2 + 公司 fallback (4-5 天, $0 增量)
   │  ↓ recommendation.py 重写; UI 新加 fallback 区域
   │
   ↓
学生第一屏推荐: 100% ground truth + good 质量 + sub_cat 命中
```

**总工期**: 12.5-15.5 天
**总成本**: $50-60 (LLM + crawl)

---

## 3. Architectural 决策 (4 个, 不可绕开)

### D-1 · canonical_track 老字段在推荐链路完全废弃

- 保留 `canonical_track` 列 (digest / coverage 模块还在读, 不动那些)
- Phase G 推荐链路 v2 **不再读 canonical_track**, 只读新的 `sub_category` / `industry_focus` / `institution_tier`
- 老 `_classify_track_match` / `_build_track_condition` 14 大类匹配函数在 v2 启用时全部 deprecated
- 老代码留 reference 半个月, 不走 code path
- 长期 (Phase H+) 评估能否 drop canonical_track 列

### D-2 · sub_category NULL 的岗位永远不进推荐池

- 只有 ground truth 公司 + good/internship_only 质量的岗位会被 LLM enrich 写入 sub_category
- 没被 enrich 的岗位 (sub_category IS NULL) — 这些是非 SAIF 目标岗位 (银行总行综合管培 / 央企工程 / 销售客服) — 推荐 SQL 直接 `WHERE sub_category IS NOT NULL` 过滤
- **学生第一屏推荐看到的, 100% 是 ground truth + good 质量 + 27 sub_cat 覆盖岗位**

### D-3 · 推荐链路 v2 走灰度 (env flag, 不分新老双轨)

- 加 env flag `RECOMMENDATION_V2_ENABLED` (default OFF)
- 一开 = 推荐链路完全走新逻辑; 一关 = 完全走老的
- dev VPS 开 v2 验, 验通过 prod 切 v2, 同时 prod 也切到只读新字段
- 老 14 大类逻辑代码留半个月观察期后清理

### D-4 · canonical_track 列长期 lifecycle

- Phase G 期间冷冻 (event listener 还在赋值, 但推荐不读)
- Phase H 起做 deprecation 评估 — 如 digest / coverage 也能切到 sub_category, 老列可 drop; 否则长期共存

---

## 4. 工序 detail

### 工序 0 · 公司 ground truth 清单 (0.5 天, ~$2)

**输入**:
- `docs/taxonomy-投研-final-v1.md` 各 sub_cat typical_companies (XHS mention)
- `backend/data/saif_employment_reports_extracted.json` (SAIF 2023/2024/2025, 65+ 流向)
- `backend/data/demo_companies_v1.json` (demo 锁定 20 公司)
- `backend/config/coverage_truth.yaml` (老 14 大类 ground truth)

**输出**: `backend/data/ground_truth_companies_v1.json`

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-05-27",
  "ground_truth": {
    "公募权益研究员": [
      {
        "name": "易方达基金",
        "tier": "一线公募",
        "primary_sub_cats": ["公募权益研究员", "行业研究员·消费"],
        "industry_focus": ["消费", "医药", "TMT"],
        "source": ["xhs:26", "saif:2024,2025", "demo_v1"],
        "must_have": true,
        "notes": "SAIF 公募头部, 必须 cover 岗位级"
      }
    ]
  },
  "stats": {
    "total_companies": 187,
    "must_have_companies": 92,
    "by_sub_cat": {"公募权益研究员": 8, "量化研究员·中频": 6, "...": "..."}
  }
}
```

**生成方式**: Opus 4.7 一次性 (1M context, 4 数据源全文喂入), prompt 要求:
- 每 sub_cat 列 must-have (头部) 5-8 家 + recommended (二线) 3-5 家
- 每条公司必须有 SAIF 就业报告 OR XHS≥5 mention OR demo_v1 evidence 支持
- 禁止凭印象添加

**must_have 等级用法**:
- `must_have=true`: 必须 audit + 补爬到岗位级 (无活跃岗位仍要展示 fallback)
- `must_have=false`: 有则收, 无则推 fallback

**依赖**: 工序 3a 必须先跑完 (typical_companies 完整性需要补爬后 XHS 数据支撑)

---

### 工序 3a · XHS 补爬到 27 sub_cat baseline (1 天, $1.5-2, Pro medium)

**前置工序**: 全 Phase G 第一件事 (因 0 和 3b 都依赖 27 sub_cat 完整数据)

**Step 1: 把 demo 阶段 691 帖按 27 sub_cat 重新分桶**:
- DeepSeek v4-Pro (reasoning_effort=medium) multi-label classify 每帖 → 0-2 个 sub_cat
- threshold: classify confidence > 0.7 才入桶
- 估 ~500-600 帖能分到至少 1 sub_cat, 剩归 "general 投研" 不入桶

**Step 2: 识别短板 + 补爬**:
- 按 baseline (≥30 帖 + ≥10 公司 mention) 找出短板 sub_cat (估 7-9 个: PE 投后 / VC 行研 / 信用研究 / 固收交易 / 投行 IBD / 结构化衍生品 / 利率宏观 / 财富 FOF / 多模态推理优化)
- 每短板 sub_cat 设计 5-8 个 targeted query (sub_cat 名 + 2-3 个 ground truth 公司 + verbatim 信号词)
- 例: "高瓴 PE 投后 行研 实习" / "光大永明 信用研究 城投"

**Step 3: 跑 XHS crawler**:
- 复用 demo 已 battle-tested 的 infra: Decodo desktop + TikHub `get_note_info` xsec_token URL 模式
- 路径: `tools/xhs_post_comment_crawler/` + 现有 scripts
- DeepSeek Pro 过滤 relevance > 0.6 才入库

**输出**: 新表 `taxonomy_xhs_posts` (per 帖: sub_cat / company_mentions / verbatim_signals / raw_content / source_url), 27 sub_cat 都 ≥ baseline。

---

### 工序 3b · Opus 4.7 synthesis 27 sub_cat 知识库 (1 天, $32, hybrid)

**执行模式 — Hybrid (前 5 subagent + 后 22 pure API loop)**:

- 前 5 个 sub_cat 用 Claude Code Agent (Opus 4.7 subagent), 覆盖 7 大类各 1 个 + 数据厚/薄各 1-2 个
- agent 自检 + 多 tool use, 锁定 prompt 模板 + 输出格式 + 边界 case
- 剩 22 个用 pure Python script + Opus 4.7 API 直接调, asyncio.gather 并行 4-6 个
- 成本: 5 × $2.37 (subagent mean) + 22 × $0.9 (Opus pure API) ≈ **$32**

**Per sub_cat 输入** (~30-50k tokens):
- 该 sub_cat 全部 ≥30 帖 XHS raw + extracted fields (from 3a)
- SAIF 就业报告对应流向 (filter `backend/data/saif_employment_reports_extracted.json`)
- demo_companies_v1.json 对应公司

**结构化输出 (15 字段 JSON)**:

```json
{
  "sub_cat": "公募权益研究员",
  "sub_cat_slug": "fund_equity_researcher",
  "strategy_type": "基本面权益",
  "industry_focus_candidates": ["消费", "TMT", "医药", "周期", "新能源"],
  "institution_tier_candidates": ["一线公募", "二线公募"],
  "typical_companies": [
    {"name": "易方达基金", "tier": "一线公募", "xhs_mention_count": 26, "is_saif_alumni_dest": true}
  ],
  "hard_requirements": [
    "985 / 211 + 金融/经济/数学/CS 硕士",
    "至少 1 段公募 / 卖方 / 头部私募实习",
    "CFA 一级或以上 (强 signal)"
  ],
  "soft_signals": [
    "GitHub 量化模型 repo (≥50 star)",
    "CICC / CFA Institute Research Challenge 获奖"
  ],
  "transfer_paths": [
    {"from": "券商研究所 TMT", "to": "公募 TMT 研究员", "difficulty": "low", "notes": "..."},
    {"from": "PE 投后", "to": "公募基本面研究", "difficulty": "medium", "notes": "..."}
  ],
  "pitfalls": [
    "公募基金中后台 (产品 / 风控) 不要被名字误导, 跟投研完全不同",
    "公募指数研究员 vs 主动权益研究员 — 招聘量不同, 不要混"
  ],
  "interview_style": "推票路演 (基本面分析) + 近期行情判断 + 关键行业事件 + 市场风险溢价",
  "compensation_signal": "应届生起薪 17-28 万 (一线公募)",
  "career_trajectory": "1 年研究员 → 3 年高级研究员 → 5 年基金经理 (路径清晰但周期被拉长)",
  "verbatim_quotes": [
    {
      "quote": "投研类: 权益研究员、固收研究员、量化研究员; 市场销售类: 渠道经理、机构销售...",
      "source_url": "https://www.xiaohongshu.com/discovery/item/69d4b97a...",
      "context": "公募基金内部岗位分类"
    }
  ],
  "hiring_season": {
    "spring": "3-5 月集中开放",
    "fall": "9-11 月集中开放",
    "verbatim": "..."
  },
  "data_confidence": "high",
  "data_basis": {
    "post_count": 35,
    "company_mention_count": 12,
    "saif_alumni_count": 8
  }
}
```

**data_confidence 自动算法**:
- `high`: ≥30 帖 + ≥10 公司 + ≥3 SAIF alumni 流向
- `medium`: ≥30 帖 + ≥5 公司, 但 SAIF 流向 <3
- `low`: 补爬后帖数仍 <30 (真冷门赛道, e.g. 多模态推理优化)
- low confidence sub_cat 推荐时降权 + 推荐理由加 "本赛道知识库覆盖有限" 标注

**双轨入库**:
- `docs/sub_cat_knowledge/{sub_cat_slug}.md` — 人类可读, source-of-truth, 用户和老师可直接 review
- `knowledge_subcategories` 表 (Alembic migration 新增) — 运行时 ContextProvider 调用

---

### 工序 1 · 岗位库 audit + 补爬缺失公司岗位 (3-5 天, $2-5)

**Audit 脚本** (`backend/scripts/phase_g/audit_ground_truth_coverage.py`):

按 `ground_truth_companies_v1.json` 对比库现状, 输出 3 类 gap 报告:

| 类别 | 处理 |
|---|---|
| **绿** ground truth 公司 + 库里有 ≥3 个活跃岗位 (`scraped_at > now() - 30d`) | 跳过, 后面 enrich 直接用 |
| **黄** ground truth 公司 + 库里岗位过期或 <3 个 | 重新 crawl |
| **红** ground truth must_have 公司 + 库里 0 岗位 | 必补 |

**补爬策略 (按公司分流)**:
1. 已有 `backend/app/services/*_crawler.py` (12+ 个 finance crawler) → 复用, 配 `company_name + sub_cat 关键词` 跑批
2. 通用 ATS (Workday / Beisen / 易招通 / Moka) → 复用现有 ATS handler primitive (`docs/crawlers-notes.md`)
3. 其它 → firecrawl + 公司招聘官网 URL fallback (限定 must_have=true, 控成本)

**实习岗位识别 (新函数, 不入 DB 列)**:

```python
# backend/app/services/job_helpers.py
def detect_internship(job: Job) -> bool:
    title_signals = ["实习", "intern", "实习生", "Internship"]
    duty_signals = ["实习期", "在校生", "学生岗"]
    return any(s in (job.job_title or "") for s in title_signals) or \
           any(s in (job.job_duty or "") for s in duty_signals) or \
           (job.job_stage and "实习" in job.job_stage)
```

推荐时 on-the-fly 算 (~28k 岗位性能 OK); 性能问题留 Phase H 加列。

**过期定义**: `scraped_at < now() - 30 天` = stale, 推荐时过滤; 不删数据 (历史 audit / case study 还要看)。

**工期分配**:
- 1 天: audit 脚本 + 跑 + 出 gap 报告
- 2-3 天: 补爬 (红 + 黄, 约 30-50 家公司)
- 0.5-1 天: 入库 + 验证 (新增 ~2-4k 岗位)

---

### 工序 2 · 质量 label 词表扩展 + backfill (1 天, $6-8, Pro medium)

**词表从 4 → 7**:

| Label | 定义 | 推荐分流 |
|---|---|---|
| `good` (保留) | 真正的投研/算法/产品对口岗, JD 内容充分, 招聘需求清晰 | **第一屏展示** |
| `internship_only` (新) | 标 "实习/Internship" + 不是正式岗 (派生规则同上) | "查看实习"单独 tab |
| `agency` (保留) | 中介转招 (Robert Walters / Michael Page 简称) | **永不展示** |
| `low_signal` (保留) | JD 含糊 / 字段缺失 / 无具体岗位描述 | **永不展示** |
| `spam` (保留) | 明显垃圾 (重复抓取 / 链接死 / 标题全大写英文乱码) | **永不展示** |
| `support_role` (新) | 中后台 / 行政 / 运营 / 销售 / 客服 | **永不展示** |
| `low_pay` (新) | 薪资明显低于行业水平 (投行/公募月薪 ≤6k 几乎必是销售合规) | **永不展示** |

**Backfill 28k 全活跃岗位** (含已标 good 的也重跑, 因可能错标):

- 复用 `crawler_llm_enrich.py` 框架, 模型从 `deepseek-chat` 升 `deepseek-v4-pro` (reasoning_effort=medium)
- Prompt 重写到 7 等级 + 各等级 1-2 句判定规则 + 5-10 个 verbatim 例子
- 利用 DeepSeek prefix cache: 大 prompt byte-stable, 小变量 (单 JD) 在 user message
- 成本: 28k × ~$0.00025 ≈ **$6-8**, 时间 ~30-45 min

**优化 (跟工序 4 部分合并)**:
- ground truth 池内的岗位 (~5-8k): 一次 LLM 调用同时出 `quality_label + sub_category + 3 维`
- ground truth 池外的岗位: 单独 Pro 调用只跑 quality (省 token)

---

### 工序 4 · 岗位 sub_cat enrich Multi-pass C (2 天, $8-12, Pro high)

**Schema 改动 (Alembic migration)**:

```sql
ALTER TABLE jobs ADD COLUMN sub_category TEXT;
ALTER TABLE jobs ADD COLUMN sub_category_secondary TEXT;
ALTER TABLE jobs ADD COLUMN industry_focus TEXT;           -- JSON array as string
ALTER TABLE jobs ADD COLUMN institution_tier TEXT;
ALTER TABLE jobs ADD COLUMN sub_cat_confidence REAL;
ALTER TABLE jobs ADD COLUMN sub_cat_reasoning TEXT;        -- ≤80 字
ALTER TABLE jobs ADD COLUMN sub_cat_enriched_at DATETIME;

CREATE INDEX idx_jobs_sub_category ON jobs(sub_category);
CREATE INDEX idx_jobs_institution_tier ON jobs(institution_tier);
```

**Multi-pass C 决策树**:

```
Pass 1: JD → Pro (reasoning=high) 看 7 大类 strategy_type 描述 → 选 1 大类
Pass 2: JD → Pro (reasoning=high) 看该大类下 sub_cat (5 个左右) 的硬门槛 → 选 sub_cat
```

利用 27 sub_cat 天然 7 大类层级 — 量化 vs 公募错判几乎不可能, 但 5 个量化 sub_cat 内部混淆容易; 分层让 LLM 在小空间高准确率决策。

**Pass 2 输出**:

```json
{
  "sub_category": "公募权益研究员",
  "sub_category_secondary": "行业研究员·消费",   // 可选, 跨 sub_cat 岗位
  "industry_focus": ["消费", "医药"],
  "institution_tier": "一线公募",
  "confidence": 0.92,
  "reasoning": "JD 提及行业研究 + 推票 + 消费组岗位, 强匹配公募权益研究员主流; 消费方向 secondary"
}
```

**Scope**: ground truth 公司池 × (`quality_label='good'` OR `quality_label='internship_only'`) = ~5-8k 岗位

**重跑触发**: `sub_cat_enriched_at` 字段记录; 知识库 (3b) 更新后, 重跑当前 sub_cat 已标岗位 (人工 trigger, 不自动)

---

### 工序 5 · 推荐链路 v2 + 公司 fallback (4-5 天, $0 增量)

#### 5.1 删除老逻辑 + 新 SQL recall (1 天)

**deprecate**:
- `recommendation.py::_classify_track_match()`
- `recommendation.py::_build_track_condition()`

**新 SQL**:

```sql
SELECT * FROM jobs
WHERE sub_category IS NOT NULL
  AND quality_label IN ('good', 'internship_only')
  AND scraped_at > datetime('now', '-30 days')
  AND (sub_category IN (:preferred_sub_cats)
       OR sub_category_secondary IN (:preferred_sub_cats))
ORDER BY
  (sub_category IN (:preferred_sub_cats)) DESC,
  scraped_at DESC
LIMIT 200
```

#### 5.2 三维 cross 过滤 + 加权评分 (1 天)

新函数 `_score_three_dim_cross(student_profile, job)`:

```python
score = (
    0.50 * sub_cat_match(student.preferred_sub_cats, job.sub_category, job.sub_category_secondary)
  + 0.25 * industry_overlap(student.preferred_industries, job.industry_focus)
  + 0.15 * tier_overlap(student.preferred_tiers, job.institution_tier)
  + 0.10 * (freshness_score(job.scraped_at) + quality_bonus(job.quality_label, job.sub_cat_confidence))
)
```

学生无显式偏好时, 退到 `inferred_sub_cats / industries / tiers` (P_self / P1-P6 都有这些字段, 从 hidden_highlights 推断)。

#### 5.3 LLM rerank with 知识库 (1 天)

复用现有 `recommendation.py` Pro rerank 框架 (deepseek-v4-pro reasoning_effort=high), **prompt 升级**:

```
你是 SAIF 学院的资深求职顾问. 给你一个学生 profile + 一个候选岗位 + 该岗位 sub_cat 的知识库摘要.
请评估 fit, 输出: score (0-100) + reasoning (≤120 字).

[学生 profile]
hidden_highlights: ...
inferred_sub_cats: ...
real_challenges: ...

[候选岗位]
公司 / title / duty / req: ...

[知识库 (sub_cat = 公募权益研究员, data_confidence=high)]
hard_requirements: ["985+硕士", "1段公募/卖方实习", "CFA 一级"]
soft_signals: ["GitHub 量化 repo", "CICC Research Challenge"]
pitfalls: ["中后台与投研不同"]
verbatim_quotes: [{quote: "...", source_url: "https://..."}]
```

LLM rerank 时**显式判断**学生 vs 知识库 hard_requirements 命中如何, 缺啥 — 这是"对真人的建议"的语义增强。

**Top 20 rerank** (不全 200 都跑); 单次 ~$0.005 × 20 = $0.1/学生 query。

#### 5.4 推荐理由生成 v2 (1 天)

老模板化推荐理由删, 新版 4 anchor 必出其 3:

| Anchor | 来源 | 示例 |
|---|---|---|
| 学生 hidden_highlight 真实 mention | profile | "你那段高瓴 PE 实习覆盖 80 亿 deal, 这种 deal size 经验在公募内部 IC meeting 直接转化" |
| sub_cat hard_requirement 命中 | 知识库 + LLM | "公募权益硬门槛 (985+CFA+一段公募/卖方实习) 你完全命中, 优势项是消费组覆盖" |
| institution_tier 区分点 | 知识库 verbatim | "卖方研究员 verbatim: '社交家舞台, 依赖人脉和输出观点' — 你的 38 次客户服务对得上" |
| 差距分析 | 学生 vs 知识库 gap | "差距: 公募买方更看推票胜率 — 简历里把高瓴实习推票胜率数据补一下会更稳" |

#### 5.5 公司 fallback surface (1-2 天)

**触发条件**: 学生 preferred sub_cat 对应的 ground truth must_have 公司, 库里**无 active 岗位** → 显示 fallback 卡片。

**新 API endpoint**:

```
GET /api/recommend/companies-fallback?user_key=&sub_cat=
```

- 查 ground_truth_v1.json 取 must_have 公司
- 查 jobs 表确认无 active 岗位
- 取知识库 verbatim + hiring_season 字段构造解释

**UI 区域** (推荐结果列表底部):

```
你 [量化研究员·中频] sub_cat 头部公司动态:

🔵 灵均投资 — 本季暂未开放新增岗位
   "中频 alpha 因子方向, sharpe > 0.8 是硬指标" — XHS 量化实习生 verbatim
   通常 春招 3-5 月 集中开放, 关注招聘官号

🔵 衍复投资 — 仅有 1 个量化开发实习岗 (北京)
   ...
```

---

## 5. Schema 改动汇总 (Alembic migrations)

### 新表

```sql
-- 工序 3a 产出
CREATE TABLE taxonomy_xhs_posts (
  id INTEGER PRIMARY KEY,
  sub_cat TEXT NOT NULL,
  source_url TEXT NOT NULL UNIQUE,
  company_mentions TEXT,        -- JSON array as string
  verbatim_signals TEXT,        -- JSON array
  raw_content TEXT NOT NULL,
  extracted_fields TEXT,        -- JSON, 双 schema 抽取结果
  relevance_score REAL,
  scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_taxonomy_xhs_sub_cat ON taxonomy_xhs_posts(sub_cat);

-- 工序 3b 产出
CREATE TABLE knowledge_subcategories (
  id INTEGER PRIMARY KEY,
  sub_cat TEXT NOT NULL UNIQUE,
  sub_cat_slug TEXT NOT NULL UNIQUE,
  strategy_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,   -- 15 字段全量 JSON
  data_confidence TEXT NOT NULL, -- high / medium / low
  data_basis_json TEXT NOT NULL,
  hiring_season_json TEXT,
  embedding BLOB,                -- DashScope text-embedding-v3, RAG 用
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### jobs 表新增 (工序 4)

```sql
ALTER TABLE jobs ADD COLUMN sub_category TEXT;
ALTER TABLE jobs ADD COLUMN sub_category_secondary TEXT;
ALTER TABLE jobs ADD COLUMN industry_focus TEXT;
ALTER TABLE jobs ADD COLUMN institution_tier TEXT;
ALTER TABLE jobs ADD COLUMN sub_cat_confidence REAL;
ALTER TABLE jobs ADD COLUMN sub_cat_reasoning TEXT;
ALTER TABLE jobs ADD COLUMN sub_cat_enriched_at DATETIME;

CREATE INDEX idx_jobs_sub_category ON jobs(sub_category);
CREATE INDEX idx_jobs_institution_tier ON jobs(institution_tier);
```

### 不动

- `canonical_track` 列保留 (digest / coverage 还在用, Phase H 再 evaluate drop)
- `track_predicted` 列保留 (legacy)
- `canonical_track_pre_v2` 列保留 (legacy backup)

---

## 6. Model 选择 + reasoning_effort

| 工序 | Model | reasoning_effort | 理由 |
|---|---|---|---|
| 0 公司 ground truth | Opus 4.7 (1 次) | N/A (Anthropic) | 4 数据源融合需 large context + best reasoning |
| 3a XHS classify + 抽取 | deepseek-v4-pro | medium | 简单多标签分类 + 抽取 |
| 3b 知识库 synthesis | Opus 4.7 (5 subagent + 22 pure API) | N/A | 知识库是 source-of-truth, 投资最佳 reasoning |
| 1 audit + 补爬 | N/A (无 LLM) | N/A | 纯 SQL + crawler |
| 2 quality_label backfill | deepseek-v4-pro | medium | 7 等级词表清晰, verbatim 命中为主 |
| 4 sub_cat enrich (Multi-pass C, 2 passes) | deepseek-v4-pro | **high** | 27 sub_cat 边界 nuance 高, Phase G 准确率核心 |
| 5 推荐 rerank | deepseek-v4-pro | high (已有) | 复用 existing recommendation.py rerank |

**为什么不混 Sonnet 4.6**: 跳过 benchmark (W 方案), 直接选 X (DeepSeek Pro high only) — 因 DeepSeek 75% off 后 vs Sonnet 4.6 成本差 ~10-15x, 而中文金融 domain DeepSeek 母语优势 +reasoning_effort=high 已能 close gap; 不值得 $80+ 增量。

---

## 7. 成本 breakdown

| 工序 | 成本 |
|---|---|
| 0 ground truth (Opus 1 次) | ~$2 |
| 3a XHS 补爬 + Pro 抽取 | $1.5-2 |
| 3b 知识库 synthesis (Opus hybrid: 5 subagent + 22 pure API) | **$32** |
| 1 audit + 补爬 (firecrawl + decodo) | $2-5 |
| 2 quality_label backfill (Pro medium, 28k) | $6-8 |
| 4 sub_cat enrich (Pro high, Multi-pass C 2 passes, 5-8k) | $8-12 |
| 5 推荐 rerank (推理时, $0.1/学生 query, 摊到 user) | $0 增量 |
| **总计** | **$51-61** |

占本周 $1,479 配额的 **3.5-4%**。

---

## 8. 验收 + 灰度策略

### 灰度

- env flag `RECOMMENDATION_V2_ENABLED` default OFF
- dev VPS (lavm-wlcndo6anm) 开 ON 验
- 验证 set: 9 persona (P1-P6 + P_self + 钦奕阳 + 张志杰) × 3 sub_cat = 27 个 A/B test case
- A/B 对比 v1 vs v2:
  - **第一屏垃圾岗位数** (期望 v1: 2-5 个 / v2: 0 个)
  - **推荐理由信息量** (主观打分 1-5)
- 验证通过 → prod VPS (myvps) 切 ON, 同时 prod 也切到只读新字段 (canonical_track 字段冷冻)

### 硬验收指标

| # | 指标 | 期望 |
|---|---|---|
| 1 | 推荐第一屏 (top 10) 来自 ground truth + good 质量 + sub_cat 命中 比例 | **100%** |
| 2 | 推荐理由引用知识库 verbatim 或学生 hidden_highlight 比例 | **100%** |
| 3 | ground truth must_have 公司无活跃岗位时 fallback 卡片正确出现 | 100% case |
| 4 | 9 persona × 3 sub_cat A/B 测试 v2 优于 v1 | **≥ 22/27** |
| 5 | DeepSeek Pro sub_cat enrich 准确率 (人工 review 50 样本) | **≥ 90%** |

### 软验收

- SAIF 老师 demo: 用 P_self + 钦奕阳 + 张志杰 跑 v2 推荐, 老师感知"AI 真懂了"
- 9 persona 推荐对比报告导出 PDF + 推飞书 `Jobcopilot/20_岗位推荐/2026-06-XX_phase-g-v2-baseline/`

---

## 9. 风险 + Open questions

### 风险

| # | 风险 | mitigation |
|---|---|---|
| R-1 | 工序 1 补爬时间超 5 天 (依赖 12+ crawler 复用) | 优先补 must_have=true 公司 (估 ~30-40 家); recommended 公司有则收 |
| R-2 | 工序 3b 27 sub_cat 中某些 (低 confidence) 知识库质量差, downstream enrich + 推荐受影响 | data_confidence=low 的 sub_cat 推荐时降权 + 标注 "本赛道覆盖有限" |
| R-3 | Opus 4.7 subagent 成本超 mean 落点 ($64+) | hybrid 设计已 mitigate; pure API loop fallback 兜底 |
| R-4 | sub_cat 边界 nuance LLM 仍判错 (e.g. 公募 vs 保险资管) | Multi-pass C 决策树 + reasoning_effort=high; 人工 review 50 样本验准确率 |
| R-5 | v2 上线 prod 后老学生 (老 14 大类记忆) 体验断层 | 灰度逐步推; 切换说明放 ChangeLog |

### Open questions

| # | 问题 | 触发决策点 |
|---|---|---|
| Q-1 | hiring_season 字段 dict 已定 `{spring, fall, verbatim}` (见 3b JSON), 但是否要加 `peak_month` 数字字段方便 fallback 卡片机械化展示 (vs 全靠 verbatim 自然语言)? | 工序 3b 设计 prompt 时确定 |
| Q-2 | secondary_sub_cat 字段在推荐评分时怎么算 (二级降权多少)? | 工序 5.2 实现时调参 |
| Q-3 | 公司 fallback 卡片 UI 在桌面 vs 移动端如何 responsive? | 工序 5.5 实现时与 frontend 协调 |
| Q-4 | 灰度阶段 dev VPS 上 9 persona × 3 sub_cat A/B 是否手动跑 还是 harness? | 工序 5 验收时定 |

---

## 10. 不在 scope 内 (留 Phase H+)

- **A · 真实学生 case study 闭环** — 钦奕阳 / 张志杰 + 新 onboard 学生形成 demo case study (依赖 Phase G v2 推荐 ready 后才有意义)
- **简历链路改造** — 用 sub_cat 做语义增强 + 差距建议 + overclaim 检测 (resume-copilot 模块)
- **模拟面试链路改造** — 用 sub_cat 出题 + 评分 + 追问 (interview 模块)
- **canonical_track 列彻底 drop** — 评估 digest / coverage 切到 sub_category 后再做
- **knowledge_subcategories 表的多向量索引 + 增量更新** — 当前规模 in-memory cosine + 全量重跑 OK

---

## 11. 实施依赖关系图

```
3a (XHS 补爬, 1 天)
   ↓
0 (ground truth 公司清单, 0.5 天)
   ↓
3b (知识库 synthesis, 1 天)
   ↓
   ├── 1 (audit + 补爬岗位, 3-5 天) ─┐
   └── 2 (quality_label backfill, 1 天) ─┤
                                          ↓
                                      4 (sub_cat enrich Multi-pass C, 2 天)
                                          ↓
                                      5 (推荐链路 v2 + fallback, 4-5 天)
                                          ↓
                                      验收 + 灰度 + prod 切换
```

**关键路径**: 3a → 0 → 3b → 1 (3-5d) → 4 → 5 = **12.5-15.5 天**

工序 2 与工序 1 并行不影响关键路径。

---

## 12. 与现有架构集成点

### 改动的代码 (estimated)

- `backend/app/models.py` — jobs 表 7 列新加 (Alembic), knowledge_subcategories + taxonomy_xhs_posts 两新表
- `backend/alembic/versions/*` — 2 新 migration
- `backend/app/services/resume_copilot/recommendation.py` — 重写 `_classify_track_match` + `_build_track_condition`; 加 `_score_three_dim_cross`
- `backend/app/services/resume_copilot/narrative.py` — 推荐理由 v2, 4 anchor 模板
- `backend/app/routers/recommend.py` (或 resume_copilot router) — 新 endpoint `companies-fallback`
- `backend/app/services/job_helpers.py` (新建) — `detect_internship()`
- `backend/scripts/phase_g/` (新目录) — audit + backfill + enrich 脚本
- `backend/app/services/crawler_llm_enrich.py` — 升级 model + reasoning_effort + prompt
- `resume-copilot-web/` — 推荐结果 UI 加 fallback 区域

### 不动的代码

- `backend/app/services/interview/` (模拟面试链路 — Phase H)
- `backend/app/services/resume_copilot/chat.py` / `plan_turn.py` (简历对话链路 — Phase H)
- `backend/app/services/llm_context/` (6 ContextProvider — Phase H 接入 sub_cat)
- `backend/app/services/podcasts/` (podcast RAG — 独立模块)
- 12+ `*_crawler.py` (复用, 但配置参数变)

---

## 13. 后续 Phase H 建议路线 (out of scope)

1. **Phase H-1 真实学生 case study** — 钦奕阳 / 张志杰 + 第三个新 onboard 学生, 形成"上传 → v2 推荐 → 体验真的好 → 反馈" 闭环, 老师能看到 measurable 学生收益
2. **Phase H-2 简历链路 sub_cat 接入** — 简历 chat / plan_turn 用 sub_cat 知识库做语义增强 + 差距建议 + overclaim 检测
3. **Phase H-3 模拟面试 sub_cat 接入** — 面试出题 / 评分 / 追问用 sub_cat 知识库, 替代当前 6 legacy track 关键词匹配
4. **Phase H-4 ContextProvider 接入 sub_cat** — 6 个 provider 全部接入 sub_cat 知识库, 取代当前各自独立逻辑
5. **Phase H-5 canonical_track 列 deprecation** — 评估 digest / coverage 能否切到 sub_cat; 能切则 drop 老列

---

## 14. 元数据

- **生成方式**: superpowers:brainstorming skill, 5 节 Section A-D 逐节确认
- **协同**: user 5 轮关键 redirect (B 主线 / 推荐失耐心痛点 / 召回质量为先 / XHS 补 cat / Pro 全切)
- **下一步**: 用户 review 本 spec → 修订或 confirm → invoke writing-plans skill 出实施计划
