# 投研 + AI 跨域细颗粒度 Demo 最终报告

**日期**: 2026-05-27
**Sprint**: 投研赛道细颗粒度发现 + XHS 知识库 + 岗位 enrich
**总成本**: $5.83 (全程预算 $10)
**完成 Tasks**: 19/19

---

## 一、给 SAIF 学院的呈交

### 1.1 解决了什么问题

之前 JobRadar 的 13 个 canonical 赛道太粗:**学生分类只能落到"公募 / 私募 / 卖方"这种大类,无法回答"P1 适合公募权益研究员·消费 vs P3 适合 Quantamental"这种细颗粒**。

这次 sprint 用真实 XHS 学生帖 (~700 帖 + DeepSeek 抽取) + SAIF 2024-2025 就业报告 65 条 + 5 个画像简历, **Opus 4.7 一次合成出 27 个 sub_category 的 3 维 taxonomy** (跨 7 大类:基本面权益 / 量化 / 固定收益 / 卖方研究 / 多资产 / 相关补充 / AI 跨域)。

### 1.2 用 4 个 SAIF persona 端到端验证 (P1/P2/P3/P6)

| Persona | 背景 | Top 1 推荐 (强匹配) | Top 2 | Top 3 | 区分点 verbatim |
|---|---|---|---|---|---|
| **P1 林思远** (清华本经济 + SAIF) | 公募基本面·消费医药 | **高瓴资本 二级研究员 0.95** | 华夏基金暑期 0.85 | 中信建投基金助理 0.75 | "deal size 80 亿 + 跨 3 部门协调"被 invoke 进高瓴推荐叙事 |
| **P2** (复旦本 + SAIF, TMT 双覆盖) | 卖方研究·TMT | **中金 国际化-传媒互联网 0.85** | 中信建投投资助理 0.85 | 中金 机械组 0.75 | "服务客户 38 次 + 数据库 2300 数据点"被 invoke 进中信建投推荐 |
| **P3 陈昊** (上交数学本 + SAIF) | **跨专业**, 私募 Quantamental | 华夏暑期 0.85 | **高瓴 0.85** | 富国金融研究 0.80 | "时序模型 LSTM/Transformer 实战"3 次被 invoke (4/5/6 三个推荐) |
| **P6 韩怀宇** (上交数学+CS 本 + SAIF) | 头部量化 | **九坤【揽月计划】量化交易分析师 0.95** | 易方达研究员 0.85 | 华泰量化研究员·策略算法 0.85 | "backtest 18 分钟降到 7 分钟"+ "因子入库 4 个 sharpe>0.8"双 hidden_highlight 被 invoke |

**4 个 persona 推荐**:
- ✅ P1 / P3 都命中**高瓴** (P1 因为简历有高瓴 PE 实习,P3 因为基本面权益主轴对齐) — 同公司不同 narrative
- ✅ P2 / P6 完全无 cross-leak,strategy 主轴隔离干净
- ✅ 5 个 persona 累计 21 条 hidden_highlight 被 LLM 显式 invoke 进推荐叙事 (P_self 最多 10 条,P1 最少 1 条)

### 1.3 区分力矩阵 4/6 通过

| 维度 | 结果 | 说明 |
|---|---|---|
| (a) P1 公募基本面 vs P6 量化主轴 | ✅ pass | 0 cross-leak |
| (b) P1 公募 vs P3 私募 tier overlap | ✅ pass | 0% overlap |
| (c) P1 买方 vs P2 卖方 strategy 内部 | ⚠️ 名义 fail | metric artifact: P2 top5 里中金重复 2 次不同岗位, 去重后 unique 公司只 4 家. 实际 narrative 区分清楚 (P2 强调首席助理, P1 强调买方研究员) |
| (d) P3 跨专业关键词命中 | ⚠️ 名义 fail | LLM 用了"数学背景+量化能力"语义对了, 但 strict 关键词没命中"跨专业"四字 |
| (e) 隐藏亮点挖掘 (每 persona ≥ 1) | ✅ pass | 全 5 persona 都 ≥ 1, P_self/P3/P6 都 ≥ 4 条 |
| (f) AI vs 投研跨域 leak | ✅ pass | 0 cross-domain leak (P_self top8 跟投研 4 persona top5 完全不重) |

### 1.4 给老师的可演示物

- **细颗粒度 taxonomy 地图** (`docs/taxonomy-投研-final-v1.md`): 27 个 sub_cat 树形 + 每个挂 1-2 条 XHS 学生原话佐证 + post URL — 真"看得见"的数据驱动
- **5 persona × 84 真实 JD 完整匹配矩阵** (`backend/data/demo_match_results_v1.json`): 每个 (persona, job) pair 都有 fit_score / tier_label / narrative / hidden_highlight 引用 / persona evidence 字段
- **数据透明** (`backend/data/xhs/raw/_pilot/*.jsonl`): 任何 sub_cat 或 公司分类都可回溯到具体 XHS post URL + DeepSeek 抽取的 verbatim quote

