# Brainstorm: 统一记忆 + Plan Mode 整体演进

**Date**: 2026-05-13
**Status**: 🟢 decisions locked — 2026-05-13 16:50 用户确认 1.1=B,1.2-1.7 全采纳推荐
**Purpose**: 在 PR-2 之前把"为什么这么做、有哪些备选、风险在哪、谁先动谁后动"
理清楚。不是设计文档(`unified-memory-and-plan-mode-2026-05-13.md` 已经写了),
是**这套设计为什么是这个样子,以及落地路径的 ordering / 取舍**。

---

## 决策快照(2026-05-13 锁定)

| # | 决定 | 影响 |
|---|---|---|
| **1.1** | **P0 = B(面试 KB 召回)** | 重排 PR 序,interview 提前 |
| 1.2 | B Strangler 双写 | extractor 同时写 student_experiences + account_memory |
| 1.3 | D 三来源分批,先 B | PR-2 chat 派生 evidence;PR-8 parser 写;Plan on-demand 是 fallback |
| 1.4 | C Plan 内嵌 snapshot | plan_json 存 evidence snapshot(不可变),account_memory 是 source of truth |
| 1.5 | B 用户主动勾 + 软提示 | commitment 状态机 UI 在 PR-8 才接 |
| 1.6 | C 渐进 — interview 框架先,KB 召回后 | interview 拆 2 个 PR |
| 1.7 | C 留口子不实现 | `source_module` 已能承载,user_key 合并工具未来再做 |

## P0=B 重排后的 PR 序

| PR | 内容 | 行数预估 | 状态 |
|---|---|---|---|
| PR-1 | account_memory 基建(model + migration + dispatcher + schemas + 52 测试) | ~1209 行 | ✅ 已完成 |
| **PR-2** | **Chat extractor 多 category + 双写 + evidence 派生** | ~250 | 🟢 进行中 |
| PR-3 | Interview subagent 基类 + ExperienceRecaller | ~250 | 待办 |
| PR-4 | AnswerScorer + FollowUpDecider | ~200 | 待办 |
| PR-5 | Interview Orchestrator + flag-branch + golden test | ~250 | 待办 — **P0 达成** |
| PR-6 | Plan Mode evidence 解耦(plan_json snapshot 化) | ~250 | 待办 |
| PR-7 | Plan finalize → commitment + 跨 session 复用 | ~150 | 待办 |
| PR-8 | Parser 同步写 + UI 轻确认 banner | ~150 | 待办 |

---

## 0. 为什么"复杂"

不只是因为代码多。复杂在**5 个维度同时演化**,每个维度都有自己的现状 / 目标 / 风险:

| 维度 | 现状 | 目标态 | 跨维度依赖 |
|---|---|---|---|
| **数据层** | 4 套半成品(student_experiences / plan_json embedded Evidence / parsed_profile / preferences) | 1 张 account_memory + provenance | 改了 schema 4 个模块都要跟 |
| **chat extractor** | Phase 1 已 ship,只抽 experience(category) | 多 category,派生 evidence | 升级要兼容老存储期 |
| **Plan Mode** | session 级,Evidence inline 在 plan_json | account 级,Evidence by-reference | 数据迁移敏感,prod active |
| **Mock Interview** | 单 LLM call,无 KB 召回 | subagent 化 + 召回 experience | 依赖记忆层先稳定 |
| **UI** | 无 memory 概念 | low-confidence inline 确认 | 依赖后端契约稳定 |

任一维度独立演化都不难。**难在 ordering——谁先动,谁等谁,谁可以并行**。

---

## 1. 先把"我现在能想到的所有真正的不确定性"列出来

> 每一条后面我标了**🤔 我倾向**和**🟥 等你拍板的关键**。
> 用户可以直接在每条 paste 一行答复,我据此往下推。

### 1.1 用户价值优先级
**问题**:**最该先做哪个价值点**?有四个候选,各自驱动的工程顺序完全不同:

