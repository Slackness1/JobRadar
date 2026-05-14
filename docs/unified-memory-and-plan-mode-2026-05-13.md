# 设计文档:全局账号记忆 + Plan Mode 的统一架构

**Date**: 2026-05-13
**Author**: Claude Code (claude-opus-4-7) + Slackness1
**Status**: 设计中,待 review 后实施
**估时**: 后端 ~900 行 + 100 行测试 + 1 次 migration,3-4 天工程

---

## 1. 背景:当前其实有两个"半成品记忆系统"

走查代码后,JobRadar 现在并存两套**记一个学生事实**的机制:

| 系统 | 表 / 字段 | 粒度 | 触发模块 | 谁在用 |
|---|---|---|---|---|
| **Phase 1 student_kb**(已部分回滚) | `student_experiences` 表 | STAR-grained(整段经历) | chat 异步抽取 | 当前没人在读;原本是给 interview 召回 |
| **Plan Mode 的 Evidence**(active) | `ResumeCopilotSession.plan_json` 内嵌 | bullet-grained(一条 metric/tech/role 标签) | parse_resume + user_clarification | 仅本 session 的 plan agent 自用 |

**两者是同一概念在不同语境下的不同切面**:
- `Evidence` 是**原子事实**(citable)——"字节实习 / 次留率 12%→16% / 三个月"
- `StudentExperience` 是**叙事事实**(STAR-narratable)——"三个月内把次留率从 12 提到 16,我的做法是..."

一段经历可以**支撑**多个 Evidence;一组 Evidence 也可以**组合**成一段 STAR 经历。
这两层若各做一套永久存储,就会出三个问题:

1. **重复抽取** —— 同一份简历同样的 metric,plan 抽一次,chat 抽一次,可能不一致
2. **跨模块无引用** —— interview 想用 plan 已经验证过的 Evidence 做 STAR hook,只能再 LLM 推一遍
3. **跨会话丢失** —— plan 是 session 级,下次用户上传新简历,所有 Evidence 重头来

**Plan Mode 本身的设计极强**(读了 `plan.py` 后):
- "one tool call per turn"
- `audit_draft` 强制 draft 的每个 metric/tech/leadership 都 traceable 到 Evidence
- Blocking risk flags(missing_metric / vague_verb / tech_unverified)在数据层挡 hallucination

**这套思路应该升格成账号级**——它不该被 session 隔离绑死。

## 2. 设计原则(三条不变量)

### 原则一:**Memory 是事实层,Plan 是工件层**

> Memory 存的是**关于这个人的事实**(永久,跨对话)。
> Plan 存的是**某次为这个人产出的工件**(临时,可重做)。

工件可以 throw away 重做,事实不能。一份简历可以重写,但"我大三在字节做用户增长 + 次留率 12%→16%"这个事实只成立一次。

### 原则二:**单表 + category 鉴别符,而非多表分裂**

跟 Claude Code memory 的"平铺 .md + frontmatter type"对齐——单个 `account_memory` 表,
`category` 列鉴别行类型,category-specific 字段塞 `payload_json`。

**好处**:
- 跨 category 召回是同一条 SQL(`SELECT * WHERE user_key=? AND category IN (...)`)
- 加新 category 是新建 payload schema,不需 DB migration
- Provenance / staleness / confidence 三列对所有 category 统一

### 原则三:**UI 轻 — 模块感知强,用户感知弱**

参考 ChatGPT memory / Claude.ai memory:
- 默认**不打扰**用户,extractor 后台沉淀
- **只在 low-confidence 时**通过 inline 小气泡(不是单独页面)让用户确认/纠正
- 用户可以从设置入口审阅完整列表,但**90% 用户从不会打开**
- 真正的"产品力"在**模块如何用 memory**,不在用户怎么编辑 memory

## 3. 架构总览

