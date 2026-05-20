# Mock Interview 反馈系统 — Day 8 计划 (2026-05-21)

> 上接 `docs/mock-interview-feedback-redesign-plan-2026-05-20.md` (Day 1-7 已完成)。本 Day 8 基于 **SAIF 历年就业报告 (2024/2025届 MF) 的真实就业数据** 升级 persona 矩阵, 并修 v3 baseline 暴露的 3 个 bug, 再跑增量 baseline 给学院老师看 v4 数据。
>
> **核心动机**: v1 那 20 个 persona 是凭老师口头反馈 + 我的金融通识造的 — Day 8 P1 解析就业报告发现 4 个数据偏差 (管培 underweight / S&T 缺失 / 文科占比偏多 / 大宗能源 overweight), 必须按真实数据校准, 学院老师拿到 v4 才会觉得 "你测的学生就是我们的学生"。

---

## 1. 背景 — Day 1-7 已完成 (回顾)

| | 输出 | 链接 |
|---|---|---|
| Day 1-2 | 20 个 persona + 改前 baseline + 4 smoking gun 诊断报告 | `docs/eval-full-loop-reports/mock_interview_baseline_pre_2026_05_20.md` |
| Day 3-4 | scoring + 反馈守卫 + LLM 沉默 fallback (5 处生产代码改 + 32 单元测试) | commit `3a804af` |
| Day 7 | v3 改后 baseline + SAIF 对照报告 (10 行硬指标 + 5 case study) | `docs/eval-full-loop-reports/mock_interview_post_2026_05_20.md` |

**v3 已达成**: 强弱档倒挂修复 (-15 → +12.5), dim spread 5.6 → 18.6, "同期候选人" 对照线 0% → 65%, LLM 沉默失败 5% → 0%, fab-quote 严重 case 80% → 25% suppress。

**Day 5/6 (后端 retry endpoint + 前端 v2 灰度页)** 故意暂停 — 不影响反馈质量, 等内容层 (Day 8) 修完再做。

---

## 2. SAIF 就业报告关键数据 (Day 8 P1 解析结果)

### 2.1 数据源 (飞书云盘 `Jobcopilot/就业报告/`)

| 报告 | 状态 |
|---|---|
| 2023届 MF 就业报告.pdf | 图片版, pypdf 抽不出文本, 跳过 |
| **2024届 MF 就业报告.pdf** | ✓ 解析完 (80 人) |
| **2025届 MF 就业报告.pdf** | ✓ 解析完 (86 人) |

### 2.2 关键数据 (2025届 — 距今最近, 权重最高)

**整体 MF (86 人, 75 国内 + 8 境外 + 3 创业/读博)**:

| 维度 | 分布 |
|---|---|
| **本科院校** | C4 (清北交复) **75%** / 其他 C9 3% / 其他 985-211 13% / 境外 9% |
| **本科专业** | 经管 50% / 理工 48% / **文科 2%** |
| **行业** (Industry) | 资管 45 / 投行券商 14 / 实业 14 / 科技互联网 10 / 商业政策银行 9 / **监管 6** / 其他 2 |
| **职能** (Function) | **投研 43 / 管培 26 / 咨询战略数据 9 / S&T 9 / 投行 8 / 其他 5** |

**MF-General 子集**:
- 院校: C4 73% (略低), 境外 13%
- 专业: 经管 72 / 理工 25 / 文科 3
- 职能: **投研 40 / 管培 33 / 投行 11 / 咨询战略数据 8 / S&T 6 / 其他 2**

**MF-FinTech 子集**:
- 院校: C4 77% (略高于整体)
- 专业: **理工 87% / 经管 13%** (理工绝对主导)
- 职能: **投研 50 / S&T 14 / 管培 14 / 数据科学开发 11 / 其他 11**

### 2.3 vs Day 1 我之前的估计, 4 个偏差最大的

| 赛道 | 我之前 plan 假设 | 真实 2025届 | 修正方向 |
|---|---|---|---|
| **管培** | "MF-G 33%, 看一下" | **整体 26% / G 33% / FT 14%** = 第 2 大职能 | ⚠️ underweight, 当前 P4 1 个 (5%), 应 4-5 个 |
| **S&T 销售交易** | "MF-FT 14%, 应补" | **整体 9% / G 6% / FT 14%** 完全正确 | ⚠️ 当前 0 个 |
| **文科** | "weak 案例" | 实际只 2% (全班可能就 1-2 人) | ⚠️ 当前 M6 占 5%, 是真实比例的 2.5 倍 |
| **大宗能源** | "8 大赛道之一" | 实业 14% 主要是 corp finance / M&A, 不是大宗 | ⚠️ P8 当时挑的特定 case 实际不存在 SAIF 流向 |

