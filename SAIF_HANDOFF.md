# Saif Coaching Batch — Brainstorm Handoff Doc

> **Status**: 工作已完成（5 个 commits / ~9000 行 / backend 141 测试全过 / 前端 build 通过），但**因为跟另一会话的 memory 工作冲突已回退**，未部署。
> **Recovery tag**: `wip-saif-coaching-2026-05-14` 指向 `827978f`。要复活：`git reset --hard wip-saif-coaching-2026-05-14`。
> **此文档目的**：给重新 brainstorm 的会话当 context 起点。

---

## 1. Why（这个 feature 的初衷）

### 1.1 触发事件

2026-05-14 用户上传了两份资料到 `tencent-recruit-pack/`：
- **Saif 老师真实使用纪实**（`腾讯面试准备对话原文记录.md`，1407 行 / 44 轮对话）—— 一名 SAIF MBA 学生用 WorkBuddy 的「腾讯校园招聘」skill 全程跑了一遍：选岗 → 简历 → 面试 → 群面模拟 → 复盘
- **WorkBuddy `tencent-campus-recruit` skill 全文**（11 份 reference + 8 份 script）

Saif 老师的反应是："**面试部分很有借鉴意义**"。

### 1.2 我们当前模拟面试的 4 个 gap（对照 Saif 使用记录）

我们的 Mock Interview 模块已经很厚（Jerry 6 维 rubric / 动态 follow-up / 参考答案 / 弱项画像 / 周计划），但跟 Saif 老师的辅导对话比起来：

1. **教学体感差一档** —— 我们给的是诊断（hits/misses/bonuses 标签 + 0-100 分），Saif 老师给的是**辅导**（做得好 / 可提升 + 改写示例 / 打分 8.5/10 + 引用学生原话）
2. **缺前置脚手架** —— 没"💡 提示"告诉用户"这一题面试官在测什么"
3. **缺安全护栏** —— 学生问"我能过吗""字节通过率多少"我们没强制规避（LLM 会胡给）
4. **缺规则化反馈** —— 简历检查全靠 LLM，缺 zero-cost 即时规则反馈
5. **缺群面** —— 我们 1v1，但腾讯/字节/咨询都把群面当核心淘汰环节
6. **缺多阶段漏斗** —— 我们单一阶段，没有"业务一面 / 二面 / HR 面"的阶段化练习

---

## 2. What（实施了什么 — 4 个 tier）

### Tier 1：教学脚手架 + 安全护栏（5 个 batch）

- **T1.1 每题前置「💡 提示」**：每个 follow-up 题之外，让 LLM 多产一段 `coaching_hint` 字段，告诉学生"这题面试官想听什么 / 答题长度建议"。前端在题干上方用黄色 callout 卡呈现。skeleton 题硬编码 6 段提示，follow-up 让 LLM 出 JSON `{question, coaching_hint}`。

- **T1.2 重构每题反馈布局**：把 hits/misses/bonuses 标签 + 0-100 分换成 Saif 老师那种"做得好（带证据引用）/ 可提升（带改写示例）/ 打分 X.X/10"。新 schema `{strengths: [{point, evidence}], improvements: [{point, suggested_rewrite}], score_x10}`，旧字段从新结构派生作 backward compat。报告页用新结构，旧 hits/misses 折叠到 expandable。

- **T1.3 敏感话题三红线**：学生问薪酬数字 / 通过率 / offer 承诺时，LLM 走 fallback 话术（"以 HR 正式沟通为准"），不评估、不预测、不暗示。三处共享 `SAFETY_RAILS_SUFFIX` 常量。

- **T1.4 绝对化措辞禁令**：禁用"一定 / 肯定 / 必须"，统一"通常 / 往往 / 建议"。

- **T1.5 GOOD/BAD 示例对比**：每个 prompt 末尾加一组好/烂反馈对比例子，锚定 LLM 行为。

### Tier 2：内容层加固（3 个 batch）