```
┌────────────────────────────────────────────────────────────────────┐
│                  account_memory  (user_key 级,永久层)              │
│  ─────────────────────────────────────────────                     │
│  category         payload_json (category-specific)                  │
│  ─────────        ──────────────                                    │
│  evidence         {text, tags[], source, citation_msg_id}           │
│  experience       {summary, behavioral_hook, star_dimensions[],     │
│                    quantified, raw_excerpt}                          │
│  skill_claim      {skill_name, level, evidence_ids[]}               │
│  preference       {dimension, value} (city/role/comp/...)            │
│  identity_fact    {kind, value} (school/major/year)                 │
│  goal             {target_role, deadline, status}                    │
│  commitment       {description, deadline, linked_plan_item_id,      │
│                    status: pending|done|abandoned}                   │
│  weakness_signal  {dimension, severity, source_interview_id}        │
│                                                                      │
│  + 通用列(所有 category 共享):                                      │
│    user_key, summary_hash, confidence, user_confirmed,              │
│    source_module, source_session_id, captured_at,                   │
│    last_verified_at, last_used_at, use_count,                       │
│    superseded_by_id, is_archived                                    │
└────────────────────────────────────────────────────────────────────┘
                  ▲ writes              ▲ reads + writes
   ┌──────────────┼──────────────┐      │
   │              │              │      │
   ▼              ▼              ▼      ▼
┌─────────┐ ┌──────────┐  ┌──────────────────┐  ┌───────────────────┐
│ Chat    │ │ Resume   │  │  Plan Mode       │  │  Mock Interview   │
│ ext.    │ │ parser   │  │  (resume-build)  │  │                   │
│         │ │          │  │                  │  │                   │
│ writes: │ │ writes:  │  │ reads:  evidence │  │ reads: experience │
│ exp.    │ │ identity │  │         exp.     │  │        skill      │
│ skill   │ │ fact     │  │         goal     │  │        goal       │
│ pref    │ │ skill    │  │ writes: evidence │  │ writes: weakness  │
│ ident.  │ │ (raw)    │  │         (refined)│  │        signal     │
│         │ │          │  │         commit-  │  │        exp.       │
│         │ │          │  │         ment     │  │        (post-     │
│         │ │          │  │  (commitments    │  │        interview) │
│         │ │          │  │   created when   │  │                   │
│         │ │          │  │   plan approved) │  │                   │
└─────────┘ └──────────┘  └──────────────────┘  └───────────────────┘
```

## 4. Schema 详细设计

### 4.1 主表 `account_memory`

```python
class AccountMemory(Base):
    __tablename__ = "account_memory"
    id = Column(Integer, primary_key=True)

    # 主键维度
    user_key = Column(Text, nullable=False, index=True)
    category = Column(Text, nullable=False, index=True)
    # one of: evidence | experience | skill_claim | preference |
    #         identity_fact | goal | commitment | weakness_signal

    # 内容
    summary = Column(Text, default="")          # 短摘要,任何 category 都填
    payload_json = Column(Text, default="{}")   # category-specific 详细载荷
    summary_hash = Column(Text, default="", index=True)  # dedup key

    # Provenance(跨模块审计)
    source_module = Column(Text, default="")     # chat | plan | parser | interview | manual
    source_session_id = Column(Integer, nullable=True)  # 哪次 session 产生
    source_message_id = Column(Integer, nullable=True)  # chat/interview 内具体哪条消息
    raw_excerpt = Column(Text, default="")       # 原文引用(防幻觉锚)

    # 信度 & 用户确认
    confidence = Column(Float, default=0.0)
    user_confirmed = Column(Boolean, default=False, index=True)

    # 生命周期
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0)

    # 演化(版本超链)
    superseded_by_id = Column(Integer, nullable=True)  # 被哪条新行替代
    is_archived = Column(Boolean, default=False, index=True)

    __table_args__ = (
        UniqueConstraint("user_key", "summary_hash",
                         name="uq_account_memory_user_summary"),
    )
```

