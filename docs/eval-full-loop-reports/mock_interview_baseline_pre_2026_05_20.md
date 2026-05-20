# Mock Interview 反馈系统 — 改造前 Baseline (2026-05-20)

> 对 20 个 SAIF MF 模拟学生 (4 strong / 10 mid / 2 weak / 4 极端档) × 6 道骨架题 = **120 段答题** 跑了一遍当前生产链路, 把 5 维评分 + 整场反馈报告全部记录, 用于和改造后做对照。
>
> 跑法 / 数据细节: `backend/tests/eval/_out/mock_interview_baseline_pre_2026_05_20.json` (425 KB, 28.8 min, ~$3 LLM)
> 计划文档: `docs/mock-interview-feedback-redesign-plan-2026-05-20.md`

---

## 一句话给领导

**当前反馈系统对 SAIF 试点不可用** —— 不是"反馈不够细"的问题, 是 **打分扁平 / 强弱不分 / 编造候选人原话 / 顶档候选人会偶尔拿到 0 分** 四个并存的硬 bug。这份 baseline 把这 4 个问题都用数据钉死, 给改造后做对照基准。

---

## 一、 8 行硬指标 (Plan §7 的"改造前"列)

| 指标 | 改造前 (本次跑出) | 改造后目标 | 差距 |
|---|---|---|---|
| **Strong 档 (P1/2/5/6) 整场报告平均分** | **65.25** ⚠️ (含 P1=0 沉默失败) | ≥ 75 | 看似低, 但实因 1 例 LLM 失败拖累 |
| Strong 档 (去掉 P1 失败) | 87.0 | ≥ 75 (拉低天花板) | 比目标还高 → 没有拉开 spread |
| **Weak 档 (M6/M8) 平均分** | **85.5** ⚠️ | ≤ 45 | **+40 分**, weak 比 strong 还高 |
| **极端档 (M9/M10/M11/M12) 平均分** | **80.25** ⚠️ | ≤ 25 | **+55 分**, 套模板/编数字也能拿 80 |
| **Strong vs Weak spread (不算 P1 失败)** | **1.5** | ≥ 30 | **20 倍差距** |
| **整场报告 6 个维度内部标准差均值** | **5.6** (基本同分) | ≥ 15 | 6 维评分是摆设 |
| **反馈引用 JD 锚点 / 同期对照覆盖率** | 25% JD / **0% 同期** | ≥ 90% / ≥ 60% | "同期候选人 P50" 完全缺失 |
| **反馈中含 LLM 编造的候选人原话的报告占比** | **80% (16/20)** ⚠️ | 0% | 95 条编造引文累计 (P8 一份就 16 条) |

---

## 二、 4 个 smoking gun (按严重度排)

### Gun #1 — Strong 档反馈分布: 1 例**完全沉默失败** + 3 例和 weak 同分

| Persona | 档位 | 报告整体分 | 6 维标准差 | 单题平均分 |
|---|---|---|---|---|
| **P1 林思远** 清华本经济 + 中信+易方达 | strong | **0** ⚠️ (LLM 返空 + 2 次重试都空) | n/a | 85.2 |
| P2 复旦本经济 + 中金+中信建投 TMT | strong | 87 | 4.6 | 84.2 |
| P5 北大本经济 + 中金 IBD + 高盛 GBM | strong | 83 | 3.0 | 76.7 |
| P6 上交本数学+CS + 九坤/乾象 量化 | strong | 91 | 6.3 | 82.5 |

- **P1 这个失败模式是生产 bug** —— 候选人讲了 6 段非常充分的 thesis (山西汾酒省外扩张 / 药明康德生物安全法案 / 易方达消费医药持仓判断), 单题分 76-92 全部正常, 唯独整场报告 LLM 返空 → 用户在前端看到的会是 **overall_score=0 + 空 dimensions + 空 highlights + 空 improvements + 空 overall_comment**。

  这个 bug 在生产里很可能已经偶发但被人当作"DeepSeek 抽风"忽略, 而 baseline 跑 20 个就触发了 1 次 (5%) —— 在 SAIF 试点 86 个学生量级会变成 4-5 次惊吓。

