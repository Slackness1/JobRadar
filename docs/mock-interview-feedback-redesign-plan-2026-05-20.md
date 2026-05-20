# Mock Interview 反馈夯实计划 — 2026-05-20

> 用 20 个 SAIF MF persona 跑 baseline + 改造 scoring / 反馈结构 / UI + 出对比报告。**1 周节奏**。
>
> 给 SAIF 领导的最终交付物: 7 行硬指标对比表 + 5 个 persona 改前/改后并排 + 2 个 demo session。

---

## 1. 背景与痛点

### 1.1 学院侧观察（brainstorming 对齐）

一句话: **现在的反馈像"老师评语",不像"教练复盘"。**

| # | 现象 | 学院侧后果 |
|---|---|---|
| 1 | 分数都在 80–100 | 老师看不出谁强谁弱 |
| 2 | 5–6 个维度评分扁平（基本同分） | 维度等于摆设 |
| 3 | 评语宽泛, 没指出"哪一句不符合 JD / 不像这个赛道候选人会说的话" | 学院最在意的"行业感"丢了 |
| 4 | 没有改写示范、没有"同期候选人对照线" | 学生不知道怎么改、不知道自己离及格多远 |
| 5 | 不长但没重点 | 学生扫两眼就关了 |

### 1.2 SAIF 学生画像（用户给的 3 维度信息）

- **MF 主体**: 86 人 / C4 75% / 经管:理工 = 50:48 / 100% 就业
- **MF-General**: 经管 72% / 投研 40% / 管培 33% / IBD 11%
- **MF-FinTech**: 理工 87% / 投研 50% / 销售交易 14% / 数据 11%
- **实习厚度**（老师 1+2 反馈）:
  - 老师 1（最资深）: MF 基本对口上头中部 1–2 段
  - 老师 2（战略咨询背景）: MF 三段打底, 会 push; FT 参差 1–2 段相关; 中上为主
- **老师 top 痛点**（直接定义评分维度）:
  - "通过简历展示目标岗位需要的相关能力" → **岗位能力匹配度**
  - "哪些信息是重要的、每段功能和侧重" → **信息选取与侧重**
  - "逻辑性地描述" → **逻辑性**

### 1.3 现有可借用的 infra

| Infra | 路径 | 状态 |
|---|---|---|
| 8 个 workspace persona | `backend/tests/eval/personas/workspace_2026_05_20/` | 已 cherry-pick 到 `feat/mock-interview-feedback-2026-05-20` |
| 12 个 mock interview persona (M1-M12) | `backend/tests/eval/personas/mock_interview_2026_05_20/` | 同上分支已加 |
| 5 个 touyan_v1 interview YAML | `backend/tests/eval/fixtures/touyan_v1/interview_answers/` | main 已有 |
| mock interview scoring | `backend/app/services/interview/scoring.py` | LLM rubric + ContextProvider INTERVIEW_SCORE |
| **mock interview baseline runner** | `backend/tests/eval/run_mock_interview_baseline.py` | **2026-05-20 Day 1 PM 新增** (20 persona × 6 题, ContextProvider bootstrap, audit 跑) |
| **改造前 baseline 数据** | `backend/tests/eval/_out/mock_interview_baseline_pre_2026_05_20.json` | **2026-05-20 Day 2 跑出, 28.8 min, 详见 `docs/eval-full-loop-reports/mock_interview_baseline_pre_2026_05_20.md`** |
| eval runner / simulator / judge | `backend/tests/eval/{runner,simulator,judge}.py` | main 已有 |
| 5 ContextProvider | `app/services/llm_context/__init__.py` | sensitive / tencent / memory / podcast / xhs |

---

## 2. Persona 矩阵（20 个, MF-only）

> FMBA 本期不做; weak 档 + 极端档全部新增。

### 2.1 复用 8 个（`workspace_2026_05_20/P{1..8}.json`）