- (A) **跨会话连续性** — 学生第二次进 plan,不用再回答相同问题 → 工程顺序:**unified memory → plan refactor 优先**
- (B) **面试里 KB 召回** — 学生答不上时 AI 提示 "你有 X 经历可以讲" → 工程顺序:**Phase 1 student_kb extractor 升级 → interview subagent 优先**
- (C) **简历去幻觉** — Plan Mode 的 evidence-cited 写作落到账号级,跨简历版本沿用 → 工程顺序:**memory + plan 优先,interview 推后**
- (D) **运营/数据可见性** — 我们想从后台看到学生 KB 在长什么样,辅助产品判断 → 工程顺序:**memory + admin UI 先,模块串行**

🤔 **我倾向 B**——它是用户面前最直接能感知 AI 能力的瞬间,且 Phase 1 已经垫了一半。但这是产品判断,你说了算。

🟥 **等你拍板**:A/B/C/D 哪个是 P0?(多选也行,但只有一个能"立刻动")

---

### 1.2 数据迁移激进度
**问题**:`student_experiences` 表和未来的 `account_memory` 怎么共存?

- (A) **激进**:PR-2 直接把 extractor 改成只写 `account_memory`,迁移老数据,下线 `student_experiences`。**风险高,1 周清结**
- (B) **温和**:Extractor **同时写两份**(shadow write),老路径继续 active,跑 2 周稳定后切;切完再下线老表。**风险低,3 周清结**
- (C) **冻结**:Phase 1 student_kb 不再写新数据,但保留可读;`account_memory` 是新业务专用。**风险最低,代码两份永久**

🤔 **我倾向 B**(strangler fig)。Claude Code memory 的实战经验也是这样:旧 .md 文件保留,新 frontmatter 渐进。

🟥 **等你拍板**:A/B/C?(也想听你对"prod 已经积累了多少 student_experiences 行"的判断——如果只有几十行,可以更激进)

---

### 1.3 `evidence` category 的来源
**问题**:Evidence 是 bullet 粒度的事实(metric/tech/role tag)。它**第一次入库**应该来自哪里?

- (A) **Resume parser** — Upload PDF 时 parser 跑 LLM 拆每个 bullet 的 metric/tech → 写 evidence。**优势:用户上传一刻就有 KB**
- (B) **Chat extractor 派生** — Experience 抽出时同时拆 metric/tech tags → 写 evidence。**优势:抽取上下文更完整**
- (C) **Plan Mode 接管** — 只有 plan 启动时按需把 parsed_profile 里的 bullet 转 evidence。**优势:不浪费 LLM call**
- (D) **三个都做** — A + B + C 都写,靠 summary_hash 去重

🤔 **我倾向 D**,但实施分批:**先 B(Phase 2 chat extractor 已有 LLM call,顺手派生)**,**再 A(parser 上传时一并跑)**,C 是自然 fallback。

🟥 **等你拍板**:OK 用 D 分批?还是先只走 B?

---

### 1.4 Plan Mode 内部的 Evidence 到底要不要迁
**问题**:`plan.py::PlanItem.evidence` 现在是内嵌完整 `Evidence` 对象到 plan_json。
迁到 account_memory 后:

- (A) **plan_json 只存 evidence_id list** — 真实数据在 account_memory。**plan_json 体积小但要 JOIN 才能用**
- (B) **plan_json 仍内嵌完整 Evidence** — 同时也写一份到 account_memory(冗余)。**易回滚但有不一致风险**
- (C) **plan_json 内嵌"snapshot"** — 不可变拷贝,account_memory 是 source of truth。**evidence 之后被 archive 不影响 plan 历史**

🤔 **我倾向 C** —— plan 是工件层,工件应当锁定 snapshot;memory 是事实层,事实可演化。这两层语义本来就分。

🟥 **等你拍板**:A/B/C?

---

### 1.5 谁来 own `commitment` 行的状态机
**问题**:Plan finalize 写 commitment(status=pending)。**后续怎么变 done?**

- (A) **Chat 推断** — Chat extractor 看到用户说"做完了"自动匹配 commitment 标 done。**LLM 误判概率不低**
- (B) **Plan 显式更新** — 用户在 plan 界面手动勾"完成"。**UX 重,但准**
- (C) **完全不更新** — commitment 只是历史记录,90 天后自动 abandoned。**最简单,但价值有限**

