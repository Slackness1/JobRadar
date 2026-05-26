# 投研赛道细颗粒度发现 + XHS 知识库 + 岗位 enrich Demo 设计

**日期**: 2026-05-26
**作者**: chuanbo + Claude (网站设计-devvpstmux session)
**状态**: 待 user review

---

## 1. 背景与动机

JobRadar 当前 taxonomy 是 13 canonical 金融赛道（公募/资管·投研、私募·基本面、量化、卖方研究、S&T·FICC、投行·并购、一级股权·PE/VC、监管·体制内、银行·总行核心、金融科技、咨询·MBB+Tier2、企业战略·管培·实业金融、大宗·能源）。

这套 taxonomy 是基于通识 + 公开市场情报搭的，但 SAIF MF 学生的真实流向**远比 13 个赛道更细**：

- 同样是"公募/资管·投研"，学生区分**消费组 / TMT组 / 医药组 / 周期组**，目标公司也按一线公募 / 二三线公募 / 银行理财子 / 保险资管 / 券商资管分层
- 同样是"量化"，学生区分**多因子 / 高频 / 机器学习 / 期权策略**，目标公司分头部量化私募 / 公募量化部 / 券商自营量化
- 同样是"卖方研究"，按行业组（消费/TMT/医药等）拆分

当前匹配系统的瓶颈不在算法，而在**学生分类器 + 岗位分类器 + 知识库**三者用同一套**过粗的** taxonomy。结果：

- 学生写"易方达消费组实习" → 系统标"公募/资管·投研"
- 岗位库里"嘉实周期研究员" → 也标"公募/资管·投研"
- 推荐时算法看不出"消费 vs 周期"的错配

**本设计的目标**：用 XHS 数据驱动 + 多源共识，发现 SAIF MF 投研空间的真实细颗粒 taxonomy，并打通 demo 端到端链路（学生分类 → 岗位 enrich → 知识库匹配 → 输出推荐）。

---

## 2. Goals & Success Criteria

### 2.1 In-Goals（必须达成）

1. **细颗粒 taxonomy** —— 至少 3 个 dimension（strategy_type / industry_focus / institution_tier）的发现性 taxonomy，每个 dimension 下有 XHS 数据驱动出的 sub-categories
2. **共识层级标注** —— 每个 sub-cat 标注共识强度（高/中/低），来源于 XHS + 就业报告 + Pony 现有 insights 三源交叉
3. **端到端 demo** —— 输入 P1 简历（林思远），输出 top 5 投研岗推荐 + 每条带 KB-backed 理由（引用 XHS 学姐学长 verbatim quote）
4. **XHS 知识库种子** —— 每个 sub-cat 至少 5-10 条代表性 verbatim quote 入 `xhs_insights` 表
5. **10 家 demo 公司清单** —— 综合 XHS 高频 + 就业报告流向 + 多源共识，自动选出

### 2.2 Non-Goals（不做）

- 不做"全 SAIF MF 流向 taxonomy"，只做投研空间（含 PE 研究端、量化 IT 等相关补充）
- 不做 prod 部署，demo 跑通后落 `docs/` + `backend/data/`，不强求 enrich 全 32k 岗位库
- 不做 human-in-the-loop（user 自评不懂金融细节，由 Opus 4.7 最终拍板）
- 不做 expert review（不找真人 SAIF 学长学姐 sanity check）

### 2.3 Demo 成功判据

跑完 demo 拿到的产出：
- `docs/taxonomy-投研-final-v1.md` —— taxonomy 文档，带共识层级
- `backend/data/xhs/raw/<keyword>/{notes,comments}.csv` —— 全部原始数据落地
- `xhs_notes` + `xhs_insights` 表填充
- `scripts/demo_p1_match.py` —— 给 P1 简历跑一次匹配，输出 top 5 推荐
- 跑完报告写 `docs/eval/<完工日期>-投研-demo-report.md`

---

## 3. 三根柱子（设计架构）

| 柱子 | 职责 | 输出物 |
|---|---|---|
| **学生分类器** | 从简历提取 (strategy_type, industry_focus, institution_tier) 三维标签 + 核心能力栈 | LLM prompt + 新增 `scripts/classify_student.py` |
| **岗位分类器** | 给现有 32k 纯金融岗位打同样三维标签 | LLM prompt + `scripts/enrich_jobs_v2.py`（demo 阶段只跑 demo 选的 10 家公司岗位） |
| **知识库** | 每个 sub-cat × company 单元的 XHS verbatim insights | `xhs_notes` + `xhs_insights` DB 表 |