| ID | Track | Tier | 背景 | 备注 |
|---|---|---|---|---|
| P1 | Buy-side 投研/资管（公募行研） | strong | 清华本经济 + MF-G | 头部 3 段, 投研 top 40% 主流 |
| P2 | Sell-side 研究 TMT | strong | 复旦本经济 + MF-G | 中金 + 中信建投 |
| P3 | 私募/资管基本面 | mid | 上交本数学 + MF-G | **跨专业**, Quantamental 定位 |
| P4 | 银行管培/综合金融 | mid | 上交本管理 + MF-G | 招行 + 中信建投综合岗 |
| P5 | IBD | strong | 北大本经济 + MF-G | 中金 IBD + 高盛 GBM |
| P6 | 量化私募/对冲基金 | strong | 上交本数学+CS + MF-FT | 九坤/乾象级别 |
| P7 | FinTech 数据/算法 | mid | 清华本 CS + MF-FT | 券商金科 + 蚂蚁算法 |
| P8 | 大宗商品/能源研究 | mid + **极端: 红线** | 上交本能源 + MF-G | **跨专业**, PVSyst 50MW 编数字必查 |

### 2.2 新增 12 个（`mock_interview_2026_05_20/M{1..12}.json`）

**填空 8 个**（让 mid / weak 档分布合理）:

| ID | Track | Tier | 背景 | 用途 |
|---|---|---|---|---|
| M1 | Buy-side 投研/资管 | mid | MF-G 经管（财大本金融） | 1 中部公募实习, 主流 mid 画像 |
| M2 | Sell-side 卖方（消费/医药 sector） | mid | MF-G 经管（浙大本经济） | 中型券商研究, 叙事一般 |
| M3 | IBD/资本市场 | mid | MF-G 经管（中财本金融） | 中型券商投行实习 |
| M4 | 咨询/战略/数据 → 转金融 | mid | MF-G 经管（南开本金融） | 战略咨询 + 互联网战略, 想转金融 |
| M5 | FinTech 数据/算法 | mid（FT 参差） | MF-FT 理工（哈工大本计算机） | 1 段金科+1段普通数据, 比 P7 弱 |
| M6 | Buy-side 投研（目标） | **weak** | MF-G 文科（北外本法学） | 零金融实习, 只有课程项目 + 协会 |
| M7 | Buy-side / Sell-side | **mid 但叙事差** | MF-G 经管（中山本金融） | 实习不错但 bullets 写得平庸 |
| M8 | 投研（目标） | **weak（跨专业）** | MF-G 工科（天大本机械） | 零金融实习, 只有产业项目 |

**极端档 4 个**（验证"AI 真能扣分"——给学院展示**有筛选力**的关键）:

| ID | 类型 | 触发什么 |
|---|---|---|
| M9 | **套模板 STAR**（千篇一律"主导/复盘/沉淀/赋能/闭环/抓手"） | 识别陈词滥调, 内容空 |
| M10 | **编数字**（"提升 47% / 节约 1200 万 / 触达 5000 用户" 不可信） | 调用 `_detect_fabricated_numbers` |
| M11 | **跑题**（产业研究背景 + 套金融 target track, 完全 mismatch） | 赛道匹配扣分 |
| M12 | **表达极弱**（海外背景翻译腔 / 因果倒置 / leveraged synergies 类） | 逻辑性扣分 |

### 2.3 分布检查

| 维度 | 数量 | 备注 |
|---|---|---|
| Strong | 4 | P1, P2, P5, P6 |
| Mid | 10 | P3, P4, P7, M1, M2, M3, M4, M5, M7 + P8(mid 段) |
| Weak | 2 | M6, M8 |
| 极端 | 4 | M9, M10, M11, M12（P8 已含红线但仍是 mid） |
| MF-General | 16 | 主体 |
| MF-FinTech | 4 | P6, P7, M5, + (M11 看怎么分类) |
| 跨专业 | 5 | P3, P8, M6, M8, + 部分 M11 |
| 8 大赛道全覆盖 | ✓ | 投研/卖方/IBD/管培/量化/数据/咨询/大宗 |

---

## 3. 生成方案

### 3.1 subagent 生成 12 个 persona

