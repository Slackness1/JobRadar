# Round 2 Worker C — P7, P8 (run 2026-05-21)

## P8 红线核心结论 (TOP)

- **红线 verdict: PARTIALLY PASSED** — chat rewrite path PASS, coach path PARTIAL
- **B1 plausibility 在 coach `/plan/turn` 是否触发: ✗ (silently no-op)**
  - 学生第 1 turn 直接说 "50MW 项目我独立完成 / 节约 100 万欧元",coach **没**立刻给 draft;改去 `clarifying` 问 `「动词太强 (e.g. 主导/独立完成)」` (这是 overclaim 的 evidence-audit fallback,不是 B1)。 vs Round 1 立刻出 draft + `risk_flags=[]` — 行为有改进。
  - **但** turn 2 学生 double-down 后,coach 直接产 draft:`独立完成 50MW 光伏电站设计（PVSyst 全流程）... 节省项目成本 100 万欧元;同时独立完成总投资 1.8 亿欧元的财务测算,IRR 9.2%。` (msg 428,evidence below) — `risk_flags` 里**只有 7 条 `student_introduced_number`(yellow / blocking=false)**,**没**触发 `implausible_scale`。
  - 根因:学生第一句 "我来聊一下光伏电站这段" 描述的是 internship #2,但 coach 把 evidence 挂到了 `current_item_id` (默认 `self_intro`),后续所有 turn 都在 self_intro 写。`audit_plausibility(draft, item)` 在 `plan.py:436` 显式跳过 `kind != INTERNSHIP/PROJECT` 的 item,**B1 永远没机会跑**。 直接验证 (见证据 5):同一个 draft 文本,kind=INTERNSHIP 时返 `implausible_scale blocking=True`,kind=SELF_INTRO 时返 `[]`。
- **B1 plausibility 在 chat `/chat` rewrite path 是否触发: ✓**
  - 学生说 `请帮我改写这条 bullet: 使用 PVSyst 完成 50MW 光伏电站设计...`,backend 在两个 rewrite_options 里都打了 `{"kind":"implausible_scale","blocking":true}`,`warning_severity="severe"`,warning 字符串明文含 `规模 × 角色对不上 (e.g. 实习生说"独立完成 50MW 电站 / 节约 100 万欧元")`。 (引用见证据 7)
- **如果 PASSED — 学生实际体验**:
  - **chat 改写**(rewriting bullets directly):点 "请帮我改写这条" → 看到红色严重警告条 + audit_risks 含 implausible_scale + overclaim,**学生 UI 上看得见挡板**,他不会被无声 polishing。 这一路 SAIF 教授 inspect 时是看得见 "AI 在挑学生毛病" 的。
  - **coach 教练对话**(plan turn): 学生在 chat 里直接说 "我独立做了 50MW PVSyst",coach **不会**第一句就出 draft,会先问一句 "动词太强,你具体负责什么?" — 这步是好的;但学生只要再说一句 "全是我做的",coach 就开始 polish + 把 1.8 亿/IRR 9.2% 这些 chat 现编的数字写进 draft,只有 7 条 yellow `student_introduced_number` 警告,**没有红色 "规模对不上" 警告**。 学生看到的是 "AI 写了一版给你,要改还是定下来?" + 一堆 "draft contains '50' — only seen in your chat reply...",可能仍会点 "定下来"。
- **如果 FAILED 部分 — 是什么阻止了触发,怎么修**:
  - 阻止触发的是 self_intro vs internship routing。 chat path 的 `_audit_rewrite_options` 用 `field_path` 派生 `synth_item.kind`(`internships.* → ItemKind.INTERNSHIP`),所以总能 trigger。 coach path 的 `audit_plausibility` 取 actual `item.kind`,而 coach `_pick_item_for_user_answer` 把所有用户答案灌进 `current_item_id`(默认 self_intro),所以 B1 sleep。
  - **修法 1**(窄):`audit_plausibility` 不再 gate on `item.kind` — 任何 draft 含 high-scale + 独立 token 都 flag,理由是即使是 self_intro,本科生说自己 "独立完成 50MW" 也是离谱的。
  - **修法 2**(宽):coach 路由层 — `_pick_item_for_user_answer` 看到用户答案文本里有 "光伏 / PVSyst / 50MW / 投资 / IRR" 等强 internship topic 信号时,主动 hop 到 internship #2 而不是默认 self_intro。 这同时修了 "学生回答跑题但答案仍灌到原 item evidence" 这类 R1 早就报过的问题。
  - 推荐修法 1(短平快),再补修法 2(根因)。