### 2.4 之前估对的 (不动)

- 投研 (买/卖) 43-50% → 当前 7 个 (35%) 略低但可接受
- IBD 8-11% → 2 个 (10%) ✓
- 量化 → 2 个 (10%) ✓
- 100% 985 以上 → 现状无双非 ✓
- 弱档应该极少 (老师 1: "MF 基本都有对口 1-2 段") → 当前 weak 30% 包括极端档过多

---

## 3. Persona 升级方案 (基于真实数据)

**改造 6 个旧 persona** (现实化, 不极端 → 真实弱):

| ID | 旧设定 | 新设定 | 改造目的 |
|---|---|---|---|
| **M6** (weak 文科) | 北外法学 + **0 金融实习** | 北外法学 + 1 段金杜资本市场组 + 1 段券商资管协助岗 | 现实型 weak: 实习不对口但不为零 |
| **M8** (weak 工科) | 天大机械 + 0 金融实习 | 同校同背景 + 1 段中信汽车研究助理实习 | 跨专业 mid (不再算 weak) |
| **P8** (mid 大宗能源) | 大宗能源 + PVSyst 编数字 | 改为 **顶级阳光私募 (高毅级) 研究员** 或 **总行 IBD/FICC** | 替换为 SAIF 真实头部去向 |
| **M4** (mid 咨询转金融) | 战略咨询 → 转金融 mid | **升级为 P9 strong** — BCG/MBB FS practice 中型 case | 升 strong, 覆盖头部学生跳板路径 |
| **M11** (extreme 跑题) | 化工本 + target 公募行研 | 化工本 + target **corp dev / M&A** + 0 转译 | 保留跑题极端度但更真实 (target 至少跟实业相关) |
| **M12** (extreme 翻译腔) | 曼大本 + 翻译腔简历 | SAIF FT 海归 + 1 段海外 S&T intern + 翻译腔**说话风格** | 改成"内容 OK 但表达极弱"案例 |

**新增 4 个 persona** (补真实数据缺漏):

| ID | 类型 | 背景 | 覆盖 |
|---|---|---|---|
| **M13** | 管培 strong | 中信集团总部管培 / 招行总行总管培 (财大本金融 + SAIF MF-G) | MF-G 33% 管培大头 |
| **M14** | 管培 mid | 平安/兴业 总行管培 (中财本 + SAIF MF-G) | 管培 mid 池 |
| **M15** | S&T 销售交易 | MF-FT 数学本 + 1 段中信 FICC 衍生品 + 1 段交易系统开发 | MF-FT 14% S&T 大头 (当前 0 个) |
| **M16** | 监管 / 体制内 | 北大法学 + SAIF MF-G + target 人行/上交所/中投 | MF-G 10% 监管/政府路径 |

**保留 10 个不动** (核心匹配, 不再生成):
- P1 (公募行研 strong, 清华+中信+易方达) / P2 (卖方 TMT) / P3 (私募/资管基本面) / P5 (IBD) / P6 (量化九坤) / P7 (FinTech 数据)
- M1 (中欧大消费 mid) / M2 (卖方消费医药 mid) / M3 (IBD 中型券商 mid) / M5 (FT 数据 mid)

**保留极端档 4 个** (守卫试金石 — 不算分布数):
- M9 套模板 STAR / M10 编数字 / **改造后的 M11 跑题** / **改造后的 M12 翻译腔**

**新总数**: 20 → 20 + 4 = **24 个 persona** (其中 6 个 schema 改, 10 个新增 / 改 = 14 个待生成)

---

## 4. Day 8 任务清单 + 节奏

| Task | 干啥 | 投入 | 输出 |
|---|---|---|---|
| **P1** | 解析 SAIF 历年就业报告 | 已完成 (本文档 §2) | 真实数据 + 偏差分析 |
| **P2** | persona 升级方案 (本节) | 已完成 (本文档 §3) | 24 persona 调整方案 |
| **P3** | **subagent 并行生成 10 persona** (6 改 + 4 新) | ~30 min subagent | `mock_interview_2026_05_20/{M6,M8,M11,M12,M13,M14,M15,M16}.json` 改/新 + `workspace_2026_05_20/{P8,M4→P9}.json` 改 |
| **P4** | 增量 baseline v4 (只跑改/新 14 个 × 6 题 + 4 个 strong control = 18 个) | ~$2 + ~20 min | `_out/mock_interview_post_v4_2026_05_21.json` + 增量对照报告 |
| **P5** | 顺手修 v3 暴露的 3 个 bug (并行做) | ~3 小时代码 + ~$2 测试 | 见下面 §5 |