**关键约束**：三者用**完全相同的 taxonomy enum**，差异在于"输入是简历 / 岗位 / XHS 帖子，输出是同一套维度标签 + 维度配套数据"。

---

## 4. Taxonomy 发现方法（结构化自下而上）

### 4.1 3 个 dimension（预设，不展开 category）

| Dimension | 说明 | 候选 categories（XHS 数据生长）|
|---|---|---|
| **strategy_type** | 做什么投资 / 研究 | 基本面权益 / 量化 / 固收 / 卖方研究 / 多资产-FOF-衍生品 / 相关补充（PE 研究、量化 IT 等） |
| **industry_focus** | 看哪个行业（主要给基本面 / 卖方研究用） | 消费 / TMT / 医药 / 金融 / 周期 / 制造 / 公用-交运-地产 / 港股-海外 / ESG-主题 |
| **institution_tier** | 什么类型平台 | 一线公募 / 二三线公募 / 银行理财子 / 保险资管 / 券商资管 / 信托 / 头部主观私募 / 中型主观私募 / 头部量化私募 / 中型量化私募 / 公募量化部 / 券商自营量化 / 卖方研究所 / 政府引导基金 |

Dimension 是固定的 3 个；每个 dimension 下的具体 category 由 XHS 数据 + LLM 聚类 + Opus 合成产出。

### 4.2 多向量爬取策略（5 个 vector）

不是单纯按关键词洒——5 个独立 vector 同时跑，提升信号源多样性：

| Vector | 来源 | 预期产出 | 优先级 |
|---|---|---|---|
| **V1 关键词** | 6 大策略 × institution_tier 组合 query（如"公募 基本面 校招"、"量化私募 多因子 实习"） | ~600 帖 | P0 必跑 |
| **V2 候选博主深爬** | 25 个候选博主（已有 Pony 报告产出）+ Pony 全量 | ~750 帖 | P0 必跑 |
| **V3 同公司多视角** | top 15 公司 × 5 视角（"+面试 / +实习 / +入职 / +离职 / +真实"）| ~750 帖 | P0 必跑 |
| **V4 评论网络** | V1-V3 高赞帖下"被点名 / 高互动"评论作者 | ~400 帖 | P1，预算允许才跑 |
| **V5 反向追踪** | V1-V4 中新冒出的高频博主 | ~200 帖 | P1，预算允许才跑 |

V1+V2+V3 ~2100 帖必跑（预算约 $7），V4+V5 视余额决定。

### 4.3 Subagent 自驱动饱和判断

6 个 Sonnet 4.6 subagent 并行跑（用 `superpowers:dispatching-parallel-agents`），每个负责一个 strategy 大类。

**饱和指标 + 硬上限**：

| Strategy 大类 | 权重 | sub-cat 目标 | 公司目标 | 帖数下限 | 帖数硬上限 |
|---|---|---|---|---|---|
| 基本面权益 | 重 | ≥ 6 industry sub-cat × ≥ 10 mentions | ≥ 15 公司 × ≥ 5 mentions | 200 | 1500 |
| 量化研究 | 重 | ≥ 4 sub-cat × ≥ 8 mentions | ≥ 10 公司 × ≥ 5 mentions | 100 | 800 |
| 固定收益 | 中 | ≥ 3 sub-cat × ≥ 5 mentions | ≥ 6 公司 × ≥ 3 mentions | 60 | 500 |
| 卖方研究 | 中 | ≥ 4 行业组 × ≥ 5 mentions | ≥ 5 券商研究所 | 60 | 500 |
| 多资产/FOF/衍生品 | 低 | ≥ 1 sub-cat × ≥ 5 mentions | ≥ 3 家 | 20 | 200 |
| 相关补充（PE 研究/量化 IT） | 最低 | 各 1 例即可 | 各 ≥ 2 mentions | 10 | 100 |

**Subagent 循环**：