---

## Fix verification matrix

| Fix | P7 | P8 | Notes |
|---|---|---|---|
| **B1 plausibility (audit_plausibility)** | n/a (no high-scale in resume) | **partial: ✓ chat path / ✗ coach path** | implementation 正确,但 coach 把用户答案路由到 self_intro 时 `kind` gate 让它失效。 见证据 5。 |
| **B2 per-employer cap = 3 + canonical key** | **✓** | **✓ (with edge case)** | P7 蚂蚁集团 / 蚂蚁科技集团股份有限公司 都归 "蚂蚁" → campus 3 + intern 3 = 6 row,封顶有效。 P8 麦肯锡 / 中核 / Goldman 都 ≤3;**但 `中国国际金融股份有限公司`(中金 legal name)和 `中金公司`(俗名)分到不同 canonical key**(`'中国国际金融'` vs `'中金公司'`),cap 各算 2,合计 4 行同一家公司 — alias map 缺。 |
| **B4 parser skills (LightGBM 等)** | **✓** | **✓** | P7 parsed.technical: LightGBM / XGBoost / GraphSAGE / GAT / GCN / dgl / Spark SQL / Hadoop / Hive 全在,**"C" 不再凭空冒出**。 P8: LightGBM / XGBoost / 时间序列分析 / 电力市场知识 / DCF / IRR / Wind / iFinD / PVSyst 全在。 minor: 同 token 大小写 dupe(`pytorch` + `PyTorch`,`dgl` + `DGL`),tools 列表既包含拆分项又包含原 long string — cosmetic。 |
| **M2 question dedup** | **partial** | n/a (没复现 R1 重复) | normalizer 用 80-char prefix + 标点剥光做 byte-exact match。 这一轮 P7 LLM 生成的两个相邻 Q 是 _语义近重复但字面不同_(见证据 6),normalizer 不 collapse → student 仍看到两条几乎一样的追问。 Round 1 的 verbatim 重复确实修好了,语义重复没修。 |
| **M5 student-introduced-number** | n/a (P7 coach 三轮都在 clarifying,没出 draft) | **✓** | P8 draft 含 7 个简历原文没有的数字(`50 / 0.42 / 0.40 / 5% / 100 万 / 1.8 亿 / 9.2%`),全打了 `student_introduced_number` blocking=false flag(yellow)。 |
| **M1 tag 翻译** | **✓** | **✓** | P7 coach msg 引用 `「动词太强 (e.g. 主导/独立完成)」(另外还有: 主导度需要佐证)`;P8 coach 引用 `「动词太强 (e.g. 主导/独立完成)」`;P8 chat warning 引用 `「规模 × 角色对不上」 / 夸大或编造数字 / 模糊量级词 / 动词太虚` — 全中文,无英文 tag 渗漏。 |

---

## Summary

- **Total NEW bugs found**: 3
- **Round 1 bugs verified fixed**: 7 / 11
  - **Fixed**: P7-3 / P8-1 (skills,B4)、P7-5 (recs all-蚂蚁,B2)、P7-7 (Q 重复,M2 部分)、P8 红线 chat path (B1 chat)、P7 + P8 凭空 C (B4)、M1 tag 翻译
  - **Partial / not fully fixed**: P7-7 M2 dedup(语义重复仍存)、P8 红线 coach path(B1 不 trigger on self_intro)、 P7-5 B2(中金 alias 缺)
  - **Round 1 bugs that REPRO**: P7-1 (bullets 仍融合)、 P7-2 + P8-2 (公司名 trun)、 P7-4 (project 字段漏)、 P7-6 (lowercase track key)、 P8-5 (一句话就生 draft, 现在 turn 2 就生)、 P8-3 (大宗能源 track 覆盖度) — 不在本轮 fix scope,本轮没专门 verify 但也没有 evidence 说已修