**重要决定**:
- **不分多表**——所有 category 共用一个表。Claude Code memory 是平铺 `.md` 文件 + frontmatter type discriminator,等价。
- **payload_json 不入 schema**——pydantic 在应用层校验,DB 只看 Text。新增 category 只需新增 pydantic model + extractor,无 migration。
- **dedup 仍按 (user_key, summary_hash)**——同一事实的不同表述只入库一次。
- **`superseded_by_id` 解决演化**——大三说"想做研发",大四说"想做产品",大四的行 superseded 大三的行。读端默认 `WHERE superseded_by_id IS NULL`。

### 4.2 各 category 的 payload schema(Pydantic)

```python
class EvidencePayload(BaseModel):
    """Bullet-grained citable fact. Source of truth for Plan Mode drafts."""
    text: str                          # "次留率从 12% 提到 16%"
    tags: list[EvidenceTag]            # type=metric, value="次留率"... (复用 plan.py 的 EvidenceTag)
    source: Literal["parsed_resume", "user_clarification", "uploaded_doc"]
    related_role: str | None = None    # "字节 / 产品实习生"

class ExperiencePayload(BaseModel):
    """STAR-narratable retelling. Used by interview recall."""
    behavioral_hook: str               # S=...|T=...|A=...|R=...
    star_dimensions: list[str]         # 14 个固定 ontology
    quantified: dict                   # {team_size: 50, duration_months: 3, outcome: ...}
    evidence_ids: list[int] = []       # 关联到 evidence category 的 row ids — 跨 category 链接

class SkillClaimPayload(BaseModel):
    skill_name: str                    # "Python pandas"
    level: Literal["basic", "intermediate", "advanced", "expert"] | None = None
    evidence_ids: list[int] = []       # 哪些 evidence 支撑(可空)

class PreferencePayload(BaseModel):
    dimension: Literal["city", "industry", "role", "comp", "company_type", "stage"]
    value: str                         # "上海" / "buy-side" / "18-25k" / ...

class IdentityFactPayload(BaseModel):
    kind: Literal["school", "major", "degree", "graduation_year", "program"]
    value: str

class GoalPayload(BaseModel):
    target_role: str                   # "买方量化研究员"
    deadline: str | None = None        # "2026 秋招"
    status: Literal["active", "paused", "achieved", "abandoned"] = "active"

class CommitmentPayload(BaseModel):
    description: str                   # "完成 字节实习 量化改写"
    deadline: datetime | None = None
    linked_plan_item_id: str | None = None  # plan.PlanItem.id
    status: Literal["pending", "done", "abandoned"] = "pending"

class WeaknessSignalPayload(BaseModel):
    dimension: str                     # "analytical_thinking"
    severity: Literal["minor", "moderate", "major"]
    source_interview_id: int           # InterviewReport.id
    suggested_practice: str | None = None
```

## 5. 模块间合同(读 / 写表)

### 5.1 Chat extractor(已有 Phase 1 代码,扩 category)

| 行为 | 写入 category | 触发 |
|---|---|---|
| 学生讲具体事件(含 STAR 三锚点) | `experience` + 派生 `evidence` (展开 metric/tech tags) | turn 末 BackgroundTask |
| 学生陈述技能 | `skill_claim` | 同上 |
| 学生表达偏好 | `preference` | 同上 |
| 学生 mention 学校/专业 | `identity_fact`(去重:已有 identity_fact 同 kind 就更新) | 同上 |

**新增**:派生 evidence 用一个独立 LLM call(或同一个 prompt 多任务输出),把
experience 里能 citable 的具体 metric/tech 拆出来,带 tags 入 `evidence` 行,
并在 experience 的 `payload_json.evidence_ids` 里反向链接。

### 5.2 Resume parser(`parser.py`)

| 行为 | 写入 category |
|---|---|
| Parse PDF 后,把 internships/projects 里的每个 bullet 抽 evidence | `evidence` (`source="parsed_resume"`) |
| Parse 出 school/major/degree | `identity_fact` |
| Parse 出 skills(raw 字符串) | `skill_claim`(low confidence,等 chat 进一步确认) |

