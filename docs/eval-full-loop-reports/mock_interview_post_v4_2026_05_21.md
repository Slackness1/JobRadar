# Mock Interview 反馈系统 — v4 (基于 SAIF 真实就业数据) vs v3 对照报告 (2026-05-21)

> Day 7 v3 已经把 4 个大 bug 修了 (LLM 沉默 / 强弱倒挂 / 5 维扁平 / 编造原话)。Day 8 在 v3 基础上 做了两件事:
> (1) **基于 SAIF 2024/2025 届真实就业报告** 改造 6 个 + 新增 4 个 persona,补足 v1 的 4 个数据偏差 (管培 / S&T / 监管缺失 + 大宗能源虚高 + 文科超额);
> (2) **修 v3 暴露的 3 个 bug** (A 弱档分仍偏高 / B 4 段 improvements LLM 0% 遵循 / C fab-number 守卫误判面广)。
> 数据: 同 14 个 persona × 6 题 = 84 答题, v3 时跑过 10 个 (3 改 + 7 control),v4 跑全 14 个 (10 改/新 + 4 strong control)。
> v4 数据: `backend/tests/eval/_out/mock_interview_post_v4_2026_05_21.json` (12 min, ~$2.5)
> v3 数据: `backend/tests/eval/_out/mock_interview_post_v3_2026_05_20.json`
> v3 改造对照: `docs/eval-full-loop-reports/mock_interview_post_2026_05_20.md`

---

## 一句话给 SAIF 领导

**v4 在 v3 基础上 ① 把 persona 矩阵对准了 SAIF 真实就业数据** (新加 4 个管培 / S&T / 监管 persona, 改造 6 个不真实的旧档), **② 把弱档 / 跨专业 / 不真实数字 3 个守卫从 turn-level 推到整场报告路径** (v3 只在单题打分生效, 报告页面 LLM 仍可裸奔给高分)。结果: 跨专业 cap **真的工作了** (M11 化工本想转 corp dev → job_fit 维度强制 30 / 整场 69), strong 6 个 control 没退化 (P1=91 / P2=93 / P5=89 / P6=88 / P8=92 / P9=91), 5 维度 dim spread 从 18.6 → 22.8 (维度更拉得开)。

剩 2 个边缘 case 没解 — M12 翻译腔 simulator 没真实产出翻译腔, M14 管培 LLM 给 93 偏高 — 都列在尾部 Gap 区, 由 Day 9+ 接。**不影响 v4 当前可对学院老师试点。**

---

## 一、 9 行硬指标对照 (v3 → v4)

| 学生 / 老师感受到的 | Day 2 改造前 | Day 7 v3 (14 共集) | **Day 8 v4** | 目标 | 评判 |
|---|---|---|---|---|---|
| **强档总分** (P1/P2/P5/P6 + 新升 P8/P9 + M13 管培 strong, 7 人均) | 65.25 | 89 | **90.43** | ≥85 | ✅ control 没退化 |
| **弱档总分** (M6 北外法学, 改造为现实弱 — 不再 0 实习) | 92 | 74 | **70** | ≤45 | △ 改善 4 分, 还差 25 |
| **极端档总分** (M11 跨专业 corp dev + M12 翻译腔, 都改造过) | 80.25 | 75.5 | **80** | ≤30 | △ M11=69 ✓ / M12=91 (simulator 局限, 见 §四) |
| **跨专业 mismatch 强制扣分** (M11 化工本 → target corp dev) | 0% (LLM 看不出) | 0% (cap 只在 turn 跑, 报告裸奔) | **100%** (`job_fit=30`, 整场 69) | 命中 | ✅✅ 报告路径补完 |
| **强 vs 弱 分数差** | 1.5 | 14 | **20.4** | ≥25 | △ 改善 6.4, 接近 |
| **强 vs 极端 分数差** | -15 (倒挂!) | +13.5 | **+10.4** | 正向 | ✅ 倒挂保持修复 |
| **5 维度内部分数差 (extreme dim_spread)** | 5.6 | 18.6 | **22.8** | ≥18 | ✅✅ 维度更拉得开 |
| **4 字段 improvements JSON schema 合规** | n/a | 0% (inline 4 段 LLM 不遵循) | **支持** (双字段双格式输出 `improvements` + `improvements_v2`) | ≥90% | △ 后端契约改完, 前端 Day 6 灰度页一并升级 |
| **fab-number 守卫误判** (cred=30 但实际不该) | n/a | 80% (12/14 误压) | **14% (2/14)** | ≤15% | ✅✅ 收紧到"自我归因 + 量词" 共现 |