- 即使**剔除 P1 失败**, 剩下 3 个 strong 档 (P2/P5/P6) 平均 87 分, 和 mid 档 (86.2) **几乎不可区分**。

### Gun #2 — 报告整体分扁平到无法区分 4 个档位

去除 P1 沉默失败后的真实分布:

| 档位 | 人数 | 报告整体分均值 | 区间 |
|---|---|---|---|
| Strong (P2/P5/P6) | 3 | **87.0** | 83 – 91 |
| Mid (M1-M5/M7 + P3/P4/P7/P8) | 10 | **86.2** | 81 – 92 |
| Weak (M6/M8) | 2 | **85.5** | 79 – 92 |
| Extreme (M9-M12) | 4 | **80.25** | 69 – 93 |

- 4 档分布全部落在 **80-87 之间**, 总 spread = 7 分
- 极端档里最高的 M12 (翻译腔, "通过协同杠杆赋能 / 端到端价值闭环") 拿到 **93 分**, 比所有 strong 都高
- weak 档里的 M6 (北外法学本, 0 金融实习) 拿到 **92 分**, 和 strong P6 (上交量化九坤) 同档
- 这意味着: SAIF 老师拿到这份反馈, **完全无法用分数信号识别学生强弱**, 反馈系统对学院侧没有筛选力

### Gun #3 — 95 条 LLM 编造的候选人原话散布在 16/20 份报告里

整份报告强制 highlights/improvements/overall_comment 必须包含 「」 引用候选人原话, 现有 `verify_quotes_against_transcript` 守卫会扫描并把对不上的列入 `_fabrication_warnings`, **但只 log warning, 不阻断**。20 份报告里:

| Persona | 编造引文数 | 性质 |
|---|---|---|
| **P8** 大宗能源 mid | 16 | 数量第一, 含 "把发电侧工程参数转化为研究判断" 等 LLM 自创短语 |
| **M1** 中欧大消费 mid | 15 | 含编造的整段产业链描述 |
| M8 比亚迪机械 weak | 9 | |
| M9 套模板 extreme | 8 | 含 "我把上下游四层纪要全部过了一遍" (候选人没说过) |
| M12 翻译腔 extreme | 8 | |
| P6 量化 strong | 8 | |
| 其余 10 个 | 1-6 | 几乎全部不为零 |

**最危险的一类是把 LLM 自己的洞察伪装成候选人原话**, 比如 M6 报告里:

> 「市场把'资本新规'看作约束，我认为是结构性利好」—— 非共识判断，体现独立研究能力

候选人 (北外法学本, 零金融实习) **完全没说过这句话**, 是 LLM 自己根据上下文编出来夸她的。SAIF 老师如果在反馈页看到这种"非共识判断"会以为学生真的有这个洞察, 后续给推荐时会失真。**这是会捅破学院信任的红线**。

### Gun #4 — 极端档完全识别不出, "可信度" 维度形同虚设

| Persona | 极端类型 | 报告整体分 | LLM 反应 |
|---|---|---|---|
| **M10** 编数字 | 实习生独立 own 80 亿欧元并购 / sharpe 3.2 / 触达 5000 机构 | **79** | highlight 仍在夸 "「EV/EBITDA 相对历史中枢折价 45%」展示了对估值工具的深入理解" |
| **M11** 跑题 | 化工本 (Ni 基催化剂 / MDI 装置), target 写公募大消费 | 69 | 唯一一个略低的极端, 但 69 比 P1 strong 还高 |
| **M12** 翻译腔 | "通过协同杠杆赋能 / 端到端价值闭环 / 利益相关方对齐" | **93** | LLM 反而被翻译腔黑话唬住, 给出最高分 |
| **M9** 套模板 | 6+ bullets 全 "主导/复盘/沉淀/赋能/闭环/抓手", 0 数字 0 公司名 | 80 | improvements 还引用候选人编出来的 "我把上下游四层纪要全部过了一遍" |