**与现状的差**:目前 parser 把所有结构丢进 `ResumeParsedProfile.profile_json`,**没有任何账号级沉淀**。本设计让 parser 同时写一份到 account memory。

### 5.3 Plan Mode(resume-build agent)

| 行为 | 读 | 写 |
|---|---|---|
| 启动 / drafting_plan | `evidence`, `skill_claim`, `goal`, `preference` | — |
| `audit_draft` 检查 risk | `evidence` (确认 draft 引用合法) | — |
| User clarification 答出新事实 | — | `evidence` (`source="user_clarification"`) |
| `awaiting_plan_approval → done` | — | 每个 finalized PlanItem 写 `commitment`,关联 `linked_plan_item_id` |
| 用户后来在 chat 说"做完了" | 找 `commitment` 中 linked plan item 匹配 | 改 `commitment.status=done` |

**关键合同**:**Plan 的 Evidence 不再存 plan_json 内嵌**,改成存 `account_memory` 的
`evidence` category 行。`plan_json` 里只存 evidence 行的 id 引用。这样:
- 用户重做 plan → plan_json 重建 → 但 evidence 行还在,新 plan 不用重抽
- chat 新抽出的 evidence 自动也能被下一次 plan 用

### 5.4 Mock Interview(若未来上 Phase 2 subagent)

| 行为 | 读 | 写 |
|---|---|---|
| ExperienceRecaller 召回 | `experience` (with current_topic_dimensions 维度过滤) | 中标后的 use_count +1 |
| 面试结束 report 生成 | `experience`, `weakness_signal` (历史) | 新 `weakness_signal`(若本次暴露弱点) |
| Report 推荐"你应该练 X" | — | 写 `commitment`(可选,需要 user 确认) |

## 6. Plan Mode 与 Memory 的生命周期对接

### 6.1 Plan 启动

```
触发: POST /api/resume-copilot/sessions/{id}/plan/start
────────────────────────────────────────────────
1. 读 parsed_profile(session 级)
2. 同时读 account_memory:
   - evidence    where user_key=? AND superseded_by_id IS NULL
   - skill_claim where user_key=? (confirmed only?)
   - goal        where user_key=? AND payload.status='active'
   - preference  where user_key=?
3. 把 evidence 行 inject 到 PlanItem.evidence[] 列表(by reference, id only)
4. plan_status → drafting_plan
5. session.plan_json 持久化
```

### 6.2 Plan turn (drafting → user clarification → write)

```
agent action = "ask":
  - 写 OpenQuestion 到 plan_json
  - 不写 memory

user 答了 clarification:
  - chat extractor 异步跑(走老路径)→ 写 evidence 行到 memory
  - plan_turn 检查这条新 evidence 是否答了 current_item 的 OpenQuestion
  - 若是,attach evidence id 到 plan_item.evidence[]

agent action = "write":
  - audit_draft 用 plan_item.evidence (从 memory 读取) 校验
  - 通过 → plan_item.status = awaiting_review,draft 写入 plan_json
  - 失败(blocking risk)→ 不入 plan_json,告诉用户为什么
```

### 6.3 Plan 完成

```
触发: POST /api/resume-copilot/sessions/{id}/plan/finalize
────────────────────────────────────────────────
1. plan_status → done
2. **对每个 finalized PlanItem,在 account_memory 写一条 commitment**:
   payload: {
     description: f"已完成 {item.kind}/{item.title} 的简历写作",
     status: "done",
     linked_plan_item_id: item.id,
     deadline: None
   }
3. session 级的 plan_json 保留(供历史回看),但不再是 source of truth
```

### 6.4 跨会话:第二次 Plan