```
seed query → 爬 50 帖 → DeepSeek 抽 dual schema → 检查饱和指标
  ├─ 达标 → 写 "saturated at N 帖" 报告 → 停
  ├─ 内容稀缺（连续 3 batch < 5 insight）→ 写 "scarce" 报告 → 停
  ├─ 触上限 → 写 "hit ceiling" 报告 → 停
  └─ 未饱和 → 用本轮发现的新公司名 / sub-cat 词当 query → 继续
```

---

## 5. 数据抽取 Schema（Dual Schema）

每帖 LLM **一次调用**抽出两类字段：

### 5.1 Taxonomy 发现字段（新设计）

| 字段 | 类型 | 说明 |
|---|---|---|
| `post_id` / `url` / `time` / `author` | str | 溯源用 |
| `relevance_score` | float 0-1 | 该帖是否真讨论投研，< 0.3 drop |
| `strategy_signals` | list of {canonical: enum, verbatim_phrase: str} | 学生原文用什么词描述策略 |
| `industry_signals` | list of {industry: enum, verbatim_phrase} | 行业方向信号 |
| `institution_signals` | list of {tier_guess: enum, company_name, verbatim} | 平台类型信号 |
| `discovered_sub_categories` | list of str | 学生用来区分岗位的具体词（如"消费组"、"投研一组"）|
| `company_role_pairs` | list of {company, role_or_dept, strategy} | 公司-岗位-策略映射 |
| `dimension_distinctions` | list of {axis, x_vs_y, note} | 学生显式做的"X vs Y"对比 |

### 5.2 KB 字段（沿用 Pony 5-type schema，保证下游 mock interview / 推荐兼容）

| 类型 | 说明 | 占比预期 |
|---|---|---|
| `role_insight` | 工作内容 / 工作感受 / 招聘流程 | ~30% |
| `interview_qa` | 面试题 + 回答方向 + verbatim | ~25% |
| `company_anecdote` | 单公司故事（文化、风险、内幕） | ~20% |
| `resume_tip` | 简历建议 / 内推渠道 | ~15% |
| `industry_trend` | 行业趋势 / 长线判断 | ~10% |

每条 KB insight 必带：`text`（1 句摘要）+ `verbatim_quote`（原文截取）+ `confidence` ∈ {high, med, low}。

### 5.3 处理 DeepSeek 争议帖

DeepSeek 输出 `confidence < 0.7` 的 taxonomy 判定 → 该 strategy 大类对应的 Sonnet subagent 二次审视；如 DeepSeek 与 Sonnet 两家不一致 → 标 `contested`，进入 Opus 最终合成时单独考虑（Opus 看原文 + 两家分歧理由再裁决）。

---

## 6. 多源共识识别（Opus 合成）

跑完 subagent + DeepSeek 抽取后，Opus 4.7 做最终合成。输入：

1. **XHS 全量产出**（subagent 1-6 各自的 saturation 报告 + 所有 taxonomy 字段抽取）
2. **就业报告 ground truth**（DeepSeek 抽 23/24/25 三年 SAIF MF 流向，公司 + 岗位 + 人数）
3. **Pony 现有 139 insights**（5-type schema 形态）
4. **当前 13 canonical taxonomy**（向后兼容参考）

输出：

### 6.1 Final Taxonomy 表

```yaml
taxonomy:
  strategy_type:
    - canonical: 基本面权益
      consensus: high            # 三源都认
      sub_categories:
        - canonical: 消费组研究
          consensus: high          # XHS + 报告 + Pony 都现
          aliases: [消费, 大消费, 食饮研究]
        - canonical: TMT组研究
          consensus: high
        - canonical: 医药组研究
          consensus: high
        # ... 更多 industry sub-cat ...
    - canonical: 量化研究
      consensus: high
      sub_categories:
        - canonical: 多因子研究
          consensus: high
        # ...
  industry_focus:
    - ...
  institution_tier:
    - canonical: 一线公募
      consensus: high
      member_companies: [华夏, 易方达, 嘉实, 南方, 广发, 富国, 招商]
    - canonical: 头部量化私募
      consensus: high
      member_companies: [幻方, 九坤, 明汯, 灵均, 鸣石, 衍复]
    # ...
```

### 6.2 10 家 demo 公司清单

综合"报告流向人数 + XHS 讨论度 + 多源共识"评分，输出 top 10：