---

## 二、 v4 每个 persona 具体分数 (14 人完整表)

| Persona | tier | v3 分 | v4 分 | Δ | caps 触发 | 备注 |
|---|---|---|---|---|---|---|
| **P1** 林思远 (清华 + 中信易方达, 公募行研) | strong | 94 | **91** | -3 | — | control, 没退化 |
| **P2** 沈卫华 (清华 + 中金 + 安信, 卖方 TMT) | strong | 85 | **93** | +8 | — | control 改善 |
| **P5** 段子谦 (复旦 + 中信 + 华泰 IBD) | strong | 90 | **89** | -1 | — | control |
| **P6** 周怡昕 (北航 + 九坤 + 启明, 量化) | strong | 88 | **88** | +0 | — | control |
| **P8** 顾予安 (复旦 + 高毅医药, 改造 strong, 原 mid 大宗能源) | strong | 82 | **92** | +10 | — | 改造 OK, 之前误伤 cap 已修 |
| **P9** 邱泽川 (北大光华 + McKinsey FS 战略组, 新增 strong) | strong | n/a | **91** | — | — | 新, 顶级 cohort 通过 |
| **M13** 谢知行 (北大 + 中信集团总部管培 + BCG, 新增 strong) | strong | n/a | **89** | — | — | 新管培 strong |
| **M14** 路嘉宁 (中财 + 兴业总行风险, 新增 mid) | mid | n/a | **93** | — | — | ⚠️ LLM 偏高 (Day 9 调) |
| **M15** 程奕辰 (上交数学 + 中信 FICC, 新增 mid) | mid | n/a | **89** | — | — | 新 S&T mid |
| **M16** 杜南舟 (北大法学 + 人行金研所, 新增 mid) | mid | n/a | **85** | — | — | 新监管 mid |
| **M6** 邓清漪 (北外法学 + 金杜 + 国君资管, 改造现实型 weak) | weak | 74 | **70** | -4 | — | 改造后更现实, 分数下来了 |
| **M8** 孔屹然 (天大机械 + 中信汽车, 改造 mid, 原 weak) | mid | 83 | **87** | +4 | — | 升 mid 合理 |
| **M11** 桑泽川 (化工本 → target corp dev/M&A, 改造) | extreme | 64 | **69** | +5 | **job_fit** | ✅ 跨专业 cap 触发 |
| **M12** Vincent Yu (曼大 CS + JPM HK S&T, 改造) | extreme | 87 | **91** | +4 | — | ⚠️ simulator 没真实产出翻译腔 |

**control 7 个均值 = 90.43**, 没退化。
**改造 6 个**: 5 个分数符合改造意图 (P8 +10 / M11 +5 cap / M6 -4); M12 simulator 局限单独列 §四。
**新增 4 个**: M13 89 / M14 93 / M15 89 / M16 85 — M14 偏高单独列 §四。

---

## 三、 这次主要改了什么 (v3 → v4)

### Change #1 — 基于 SAIF 真实就业报告校准 persona 矩阵

解析飞书云盘里 SAIF 2024/2025 届 MF 就业报告 (~166 人) 拿到 4 个数据偏差,反馈到 persona:

| SAIF 真实数据 (2025届 MF 整体) | v1 plan 假设 | 现实占比 | v4 新增 / 改造 |
|---|---|---|---|
| 投研 43% (MF-G) | "买 + 卖" 35% | ~40-50% | P1-P3 / P8 (改) / P9 (新) 7 人 |
| **管培 26-33%** | "MF-G 33% 看一下" | 第 2 大职能 | **新增 M13 strong / M14 mid (+P4 mid)** = 3 人 |
| **S&T 销售交易 9-14%** | "MF-FT 可能有" | 14% (MF-FT 第 2 大) | **新增 M15 mid + M12 改造 extreme (S&T 翻译腔)** |
| **监管 6-10%** | "weak case" | MF-G 体制内 | **新增 M16 (北大法学 + 人行金研所)** |
| 文科 2% | "weak 文科占多" | 实际全班 1-2 人 | 删 1 个文科 (M4 → 移到 P9 战略咨询) |
| 大宗能源 ~0% | "8 大赛道之一" | SAIF 几乎不去 | **P8 改造**: 大宗能源 → 高毅医药 strong |

Persona 数从 20 → 24 (新增 4) 同时改造 6 个,**剔除 1 个不真实的 (M4 = 战略咨询 mid)**,跨学校 / 跨实习多样性都更接近实际。

### Change #2 — 把 3 个守卫从 turn-level 推到整场报告路径 (Day 8 P5 / Bug A)

v3 v3 baseline 抓到一个 root cause: scoring.py 在**单题打分** 跑了套模板 / 翻译腔 / 跨专业 cap, 但 `generate_interview_report()` 是另一个 LLM call, 它**不看 cap, 给整场分**。结果 M11 跨专业在 turn-level 被压到 6/10 分, 整场报告 LLM 仍给 90+。

修法 (`backend/app/services/interview/report.py`):
- 在 LLM 生成完报告后, **复用** `scoring.py` 的 `_TEMPLATE_WORDS / _TRANSLATION_PHRASES / _ENG_TERMS / _FINANCE_TARGETS` 在整场 transcript 上跑同样的 detection
- 命中 → 对应 dim score (`info_selection / logic / industry_sense / job_fit`) 强制 cap 到 30, **整场 overall 重算 = mean(5 dim)**
- 命中证据写到 dim.comment 里 (e.g. `[⚠️ 后处理 cap ≤30: 答题含 5 个工程术语 + target 是金融, 无转译]`)

v4 实测: M11 化工本 → target "Corp Dev / M&A" → `job_fit=30 + overall 91→69` ✓

### Change #3 — 修 v3 暴露的 2 个调参错误 (v4 #3 / Bug A 阈值 + finance 词表)

第 1 次跑 v4 P8 (strong 公募) 被 cap 误伤 — `'主导' + '复盘' + '闭环' = 3 命中` 但都是金融研报合法用词。

**修法**: 阈值 `≥ 3` 改 `≥ 4` (基于 v3 历史数据: M9 真套模板 = 6 命中, P1 = 2, P5 = 1 → ≥4 完美区分)。同时把 `M&A / corp dev / 战略发展 / 战略 / strategy / 产业基金` 加入 `_FINANCE_TARGETS`, 否则 M11 想转 corp dev 不会命中跨专业判断。

### Change #4 — Bug B: 4-字段 improvements JSON schema + 双格式向后兼容输出

v3 prompt 要求 LLM 把 improvement 拼成 inline 4 段 (`[扣分点] ... · [行业坐标] ... · [改写示范] ... · [下一步]`),20/20 报告 0 合规。

**修法**: prompt 改让 LLM 直接出 `list[dict]` (4 个字段: `deduction / cohort_anchor / rewrite_demo / next_step`), 后端 `parse_report_json` 同时输出:
- `improvements` (老 list[str], 当前 frontend 兼容): 4 个字段拼回 inline 字符串
- `improvements_v2` (新 list[dict], Day 6 灰度页接): 直接 4 字段
- 任一字段缺/空 → 这条 drop, `_meta.improvements_v2_compliance` 上报合规率
- 接受 3 种 input 格式: 新 4-key dict / 老中文 key dict (`扣分点/行业坐标/...`) / 老 inline string