```
用户 N 周后传第二份简历(新 session)
────────────────────────────────────────────────
1. parser 跑(同 6.1 第 1 步)
2. plan/start 时读 account_memory
3. 看到之前的 evidence、commitment(状态 done)
4. drafting_plan 时,LLM 知道:
   - 用户已经"完成过"哪些 PlanItem(commitment status=done)→ 可以直接复用 draft
   - 用户从未做过的 kind → 重新走 ask/clarify 流程
5. 用户可以选"清空记忆重做" → archive 所有 commitment + evidence
```

这个就是**跨对话连续性的具体落地**——同一人第二次进 plan 模式,不用再答相同的 clarification。

## 7. UI 设计(轻路线)

### 7.1 默认情形:**用户完全感知不到 memory**

- chat extractor 后台跑,**不显示**任何"已沉淀 X 条"提示
- plan/interview 读 memory **静默**,**不告诉**用户"刚才用了你 3 周前提过的经历"
- account_memory 表对**普通用户透明**

### 7.2 唯一显眼的入口:**low-confidence 行的 inline 确认**

当 extractor 写了一条 `confidence < 0.7` 且 `user_confirmed=false` 的行,
**在下次该用户进入工作区时**,在 chat rail **顶部**显示一条小 banner(单条卡片):

```
┌────────────────────────────────────────────────┐
│  我想确认一下:你刚才说的「次留率 12%→16%」    │
│  是在字节实习对吗?   [对]  [不是]  [稍后]    │
└────────────────────────────────────────────────┘
```

- 用户点"对" → confirm
- 点"不是" → archive + LLM 重新解释一遍那段原文
- 点"稍后" → 24 小时内不再提示,但 row 状态不变

每次最多显示**一条**,避免打扰。

### 7.3 高级用户入口(隐藏)

设置页(或键盘 `Cmd+,`)有"我的 AI 记忆"折叠面板,展示所有行:
- 按 category 分组
- 每行可 archive / delete / edit summary
- 大多数用户从不打开

**最低限度**:Phase 1 可以只有 setting 页 placeholder,不实现 UI。等用户真的有需求再做。

## 8. 现状到目标的 Migration Plan

### 8.1 现状清单

| 项 | 状态 |
|---|---|
| `student_experiences` 表 | 已存在(c3f87a1e9b42 migration applied) |
| `student_experiences` 数据 | 可能有少量测试数据(deploy 后曾测过) |
| `ResumeCopilotSession.plan_json` 含 Evidence | active 使用中 |
| `app/services/resume_copilot/memory/extractor.py` | 已有 ~400 行,扩 category 即可 |
| `app/services/resume_copilot/plan.py` Evidence 类 | active 使用中 |
| `app/services/resume_copilot/parser.py` | 不写 account memory |

### 8.2 Migration 5 步

```
Step 1: 新表 account_memory(新 alembic migration)
        ── 不删 student_experiences,先共存
        ── account_memory 用更通用的 schema

Step 2: 数据迁移脚本(`scripts/migrate_student_experiences_to_memory.py`)
        ── 把 student_experiences 行 1:1 迁到 account_memory(category="experience")
        ── 一次性,跑完后 student_experiences 表只保留作历史归档

Step 3: 改造 extractor
        ── 输出多 category 行(不只 experience)
        ── 派生 evidence(从 experience 拆 metric/tech 出来)

Step 4: 改造 plan_turn.py
        ── 读 evidence: 从 account_memory 而非 plan_json 内嵌
        ── 写 evidence: 新 evidence 入 account_memory + plan_json 只存 id
        ── finalize 时写 commitment

Step 5: parser.py 同步写 identity_fact + skill_claim(raw)
```

每个 step 独立 PR,**flag-gated**(`UNIFIED_MEMORY_ENABLED`,默认 OFF):
- flag OFF:走老 path(student_experiences + plan_json 内嵌 Evidence)
- flag ON:走 account_memory 统一路径

灰度跑 1-2 周稳定后,删除老 path 代码 + drop student_experiences 表。

### 8.3 兼容性 — Phase 1 student_kb 怎么处理