```yaml
demo_companies:
  - name: 易方达基金
    selected_reason: SAIF 2024 流向 top 1 + XHS 高频 + Pony 5 insights
    confidence: high
    taxonomy_tags:
      strategy_type: 基本面权益
      institution_tier: 一线公募
  # ... 9 more ...
```

### 6.3 sub-cat 代表性 verbatim quote

每个高共识 sub-cat 配 5-10 条 verbatim quote，从 `xhs_insights` 表里挑 confidence=high 的：

```yaml
sub_cat_quotes:
  消费组研究:
    - quote: "我在易方达消费组做白酒研究的时候，每月跑 6 家 KA 商超 + 调研 12 家经销商，那是真练手"
      source: xhs_note_id=xxx, author=yyy
      confidence: high
    # ...
```

---

## 7. 端到端 Demo 链路

跑完上述发现 + 合成后，针对 P1 简历（林思远）走一次端到端：

### 7.1 学生分类器（针对 P1）

输入：林思远简历 全文 + final taxonomy
输出：

```yaml
student_p1:
  primary:
    strategy_type: 基本面权益
    industry_focus: [消费, 医药]    # 双覆盖
    institution_tier_target: [一线公募, 头部主观私募]
  secondary_signals:
    - 一级股权 PE 研究端（高瓴实习）
  core_skills: [财务建模 DCF, 草根调研, Python pandas/Airflow, SQL, 时间序列计量]
  weak_signals:
    - 港股 / 海外（未涉及）
    - 量化（未涉及，纯主动管理路径）
```

### 7.2 岗位分类器（针对 demo 10 家公司）

只跑 demo 10 家公司的岗位（非全 32k）：

```sql
SELECT * FROM jobs
WHERE company IN (...10 家...)
  AND scraped_at >= '2026-01-01'
```

每个岗位 LLM enrich：

```yaml
job_jobid_xxx:
  company: 嘉实基金
  job_title: 消费组研究员（暑期实习）
  strategy_type: 基本面权益
  industry_focus: 消费
  institution_tier: 一线公募
  seniority: 实习生
  required_skills: [行业研究, 财务建模, 草根调研]
  enrichment_confidence: high
```

### 7.3 匹配 + 推荐输出

```yaml
p1_recommendations:
  - rank: 1
    job: 嘉实基金 消费组研究员（暑期实习）
    match_score: 0.93
    reasoning:
      - "你在易方达消费组的实习经历，与本岗目标行业 100% 重合"
      - "你的白酒批价-动销 VAR/VECM 模型，正是消费组研究员需要的量化建模能力"
    xhs_evidence:
      - quote: "嘉实消费组带新人的方式跟易方达类似，都是先给一个细分子赛道让你深度跟踪"
        source: xhs_post_xxx
    risk_signals: []
  # ... 4 more ...
```

---

## 8. 成本与预算控制

### 8.1 严格 $10 上限

| 项 | 数量 | 单价 | 小计 |
|---|---|---|---|
| TikHub search_notes | ~50 query | $0.010 | $0.50 |
| decode 抓帖 + 评论 | ~2500 帖 | $0.0015 | $3.75 |
| DeepSeek 双 schema 抽取 | ~2500 帖（avg 2k input + 800 output） | ~$0.0014 | $3.50 |
| DeepSeek 就业报告抽取 | 3 PDF（30k token total） | ~$0.10/PDF | $0.30 |
| 争议帖二次抽 + 边界 case 缓冲 | ~10% | | $1.00 |
| **API 合计** | | | **~$9.05** |

**Sonnet subagent（6 个并行）+ Opus 4.7 最终合成** = Claude Code session 自带，**不计入** $10。

### 8.2 触顶自动停

每个 subagent 内置硬上限（见 §4.3）；6 个 subagent 协同有全局 budget tracker，跑到 $9 时自动 freeze V4/V5 不再启动。

---