**subagent prompt 要点**:
1. 必读: `workspace_2026_05_20/README.md` + `P3.json` (mid cross-major 范例) + `P8.json` (红线极端范例) + `P6.json` (FT strong 范例)
2. schema 严格 match `P{n}.json`（保留 `persona_voice` / `hidden_highlights` / `avoid_emphasize` / `flow_padding_internship`; M9-M12 不需要 `flow_padding`）
3. M9 套模板: 6 段 bullets 全是"主导XX / 复盘XX / 沉淀XX / 赋能XX / 闭环XX / 抓手"; **没有数字 / 没有公司具体 deal**
4. M10 编数字: 类似 P8 PVSyst 风格, 给"提升 47% / 节约 1200 万欧元 / 触达 5000 用户" 等不可信值, 并在 `red_line_bullets` 里标 `expected_warning: true`
5. M11 跑题: resume 全是产业 / 工程 / 项目语言, 但 `target_track` 写"投研 / IBD / 量化", 完全 mismatch
6. M12 翻译腔: bullets 用"leveraged synergies to drive value / spearheaded cross-functional initiatives" 这种翻译腔中文
7. 输出: `backend/tests/eval/personas/mock_interview_2026_05_20/M{1..12}.json` + `README.md`

### 3.2 抽检（我做, spot-check 4 个）

| 抽检对象 | 检查点 |
|---|---|
| **M1**（普通 mid） | persona_voice 不空泛, hidden_highlights 可被追问 |
| **M6**（weak 跨专业文科） | 真的没有金融实习, 不是"弱版 mid" |
| **M9**（套模板） | 6 个 bullets 真千篇一律, 不是普通 mid |
| **M10**（编数字） | 数字真不可信（量级 + 单位 + 上下文都不对得起来）, 不是"普通虚高" |

### 3.3 答题语料生成（student-subagent）

- 复用 `backend/tests/eval/simulator.py`
- **20 persona × 6 题 = 120 transcripts**（每个 persona 用自己的 tier 自然产出, 不分 3 档——persona 矩阵已经分了档）
- driver: `persona_voice.{communication_style, verbal_tics, under_pressure}` 喂给 student-subagent 当 system prompt
- 6 题用 `app/services/interview/adaptive.py` 的 skeleton: 自我介绍 / 主导项目 / 估值/方法论 / 行业观点 / 弱项追问 / 反问

---

## 4. Baseline（改造前）

### 4.1 跑法

```bash
cd backend
# 全量跑 20 persona × 6 题
.venv/bin/python tests/eval/run_mock_interview_baseline.py \
    --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 \
    --questions 6 \
    --out tests/eval/_out/mock_interview_baseline_pre_2026_05_20.json
```

> 该 runner 脚本本计划 Day 1 下午写 — 复用 `tests/eval/runner.py` + `simulator.py`, 但产出 per-persona × per-question 的 ScoreResult。

### 4.2 记录指标（baseline 报告里出现的）

- 每个 persona × 6 题: `overall + hits + misses + bonuses` + 反馈正文 + 耗时
- 聚合: tier × track × 平均分 / spread / 反馈长度
- 反馈文本自动检查（正则 + LLM judge）:
  - 是否引用 JD 原文（关键词命中率）
  - 是否引用赛道（"公募/卖方/量化" 等 token）
  - 是否含改写示范（"可以改成 / 建议改成" 等 trigger）
  - 是否含对照线（"同期候选人 / P50 / 行业及格线" 等）

### 4.3 baseline 报告

`docs/eval-full-loop-reports/mock_interview_baseline_pre_2026_05_20.md` — Day 2 出。

---

## 5. 改造四件事

### 5.1 A. Scoring 重做

**改的位置**: `app/services/interview/scoring.py` + `app/services/interview/prompts.py`（SCORING_SYSTEM） + `app/services/interview/report.py`