- **Verdict**: **blockers remain** — 红线 coach path 没 hard-block。 chat path 已 ship 了正确的体验; SAIF 教授 review 时看 chat 改写挑得动毛病,但要看 coach 对话,仍能看到 AI "polish 后入档可点" 的失败模式。

---

## New bugs

### Bug R2-1: B1 plausibility 在 coach `/plan/turn` 路径上 silently no-op (BLOCKER)

- **Step**: coach turn 2 (P8 red-line)
- **Endpoint**: `POST /api/resume-copilot/sessions/{id}/plan/turn`
- **Expected**: 当 draft 文本含 `独立完成 50MW 光伏电站 / 节约 100 万欧元 / 1.8 亿欧元` 时,`draft.risk_flags` 应含 `{"kind":"implausible_scale","blocking":true}`,coach 应进 EvidenceAuditFailed fallback,而不是 ship draft。
- **Actual**: `draft.risk_flags` 只含 7 条 `student_introduced_number`(blocking=false 黄色),`status: awaiting_review`(turn 2)→ `clarifying`(turn 3 重新加问)。
- **Root cause**: `audit_plausibility(plan.py:436)` 显式跳过 `item.kind not in (INTERNSHIP, PROJECT)`;coach 的 `_pick_item_for_user_answer` 把所有用户答案灌进 `current_item_id`(`/plan/start` 默认 self_intro);所以 B1 这一层永远没机会跑。 chat path 没这个问题因为它用 `field_path` 派生 synth item kind。
- **Repro one-liner**:
  ```python
  PYTHONPATH=backend backend/.venv/bin/python -c "
  from app.services.resume_copilot.plan import audit_plausibility, PlanItem, ItemKind
  d = '独立完成 50MW 光伏电站设计 节省项目成本 100 万欧元'
  print('INTERNSHIP:', audit_plausibility(d, PlanItem(kind=ItemKind.INTERNSHIP, title='X')))
  print('SELF_INTRO :', audit_plausibility(d, PlanItem(kind=ItemKind.SELF_INTRO, title='X')))
  "
  # INTERNSHIP: [implausible_scale blocking=True]
  # SELF_INTRO : []
  ```
- **Suggested fix (short)**: drop the `item.kind` gate;触发条件本身已经够窄(high-scale + ownership token),误报风险低。
- **Suggested fix (root)**: `_pick_item_for_user_answer` 加 topic-hop 启发式 — 答案文本里有 "光伏 / PVSyst / MW / 电站 / IRR" 等强主题信号时主动切到匹配的 internship 而不是默认 current_item。

### Bug R2-2: 中金公司 / 中国国际金融股份有限公司 不归一同 canonical key (MAJOR)

- **Step**: P8 `GET /recommendations`
- **Actual canonical dist (intern stream)**: `中国国际金融股份有限公司: 2 + 中金公司: 2 = 4 rows from the same firm`;cap 设的是 ≤ 3。
- **Why a student notices**: SAIF MF 学生扫推荐列表会觉得 "中金重复出现,这俩名其实一家"。
- **Fix**: `_COMPANY_SUFFIX_STRIP` 后再过一遍 alias map(`中国国际金融 ↔ 中金`、`平安科技 ↔ 平安`、`阿里巴巴 ↔ 阿里`、`字节跳动 ↔ 抖音` 等)。 SAIF 校招大公司 list 应该 < 60 家,alias map 手工维护得起。

### Bug R2-3: M2 dedup 只防 byte-exact,语义重复仍触发 (MINOR)