## 9. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| XHS 营销号 / 噪声多 | 高 | taxonomy 偏 | `min_likes 30 + min_comments 8` 硬过滤；作者 fans > 100k drop |
| DeepSeek 抽取漂移 | 中 | taxonomy 错位 | Sonnet subagent 对 confidence < 0.7 二次审视 |
| Sonnet & DeepSeek 同时错 | 低 | undetected bias | Opus 合成时引入就业报告 ground truth 锚定 |
| 就业报告 OCR/抽取错 | 中 | ground truth 跑偏 | 3 年报告交叉验证；先验证 2024（最稳定）再外推 |
| 单博主声音过大（Pony 已 49 帖在库） | 中 | Pony 个人偏好污染 taxonomy | 25 候选博主 deep crawl 平衡；Opus 合成时显式分权 |
| API 失败 / rate limit | 低 | demo 跑不完 | TikHub 10 RPS + sleep 5-15s 随机；失败重试 3 次 |
| 预算超 $10 | 低 | 钱 | 全局 budget tracker freeze V4/V5；硬上限 |

---

## 10. 输出物清单

跑完 demo 后，仓库里多出：

### 10.1 文档

- `docs/taxonomy-投研-final-v1.md` —— 最终 taxonomy（带共识层级 + member companies）
- `docs/eval/<完工日期>-投研-demo-report.md` —— P1 端到端 demo 报告（约 2026-05-30 至 06-01 完工，按实际跑通日填入）
- `docs/superpowers/specs/2026-05-26-investment-research-taxonomy-discovery-design.md` —— 本设计文档

### 10.2 数据

- `backend/data/xhs/raw/<keyword>/{notes,comments}.csv` —— 全部 ~2500 帖原始数据
- `backend/data/xhs/raw/_taxonomy_extracts/` —— DeepSeek dual schema 抽取 JSONL
- `backend/data/saif_employment_reports_extracted.json` —— 3 年报告流向结构化

### 10.3 DB

- `xhs_notes` 填充 ~2500 行
- `xhs_insights` 填充 ~600-1000 条 high confidence insight
- 新增表 `xhs_taxonomy_extracts`（dual schema 中的 taxonomy 字段，与 KB 分开存以便后续 query）

### 10.4 脚本

- `scripts/xhs_discovery_subagent.py` —— 6 个 strategy 大类的 subagent 入口
- `scripts/extract_employment_reports.py` —— 报告 LLM 抽取
- `scripts/opus_taxonomy_synthesis.py` —— Opus 合成入口
- `scripts/classify_student.py` —— 学生分类器
- `scripts/enrich_jobs_v2.py` —— 岗位分类器（按 demo 10 家公司 scoped）
- `scripts/demo_p1_match.py` —— P1 端到端跑

---

## 11. 不在本设计范围

- ❌ 全 32k 岗位库 enrich（demo 阶段只跑 10 家公司的岗位，全量是后续工作）
- ❌ Frontend UI 改动（demo 输出走 markdown 报告，不接前端推荐卡）
- ❌ Prod VPS 部署（demo 跑本地 dev VPS）
- ❌ Human-in-the-loop（user 不介入决策，Opus 拍板）
- ❌ Expert review（不找真人学长学姐）
- ❌ 量化交易 / S&T desk 等执行端深度建模（demo 只覆盖"研究端"）
- ❌ 其它 SAIF 流向（IBD / 咨询 / 体制内）

后续可补做的 stretch：

- 跑通 demo 后 expand 到其它 SAIF MF 主流方向（IBD / 咨询）
- 全 32k 岗位 enrich pipeline
- 接入推荐 V4 + 前端推荐卡
- Multi-model 升级到 DeepSeek + Sonnet + Qwen 三路交叉

---

## 12. 估算总时长

| Phase | 工时 | 说明 |
|---|---|---|
| 实施 plan 撰写（writing-plans skill） | 0.5 天 | 下一步 |
| 就业报告抽取脚本 + 跑通 | 0.5 天 | 独立 |
| Subagent 框架 + V1-V3 跑通 | 1.5 天 | 主体 |
| DeepSeek dual schema 抽取脚本 | 0.5 天 | 主体 |
| Opus 合成 + taxonomy 输出 | 1 天 | 主体 |
| 学生 + 岗位 分类器 + demo 端到端 | 1 天 | 主体 |
| 评估报告 + 文档收尾 | 0.5 天 | 收官 |
| **合计** | **~5-6 天** | |

---

## 13. 后续步骤

1. ✅ 设计文档已写（本文档）
2. ⏭️ User review 本设计
3. ⏭️ 调用 `superpowers:writing-plans` skill 生成详细实施计划
4. ⏭️ 调用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development` 执行