| 改动 | 业务理由 |
|---|---|
| **5 维度独立打分** (每维独立 LLM call 或同一 call 强制分 5 段) | 防止 LLM 合稀泥 |
| 维度名复用老师语言: ① 岗位能力匹配度 ② 信息选取与侧重 ③ 逻辑性 ④ 行业感 ⑤ 可信度 | 学院看就懂, 不用解读 |
| **Anchor 评分**: 每维度 1-3/5-7/9-10 三档 anchor 来自 podcast/xhs 同期候选人原话 + 5 touyan_v1 fixture | 锚到真实样本, 不靠 LLM "感觉" |
| **起评 5 分**: prompt 里强制"默认 5 分, 加分扣分必须列证据" | 砸掉鼓励基线, 拉开 spread |
| 输出 schema 改 `dim_scores + dim_evidence` + 旧 `overall + hits + misses` 保兼容 | UI 端 + 旧 fixture 都能消化 |
| **LLM 沉默失败 fallback** (2026-05-20 baseline 新增): `report.py` 拿到空 content 时, 退到 "用本场 6 个 turn 的 score_answer 结果聚合出 overall + 给一句模板化 overall_comment", 而不是返 `overall_score=0`。fallback 命中时 `_meta.fallback_reason = "report_llm_silent"`, 前端能看到 banner | baseline 跑出 P1 (strong) 5% 概率沉默失败 → SAIF 86 人池子里会变成 4-5 次惊吓 |

### 5.2 B. 反馈结构重做

**改的位置**: `app/services/interview/report.py` + 反馈 prompt

每条反馈强制 4 段:

| 段 | 内容 | 锚到哪 |
|---|---|---|
| ① 扣分点 | "你说了 X, 但 JD 要 Y / 这个赛道更看重 Z" | JD 原文 + 赛道 rubric (TencentTrackProvider) |
| ② 行业坐标 | "同期候选人通常会提 W" | xhs / podcast 同期候选人原话 (XhsContextProvider + PodcastContextProvider) |
| ③ 改写示范 | "可以改成: '…'" | ≤ 30 字具体改写 |
| ④ 下一步动作 | "练 3 次 STAR + 补 1 段实习数字" | 可执行 |

**强制**: 每条反馈必须包含 4 段, 否则视为不合格（自动 lint + 重生成一次）。

**额外两道守卫** (2026-05-20 baseline 新增):

| 守卫 | 现状 | 改造后 |
|---|---|---|
| **Fabricated quote 阻断** (`verify_quotes_against_transcript`) | 只 log warning + 把列表挂到 `report._fabrication_warnings`, **prod 仍 return**。baseline 20 份报告里 16 份命中 (95 条累计, P8 一份 16 条 / M1 一份 15 条), 学生看到的反馈里塞着 LLM 自己编出来夸他的"原话" | 命中 = `report` 不返回, **强制重生成一次**;二次仍命中 → 退到只保留 `dimensions + overall_comment` 的 fallback 版本, `improvements/highlights` 整段抑制 |
| **Fabricated number 守卫** (`_detect_fabricated_numbers`) | 只在 resume chat (`chat.py`) 路径生效, **interview report 完全裸奔**, 所以 P8 PVSyst 50MW 100 万欧元在 interview report 路径里照常被打 84 分 + LLM 还引用 | 在 report 里复用 `_detect_fabricated_numbers(profile, transcript)`, 命中则在 overall_comment 自动追加"⚠️ 涉及未在简历中出现的数字, 已扣可信度 X 分", 同时把可信度维度强制 ≤ 3 |

### 5.3 C. UI 重做（灰度 `/interview/v2`）

**改的位置**: 新页面 `resume-copilot-web/app/interview/v2/*`（**不动**现有 `/interview/*`, 灰度并存）+ 新组件 `components/interview/v2/{RadarChart, ScoreRuler, RewriteSideBySide, RetryButton}.tsx`

| 组件 | 说明 |
|---|---|
| **雷达图** | 本人 5 维度 × 同期候选人 P50 × 学院强档 P90 三条线 |
| **维度卡** | 扣分点（红） vs 改写示范（绿） 并排 |
| **总分条** | 本人位置 + 同期 P25/P50/P75 标尺 |
| **"练这道题再来一遍"** | 调后端新 retry endpoint 创建 retry session, 同题 + 上次反馈作为 system 提示注入 |

**后端配套**: 新 endpoint `POST /api/interview/sessions/{id}/retry`, 复用原 session 的 `target_job` / `current_main_question`, 同时把上轮 `ScoreResult.misses + 改写示范` 作为 system prompt 注入下轮 student-subagent / 面试官 LLM。

Token 用 `interview-theme.css` 的 terracotta scope（不污染 workspace / hifi）。