- **T2.1 简历规则化检查**：纯 Python 7 条规则（R001-R007）：教育 / 项目 / 技能 / STAR / 量化 / 弱表达 / 篇幅。零 LLM、即时反馈，跟 LLM diagnostics 互补。基于 `ResumeProfilePayload` 结构化字段判断（不只是 raw text 扫词）。workspace 加折叠卡显示"规则检查 N 项 warning"。

- **T2.2 弱表达替换 anchor 示例**：14 条 weak→strong 示例（"参与了 → 负责 XX 模块的设计与实现" 等）注入 chat.py rewrite system prompt 做 few-shot。让 chat rewrite 候选直接给具体替换文案，不只抽象建议。

- **T2.3 岗位方向面试官视角库**：8 个 track（technical / data / product / consulting / game / market_fn / fintech / design）的 JSON 库，每条带 `interviewer_quote + key_dimensions[5] + drilling_priorities[3] + track_aliases`。三段式 match（exact alias → alias⊂target → target⊂alias）注入到 follow-up 用户 payload。

### Tier 3.1：群面（无领导小组讨论）模拟 MVP

复刻 Saif 老师转录里"5 个差异化背景同学一起讨论真实商业 case"的体验。

- **场景**：1 个手写 scenario（腾讯智慧零售 / 三线城市餐饮 / 3 人 6 个月，1:1 照搬转录）
- **Persona**：5 个手写 peer（B 产品 / C 奶茶运营 / D 技术 / E 营销 / F 金融），各带差异化 viewpoint_seed + tone + emoji
- **状态机**：`created → individual_statement → free_discussion ×2 → follow_up → completed`
- **Simulator**：串行调 LLM 生成每个 peer 的 in-character 发言（不是批调，因为批调会塌缩成"集体共识"），每次喂入累计 history 让后说的人能回应前面；LLM 失败 fallback 到 viewpoint_seed
- **Evaluator**：双轴打分（speak_quality_x10 + collaboration_x10），复用 T1.2 strengths/improvements schema；round-aware（individual 重 速度/深度/广度，free_discussion 重 整合 + 邀请式，follow_up 重 自我认知）
- **UI**：stacked bubble 列表（peer 头像 emoji + 名字 + 内容），用户气泡下方挂内联评分卡；不做 SVG 圆桌（v2 再说）
- **完整复盘报告**：avg speak_quality + avg collaboration + overall

### Tier 3.2：多阶段面试漏斗

把 1v1 拆成 3 个 stage（业务一面 / 业务二面 / HR 面）+ 群面（已有），让用户按真实校招漏斗练习。

- **Stage-aware prompts**：
  - `busi_2nd`：senior 视角，**强制抛 1 个场景题**，战略思维 lens
  - `hr`：跳过技术八股，按意愿适配/抗压/通用素质 3 类挑题
- **Stage-aware scoring**：scoring_system.md 加「按阶段调整评分侧重」段
- **跨阶段进度**：`/api/interview/stage-stats` 端点聚合 per-stage（session_count / avg / best / last 岗位），按 funnel 顺序排序，含群面数据
- **入口页**：4 个 stage 卡 + 顶部跨阶段进度条

### Tier 4（未实施）

spec 里规划了 3 个 batch 但**没做**：
- T4.1 选项式追问 (option-style clarification) — 待产品定位决策
- T4.2 求职画像跨 session 长期记忆 — **跟另一会话的 memory 工作直接冲突**（这就是这次回退的根本原因）
- T4.3 首次激活引导菜单 — 优先级低

---

## 3. 关键架构决策 + 经验教训

### 3.1 共享 `SAFETY_RAILS_SUFFIX` 常量

把"敏感话题红线 + 措辞约束"做成一个 Python 字符串常量（在 `services/interview/prompts/__init__.py`），4 处 prompt 文件都 append 一份，外加 2 个 .md prompt 内嵌相同文本。`test_safety_rails.py` 自动 catch regression。

**好处**：一处改全部地方都看得见；测试保证不漏。

### 3.2 双向 schema 降级（T1.2）