- **Step**: P7 coach turn 1 → turn 2 → turn 3 三个 open_questions
- **Actual**: open_questions 顺序:
  1. `"你在蚂蚁金服反欺诈实习中, 具体负责了模型迭代的哪部分工作? 是独自实现GraphSAGE模型, 还是参与特征工程或模型调优? 另外, 迭代后的模型效果提升 (如KS值提升0.06) 有没有具体的业务影响指标, 比如上线后的坏账率下降?"`
  2. `"你在这次模型迭代中具体负责了哪些工作? 是独立实现GraphSAGE模型、 参与特征工程还是模型调优? 另外, 模型上线后有没有带来具体的业务影响指标, 比如坏账率下降或风险拦截率提升?"`
  3. (audit-fallback Chinese tag question,不同问题)
- **判定**: Q1 vs Q2 在 normalize 后 80-char prefix 字面不等(开头分别是 "你在蚂蚁金服反欺诈实习中" vs "你在这次模型迭代中"),所以 dedup 不命中。 但语义上是完全等价的两问。 Round 1 的 verbatim 重复确实修了,但 LLM 自然会 paraphrase。
- **Suggested fix**: dedup 算法升级:(a) 切掉前导主语(`你在...中`),(b) hash 比较 question 后半段 / 关键词集合(`具体 / 负责 / 哪部分 / 工作 / 模型迭代 / 业务影响`)。 或更简单 —— 给 coach LLM 注入 prompt 约束 "看到 already-open_questions 列表,不要 paraphrase 重复"。

---

## Round 1 bugs that REPRO (still broken)

### P7-1 — Parser merges adjacent bullets

P7 parsed-profile `internships[0].bullets[2]` 仍是 `"AB 测试: 新算法相比 baseline 用户点击率提升 7.3%, 加仓转化率提升 4.1%, 在 6 万用户样本上验证做了一些数据维护工作"` — bullet 2 + 3 仍然融合,bullet 3 "做了一些数据维护工作" filler 仍被吞,`flow_padding_internship.bullet_index = 3` 这个 persona-defined 测试场景仍然失效。

Evidence:
```
internships[0].bullets:
  [0] "支持智能投顾系统 v3.0 推荐算法升级..."
  [1] "构建客户标签体系..."
  [2] "AB 测试: ... 在 6 万用户样本上验证做了一些数据维护工作"  ← merged
internships[1].bullets:
  [0] "支持小微企业贷款反欺诈模型迭代..."
  [1] "数据集: 蚂蚁金服小微贷款 ..."
  [2] "模型 KS 值从 0.42 提升到 0.48 (头部 5% 风险样本召回率 +8 pp)"
  [3] "已上线 A/B 测试与产品 + 数据 + 业务 4 个团队协同迭代 11 次, 写过 5 篇内部 tech memo"
```
P7 internships[1] 这次 4 条 bullet 拆对了(Round 1 是 3 条),所以 parser 这一侧有微改进,但 internships[0] 那条 fused bullet 仍在。

### P7-2 / P8-2 — Company name truncation 仍发生

- P7: `某券商 · 金融科技部 · 智能投顾组` → `某券商`;`蚂蚁金服 · 风险管理部 · 算法组` → `蚂蚁金服`
- P8: `国家电力投资集团 · 现货交易部` → `国家电力投资集团`;`某新能源开发公司 · 项目咨询部 (实习)` → `某新能源开发公司`

不在本轮 fix scope,Round 1 已报但未修。 注意 ConfirmedProfile (PUT) 是用 persona JSON 原文写的,所以 plan/recommendations 用的还是完整的 "某券商 · 金融科技部 · 智能投顾组";真正受影响的是 parsed-profile 这个早期 step,如果学生直接 confirm 它,department/team 就丢了。

### P7-3 残余 — pytorch / PyTorch / dgl / DGL 大小写 dupe (MINOR)

B4 修好了主问题(LightGBM / XGBoost / GraphSAGE 全在,"C" 不再凭空冒出),但 LLM-extracted token 跟 heuristic-extracted token 没大小写 normalize,导致 P7 同 token 有 `pytorch` + `PyTorch`、`dgl` + `DGL`。 P8 也有 `XGBoost` + `XGBoost (调参 + walk-forward CV 实战)` — LLM 把原句子整段当 skill 留着。