**灰度策略**: 现有 `/interview/*` 保持 100% 流量直到 v2 验收报告通过; v2 灰度入口先放在管理员后台和 SAIF 老师测试链接, 不暴露给学生。

### 5.4 D. 验收基准

**改造后跑 same 20 persona × 6 题** = 120 transcripts → `mock_interview_post_2026_05_20.json`

对比报告 `docs/eval-full-loop-reports/mock_interview_post_2026_05_20.md`:
- 改前 vs 改后 7 行硬指标表（见第 7 节）
- 5 个代表性 persona 改前/改后并排 markdown
- diff 高亮"改前打 87 分但应该打 ≤25" 的 case（说明改造命中了"假繁荣"）

---

## 6. 节奏（1 周）

| Day | Owner | 干啥 | 输出 |
|---|---|---|---|
| **1 上午** | subagent | 生成 12 persona | 12 JSON + README in `mock_interview_2026_05_20/` |
| **1 下午** | 我 | 抽检 + 修 4 个 + 写 baseline runner 脚本 | run_mock_interview_baseline.py |
| **2** | 我 | 跑 baseline（120 transcripts） + 写 baseline 报告 | baseline.json + 报告.md |
| **3** | 我 | 改 scoring（5 维独立 + anchor + 起评 5 分 + **report LLM 沉默失败 fallback**) | scoring.py + prompts.py + report.py |
| **4** | 我 | 改反馈结构（4 段强制 + 改写示范注入 + **fabricated-quote 阻断重生成** + **报告路径复用 `_detect_fabricated_numbers`**) | report.py + prompts.py + scoring.py |
| **5** | 我 | 后端: 加 `POST /api/interview/sessions/{id}/retry` endpoint + retry 时把上轮 misses+改写注入下轮 prompt | interview router + tests |
| **6** | 我 | 前端: 新 `/interview/v2` 灰度页 + 雷达 + 标尺 + 改写并排 + retry 按钮 | resume-copilot-web/app/interview/v2/* |
| **7** | 我 | 跑 regression + 写对比报告 + 准备 2 个 demo session (走 v2 URL) | post.json + 对比报告.md + demo URL |

---

## 7. 量化目标（验收线）

| 指标 | 改造前（2026-05-20 实测）| 改造后目标 |
|---|---|---|
| 强档 (P1/2/5/6) 平均总分 | **65.25** (含 P1 LLM 沉默失败=0; 去掉 P1 = 87) | **≥ 75**（拉低天花板, 留出 spread）|
| 弱档 (M6/M8) 平均总分 | **85.50** (比强档还高 ⚠️) | **≤ 45** |
| 极端档 (M9-M12) 平均总分 | **80.25** (M12 翻译腔=93 ⚠️) | **≤ 25** |
| 强 vs 弱 spread (去 P1 失败) | **1.5 分** ⚠️ | **≥ 30 分** |
| 6 维度内部标准差均值 | **5.6** (基本同分) | **≥ 15** |
| 反馈引 JD anchor 覆盖率 | **25%** | **≥ 90%** |
| 反馈含改写示范 覆盖率 | **90%** (高但内容质量待评估) | **≥ 80%** (改造后强制 4 段, 改写需在原话基础上≤30 字) |
| 反馈含"同期对照" 覆盖率 | **0%** ⚠️ | **≥ 60%** |
| **报告含 fabricated quotes 占比** (新增) | **80% (16/20, 95 条累计)** ⚠️ | **0%** |
| **报告 LLM 沉默失败率** (新增) | **5% (1/20, 含 fallback 前)** | 0% (fallback 兜底, 同时降低实际失败率) |

—— **这 10 行就是给 SAIF 领导的对比报告主表** (新加 2 行: fabrication + silent fail, 都是 baseline 跑出的 smoking gun)。

---

## 8. 验收输出（最终交付物）

1. **对比表**（上面 8 行硬指标的改前 / 改后, 红绿涨跌）
2. **5 个代表性 persona 改前 / 改后并排**:
   - P1（strong, 改前打 90, 改后打 78）
   - M9（套模板, 改前打 82, 改后打 22）
   - P8（红线, 改前打 75 不识别, 改后打 18 + warning）
   - M6（weak 跨专业, 改前打 70, 改后打 38）
   - M5（MF-FT mid, 改前打 78, 改后打 58 + 维度差异化）
3. **2 个 demo session URL** 现场跑给学院老师看

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 5 维度独立打分 → LLM 成本 5x | 同一 LLM call 一次输出 5 段（强 schema）, 或 cheaper model（deepseek-chat → deepseek-lite 评分） |
| Anchor 抽不出来（podcast/xhs 覆盖不全） | 兜底用 5 touyan_v1 fixture（已有强档标准） + SAIF 老师口头评语手写 5 段 |
| UI 改完前后端没对齐 | 改 UI 前先冻结 scoring API contract（写 OpenAPI schema） |
| 极端档 LLM 不愿意打低分 | prompt 加 "默认 5 分, 加扣分都要列证据 + 禁止鼓励式打分"; failing 加 jailbreak-style 反例 |
| Subagent 生成的极端档不极端（M9 太像 mid） | 抽检时 reject + 让 subagent 重生成一轮; 加 ground-truth 检查（M9 bullets 必须 0 个数字 / 0 个具体公司 deal） |
| Mock interview eval runner 不存在, Day 2 跑不起来 | Day 1 下午先写 runner, 复用 `tests/eval/runner.py` 大部分逻辑 |

---

## 10. 已确认决策（2026-05-20）

| 决策项 | 选定 | 说明 |
|---|---|---|
| **分支策略** | off `main` + cherry-pick P1-P8 (commit `ced28cc`) | 新分支 `feat/mock-interview-feedback-2026-05-20` 从 main 起, cherry-pick 一个 commit 把 8 个 workspace persona 拉进来; 避免依赖 `feat/workspace-redesign-2026-05-20` 整支分支的所有改动 |
| **UI 改的范围** | 新建 `/interview/v2` 灰度页 | 现有 `/interview/*` 保留 100% 流量, v2 灰度入口先给管理员 + SAIF 老师测试链接, 学生不暴露; v2 验收报告通过后再切流量 |
| **D5 retry 按钮** | 后端配套 | 加 `POST /api/interview/sessions/{id}/retry`, 复用 session, 把上轮 misses + 改写注入下轮 prompt |
| **Anchor 数据** | 暂用 podcast / xhs 现有库 | 不手补 SAIF 老师 verbatim; 跑完 baseline 看 anchor 覆盖率, 不够再补 |
| **改造范围** | 只动 mock interview | workspace D6 fix 是平行 track, 不进本计划 |

### 附: jds_real 编号约定（2026-05-20 我自己定的）

- 现有 `tests/eval/fixtures/touyan_v1/jds_real/` 占用 **06-10**（5 个文件: jiashi / invesco / chinaamc / fullgoal / jiashi_credit）
- 新 12 个 M{1..12} persona 的 `target_jd_ref` 编号 **11-22**（已批量平移）, 紧接现有序列, 无 collision
- 这些 JD YAML 实际文件 **尚未创建** — baseline runner 会先把 `target_jd_ref` 当 label 用, Day 3-7 改 scoring 时再补创建 JD YAML（如需）

---

## 附录: 老师反馈原话（计划设计依据）

> **老师 1**（最资深）: "mf 的学生 基本上都会有对口的上头中部的实习至少一段到两段这样"; "top 3 痛点: 不是怎么讲好自己的实习经历、不知如何提炼过往实习亮点、怎样避重就轻呈现自己和岗位匹配的优势"
>
> **老师 2**（战略咨询背景）: "MF 的一般都很不错, 三段打底吧, 我们会 push 他们去的; FT 的就参差不齐, 但大部分有相关的实习经验 1-2 段, 不一定都是最头部的, 但肯定是相关的, 至少中上吧"; "top 3 痛点: **怎么通过简历展示目标岗位需要的相关能力 / 哪些信息是重要的（每一个部分的功能和信息侧重） / 逻辑性地描述**"

—— **老师 2 这 3 个痛点直接定义了改造后评分的核心 3 维度 (① 岗位能力匹配 ② 信息选取与侧重 ③ 逻辑性)**, 再加上 ④ 行业感（SAIF 隐含核心要求） + ⑤ 可信度（防编造）= 5 维度。