---

## 二、给周传博的求职情报

### 2.1 你的 AI 应用/PM 跨域分类 (DeepSeek 算的 + Opus 拍板)

- `strategy_type`: **AI应用_PM_开发**
- `sub_category`: **LLM 应用开发 / Agent 工程师** (confidence 0.95)
- `industry_focus`: ["AI 应用层", "金融科技"]
- `institution_tier`: ["大厂 AI 部门", "Agent 应用层创业"]

### 2.2 Top 7 推荐岗位

| # | fit | tier | 公司 | 岗位 | 为什么 fit (LLM narrative) |
|---|---|---|---|---|---|
| 1 | **0.92** | 强匹配 | AI 应用初创 (头部创业) | LLM 应用 + Agent + AI PM 全栈 | 0-1 全栈 + Agent 平台 + 产品思维完美匹配; AgentX + JobCopilot 双阶段设计直接对应, GitHub 350+ stars 验证 |
| 2 | **0.90** | 强匹配 | 九坤投资 | 多模态 Agent 算法实习生 | 多模态 Agent 方向与 LLM 应用开发主轴完全对齐, AgentX 项目直接匹配 (隐藏亮点:"platform 非 SDK"产品哲学) |
| 3 | **0.90** | 强匹配 | 蚂蚁集团 | 研究型实习生-个性化 agent 交互规划研究 | Agent 工程师主轴对齐 + AgentX 平台经验直接匹配 |
| 4 | **0.85** | 强匹配 | 华夏基金 | 资产配置研究员 (AI 模型方向) | AI 模型 + 多资产配置, 0-1 全栈 + 量化背景双匹配 (跨域机会) |
| 5 | **0.85** | 强匹配 | 灵均投资 | Python 研发实习生 (大模型应用方向) | 大模型应用 ↔ LLM 应用开发完全对齐 + SAIF 学院合作是稀缺背景 |
| 6 | **0.85** | 强匹配 | 字节跳动 | AI 产品实习生 - 抖音生活服务 | AI PM 业务侧, GenAI 产品经理经验匹配 + SAIF institutional 客户加分 |
| 7 | **0.85** | 强匹配 | 腾讯 | 混元基座模型 - 可在线持续进化的智能体算法 | 智能体算法 ↔ Agent 平台经验高度匹配 |

### 2.3 AI PM vs AI 应用开发 — 哪个 conversion 更高?

**Opus 4.7 基于 XHS 数据 + 你简历分析**:

→ **主投 AI PM 路径 (70% 简历投递权重)**

理由:
- 在 AI PM 实习池里, 你 4 个 ship 项目 + GitHub 350+ stars + SAIF institutional 合作是**头部 5%**。绝大多数 PM 候选人是商科复合背景但缺真 ship。
- 在 LLM 算法 / 应用开发实习池里, 对手是 ICPC / ACM / 北邮 / 清北 CS 本科, 你帝国理工 DS "中上"但缺 LLM post-train (SFT/RLHF/DPO)、推理优化 (Speculative Decoding) 这些 XHS 数据显示的 hot sub_cat 经验。

→ **次投 LLM 应用 / Agent 工程师 (30%)**

→ **不推荐 LLM post-train 算法岗** (学术门槛过高, ROI 低)

### 2.4 平台投递优先级 (按 ROI 排)

1. 🎯 **蚂蚁集团** — 跨域金融+AI 命中点最强 (帝国理工 DS + 剑桥经济 + 利物浦金融数学 + JobCopilot 跟 SAIF 合作), 蚂蚁百宝箱 Agent 是核心战略
2. **字节跳动 AI 应用 / AI PM 方向** — boss + 字节官方双通道
3. **腾讯** — 微信 + 元宝 Agent, 你 Lewoo 校园 Agent 经验天然 fit
4. **某 AI 应用初创 (头部创业)** — 0-1 全栈直接出活, 给 leadership 机会, 拿 offer 概率最高
5. **DeepSeek** — 拼一把, 即使被拒也是简历亮点
6. **百度 / 美团 / 小红书** — 备选, 走校招主流程
7. **阿里 / TikTok / 华为** — 大厂流程慢, 当 backup

### 2.5 必须解决的 2 个简历差距

**差距 1: 缺大厂 AI 正式实习 tag**
- 短期补救: JobCopilot 简历那一行突出 "已签 SAIF institutional 合作 + 真实学生用户 N 名" (N 等 SAIF 试点跑起来填)
- 进阶: 投递时挑 1-2 个 production code 实习 (4-6 周, 哪怕 unpaid), 拿到大厂 tag 后再投 AI PM