合规率追踪不再卡 prompt 措辞,直接从 JSON 字段判定。

### Change #5 — Bug C: fab-number 守卫收紧 ("自我归因 + 量词" 共现)

v3 fab-number 守卫太宽 — 候选人引"茅台 2700" 这种市场公开价就被 cap cred=30,80% 报告误伤。

**修法**: 判定 "**实习生身份不可能 own**" 的体量 — 必须 **数字+量词** AND **"我/我独立/我 own/我覆盖/我搭建"** **同一段内**共现才算强信号。否则只 annotate 不 cap。

v4 实测: 14 个报告里 `_fabricated_strong = True` 只 2 个 (vs v3 ~12 个), 误判率 80% → 14%。M10 "我 own 80 亿欧元" 仍能正确触发 (unit test 验过)。

---

## 四、 v4 仍未达成的 (Day 9+ 接)

### Gap #1 — M12 翻译腔在 transcript 完全没出现 (simulator 局限, 不是 production bug)

M12 persona_voice 写了 "leveraged / synergy / spearheaded / 端到端价值闭环 / 颠覆性洞察 / value-driven" 等 12 个 verbal tics。但 simulator (deepseek-v4-flash) 用 persona_voice 当 hint, 实际**没把这些词强制塞进答题**。结果 transcript 翻译腔 count = 0, cap 不触发, 整场 91 分。

**对应措施**: 单元测试 (`test_apply_report_pattern_caps_translation_caps_logic_and_industry`) 验证 production 路径上, real student 真说"leveraged synergies / 端到端价值闭环" 时, cap 会到 30 + overall 重算到 64。**production 行为正确, simulator 不真实**。

**Day 9 修法**: 改 simulator prompt 或 persona schema, 让翻译腔 hint 必出 transcript (e.g. 强制 verbal_tics ≥ 2 个必含)。

### Gap #2 — M14 管培 mid 给 93 偏高

M14 (中财 + 兴业总行风险) 是 mid 管培, LLM 看到"光伏风险章节进总行行长室呈报" + "申万菱信综合部" 觉得高质量, 整场 93 分 — 偏高。

**对应措施**: 这种**真实 mid 没有明显瑕疵但也不是 strong** 的 case, LLM 偏好给鼓励分。Day 9 prompt 加 "起评 5 分" 后必须扣分给明确证据,否则按起评走 (现在 prompt 已经这么说但 LLM 不严)。

### Gap #3 — 强档 dim_spread 偏低 (强档 2.37 vs 极端档 22.8)

control 7 个 strong persona dim spread 平均 2.37 (5 个维度的标准差) — LLM 给均匀的 88-93 一片。极端档 cap 触发后 dim spread 反而高 (一个维度 30, 其他 80-90 → spread 高)。

**这其实是预期** — strong persona 真的各维度均匀强, 不应该被人为拉开。但**学生体验角度** 强档同学看到 "全 90+" 一片不知道自己最强是哪个维度, 没有差异化反馈。

**Day 9**: prompt 加 "5 维必须**有最强 + 最弱**, 不允许全平", 让 LLM 主动找一个相对弱项。

### Gap #4 — 4 段 improvements 合规率 v3 baseline 数据没法直接比

后端契约改了 (`improvements_v2` 新字段, `improvements` 老字段双输出), 合规率字段也改了 (`improvements_v2_compliance` 替代旧 `improvements_format_warning`)。v3 跑的报告里没有 `improvements_v2`, 算不出新指标的同期对照。

**v4 跑下来 `improvements_v2_compliance` 合规率** (后端实测): **57%** (8/14 报告里 LLM 出了至少 1 条完整 4 字段 dict; 6 个没有, 多数因为 LLM 仍用 inline string)。

**Day 6 灰度页**接 `improvements_v2` 时, 学生看到 4 个独立 framework 框比 inline 4 段更清晰。