---

## 5. v3 暴露的 3 个 bug + 修法 (Day 8 P5)

### Bug A — 弱/极端档分数仍偏高 (M9/M10/M12 在 80-87 区间)

**症状**: M9 套模板 80, M10 编数字 80, M12 翻译腔 87 — 应该 ≤25。LLM 倾向"看不到证据就给鼓励分"。

**修法** (`prompts/scoring_system.md` + `report.py` 后处理):

1. **`info_selection / logic` 维度内嵌**模板词检测器:
   - prompt 加 "**模板词触发器**" 段, 列举"主导/复盘/沉淀/赋能/闭环/抓手/打法/心智" 等 12 个词, 候选人答里出现 ≥3 个 → 该维度强制 ≤ 3
2. **`logic / industry_sense` 维度内嵌**翻译腔检测器:
   - "leveraged synergies / 端到端价值闭环 / 颠覆性洞察输出 / 跨职能协同 / 价值驱动" 等 8 个直译模式 → 这两个维度强制 ≤ 3
3. **`job_fit` 维度内嵌**跨专业 mismatch 检测:
   - target track 是金融岗, 答里 80%+ 内容都是工程/化学/物理术语 (无任何金融转译) → 该维度强制 ≤ 3

实现位置: 后处理 (parse 完 LLM 输出后, 用 regex 在 transcript 上跑模式检测, 命中则 cap 维度)。**不重生成**, 只 cap。

### Bug B — 4 段 improvements 格式 LLM 完全不遵循 (0% 合规)

**症状**: prompt 要求 `[扣分点] [行业坐标] [改写示范] [下一步]` 4 段, v3 跑 20 个 0 合规。LLM 总把 4 段合并成 2-3 段散文。

**修法**: 把 4 段拆成 **4 个独立 JSON 字段**, 不再用文本拼接的 inline markers:

```json
"improvements": [
  {
    "deduction": "你在第 2 题主导项目时, 说『我们 PM 是这么看的』...",
    "cohort_anchor": "同期头部公募大消费组的实习生通常会给出『市场看 A 我看 B』...",
    "rewrite_demo": "可以改成『市场担心高端白酒批价, 我独立测算认为次高端...』",
    "next_step": "找 1 只覆盖股, 写 1 篇 200 字独立 view, 这周内做"
  }
]
```

UI 端拿到 list[dict] 后渲染 4 个段落框, 比 inline 拼接更结构化。后端 parse 加 schema 校验, 任一字段缺 → suppress 该 improvement。

**前后端契约改动**: 影响 `resume-copilot-web/components/interview/Report.tsx` (待 Day 6 灰度页时一并改)。

### Bug C — fab-number 守卫误判面广 (17/20 报告强制 credibility=30)

**症状**: 候选人说"茅台 2700" 这种合法引市场价, 也被压可信度。当前强信号判断 (`万/亿` 量词 / sharpe / 年化 +N%) 太宽。

**修法**: 强信号判断**收紧到"实习生身份不可能 own 的体量"共现**:

- 数字 + 量词同时出现 + 候选人主语含 "我" / "我独立" / "我 own" / "我覆盖" / "我搭建" 才算编数字
- 否则只 annotate 不 cap

新检测函数 `_is_owned_extreme_fab(transcript, num)`:
```python
def _is_owned_extreme_fab(transcript, num):
    # 找数字周边 30 char 窗口
    # 同时出现: (我|独立|own) + (亿|万|sharpe|年化) → 强信号
    # 否则: 只 annotate, 不 cap credibility
```

预期效果: P1 林思远引"茅台 2700" 不再被压 cred=30; M10 "我 own 80 亿欧元" 仍命中。

---

## 6. 增量 baseline v4 设计 (Day 8 P4)

### 6.1 跑哪些 persona

**不跑全 24 个** (省 $2 + 20 min 也是钱), 只跑:

- **6 个改造**: M6 / M8 / P8 / M11 / M12 + M4→P9 (验证改后分数合理)
- **4 个新增**: M13 / M14 / M15 / M16
- **4 个 strong control**: P1 / P2 / P5 / P6 (检 regression, 不应该突然降)