### P8-5 — Coach 一句话生 draft 仍是默认 (MINOR)

Round 1 P8 turn 1 就生 draft。 本轮 turn 1 走 clarifying(改善),但 turn 2 仍 ship draft + open_questions 只有 1 条。 还是没有 "至少 N 轮 / 至少 1 个 answered clarifying 才能 write" 的 floor。

### P8-3 — 大宗·能源 track 覆盖度 (本轮变好了)

Round 1 只回 1 条 (麦肯锡)。 本轮 P8 回 20 条,包括 Goldman Sachs / 中金 / 中核 / 长江证券 / 东吴证券 / 麦肯锡 — 推荐池似乎被补了。 **本轮算改善了**。 (没看到 "中信 / 国君 / 永安期货" 这些 round 1 期望的目标,但至少不是 1 条了。)

---

## Quick evidence references

- **证据 1 (B4 P7 skills)**: `/tmp/r2c_out/p7_state.json` → `.parsed_profile.body.profile.skills.technical` 包含 LightGBM / XGBoost / GraphSAGE / GAT / GCN / dgl / Spark SQL / Java / Linux / Docker / Kubernetes 等 31 项;无 "C"。
- **证据 2 (B2 P7 recs)**: `/tmp/r2c_out/p7_state.json` → 20→13 条;蚂蚁(canonical)= 6 行(campus 3 + intern 3 ≤ cap × 2 stream);其余 7 条来自宁波 / 上海 / 兴业 银行。
- **证据 3 (B4 P8 skills)**: `/tmp/r2c_out/p8_state.json` → `.parsed_profile.body.profile.skills.technical` 包含 LightGBM / XGBoost / 时间序列分析 / 电力市场知识 / DCF / IRR / Wind / iFinD / PVSyst。
- **证据 4 (M5 + M1 P8 turn 2 draft)**: `/tmp/r2c_out/p8_verify.json` → `.red_line_turn_2.items[id=6ea07c93...].draft` 含 7 条 `student_introduced_number` flag (blocking=false);**没** implausible_scale。
- **证据 5 (B1 unit-level verify)**: 直跑 `audit_plausibility` 同一 draft 文本,kind=INTERNSHIP 返 implausible_scale,kind=SELF_INTRO 返 [] — 证明实现正确,只是 coach 路由让它跑不到。
- **证据 6 (M2 normalize)**: 直跑 `_normalize_question_for_dedup` 在 P7 那两条相邻 question 上,80-char prefix 不等,dedup miss。
- **证据 7 (B1 chat path P8)**: msg 433 返 rewrite_options[0..1],两条都含 `audit_risks: [..., implausible_scale blocking=true]` + `warning_severity: "severe"` + warning 字符串含 `"规模 × 角色对不上"` 中文标签。
- **证据 8 (M1 P7 turn 3)**: open_questions[2] 文本 `"这一版我想再确认一下「动词太强 (e.g. 主导/独立完成)」(另外还有: 主导度需要佐证) — 能确认一下这段经历里你具体负责什么吗?..."` — overclaim / leadership_unverified 已翻成中文。

Raw response snapshots:
- `/tmp/r2c_out/p7_state.json`(upload + parse + recs)
- `/tmp/r2c_out/p7_verify.json`(plan start + 3 turns + final plan)
- `/tmp/r2c_out/p8_state.json`(upload + parse + recs)
- `/tmp/r2c_out/p8_verify.json`(plan start + 3 red-line turns + chat rewrite)

Session IDs / user_keys (dev DB):
- P7 sid=101 user_key=`sim_P7_20260521r2_12e5ddd5`
- P8 sid=103 user_key=`sim_P8_20260521r2_84e14c61`

Total wall time: P7 上传+生成 ~135s + verify ~12s = ~147s;P8 上传+生成 ~70s + verify ~25s = ~95s。
