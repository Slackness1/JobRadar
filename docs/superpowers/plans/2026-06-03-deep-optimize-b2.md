# 深度优化(反问取证 · 重塑 coach)实施计划 — B-深度优化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans / subagent-driven-development。Steps 用 checkbox。

**Goal:** 从打分的逐段缺口点进来 → AI 在流式文字里反问取证(无选择框)→ 把学生真实细节问出来 → 针对目标 subcat 定制改写写回 profile。重塑鸡肋的 coach。

**Architecture(关键:复用,不重建):** 现有 coach/plan 管道**已具备**反问(`OpenQuestion`)、证据门(`audit_draft`/`EvidenceAuditFailed`)、记忆写入(BackgroundTasks→`extract_for_chat_turn`)、thesis-aware 改写(`propose_rewrite_v0_v2` + 编数字红线)。本期是**定向改造**:① 从打分 gap 播种一个聚焦单段的 plan;② 第一句反问先对齐目标 subcat;③ 反问由打分缺口驱动(缺 Result 问结果、缺量化问真实数字);④ 改写按 subcat 定制 + 写回 → 中栏预览刷新;⑤ 前端流式面板(chip C)。

**Tech Stack:** 后端 FastAPI/SQLAlchemy + 现有 `plan.py`/`plan_turn.py`/`chat.py` 管道;前端 Next.js + chip C 外壳。后端 TDD;前端 lint+build+人工。

**复用的现成件(已读):**
- `app/services/resume_copilot/plan.py` — `PlanState`/`PlanItem`(kind/status/evidence/draft/open_questions)、`init_plan_from_template`、`apply_action`、`audit_draft`、`EvidenceAuditFailed`、`ItemKind`/`ItemStatus`。纯函数无 I/O。
- `app/services/resume_copilot/plan_turn.py` — `run_plan_turn`(one-tool-per-turn 编排)、`_is_finalize_intent`、clarification attach、`_format_assistant_reply`。
- `app/routers/resume_copilot.py` — `POST /sessions/{id}/plan/turn`(`post_plan_turn`→`run_plan_turn`)、`POST /chat`、`POST /chat/apply-rewrite`(`propose_rewrite_v0_v2`)。
- `app/services/resume_copilot/scoring.py` — `score_resume` 产 `SectionGap`(section/label/gaps/detail)。
- 记忆写入唯一路径:BackgroundTasks → `extract_for_chat_turn`(硬契约 5,**不要**绕)。
- 改写硬契约:`_detect_fabricated_numbers` warning 必须露出(硬契约 2);evidence_id 必须来自 `_profile_to_evidence_list`(硬契约 3)。

**范围边界:** 不重写 plan 状态机;不碰打分(已好);不做编辑页三栏/WYSIWYG(另计划)。本期产出 = 深度优化能从 gap 跑通一段经历的反问→改写→写回 + chip C 外壳把打分/优化/自由chat 串起来。

---

## Task 1:从打分 gap 播种聚焦 plan(后端,纯函数,TDD)

**Files:**
- Create: `backend/app/services/resume_copilot/deep_optimize.py`
- Test: `backend/tests/test_deep_optimize.py`

新函数 `seed_plan_from_gap(section, label, gap_tags, gap_detail, target_track) -> PlanState`:建一个**单 item** 的 `PlanState`(item.kind 由 section 前缀推导:internships→EXPERIENCE / projects→PROJECT / 其它→对应 ItemKind),item.title = label,status=CLARIFYING,并预置**第一条 open_question = 对齐 subcat**(「这段要往「{target_track}」方向改吗?如果目标不同先告诉我」),把 gap_detail 作为一条 `Evidence`(source='score_gap')挂上(供后续 audit/prompt 参考,但不当用户事实)。

- [ ] **Step 1: 写失败测试**
```python
# backend/tests/test_deep_optimize.py
from app.services.resume_copilot.deep_optimize import seed_plan_from_gap
from app.services.resume_copilot.plan import ItemKind, ItemStatus, PlanStatus

def test_seed_from_internship_gap():
    plan = seed_plan_from_gap(
        section='internships.0', label='九坤投资 · 量化研究实习',
        gap_tags=['STAR 缺 Result'], gap_detail='协助搭建因子回测框架缺最终结果',
        target_track='量化',
    )
    assert plan.status == PlanStatus.CLARIFYING
    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.kind == ItemKind.EXPERIENCE
    assert item.title == '九坤投资 · 量化研究实习'
    assert item.status == ItemStatus.CLARIFYING
    # 第一条反问对齐 subcat
    assert '量化' in item.open_questions[0].text
    # gap detail 作为 score_gap evidence 挂上
    assert any(e.source == 'score_gap' for e in item.evidence)
```