新评分 schema `score_x10 / strengths / improvements` 上线时，旧 `overall / hits / misses / bonuses` 仍然持久化。逻辑：
- LLM 只给新字段 → 从 strengths.point 派生 hits[]
- LLM 只给旧字段 → 从 overall 推 score_x10
- 前端报告页优先渲染新结构，旧字段折叠

**好处**：迁移期 backward compat 不破；老的 weakness aggregation 仍然 work。

### 3.3 Skeleton hint 硬编码 vs LLM 生成（T1.1）

Skeleton（前 6 题）的 coaching_hint 用**硬编码**（`SKELETON_HINTS_BY_INDEX` array, 1:1 对齐 SKELETON_TOPIC_LABELS）；只有 follow-up 让 LLM 出 JSON。

**好处**：零 LLM 成本 + 100% 一致性 + 不会 hallucinate"这题在测什么"。

### 3.4 群面 LLM 调度：串行 vs 批调（T3.1）

5 个 peer 的发言用 5 个**独立 chat call** 串行生成，每次喂入累计 history。**不是**一次性让 LLM 出 5 段。

**为什么**：批调会塌缩成"集体共识"——LLM 会自动协调让 5 个 peer 不冲突，破坏差异化属性。串行能保证每个 peer 站在自己 viewpoint_seed 的角度发声。

**代价**：5 次 LLM call 成本 + 延迟。可接受（一轮总共 30-60s）。

### 3.5 群面 evaluator 双轴评分

发言质量 (speak_quality) 和 合作表现 (collaboration) 是**正交维度**，必须分开打分。Saif 转录里强调："发言质量 = 整合 / 推进 / 差异化洞察；合作表现 = 尊重 / 推动共识 / 留空间。" 一个人可能"逻辑犀利但抢话筒"，发言质量高但合作低。

模型层、表层、UI 层全部对齐这两个轴。

### 3.6 资源 stage 字段放在 turn 层不是 session 层

InterviewTurn 加 `stage` 列（默认 `'busi_1v1'`），而**不是**新建 InterviewSession 表。理由：会话粒度的 session 不存在（只有 string session_id），加 stage 列是最小变更。**denormalized 但简单**。如果以后想做 InterviewSession 模型，再 refactor。

### 3.7 跨 stage 统计：1v1 + group 数据合一

`/stage-stats` 端点同时查 InterviewTurn 和 GroupInterviewSession 两张表，按 funnel 顺序输出 4 个 stage。group 的"per-session 分"是该 session 用户轮次中 (speak+collab)/2 的最大值；1v1 是该 session turn 中 score_x10 的最大值。

**注意**：这两个 score 的语义不完全一样（双轴 vs 单轴），用户看可能有点不适。

---

## 4. 文件全景（实施层 — 给新会话当代码索引）

### 4.1 新文件（19 个）

**Backend:**
- `backend/alembic/versions/0005_interview_turn_coaching.py` — coaching_hint + score_x10 + strengths_json + improvements_json
- `backend/alembic/versions/0006_feedback_rules_json.py` — resume_feedback_runs.rules_json
- `backend/alembic/versions/0007_group_interview.py` — 新建 group_interview_sessions + group_interview_turns
- `backend/alembic/versions/0008_interview_turn_stage.py` — interview_turns.stage
- `backend/app/services/resume_copilot/resume_rules.py` — 7 条规则纯 Python
- `backend/app/services/resume_copilot/rewrite_examples.py` — 14 条 weak→strong 示例
- `backend/app/services/interview/anchors/interviewer_perspectives.json` — 8 track 视角
- `backend/app/services/interview/perspective_lookup.py` — 三段式 match
- `backend/app/services/interview/group/scenarios.py` — 1 个手写场景
- `backend/app/services/interview/group/personas.py` — 5 个 peer
- `backend/app/services/interview/group/simulator.py` — peer 发言生成
- `backend/app/services/interview/group/evaluator.py` — 双轴评分
- `backend/app/services/interview/prompts/group_persona_system.md`
- `backend/app/services/interview/prompts/group_evaluator_system.md`
- `backend/tests/test_safety_rails.py`
- `backend/tests/test_resume_rules.py` (23 用例)
- `backend/tests/test_chat_rewrite_examples.py`
- `backend/tests/test_interviewer_perspectives.py` (13 用例)
- `backend/tests/test_group_interview.py` (15 用例)
- `backend/tests/test_interview_stages.py` (11 用例)
- `docs/superpowers/plans/2026-05-14-saif-coaching-batch.md` — spec doc