Phase 1 我已 ship 的 `student_kb router`,选项:
- **A. 保留 + 改实现**——`/api/student-kb/*` 后端改读 `account_memory where category='experience'`,前端不动
- **B. 弃用 + 新 router**——`/api/account-memory/*` 是新 API,旧 student-kb 路径 deprecate

倾向 **A**——URL 稳定有利于已有前端代码不改;且 student_kb 是"看 experience" 这一面,语义没变。

## 9. 失败模式 / 风险

| 风险 | 应对 |
|---|---|
| **payload_json 没 schema 校验导致脏数据** | 应用层用 pydantic 校验,任何写入路径强制经过 dispatcher;不允许直接 `json.dumps` 入库 |
| **跨 category 召回 SQL 慢**(无索引覆盖) | (user_key, category) 联合索引,关键 category 单独有 partial index |
| **superseded_by_id 形成环** | 写入时检查 `not exists(target where superseded_by_id = self)` |
| **payload schema 演化破坏旧行** | 加 `payload_version` int 列(隐式 default 1),read 端 dispatch 适配 |
| **chat extractor 与 parser 同时写同一 identity_fact** | (user_key, summary_hash) 唯一索引天然 dedup;两者用相同 hash 规则 |
| **plan 跨 session 时承接错乱**(用户传两份完全不同的简历) | plan/start 默认读 memory,但**提供"清空记忆重做"按钮**——一键 archive 该 user 全部记忆 |
| **commitment 永远 pending(用户没真的做)** | 90 天后自动转 `abandoned`,daily 后台任务;LLM 拒绝再引用 abandoned 的 commitment |
| **隐私/账号合并** | 当前 user_key 是 localStorage uuid,**没真账号**。本设计先支持 uuid 模式;后续支持邮箱/手机登录时,加一次 `merge_user_keys(old, new)` 工具 |

## 10. Open Questions(等你拍板)

1. **`student_experiences` 表要不要保留兼容?**
   - 保留:风险低,代码两份
   - 移除:干净,需要数据迁移脚本
   - **倾向**:保留 1 个 alembic 周期,确认稳定后 drop

2. **`evidence` category 的 dedup hash 该怎么算?**
   - 选项 A:hash(text) — 同一句话 dedup,但同义不同写法的不去重
   - 选项 B:hash(canonicalized_tags) — 按 tags 集合 dedup,泛化更好但实现复杂
   - **倾向**:首版选 A,后续 LLM 跑一遍合并 pass

3. **新 evidence 进来后,要不要自动 attach 到 ongoing plan?**
   - YES:chat 实时帮 plan 答 OpenQuestion,体验丝滑
   - NO:plan 是用户主动驱动,自动 attach 可能扰乱
   - **倾向**:YES,但**仅当 confidence > 0.85**;< 0.85 留给用户在 plan 里手动 attach

4. **`commitment` 是否自动从 chat 抽?**
   - 学生说"我下周会练 STAR"——LLM 看了应该写 commitment
   - 但这跟 plan-finalize 写 commitment 概念上重叠了
   - **倾向**:只在 plan-finalize 写;chat 不抽。Plan 是 commitment 的唯一 producer

5. **跨账号/用户合并**
   - 当前 `user_key` 是 localStorage uuid。同一个学生换浏览器 = 两个 user_key
   - 未来加邮箱登录,要 `merge_user_keys(old, new)` 工具吗?
   - **倾向**:本设计先不做,但 schema 留 `legacy_user_keys: list[str]` 字段(payload 里),
      未来 merge 时把旧 key 写进 list,query 时 OR 它

6. **Memory 的「忘记」有没有时间窗?**
   - 比如 1 年没动的 row 是不是该自动 archive?
   - **倾向**:NO 自动 archive。学生求职链路长,2 年前的 experience 也可能用得上。
      但 read 端按 recency 加 decay 权重(已设计)

## 11. 实施计划(分 5 个 PR)

