# S1 开关 ON 端到端冒烟 + XHS rerank 消融(2026-06-15)

## 1. 端到端冒烟(HYBRID_RECALL_ENABLED=1 + RERANK_FALLBACK_ENABLED=1)

dev 真库,模拟公募行研学生(target=公募权益研究员/行业研究员·消费):
- 混合召回返回 20 个 → match_tier 分布 **strong 4 / transferable 13 / explore 3**(三态齐全)。
- 抽样对位正确:strong=公募权益研究员(目标);transferable=基金产品/固收+多资产(相邻研究岗);
  explore=sub_cat 空的固收/可转债研究(语义捞出的未标注岗)。

→ **整条链路通**:开关 ON → 混合召回(丢硬闸)→ item 三态分层 → 前端三栏会被真实填满(非退化全 strong)。

## 2. XHS rerank 消融(I-C)

**问题**:小红书一手情报会注入岗位精排 prompt 当证据。它到底帮忙还是添乱?

**做法**:挑 17 个"有本公司小红书证据"的(persona,岗位)对,sonnet 双臂打 fit 分(带证据 / 不带证据),
判证据作用(helped/hurt/neutral)。

**结果**:

| 类别 | 条数 |
|---|---|
| helped(证据让判断更准) | 5 |
| hurt(证据把分带偏) | 7 |
| neutral | 5 |

平均分变动 5.53(最大 15)。**净风险 > 净收益。**

**根因(比 I-A 更深一层)**:证据按**公司名**取、未按**岗位职能**过滤。17 条里 ≥6 条证据讲的是该公司的
**别的岗**(给量化岗塞投行面经、给产品岗塞算法面经),仍会把分带偏;且单条情绪/排名帖就能翻 5-15 分。
I-A 修好了"别张冠李戴到别的公司",但"同公司、错职能"这层还在。而 helped 的 5 条几乎都是 **JD 为空**时
证据补了基础信息——这用结构化公司库更安全,不必引小红书噪声。

**裁决**:**XHS 不再注入岗位精排(`XHS_RERANK_ENABLED` 默认 OFF)。** XHS 仍用于 CHAT / narrative /
面试准备(用户带上下文阅读),只是不再静默改精排分数。这与独立 handoff review 的核心论点一致
(情报是 sidecar 证据,不进主排序)。**这是基于数据的行为变更**(此前 XHS 一直在精排里),flag 可一键恢复;
样本偏小(17、单判官),将来可用更大 eval 复核。

## 3. 对 S1 上线的连带好处

我们验证 off@5(3.9%)用的是**干净精排器(无 XHS)**;而生产精排此前带 XHS 噪声。**把 XHS 摘出精排后,
生产精排≈我们验证过的那个干净精排器** → off@5 在线上更可信,不需要担心 XHS 把验证过的结果带偏。
(经生产 deepseek 精排的全量 off@5 复测仍受限流约束,可错峰跑;但路径已与验证版对齐。)

## 资产
- `scripts/phase_g/37_build_xhs_ablation.py` — 构 ablation 对
- `data/_phase_g/eval/xhs_ablation_in.json` / `xhs_ablation_out.json` — 17 对输入 + sonnet 双臂结果
