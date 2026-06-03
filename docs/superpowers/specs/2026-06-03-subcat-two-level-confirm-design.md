# 细分方向两级确认 + 召回口径对齐 — 设计 (2026-06-03)

## 背景 / 为什么做

投研学生在确认页只能选**粗赛道**(如「公募/资管·投研」)。该赛道经 `CANONICAL_TRACK_TO_SUBCATS`
自动展开成 **9 个 sub_cat**(权益 / 行研·消费 / 行研·TMT-医药-周期 / 公募指数 / 信用 / 固收+多资产 /
利率宏观 / 资管FOF / 财富管理FOF),全部等权进推荐池。于是**权益学生收到固收金工、FOF量化**。

诊断(session 146,选「公募/资管·投研」+ 北京/上海,7 个推荐岗)发现两条断层:

1. **赛道→subcat 捆绑太宽**:一个粗赛道把权益+固收+FOF+利率全混在一起 → 跨方向噪声。
2. **召回口径 ≠ 骨架口径**:推荐召回是「任何挂了该 sub_cat 的公司」,梯队骨架只列 GT 策展公司。
   推荐岗 vs 骨架只有 **3/7 落重合**:
   - 中欧/招商 是顶级公募做权益,却没挂「公募权益研究员」GT → 权益岗被推却不在骨架(GT 漏录)。
   - 国金是卖方券商,其资管/自营岗被打成买方 sub_cat(资管FOF/固收)串进买方池 → 不在骨架。

**这不是「subcat 不够细」(拆桶)能治的** —— 这 7 个岗没一个落在粗桶里。真正的解药是本设计的两个单元。

## 目标

- 让学生在确认页把粗赛道细化到自己真要的细分方向,推荐据此**重排**(不改召回、不藏岗)。
- 让「推出来的岗」和「梯队骨架的公司」尽量落在一起:重合度 3/7 → **≥5/7**。

## 已确认的设计决策

| # | 决策点 | 选定 |
|---|---|---|
| 1 | 取消勾选某 sub_cat 的语义 | **软信号**:不勾只降权,永不藏岗(召回不变) |
| 2 | 简历预勾来源 | **一次 LLM 判定**,复用现有 direction analysis 那步,不额外加延迟 |
| 3 | 预勾激进度 | **只勾最像的 1-3 个**(权益简历就勾权益,不勾固收/FOF),学生可手动加 |
| 4 | 召回口径对齐方向 | **补骨架为主 + 标注梯队外**:补 GT 漏录、保持召回宽、明显梯队外岗打标 |

## 架构 — 两个独立单元,共用确认页数据流

### Unit 1 — 两级确认选择器(B)

**1a. 数据模型**
- `ResumePreferencePayload` 增 `confirmed_sub_cats: list[str]`(学生确认页勾选的细分方向)。
- **向后兼容铁律**:`confirmed_sub_cats` 为空/缺失 = 退回现状(整赛道等权召回、不降权)。老会话、老前端 byte-identical。

**1b. 简历预勾(LLM)**
- 位置:复用方向分析(`resume_direction_analysis`)那一步,不新增一轮 LLM 往返。
- 输入:简历 profile + 学生选中赛道展开出的 sub_cat 候选清单(去重并集)。
- 输出:`suggested_sub_cats: list[str]` —— **只挑最像的 1-3 个**。Prompt 明确「宁缺勿滥,挑学生简历最直接对应的细分方向,最多 3 个」。
- 落地:写进确认页初始 payload,作复选框默认勾选态。LLM 失败兜底 = 全勾(等于现状),不阻塞确认页。

**1c. UI(确认页)**
- 每个选中赛道底下展开它的 sub_cat 复选框,默认按 1b 预勾。
- 折叠态摘要:「细分方向 · 已选 M/N」。展开可增减。
- 学生确认 → `confirmed_sub_cats` 写入 preferences。