**Frontend:**
- `resume-copilot-web/app/interview/group/[sessionId]/page.tsx` — 群面页

### 4.2 修改文件（15 个）

**Backend:**
- `backend/app/models.py` — InterviewTurn 加 4 列 + GroupInterviewSession + GroupInterviewTurn 两表 + ResumeFeedbackRun.rules_json
- `backend/app/routers/interview.py` — coaching_hint SSE event + /stage-stats + /group/* 三端点
- `backend/app/routers/resume_copilot.py` — /rules-check 端点 + _maybe_sync_plan_to_profile helper（plan-sync 老 commit）
- `backend/app/services/interview/adaptive.py` — chat_text → chat_json + skeleton hints + plain-text legacy 兜底
- `backend/app/services/interview/llm.py` — _STAGE_PROMPT_BLOCKS + SAFETY_RAILS_SUFFIX append + stage 透传
- `backend/app/services/interview/orchestrator.py` — stage 透传 + 持久化
- `backend/app/services/interview/scoring.py` — StrengthPoint/ImprovementPoint dataclass + stage 字段
- `backend/app/services/interview/prompts/__init__.py` — SAFETY_RAILS_SUFFIX + GROUP_* prompts
- `backend/app/services/interview/prompts/scoring_system.md` — 新 schema + 阶段调整 + GOOD/BAD
- `backend/app/services/interview/prompts/follow_up_system.md` — JSON 输出 + GOOD/BAD + track_perspective 字段
- `backend/app/services/resume_copilot/chat.py` — 注入 rewrite_examples + SAFETY_RAILS_SUFFIX
- `backend/app/services/resume_copilot/workflow.py` — _persist_rules_check helper
- `backend/tests/test_adaptive_picker.py` — +5 用例
- `backend/tests/test_scoring_service.py` — +7 用例

**Frontend:**
- `resume-copilot-web/app/interview/page.tsx` — 4 stage 卡 + 跨阶段进度条
- `resume-copilot-web/app/interview/[sessionId]/page.tsx` — CoachingHintCallout + stage 透传
- `resume-copilot-web/app/interview/[sessionId]/report/page.tsx` — 新反馈结构（做得好/可提升+改写）+ 旧 hits/misses 折叠
- `resume-copilot-web/components/interview/api.ts` — coaching_hint SSE handler + stage option
- `resume-copilot-web/components/resume-copilot/api.ts` — getResumeRulesCheck
- `resume-copilot-web/components/resume-copilot/types.ts` — RulesCheckResult / RuleResult
- `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx` — rules check 折叠卡

---

## 5. 为什么回退（与 memory 分支冲突的细节）

部署到 VPS 时发现：

| 分支 | 位置 | HEAD |
|---|---|---|
| GitHub `origin/main` | github.com | `e659767`（alembic chain 修） |
| 我的 saif-coaching | `/home/ubuntu/projects/JobRadar` | `827978f`（9 commits 待 push） |
| 另一会话的 memory 工作 | `/home/ubuntu/opencode-worktrees/jobrador-edit` | `2d46445`（3 commits 未 push） |

**4 个文件冲突**：models.py / routers/resume_copilot.py / api.ts / public-resume-copilot.tsx

**Alembic 双头问题**：两条线都在 `c3f87a1e9b42` 之后加 migration（我加 0003-0008，memory 加 `f4d2c91a8e3b_account_memory_table`），合并需要手写 alembic merge migration。

**根本原因**：两个会话各自工作了一天，没协调。本身这是正常的并行开发，但 saif 工作量已经 9000+ 行，硬合代价高。

---

## 6. 给新会话的建议（重新 brainstorm 时）

### 6.1 概念上值得保留的（即使代码重写）

1. **教学口吻 vs 评测口吻** —— 这是 Saif 老师反馈的核心。具体表现：
   - 反馈结构: 做得好 / 可提升+改写 / 打分（不是 hits/misses 标签）
   - 措辞: 通常/往往/建议（不用 一定/必须）
   - 提示前置: 题前告诉学生"在测什么"

2. **安全护栏的共享常量化** —— 薪酬/通过率/offer 承诺三红线、绝对化措辞禁令，是所有 LLM 调用都该有的。值得做成一个共享 module。

3. **群面双轴评分** —— 发言质量 + 合作表现是正交的，分开打分。

4. **群面 5 peer 串行 LLM 调用** —— 别批调，会塌缩。

5. **多阶段漏斗** —— 业务一面 / 二面 / HR 面 prompt 不一样。HR 面禁问技术八股是关键。

### 6.2 实施顺序建议

跟之前一样按 tier 增量上：T1（prompt + UI）→ T2（规则/示例）→ T3.1（群面）→ T3.2（漏斗）。每个 tier 独立可发布。**不要一次性做 T4 的 memory 部分**——那块跟另一会话冲突的根源。

### 6.3 跟 memory 工作的协调

新会话开工前先确认：
- memory 分支是否已 push 到 GitHub？
- 是否要 cherry-pick 我之前的某些 commit 重做？
- saif 这块要不要先在独立 feature branch 做（不直接 commit 到 main），降低协调成本？

### 6.4 已经过验证的资料

- **Saif 老师转录**：`/home/chuanbo/projects/JobRadar/tencent-recruit-pack/腾讯面试准备对话原文记录.md`（1407 行）—— 群面那部分（约 lines 929-1340）是黄金参考，体感最准。
- **Tencent skill 全文**：`/home/chuanbo/projects/JobRadar/tencent-recruit-pack/tencent-campus-recruit/`（11 reference + 8 script）—— `interview-prep.md` / `sensitive-topics.md` / `resume-guide.md` / `job-database.md` / `resume_checker.py` 是直接借鉴源。
- **Recovery tag**：`wip-saif-coaching-2026-05-14` 指向 saif feature 完整版。如果想看具体代码怎么写，`git show wip-saif-coaching-2026-05-14:<path>`。

---

## 7. 验证状态（回退前）

- backend pytest: **141 passed**（含 saif 新增 ~50 用例 + 全套已有测试）
- 前端 `npm lint`: **0 errors / 2 pre-existing warnings**
- 前端 `npm run build`: ✓ 通过
- 手测：未做（直接 deploy 时发现冲突就回退了）

---

## 8. 下一步建议

1. 用户开**新会话**，把这份 doc 当作 context 起点
2. 先 `git fetch origin && git log origin/main` 确认 GitHub 当前状态（memory 分支可能已经 push 了）
3. 根据 memory 状态，决定 saif 工作怎么并入（独立 feature branch / 协调到 memory 之后 / 等等）
4. 重新 brainstorm 时**优先讨论**：
   - 群面的 persona / scenario 数据要不要扩（v1 只有 5 peer × 1 scenario）
   - HR 面 prompt 要不要更细分（理工科 / 商科 / 设计类 HR 提问角度不同）
   - 跨阶段统计的 score 语义统一问题（speak+collab 平均 vs score_x10 直接对比）
5. 实施时尽量用 superpowers/executing-plans 跑 spec doc 里的 checkbox

---

## 9. 联系到的设计 reference

- 自身 spec: `wip-saif-coaching-2026-05-14:docs/superpowers/plans/2026-05-14-saif-coaching-batch.md`
- 上传材料: `tencent-recruit-pack/`（不在 git 里，本地路径）
- Recovery: `git reset --hard wip-saif-coaching-2026-05-14`

如果新会话想先看代码再决定怎么做，建议从 `wip-saif-coaching-2026-05-14:backend/app/services/interview/group/` 起步——群面是最有差异化、最贴 Saif 转录的部分。