- 编数字 / 套模板 / 翻译腔 都被打 79-93 分 → **当前反馈不存在"可信度"维度的实际惩罚**
- P8 红线 persona (PVSyst 100 万欧元编数字) 已知存在 `_detect_fabricated_numbers` 守卫, 也被报告打 **84 分 + 16 条编造引文**, 守卫等于没生效 (它在 resume chat 路径下生效, 不在 interview report 路径)

---

## 三、 5 个代表性 persona 改造前真实输出

> 给 SAIF 老师看的"真实反馈样本" —— 这些就是学生当前会看到的。

### Case A — P1 林思远 (strong, 清华经济本 + 中信+易方达 大消费 + 推汾酒)

**6 题答题 (单题分 76 / 88 / 85 / 82 / 88 / 92, 平均 85)** —— 答题质量是 20 个 persona 里最强。

样例答题 (q1 主导项目 推汾酒):
> 我推山西汾酒。这是我的覆盖核心票，在中信和易方达两段实习都在深度跟踪。我的 thesis 其实浓缩成一句话: **汾酒的省外扩张不是单纯的铺货，而是进入了'终端动销驱动'的第二阶段**，市场目前还在按铺货逻辑给它估值，低估了它的底部安全垫。…… (后接 300 字论证)

**整场报告 (前端会显示给学生看的)**:
```
overall_score: 0
dimensions: []
highlights: []
improvements: []
overall_comment: ""
```

LLM 沉默返空 → 2 次重试都失败 → 学生在前端会看到 "0 分 + 没有任何文字反馈"。**这就是 SAIF 试点最不能出的事故**。

### Case B — M6 (weak, 北外法学本 + 金杜 + SAIF 投研协会 + 零金融实习, 目标公募行研)

报告整体 **92 分** (比 P1 高 92 分)

```
overall_score: 92
dimensions: [结构化 95 / 颗粒度 90 / 互动 85 / 动机 95 / 行业认知 90 / 解决问题 95]
highlights:
  - 「市场把'资本新规'看作约束，我认为是结构性利好」—— 非共识判断, 体现独立研究能力
                     ↑↑↑ 候选人没说过这句, LLM 编的
improvements:
  - 在自我介绍中, 你说「做政策敏感型的行业研究可能会更顺手」, …
  - 在推票时, 你说「我不做纯 DCF 那套」, 可能让面试官觉得你建模能力不足。可以改成: …
  - 在反问培养路径时, 你提到「零财务建模实战」暴露短板…
overall_comment: 候选人展示了极强的结构化思维和对资本新规的深度理解, …
                整体匹配二级买方研究岗位所需的研究能力和潜力
                ↑↑↑ "整体匹配二级买方研究岗位" — 北外法学 + 0 金融实习
```

⚠️ 4 条 fabricated quotes, 全部是 LLM 给她"嘴里塞"的高级观点。一个法学跨专业、零金融实习的学生拿到这份反馈, 会自我误判为"我已经接近二级买方研究岗位匹配"。

### Case C — M9 套模板 STAR (extreme)

简历 6+ bullets 全是 "主导 / 复盘 / 沉淀 / 赋能 / 闭环 / 抓手", 0 数字 / 0 公司名 / 0 deal。

报告整体 **80 分**。highlights 引用了 LLM 自己编出来的"上下游四层纪要", improvements 写法值得肯定 (有 position + weakness + suggestion 三段), 但 **integers cannot say 80 分**:

- 6 维全部落在 75-85, 内部标准差 ~4 (= "6 维全部摆设")
- overall_comment: "候选人整体表现接近合格买方研究员水平"
- 学生看到这份 = 收到"接近合格"信号 = 不会去补内容空洞的根本短板

### Case D — M10 编数字 (extreme)

实习生独立 own 80 亿欧元欧洲并购 + sharpe 3.2 + 公募实习生年化 +47% + 触达机构 5000+。