- [ ] **Step 2: 跑测试确认 FAIL** — `ModuleNotFoundError: ...deep_optimize`。

- [ ] **Step 3: 实现 `seed_plan_from_gap`**(用 `plan.py` 的 PlanState/PlanItem/OpenQuestion/Evidence/EvidenceTag;item id 用 uuid;kind 映射表 `{'internships':EXPERIENCE,'projects':PROJECT,'education':EDUCATION_或最接近,...}`,未知前缀 fallback EXPERIENCE;current_item_id 指向该 item)。**不写 DB**(纯函数,和 plan.py 一致)。

- [ ] **Step 4: 跑测试确认 PASS。**

- [ ] **Step 5: Commit** `feat(deep-opt): 从打分 gap 播种聚焦单段 plan + subcat 对齐首问`

---

## Task 2:反问由打分缺口驱动(后端 prompt,TDD)

**Files:**
- Modify: `backend/app/services/resume_copilot/plan_turn.py`(ask-prompt 注入 gap 上下文)或在 `deep_optimize.py` 加一个 `deep_optimize_ask_context(plan) -> str` 拼到 run_plan_turn 的 system/context
- Test: `backend/tests/test_deep_optimize.py`(追加)

让反问针对缺口:缺 Result→问真实结果/影响;缺量化→问真实数字/范围/频次;可防守性低→问「面试官追问你怎么答」。从 item 的 `score_gap` evidence + gap_tags 生成一段 prompt 提示注入到 run_plan_turn 的提问上下文(**不**让 LLM 自己编内容,只引导它问对问题)。

- [ ] **Step 1: 写测试** — `deep_optimize_ask_context` 输入含 'STAR 缺 Result' 的 plan,输出文本含「结果」/「影响」之类引导词;含 '量化' tag 时含「数字/范围/频次」。

- [ ] **Step 2: 跑确认 FAIL。**

- [ ] **Step 3: 实现** `deep_optimize_ask_context(plan)`:读 current item 的 score_gap evidence + tags,映射成提问引导短语表(`{'result':'追问可核实的最终结果与影响','quant':'追问真实的数字/范围/频次,不接受估测','defensibility':'追问面试官会怎么追问、学生怎么答'}`),拼成一段「本段已知缺口,请据此提问取证(不要替学生编造)」。在 `run_plan_turn` 走深度优化时把它并入提问上下文。

- [ ] **Step 4: 跑确认 PASS。**

- [ ] **Step 5: Commit** `feat(deep-opt): 反问由打分缺口驱动 — 缺Result/缺量化/可防守性 各自取证`

---

## Task 3:深度优化 start 接口(后端 endpoint,TDD)

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`(加 `POST /sessions/{id}/deep-optimize/start`)
- Modify: 持久化 plan 的现有路径(plan 存在哪 grep 确认:`grep -n "plan_json\|PlanState\|save_plan\|load_plan" app/routers/resume_copilot.py app/services/resume_copilot/plan_sync.py`)
- Test: `backend/tests/test_deep_optimize_router.py`

接口入参 `{section, label, gaps[], detail, target_track}` → `seed_plan_from_gap` → 存为该 session 的当前 plan(复用现有 plan 持久化)→ 返回 `PlanStateOut`(首问已在里面)。后续反问走**现成** `POST /plan/turn`,改写写回走现成 `apply-rewrite`/write。**写接口**,加 `_assert_not_demo` + owner guard。

- [ ] **Step 1: 写测试**(自建 in-memory client,见 `test_resume_scoring_router.py` 模式):POST start with section=internships.0/target_track=量化 → 200,返回 plan 含一个 item + 首问含「量化」;demo session(user_key=__demo__)→ 403。

- [ ] **Step 2: 跑确认 FAIL。**

- [ ] **Step 3: 实现 endpoint**(grep 确认 plan 持久化函数后,seed→save→return PlanStateOut;复用 `_get_session_or_404`/`_assert_session_owner`/`_assert_not_demo`)。

- [ ] **Step 4: 跑确认 PASS。**

- [ ] **Step 5: Commit** `feat(deep-opt): POST /deep-optimize/start — gap 播种 + 持久化 plan`

---

## Task 4:改写按 subcat 定制 + 写回(后端,TDD)

**Files:**
- Modify: `backend/app/routers/resume_copilot.py` 或 `chat.py` 调用点 — 深度优化的写回走 `propose_rewrite_v0_v2(..., target_title/target_job_description = subcat 上下文)`,确保改写朝目标 subcat;保留 `_build_fabrication_warnings`(硬契约 2)。
- Test: `backend/tests/test_deep_optimize.py`(追加,provider 注入)

复用 `propose_rewrite_v0_v2`(已有 target_title 参数),深度优化时把 target_track 作为改写定向上下文传进去;断言改写结果仍带 fabrication warnings 字段(不被剥)。

- [ ] **Step 1: 写测试** — 注入 fake v2 provider,调用深度优化写回路径,断言返回含 `warnings`(编数字红线未被剥)+ 改写朝 subcat(prompt 里含 target_track)。

- [ ] **Step 2-4: FAIL → 实现(传 target_track 进改写上下文)→ PASS。**

- [ ] **Step 5: Commit** `feat(deep-opt): 改写按目标 subcat 定制 + 保留编数字红线`

---

## Task 5:前端 DeepOptimizePanel(流式反问,无选择框)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/scoring/DeepOptimizePanel.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`(加 `startDeepOptimize` + 复用现有 plan/turn、chat api)