**1d. 打分(软信号)**
- 召回**不动**(`recall_candidates` 仍按赛道全部 sub_cat 拉)。
- 打分加一档(`recommendation_v2/scoring.py`):
  - job.sub_category ∈ confirmed_sub_cats → **加权**(boost)。
  - job.sub_category ∈ 赛道展开集但 ∉ confirmed → **降权**(penalty)。
  - confirmed 为空 → 无加减(现状)。
- boost/penalty 量级在实现时定标(小幅,确保「未勾方向」整体下沉但不归零)。

### Unit 2 — 召回口径对齐

**2a. 补骨架(GT 补全)**
- audit 脚本:扫「非 GT 公司却在某 sub_cat 有 ≥3 个 good 岗」的候选,输出清单供人工过目。
- 先手动把明显漏录的补进 `ground_truth_companies_v1.json`:中欧基金 / 招商基金 → 公募权益研究员
  (二者已是一线公募、确有权益研究,只是当初没挂这个 sub_cat)。tier 沿用其既有档位。
- 补完 `_load_gt` 的 lru_cache 需失效(重启进程或清缓存)。

**2b. 梯队外标注**
- 推荐落库 / 推荐卡数据加字段:该 job 的公司在不在它 sub_cat 的 GT 骨架内。
- 前端推荐卡小标:在 → 「梯队内」;不在 → 「梯队外机会」。
- 复用 `platform_skeleton` 的 GT 公司集合判定,**读缓存不触发 LLM**。

## 数据流(端到端)

```
简历解析
  → 方向分析  [新增: LLM 预勾 suggested_sub_cats]
  → 确认页    [新增: 两级 sub_cat 勾选, 默认按预勾]
  → 学生确认  → preferences.confirmed_sub_cats
  → 推荐召回  (不变, 按赛道全 sub_cat 召回)
  → 打分      [新增: confirmed 加权 / 未勾降权]
  → 落库      [新增: 打「梯队内/外」标]
  → 前端: 推荐卡(带梯队内外标) + 梯队骨架(补 GT 后更厚)
```

## 组件 / 待改文件(指引,非最终清单)

- `backend/app/services/resume_copilot/`:preferences payload 加字段;direction analysis 加预勾;
  dispatcher 把 confirmed_sub_cats 传进打分。
- `backend/app/services/phase_g/recommendation_v2/scoring.py`:confirmed 加权/降权一档。
- `backend/data/ground_truth_companies_v1.json`:补中欧/招商 → 公募权益研究员。
- `backend/scripts/phase_g/`:GT 漏录 audit 脚本(新)。
- `resume-copilot-web/components/resume-copilot/confirm/`:两级勾选 UI。
- `resume-copilot-web/.../workspace/`:推荐卡「梯队内/外」小标。

## 错误处理 / 边界

- LLM 预勾失败 → 默认全勾(= 现状),不阻塞确认页。
- confirmed_sub_cats 含赛道外的 sub_cat(脏数据)→ 打分时忽略,不报错。
- 学生一个都不勾 → 视为「该赛道不细化」= confirmed 为空 = 现状(全召回不降权),不是「啥都不推」。
- GT 补全只增不删,且只补「明显是该 sub_cat 头部/次头部却漏录」的,不引入争议公司。

## 测试

- 单测:打分函数在 confirmed=空 / confirmed 命中 / confirmed 未命中 三种下的加减权;预勾兜底全勾。
- 端到端验证:重生成 session 146 同 persona →
  - 重合度 3/7 → **≥5/7**(中欧/招商补 GT 后落骨架);
  - 国金 FOF/固收(未勾方向)被降权排到尾部、卡上标「梯队外机会」;
  - confirmed 为空的老路径结果与改前一致(回归)。

## 不在本设计内(YAGNI / 留后)

- **C 轻量拆桶**(行研·TMT-医药-周期 / 卖方·消费医药周期 拆细):诊断证明它治的是另一类学生
  (明确想做医药却被塞 TMT/周期),不治本设计的症状。留后单独评估。
- 私募补爬:已确认本季节性无招聘,降级机会性补爬,产品侧显示「本季暂无招聘」。
- 收召回到 GT-only:会缩刚扩的池子,不采纳。