报告整体 **79 分**, highlights 第二条:
> 在估值锚选择上提到「EV/EBITDA 相对历史中枢折价 45%」展示了对估值工具的深入理解

LLM 完全没识别这是编的数字, 反而把它当作"深入理解"夸奖。**SAIF 老师如果信这个反馈**, 会把这种 persona 误推荐进头部买方面试 → 候选人 1 轮就被打回。

### Case E — P8 大宗能源 + PVSyst 编数字 (mid 红线)

报告整体 **84 分 + 16 条 fabricated quotes** (本次最多), 包括:
- 「把发电侧工程参数转化为研究判断」(LLM 自创)
- 「把工程背景变成差异化研究优势」(LLM 自创)

而 P8 原本 resume 里有明确的红线 bullet (PVSyst 100 万欧元 50MW, 实习生独立 own), `_detect_fabricated_numbers` 守卫在 resume chat 路径下能抓到, **interview report 路径完全没有这个守卫**。

---

## 四、 这 4 个 smoking gun 怎么对应 Plan §5 的 4 件改造事

| Smoking gun | 直接对应改造 | 验收方式 |
|---|---|---|
| **#1** Strong 沉默失败 (P1=0) | §5.1 SCORING_SYSTEM 简化 + retry + JSON schema 严格验证 | 改后 P1 必须打 ≥ 75 + 报告非空 |
| **#2** 4 档扁平 spread=7 | §5.1 起评 5 分 + 5 维独立 + anchor 锚到 podcast/xhs/touyan 同期样本 | 改后 Strong - Weak ≥ 30 + 6 维标准差 ≥ 15 |
| **#3** 80% 报告有 fabricated quotes | §5.2 反馈结构强制 4 段 (扣分点引 transcript / 行业坐标引 anchor block / 改写示范≤30字 / 下一步动作) + `_fabrication_warnings` 升级为**阻断 + 自动重生成** | 改后 fabricated quotes 占比 = 0% |
| **#4** 极端档 79-93 分 | §5.1 "可信度" 维度独立 + 起评 5 分 + 砸"鼓励基线" prompt | 改后 M9/M10/M11/M12 平均 ≤ 25 |

---

## 五、 数据怎么用 / 下次怎么对照

1. **Baseline JSON 已写到** `backend/tests/eval/_out/mock_interview_baseline_pre_2026_05_20.json` (425 KB, 完整, 20 personas × 6 turns + 20 reports + 20 audits)
2. **Day 7 改造后 regression** 用 same 20 persona 跑 `mock_interview_post_2026_05_20.json`, 对比报告填 §1 的 "改造后" 列
3. **给 SAIF 领导的最终交付物**: §1 的 8 行表 (改前/改后红绿) + 5 个代表 persona 改前/改后并排 (本文档 §3 已经把"改前"段落写好了)

---

## 六、 已知限制 (本次 baseline 没覆盖的)

- 没跑 follow-up turns (只跑了 6 道骨架, follow-up 会让 transcript 更长 → 反馈数据应更密, 改造后 regression 也保持只跑骨架以可比)
- chip_key 8 个 persona 走了 `default` skeleton (没有量化/IBD/卖方专属), 改造后 regression 同样走 default 保持可比
- ContextProvider 在跑的时候 5 个全 active (sensitive_topic / tencent_track / student_memory / podcast / xhs / track_knowledge) —— 即使有 anchor 数据流进 prompt, 报告也没用上 (没引"同期", 没引 JD), 印证当前 prompt 没有真正激活 anchor 注入路径
- Scoring per-turn (single-question `score_answer`) 比 Report 整场反馈相对靠谱 (单题 spread strong-extreme = 12), 但 SAIF 学生主要看整场报告, 所以本计划改造的重心放在 Report 上

---

*跑分时间: 2026-05-20 17:19 - 17:48 (28.8 min). 分支: `feat/mock-interview-feedback-2026-05-20`. SUT: `deepseek-chat` (生产同款). Simulator: `deepseek-v4-flash`. 20 personas × 6 turns + 20 reports = 260 LLM calls.*