### PR-1:`account_memory` 表 + pydantic schemas + dispatcher(~250 行)
- 新建 `app/models.py` AccountMemory
- 新建 `app/services/memory/` 包,含 payload schemas + dispatcher(写入唯一入口)
- alembic migration(幂等,沿用 c3f87a1e9b42 的写法)
- 单测
- **flag 默认 OFF**;新表存在但没人写

### PR-2:Chat extractor 升级到多 category(~200 行)
- 改 `extractor.py` 输出多 category(从原本只 experience 扩到含 evidence/skill_claim/preference/identity_fact)
- 派生 evidence:从 experience 里拆 metric/tech tags
- 单测覆盖 12 case(同 Phase 1 evaluator,扩到多 category 输出)
- flag ON 时走新 path,OFF 走老 student_kb path

### PR-3:Plan Mode 解耦 Evidence(~250 行)
- `plan_turn.py` 改 evidence 读源:`account_memory where category='evidence'`
- `plan_json` 内嵌 Evidence 改成 evidence_id list
- 数据迁移工具:把 `plan_json.items[].evidence[]` 内嵌项 backfill 到 `account_memory`
- 现有 plan 测试全过

### PR-4:Plan finalize 写 commitment + 跨 session 复用(~150 行)
- finalize hook 写 commitment 行
- plan/start 改为读 account_memory 而非只 parsed_profile
- 新增 "清空记忆重做" endpoint

### PR-5:Parser 同步写 + UI 轻确认(~100 行 + 前端 50 行)
- `parser.py` 在写 ResumeParsedProfile 时**同时**写 identity_fact + raw skill_claim 到 memory
- 前端 chat rail 顶部加 low-confidence inline 确认 banner
- 设置页 placeholder

每 PR ~1 天工程。全做完估 5 天。

---

## Appendix A:与现有几个文档/Phase 的关系

| 文档 / Phase | 关系 |
|---|---|
| Phase 1 student_kb(已部分 ship) | 是本设计的"experience" + "skill_claim" 子集,被吸收进来 |
| `interview-subagent-design-2026-05-13.md` | 本设计完成后,interview Phase 2 的 ExperienceRecaller 读 `account_memory where category='experience'`,语义不变 |
| Plan Mode 的 plan.py(active) | 本设计**不动 plan 状态机**,只把 Evidence 存储从 session 内嵌迁出到 account_memory |
| `saif-proposal-v0.1.md`(SAIF 项目相关) | 本设计是 SAIF 项目的"长期记忆"基础设施,可在 proposal 里 cite |

## Appendix B:与 Claude Code memory 的对齐

| Claude Code memory | 本项目 account_memory |
|---|---|
| `~/.claude/projects/<path>/memory/MEMORY.md` index | `account_memory` 按 (user_key, captured_at desc) 拉的 summary 列表 |
| `<name>.md` 文件 + frontmatter | `account_memory` 单行 + payload_json |
| frontmatter `type: user/feedback/project/reference` | `category` 列(experience/evidence/.../weakness_signal) |
| `originSessionId` 字段 | `source_session_id` + `source_module` + `source_message_id` |
| `<system-reminder>memory is N days old</system-reminder>` | read 端注入 `[captured N days ago, verify if material]` |
| "What NOT to save" 清单 | extractor 三锚点 + payload pydantic 校验 |
| 用户手动编辑 MEMORY.md | 设置页隐藏入口(Phase later) |
| 静默推荐 + recommend 前 verify | low-confidence inline 确认 + use_count 跟踪 |

**核心理念保留**:**事实分类 + provenance 强追溯 + staleness 警示 + 用户最终掌权**。

---

## 一句话总结

Memory 是**账号级永久事实层**(单表 + category 鉴别符 + 强 provenance),Plan / Chat / Interview 是 **memory 的 I/O 客户端**。Plan Mode 的 Evidence 不再 session-内嵌,改为 account_memory 行 + plan_json 只存 id 引用——跨会话连续性自然得到。UI 极轻,默认用户感知不到 memory,只在 low-confidence 时 inline 小气泡确认。