照线稿 `wf/wf-scoring.jsx` 的 DeepOptimizePanel + 设计要点:**反问在流式文字里直接问,不做选择框**;顶部显示锁定的段 + 目标 subcat;对话区 = AI 反问气泡 + 用户回答输入;改写结果出来后一个「应用 → 写回简历」按钮(点了 PATCH confirmed-profile → 中栏/预览刷新)。复用现有 chat 气泡样式。

- [ ] **Step 1: api** — `startDeepOptimize(sessionId, {section,label,gaps,detail,targetTrack})` → POST start;反问 turn 复用现有 plan/turn api;改写应用复用现有 apply-rewrite。
- [ ] **Step 2: DeepOptimizePanel 组件** — props `{sessionId, gap: ScoreSectionGap, targetTrack, onApplied}`;mount 时 startDeepOptimize 拿首问;输入→plan/turn→渲染下一反问;改写出现→应用按钮。HiFi `.hf` / `.rc-score` 风格一致。
- [ ] **Step 3: lint + build** — `npm run lint`(0 error)+ `npm run build`。
- [ ] **Step 4: Commit** `feat(deep-opt-fe): DeepOptimizePanel 流式反问取证面板`

---

## Task 6:AI 助手 v2 右栏 chip 外壳(C)+ 串联

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/scoring/AssistantV2Pane.tsx`
- (可选 mount)在一个可视页里挂(编辑页未建,先独立页 `/resume-copilot/assistant?session=` 或挂工作台)

chip C:底部 composer 上方 3 chip(简历打分 / 深度优化 / 自由问)。
- **简历打分** chip → mount 已建的 `<ScoreReport showHead={false}>`,其逐段缺口 CTA「去深度优化这段」→ **切到深度优化 chip 并 seed 该 gap**(这是打分→优化的串联点)。
- **深度优化** chip → `<DeepOptimizePanel>`(无 gap 时提示「从打分的逐段缺口进来」)。
- **自由问** chip → 复用现有 chat(`POST /chat` + 现有气泡)。

- [ ] **Step 1: AssistantV2Pane** — chip 状态机 + 三能力挂载 + gap 串联(打分 CTA setState→深度优化 + seed)。
- [ ] **Step 2: lint + build。**
- [ ] **Step 3: 人工目测**(dev :3001)对照线稿 + 走通「打分→点缺口→深度优化反问→改写应用→预览刷新」。**用户确认后提交。**
- [ ] **Step 4: Commit** `feat(deep-opt-fe): AI 助手 v2 chip C 外壳 — 打分/深度优化/自由问 串联`

---

## Task 7:回归

- [ ] 后端:`pytest tests/test_deep_optimize.py tests/test_deep_optimize_router.py tests/test_resume_plan.py tests/test_resume_plan_turn.py tests/test_rewrite_v0_v2.py tests/test_chat_audit_integration.py -x`(确认没碰坏 plan/改写管道)。
- [ ] 前端:`npm run lint && npm run build`。

---

## Self-Review(对照设计 + spec)
- ✅ 从打分 gap 进入 → Task 1 seed + Task 6 串联
- ✅ 流式反问无选择框 → Task 5(前端渲成 chat,不渲选择框)
- ✅ 反问由缺口驱动 → Task 2
- ✅ 第一句对齐 subcat → Task 1 首问
- ✅ 取证写记忆 → 复用 BackgroundTasks→extract_for_chat_turn(不绕,硬契约 5)
- ✅ 改写按 subcat + 编数字红线 → Task 4
- ✅ chip C 三能力共存 → Task 6
- **未覆盖(后续):** 编辑页三栏 + WYSIWYG 导出(另计划 Track A);深度优化的「reask 上限/多段排队」可后续加。
- **复用而非重建:** plan 状态机 / audit_draft / 记忆 / 改写 全部复用,本期只加 seed + gap 驱动 + subcat 定向 + 前端面板。