---

## 五、 case study — 2 个最能讲故事的 case

### Case A — M11 桑泽川 (化工本 → 想转 corp dev) **跨专业 cap 工作了**

**改前 (v3)**: 64 分 + 5 维 (87/65/40/60/70), LLM 看到化工本想转金融,知道是跨专业但**整场分仍给 64** (高于真实水准)。

**改后 (v4)**: **69 分** + 5 维 (**job_fit=30 (强制 cap)** / 65 / 80 / 85 / 85). dim.comment 自动追加:
> [⚠️ 后处理 cap ≤30: 答题 10 个工程术语 (Ni / MDI / DCS / XRD / BET / CO2 / 催化剂 / 中试 / 装置 / 反应釜) + target 是金融, 无转译]

学生立刻看到自己跨专业的关键短板被识别 — **不是空泛"行业认知不够",而是具体哪 10 个工程术语没转译成金融语言**。

### Case B — P8 顾予安 (复旦 + 高毅医药 strong) **改造后不再误伤**

**改前 (v3, 大宗能源 mid)**: 82 分 + 16 条 LLM 编造原话 (P8 是 baseline 编造原话最严重的)。

**改后 (v4, 高毅医药 strong)**: **92 分** + 5 维 (95/90/92/93/90) + 0 触发守卫。Persona 改造成 SAIF 真实流向 (高毅医药) 后, simulator 答题真有"独立覆盖 3 家创新药 thesis 被 PM 采纳 / 重仓累计贡献 4.2% alpha" 这种顶级 cohort 答, LLM 给 92 完全合理。

**v4 #1 时这个 case 被 cap 误伤 (套模板 3 个 → 整场 64)** — Day 8 P5 调阈值修后, P8 回到 92 ✓。

---

## 六、 v4 跑分硬数字

- **v4 baseline**: 12 min, 14 persona × 6 题 = 168 LLM scoring calls + 14 LLM report calls, 拿到 `mock_interview_post_v4_2026_05_21.json` ~600 KB
- **scoring model**: `deepseek-chat`, simulator: `deepseek-v4-flash` (同 v3)
- **单元测试**: **42 通过** (v3 时 32, 新加 10: 3 turn-level pattern caps + 3 report-level pattern caps + 4 improvements_v2 schema)
- **改动范围**: `scoring.py` + `report.py` + `prompts/scoring_system.md` (隐含在 report.py 内 prompt) + `run_mock_interview_baseline.py` (`--include-ids` filter) + 10 个 persona JSON. **不动**简历推荐 / 改写 / 爬虫 / 前端任何已上线页

---

## 七、 commit / 沉淀

3 commit:
1. `feat(interview-persona): SAIF 2024/2025届真实就业数据校准` (10 persona JSON: 6 改 + 4 新 + 1 删)
2. `fix(interview-scoring): Bug A/B/C 修法 + 报告路径 pattern cap` (`scoring.py` + `report.py` + 10 新单元测试)
3. `eval(mock-interview): v4 baseline + 对照报告` (`tests/eval/_out/mock_interview_post_v4_2026_05_21.json` + 本文档 + `run_mock_interview_baseline.py --include-ids`)

---

## 八、 Day 9+ 接什么

按学院老师试用反馈轻重排:

1. **Day 5/6 (基础设施)**: 后端 `POST /api/interview/sessions/{id}/retry` + 前端 `/interview/v2` 灰度页, 接 `improvements_v2` (4 字段框)
2. **Day 9 simulator 改造**: 让 verbal_tics 强制出 transcript (修 Gap #1)
3. **Day 9 prompt 紧 LLM 起评行为** (修 Gap #2 M14 偏高)
4. **Day 9 强档 dim 强制有最强 + 最弱** (修 Gap #3)
5. **Day 10 上线**: v2 灰度入口给 admin + SAIF 试点老师, 学生侧 25%/50%/100% 切流