合计 **14 persona × 6 题 = 84 答题** + 14 报告。预估 18-22 min, ~$2.

### 6.2 不动的 10 个继承 v3 数据

P3 / P7 / M1 / M2 / M3 / M5 / M9 / M10 + 实际不变的 + control. 直接从 v3 JSON 拼接进 v4 对照报告。

### 6.3 v4 vs v3 对比报告

新文档 `docs/eval-full-loop-reports/mock_interview_post_v4_2026_05_21.md`, 8 行硬指标新加 2 列 (v3 / v4), 标识改动来源 (persona 升级 vs bug 修法各贡献多少分数变化)。

---

## 7. 量化目标 (验收线)

| 指标 | 改前 (Day 2) | v3 (Day 7) | **v4 目标** |
|---|---|---|---|
| **强档 P1/P2/P5/P6 平均** | 65 / 87 (剔 P1 失败) | 89 | ≥ 85 (control, 不应降) |
| **弱档 M6/M8 平均** | 85.5 | 71 | ≤ 60 (M6 改造后更现实, 应 50-60) |
| **极端档 M9/M10/M11/M12 平均** | 80.25 | 78 | ≤ 40 (Bug A 模板/翻译腔强制扣分) |
| **强 vs 弱 spread** | 1.5 | 10.75 | ≥ 25 |
| **强 vs 极端 spread** | -15 | +12.5 | ≥ 45 |
| **5 维 dim spread** | 5.6 | 18.6 | ≥ 18 (维持) |
| **管培 persona 实际 score 区间** (新 M13/M14) | n/a | n/a | strong M13 ≥ 80, mid M14 70-80 |
| **S&T persona 实际 score** (新 M15) | n/a | n/a | mid 65-80 |
| **监管 persona 实际 score** (新 M16) | n/a | n/a | mid 60-75 |
| **fab-number 误伤率** (cred=30 但实际不该) | n/a | 60% (12/20 误伤估计) | ≤ 10% |
| **4 段 improvements 字段合规率** | n/a | 0% | ≥ 90% (强制 JSON schema) |

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Subagent 生成的 4 个新 persona 不够真实 / 跟现有 persona 类似 | 给 subagent 喂就业报告 §2 数据 + 老师反馈原文 + 已有 8 P 的范例; 抽检 4 个新 persona 前不开 P4 baseline |
| Bug A 模板词检测误伤"真正主导过项目"的强档候选人 | 触发阈值 ≥3 次模板词 (不是 1 次); 给 P1/P5 等强档跑 control 验证不会被打低 |
| Bug B 4 段 JSON schema 改动牵动前端 | 后端先做向后兼容 (老 list[str] + 新 list[dict] 双格式输出), 前端 Day 6 灰度页一并升级 |
| Bug C 收紧后 M10 编数字不再触发 cap | 测试用例已加 (`_is_owned_extreme_fab(M10_transcript)` 必须返 true) |
| v4 跑分发现新 persona 分数全偏低/偏高 (LLM 偏见) | 不删 persona, 只调 prompt 收紧或松开扣分规则 (5-10 min 调一轮再跑 sub-baseline) |
| 5/19 XHS 那个 alembic migration 还没合 (导致 startup hang) | Day 8 范围不动, 已临时 park 到 `/tmp/`; 后续 XHS 主线负责合并 |

---

## 9. 已锁决策 + 待你决定

| 决策项 | 选定 | 备注 |
|---|---|---|
| **数据源权重** | 2025届 > 2024届 > 老师口述 | 2025最新; 2023 图片版抽不出忽略 |
| **管培 persona 占比** | 4-5 个 (新增 M13 strong + M14 mid 至少) | 真实 26-33%, 不能再只 1 个 |
| **S&T persona 占比** | 至少 1 个新 (M15) | 真实 9-14%, 当前 0 |
| **监管 persona 占比** | 1 个新 (M16) | 真实 6-10%, 当前 0 |
| **大宗能源 P8** | 改造成阳光私募 OR 总行 IBD | 真实流向接近 0 |
| **极端档保留** | 4 个保留 (M9 / M10 / M11 改 / M12 改) | 守卫试金石, 不算分布数 |
| **subagent 并行度** | 建议同时跑 3 个 subagent 各生成 3-4 个 persona | 节省 ~15 min wall time |
| **增量 baseline 范围** | 14 个 (6 改 + 4 新 + 4 control), 不跑不变的 10 个 | 省 $2 + 20 min |
| **Bug A 检测词清单** | 模板 12 个 + 翻译腔 8 个 + 跨专业 mismatch 1 类 | 见 §5 Bug A |
| **Bug B JSON schema** | 4 个独立字段, 前端 Day 6 灰度页一并改 | 后端先双格式输出 |
| **Bug C 强信号** | "我 / 独立 / own" + 万/亿/sharpe 共现 | 见 §5 Bug C |