🤔 **我倾向 B + 软性 (A)**:UI 上让用户主动勾,但 chat 检测到"已完成"语义时**只发一个小气泡提示**,不直接改状态。

🟥 **等你拍板**:你倾向 commitment 是"系统智能识别"还是"用户主动勾"?

---

### 1.6 Interview Phase 2 的位置
**问题**:已有 `interview-subagent-design-2026-05-13.md`(Phase 2 的设计),
本设计是 Phase 2 的基础设施。两者的 ordering:

- (A) **先做完 unified memory(5 PR),再做 interview subagent** — 串行,稳但慢
- (B) **unified memory + interview subagent 并行**(不同分支),共用 `account_memory where category='experience'` 的 contract — 快但合并冲突
- (C) **interview subagent 先做框架(不接 KB 召回),后续 PR 接** — 渐进

🤔 **我倾向 C**:interview subagent 的 prompt 瘦身 + 结构化打分本身有独立价值,**KB 召回是其上的 add-on**,可以等 memory 稳定后挂载。

🟥 **等你拍板**:你想看到 interview 提升 早一点还是晚一点?

---

### 1.7 用户身份(user_key)的演进路径
**问题**:现在 user_key = localStorage UUID。未来上邮箱登录后,**旧 UUID 怎么办**?

- (A) **不管** — 老 UUID 自然死亡,登录后新 user_key 从零开始 KB。**用户损失历史**
- (B) **合并工具** — 登录时弹窗 "我们检测到这个浏览器上有 X 条历史记录,绑定到你的账号?"。**正确做法,工程量大**
- (C) **先留口子** — 现在不做,但 `account_memory` 加个 `legacy_user_keys: list[str]` payload 字段(放在 source_module side 还是 payload?)备后续合并用

🤔 **我倾向 C** —— 现在不动,但 schema 留扩展点。

🟥 **等你拍板**:OK 留口子但不实现?还是直接现在就规划用户系统?

---

## 2. 几个目前还没下结论的"过早优化"风险

- **跨 category SQL 性能** — account_memory 一张表,N 万行后,(user_key, category) 索引够吗?**🤔 现在用户少,半年内不用担心,但要留 schema 余地**
- **Pydantic v2 schema 演化** — payload_json 是裸 JSON。某天 EvidencePayload 加字段,老行读出来报错怎么办?**🤔 加 `payload_version` int 列,read 端 dispatch**
- **LLM 抽取的 hallucination 跨模块扩散** — 一条幻觉 evidence 被 plan 引用、被 interview 召回,**爆炸半径**。**🤔 raw_excerpt + confidence + user_confirmed 三层防,但要常 review**

---

## 3. 我提议的"先回答 1.1 → 一切就清晰"

`1.1` 的 A/B/C/D 是**决定**后面所有 ordering 的根。你选完 1.1,我可以:
- 立刻把后续 ordering 推出来(避免你逐条答 1.2-1.7)
- 把 PR-2/3/4/5 重排成符合 1.1 优先级的版本
- 只对剩余高耦合的问题(1.2 数据迁移 + 1.4 plan evidence 迁移)单独拉出来对齐

---

## 4. 我现在的精神状态

- PR-1 已 ship-able(account_memory 表 + dispatcher + 52 测试 + 0 回归)
- **但我不应该立刻做 PR-2,因为 PR-2 之后的方向取决于 1.1**
- 现在最好的状态:把 PR-1 commit + push(不动 prod,代码进版本控制),然后等你回答 1.1

---

## TODO — 用户填空区

> 直接在下面打字回复就行,我据此推动。

**1.1 用户价值优先级(P0):** _____________(A 跨会话 / B 面试召回 / C 简历去幻觉 / D 数据可见性,或自定义)

**1.2 数据迁移激进度:** _____________(默认 B strangler)

**1.3 evidence 来源策略:** _____________(默认 D 分批)

**1.4 plan_json 内嵌还是引用:** _____________(默认 C snapshot)

**1.5 commitment 状态机 owner:** _____________(默认 B 用户主动)

**1.6 interview Phase 2 ordering:** _____________(默认 C 渐进)

**1.7 user_key 演进:** _____________(默认 C 留口子)

**额外:**(任何你想补充的方向 / 否决 / 优先级)