**差距 2: 项目都"个人/小团队" — 缺 "production code in 1000+ 工程师团队" 背书**
- 中科创达虽然不是 AI 实习, 但"输出标准化接口给下游优化层"是真 production deliverable. **简历把这条 bullet 顶到中科创达栏目第一条**, 并在 cover letter 解释"虽不是 AI 实习, 但走过完整 production 流程"

---

## 三、流程沉淀 (给后续 sprint 复用)

### 3.1 总成本明细 ($5.83)

| 类目 | 花费 | 说明 |
|---|---|---|
| 6 投研 bucket 主跑 (Decodo) | $2.40 | 405 high-rel 帖 + 1133 KB insights |
| P2 TMT patch (TikHub 备用通路) | $0.99 | 86 帖, TMT 命中从 1 飙到 70 |
| AI bucket pilot (TikHub) | $2.32 | 161 帖, surface 字节/腾讯/蚂蚁/DeepSeek 真出现公司 |
| 就业报告 LLM 抽取 (DeepSeek) | $0.07 | 2024+2025 共 65 条流向 ground truth |
| Tasks 15-17 (DeepSeek 分类+enrich+match) | ~$0.05 | 5 persona × 84 jobs × 多次调用 |

### 3.2 真实跑出来的方法论沉淀

1. **数据驱动 > 拍脑袋**: 第一次 seed 我把"字节/MiniMax/月之暗面"硬塞进 AI bucket — 被用户拦回, 改成 12 个 generic query (`AI 实习 / 大模型 校招 / Agent 工程师` 等). 结果 XHS 真高频公司 surface 出来的是**字节 23 / 腾讯 13 / 阿里 6 / 蚂蚁 5 / DeepSeek 3**, 而 MiniMax / Kimi / 智谱完全没出现 — 真实学生讨论密度跟印象差很大。

2. **Decodo 反爬墙 + 备用通路**: XHS web `/explore/<id>` 的"打开 APP 查看"墙挡住 Decodo; 必须用 `/discovery/item/<id>?xsec_token=...&xsec_source=app_share` + `device_type: desktop` + **不带 headless** 才能拿到正文。备用通路:Decodo 限流时切到 TikHub `/xiaohongshu/app/get_note_info` ($0.010/帖 vs Decodo $0.0015, 但 quota 独立)。

3. **Saturation-driven crawl > 固定 quota**: 每个 strategy 配独立 `SaturationConfig` (顶配 1500 帖 max, 量化 800, 多资产 200). 5 投研 bucket 实际跑出 691 高质量帖, 其中 4 个达饱和退出 (avg ~150 帖/bucket).

4. **Persona 简历 + hidden_highlights 是 demo 神器**: 21 次 hidden_highlight 显式 invoke 让推荐 narrative 远比"基于关键词匹配"有深度. P6 的 "backtest 18→7 分钟" 在 4 个量化推荐里都被 invoke, 直接对应 PM 招聘视角的 "工程能力 + alpha 产出双优".

### 3.3 已知 limitation 和后续优化

- **(b/d/c) discriminator metric 太 strict**: 应该升级到 LLM-based discrimination check (语义级别), 而非 strict keyword match. 当前 4/6 通过是被 keyword 误判低估了。
- **相关补充 bucket 缺数据** (Decodo 限流退出, 0 帖): PE / VC 相关流向只能依赖 SAIF 就业报告补 (高瓴/弘毅/CIC/淡马锡 等都来自 ground truth)
- **P_self 草稿待 user review** (5 个字段挂着,详见飞书 `Jobcopilot/00_personas-saif/P_self persona 草稿 — 周传博 AI 应用-PM 跨域 (2026-05-27 review)`)
- **demo_companies AI 侧**: MiniMax / 月之暗面 / 智谱 / 百川 等大模型独角兽 XHS 学生很少讨论, 没进 demo 公司清单. 用户如果想投这些公司, 需要单独走 XHS-blogger-following 通路或直接看公司官网。

---

## 四、下一步 (Phase G, demo 之后)

按用户之前确认的路线 B (生产路线, demo 之后):

1. **抽样 audit**: 把这份 taxonomy 跑去 classify 现有 32k 金融岗位的 1000 个随机样本, 看每个 sub_cat 在 DB 里岗位数 (~$1)
2. **缺口补爬**: taxonomy 高频但 DB 稀的 sub_cat (e.g. 蚂蚁百宝箱 Agent), 加 crawler
3. **全量 enrich**: 32k 岗位全跑 taxonomy 标签 (~$32 一次性)
4. **三链路接通**: 推荐 / 简历 / 模拟面试 三模块的 LLM context provider 接入新 taxonomy

预计 Phase G 工期 1-2 周, 之后 SAIF 试点学生上线就能拿到细粒度推荐叙事。