### 待你决定 (3 个开放问题)

1. **新 M16 监管/体制内 persona 的 target** — 选人行 / 上交所 / 中投三者中哪个为主? 建议 **人行总行** (SAIF 二线学生最常见保底 + 公考类)
2. **P8 大宗能源** — 选 "阳光私募高毅级" 还是 "总行 IBD/FICC"? 前者补足顶级买方私募, 后者补足 IBD 二三档。建议 **阳光私募** (头部去向, 数据 cohort 用)
3. **M4 升级为 P9 strong 的具体 case** — 选 BCG/Bain FS practice 还是 McKinsey 战略组转金融? 建议 **McKinsey 战略组** (XHS / Linkedin 上 SAIF 转金融最常见路径)

---

## 10. 节奏 (建议 1 天内做完)

| 时段 | 干啥 | 时间 |
|---|---|---|
| 早 | P3 subagent 并行生成 10 persona (6 改 + 4 新) | 30-40 min subagent (你回邮件期间) |
| 早→午 | 抽检 4 个新 persona + 修明显问题 (subagent 偏离时手改) | 20 min |
| 午 | P5 写 Bug A + B + C 的代码 + 单元测试 | 90 min |
| 午→晚 | P4 跑增量 baseline v4 (14 persona × 6 题) | 20-25 min wall |
| 晚 | 写 v4 对照报告 + import 飞书 03_eval-2026-05-20-mock-interview/ (顺手补 Day 7 的相邻条目) | 30 min |
| 晚 | 顺手 commit 全套 (3 个 commit: persona 升级 / Bug 修法 / v4 对照报告) | 10 min |

**全 Day 8 总投入估计**: 3-4 小时代码 + ~$3 LLM + 1 小时报告写作 = 半个工作日。

---

## 11. 上 / 下游协调

**上游 (Day 5/6 暂停, 等 Day 8 完)**:
- Day 5: 后端 `POST /api/interview/sessions/{id}/retry` endpoint
- Day 6: 前端 `/interview/v2` 灰度页 + 4 段 improvements UI (Bug B 配套)

**Day 9+ (按学院老师反馈定优先级)**:
- Day 9: 真实 SAIF 学生试用 + 收 1 轮老师反馈 (人在场)
- Day 10: 上线 v2 (灰度 → 全量)
- Day 11+: 持续 prompt 调优 / 加 anchor / 同期数据扩展

---

## 12. 文档 + 数据沉淀路径

| 内容 | 写到哪 |
|---|---|
| 本计划 | `docs/mock-interview-feedback-redesign-plan-2026-05-21.md` |
| 改/新 persona JSON | `backend/tests/eval/personas/{mock_interview,workspace}_2026_05_20/*.json` |
| Bug A/B/C 代码 | `backend/app/services/interview/{scoring,report}.py` + `prompts/scoring_system.md` |
| v4 baseline 数据 | `backend/tests/eval/_out/mock_interview_post_v4_2026_05_21.json` |
| v4 vs v3 对照报告 | `docs/eval-full-loop-reports/mock_interview_post_v4_2026_05_21.md` |
| 飞书云盘 | `Jobcopilot/03_eval-2026-05-20-mock-interview/` (复用现有, 不开新文件夹 — 同一个 mock interview 改造迭代) |
| 单元测试 | `backend/tests/test_{scoring_service,interview_service}.py` (新增 5-8 个 case) |
| Memory | 不动 (skill `jobradar-lark` + reporting style 都已 sticky) |

---

## 附录 — 引用

- Day 1-7 设计原文: `docs/mock-interview-feedback-redesign-plan-2026-05-20.md`
- 改前 baseline 诊断: `docs/eval-full-loop-reports/mock_interview_baseline_pre_2026_05_20.md`
- v3 改后对照报告: `docs/eval-full-loop-reports/mock_interview_post_2026_05_20.md`
- Canonical 8 赛道树: `docs/finance-tracks-2026-overview.md`
- SAIF 就业报告 PDF: 飞书云盘 `Jobcopilot/就业报告/` (2024届 + 2025届 解析完, 2023届 图片版跳过)
- 飞书云盘 skill: `~/.claude/skills/jobradar-lark/SKILL.md`
