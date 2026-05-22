# 主工作台 — 测试 finding 修复计划 (2026-05-20)

> 基于 `docs/eval-full-loop-reports/workspace-2026-05-20.md` 的 6 个 finding,本文给出 **2 个 blocking 修复** 的具体方案 + **2 个 ❓ WHY 调查结论**(plan-mode 无反问 / chat preference 漏判)。
>
> 修复完只需 P1 + P8 两个 persona 重测半轮即可放行 demo。

---

## 修复 #1 (🔴 blocking) — 防编数字红线被绕过 (Finding #1)

### 现象回顾
- P8 资料里故意埋"PVSyst 完成 50MW 光伏电站设计,节约项目成本 **100 万欧元**"是假数字
- AI 改写后 `v2.warnings = []`,**没有任何 fabricated_number 警告**
- `suggestion_options` 字段(填实数/删数/接受模糊版本)也压根没出现在响应里

### 根因(已读源码确认)
`backend/app/services/resume_copilot/chat.py:282-308` `_profile_anchor_numbers()` 把 **简历里所有 bullet** 的数字扫一遍当成 anchor,然后 `_detect_fabricated_numbers()` 返回 `v2_numbers - anchor`:

```python
def _detect_fabricated_numbers(improved, anchor):
    found = set()
    for bullet in improved or []:
        found.update(_extract_numbers(bullet))
    return found - anchor   # ← v2 出现的数字只要 anchor 里有就算 "真"
```

**漏洞链**:学生**自己**在原 bullet 写了"100 万欧元" → `_profile_anchor_numbers` 把它收进 anchor → AI 改写后还是"100 万欧元" → `set("100 万欧元") - anchor` = ∅ → 无警告。

换句话说:**当前的检测器只防"AI 凭空生成的数字",不防"学生自己写假、AI 帮忙保留"**。SAIF 老师明令零容忍的是后者。

### 修复方案

**A. 收紧 anchor 来源** (`chat.py:282`)
把 `_profile_anchor_numbers()` 拆成两类:
- **strong_anchor**:`education[].school/degree/major/start_date/end_date`、`skills`、`awards`、`candidate_summary` — 这些是 parse 阶段从 PDF 抽出的可追溯字段
- **weak_anchor**:`internships[].bullets[]`、`projects[].bullets[]` — 这些是学生自己写的 bullet,可能含假数字

改写检测时:**v2 出现的金额/百分比/体量数字必须命中 strong_anchor 或 至少 1 条 memory 旁证**;只命中 weak_anchor 不算"真"。

```python
def _build_fabrication_warnings(text, profile_dict, memory_entries):
    strong = _profile_strong_anchor_numbers(profile_dict)
    weak   = _profile_weak_anchor_numbers(profile_dict)
    memory_nums = _extract_numbers(' '.join(e['raw_excerpt'] for e in memory_entries))
    v2_nums = _extract_numbers(text)
    # 真数字 = strong ∪ memory; weak-only 也要警告
    safe = strong | memory_nums
    risky = v2_nums - safe              # 包括 weak-only 的数字
    ...
```

**B. 数字 type 分类**(可选,但推荐)
对 risky 集合按类型分级:
- 🔴 hard:金额单位 (万/亿/万元/万欧元/万美元)、deal size — 必报
- 🟠 medium:百分比 (>10%) — 报
- 🟡 soft:小整数 (年份 / 月份 / 1-2 位数) — 不报(过滤年龄、入职月)

**C. `suggestion_options` 必须无条件附带**
`_build_fabrication_warnings()` 当 `warnings = []` 时整个字段不出现。要让 UI 至少能展示"placeholder",**响应 schema 把 `warnings: list[RewriteWarning] = []` 改成必现字段**(已经是,但 P8 实测里整个数组为空,所以 UI 显示不出 3 个选项)。这条不用改代码,只需 #1 修了 risky 检测能命中。

### 验收
- 跑 `python -m scripts.eval_workspace_2026_05_20.run_one_persona --persona P8`
- 检查 `report.json` step6 `T4_redline_fabricated`:
  - `v2.warnings` 非空 ✅
  - 至少 1 条 warning 的 `number` 字段命中 `100` 或 `100 万欧元` ✅
  - `suggestion_options` 有 3 条 (`fill_real` / `delete_number` / `vague`)✅
- 同时跑 `T1` (LightGBM 真数字) 必须 `warnings = []` 不能误报

### 预计工时
~3 小时(代码改动 30 行 + 单测 + P8 重测)

---

## 修复 #2 (🔴 blocking) — P1 改写全部 fallback 到 plan-mode (Finding #2)

### 现象回顾
- P1 是清华本经济 + 中信证券 + 易方达 3 段头部实习的"学霸 persona"
- Step3 chat 5 轮后 `account_memory` 实际入了 2 条 preference entry
- Step6 改写 3 条 bullet,**全部**返回:
  ```
  v2.text: "需要更多经历细节,建议用 plan-mode 跟 AI 聊聊这段经历"
  v2.needs_plan_mode: true
  memory_refs: []
  ```
- D4 评分被打 10 / 100 拖累总分到 60.8%

### 根因(已读源码确认)
`backend/app/services/resume_copilot/chat.py:934-992` `propose_rewrite_v0_v2()` 当前是**硬门槛**:

```python
memory_entries = relevant_memory_for_bullet(db, user_key, bullet_text, k=3)

# Step 3: empty memory → guide to plan-mode, don't burn LLM tokens.
if not memory_entries:
    return RewriteV0V2Out(...needs_plan_mode=True...)   # ← 直接短路
```

并且 `relevant_memory_for_bullet` 只查 `category ∈ {experience, skill_claim}` 两类(`api_helpers.py`)— 把 preference 排除在外。P1 的 2 条 preference entry 因此被忽略,且 P1 chat turn 1 的"易方达消费数据库 + 首席采用"experience 候选**没通过 3-anchor 严格规则**(缺时间锚)被 extractor 丢弃 → `memory_entries = []` → 硬 fallback。

**双重塌方**:抽取太严(只入 preference 不入 experience)+ 改写门槛太严(只看 experience 不看 preference 不看 profile)= 高质量 persona 反而拿不到改写。

### 修复方案

**A. memory 从"硬 gate"降级为"soft boost"** (`chat.py:978-992`)

把 `if not memory_entries: short-circuit` 改成**分级降级**:

```python
profile_bullets_for_internship = _internship_bullets_for_field_path(profile_dict, field_path)

if not memory_entries and not profile_bullets_for_internship:
    # 真正啥都没有 — 这种情况才 fallback
    return RewriteV0V2Out(...needs_plan_mode=True...)

# memory 为空但 profile 有 bullet → 用 profile 改写 + 轻提示
if not memory_entries:
    memory_block = ''   # 不喂 memory
    soft_hint = "📝 你还没在 plan-mode 聊过这段经历,改写仅基于简历表层。聊一聊会更精准。"
else:
    memory_block = _format_memory_block(memory_entries)
    soft_hint = ''

raw = _provider.generate_v2(messages_payload)
...
return RewriteV0V2Out(
    ...
    v2=RewriteVersionV2(text=v2_text, needs_plan_mode=False,
                        soft_hint=soft_hint, warnings=warnings),
    ...
)
```

**B. `relevant_memory_for_bullet` 把 preference 拉进来作为 boost** (`api_helpers.py`)

当前只查 `experience + skill_claim`。preference 不是"经历细节",但可以驱动**目标岗位 alignment**(P1 说想做消费 → 改写时强调消费方向)。

```python
def relevant_memory_for_bullet(db, user_key, bullet_text, k=3):
    main = query_memory(category__in=['experience', 'skill_claim'], ...).limit(k)
    # 额外塞 1-2 条最近的 preference 作为"目标信号"
    prefs = query_memory(category='preference', ...).order_by(-use_count).limit(2)
    return list(main) + list(prefs)
```

**C. 给前端响应加 `soft_hint` 字段** (`schemas_resume_copilot.py` `RewriteVersionV2`)

软提示 banner 不阻塞改写,只在改写 box 下面加一行"还可以聊聊这段经历让 AI 更精准"。

### 验收
- 重跑 P1: `step6` 全部 3 个 bullet 必须:
  - `needs_plan_mode = false`
  - `v2.text` 不是 fallback 文案
  - `memory_refs` 可空可有(profile-only 改写时空,memory hit 时有)
  - 至少 1 个 bullet 的 `rationale` 引用了 P1 已入的 preference("消费方向"/"买方偏好")
- P1 总分预期从 60.8% → ≥ 80%(D4 从 10 → 80+)

### 预计工时
~4 小时(代码 50 行 + schema 改 + 单测 + P1 重测)

---

## ❓ WHY #1 — Plan-mode AI 完全不会反问学生 (Finding #3)

### 调查结论:**AI 实际上 IS asking,但 anchor 追踪 schema 缺失,所以评分器看不到**

读 `backend/scripts/_out/eval_workspace_2026_05_20/P3/report.json` step4 原始数据,**AI 确实问了**问题:

```json
"items": [{
  "id": "65a39d67...",
  "status": "clarifying",
  "open_questions": [{
    "text": "关于异常点 backtest: 回测的具体指标(如超额收益/胜率)是?",
    "asked_at": "2026-05-20T05:22:43.584775Z"
  }]
}]
```

P3 跑了 6 轮,每轮都有新 `open_questions` 入栈。LLM judge "AI 在 6 轮中未提出任何反问" 是**错判**。

### 三个独立 bug 叠加

**Bug 1 — Schema 没有 anchor 字段** (`backend/app/services/resume_copilot/plan.py:121-132`)

`PlanItem` 模型:
```python
class PlanItem(BaseModel):
    id: str
    kind: ItemKind
    status: ItemStatus
    evidence: list[Evidence]          # Evidence 有 EvidenceTag (metric/tech/role/scope/duration/outcome/tool)
    open_questions: list[OpenQuestion]  # 问过的问题
    draft: Draft | None = None
    # ❌ 没有 anchors / filled_anchors / progress / anchor_status 字段
```

`PlanStateOut` 响应 schema (`schemas_resume_copilot.py:355-367`) 也没有任何 "时间/行动/工具/结果" 4 anchor 的标记字段。

**Bug 2 — Prompt 没有指示 LLM 标记 anchor** (`backend/app/services/resume_copilot/agent/builder.py:34-56`)

```python
SYSTEM_PROMPT = """\
你是一个简历建造助手。每一轮对话,你只能做**一件事**——选一个动作,返回一个合法的 JSON。

可选动作(必须从中选一):
- ask: 还需要更多细节才能写。
- ready_to_write: 当前 item 的 evidence 已经够支撑一条 bullet。
- write: 直接写出一条 bullet draft...
- drop / block
"""
```

prompt 允许 LLM 问"细节",但**没有**显式说:"把问题拆成 4 个 anchor(when/what action/what tool/what outcome)按需问"。

**Bug 3 — Eval driver 找不到 anchor 字段** (`backend/scripts/eval_workspace_2026_05_20/step4_plan_mode.py:57-78`)

```python
def _count_anchors(item: dict) -> int:
    anchors = item.get("anchors") or {}        # ❌ 永远不存在
    prog    = item.get("progress") or {}        # ❌ 永远不存在
    flist   = item.get("filled_anchors") or []  # ❌ 永远不存在
    return 0  # 永远返 0
```

driver 启动时尝试读 3 个字段都不存在 → 永远 0/4。

### 修复方向(不在本轮 blocking 范围,单列 sprint)

1. **`PlanItem` 加字段**:`anchors_filled: dict[Literal['when','action','tool','outcome'], bool] = {}` + `next_anchor_to_ask: str | None = None`
2. **Prompt 加规则**:`ask` action 输出额外字段 `{"anchor_target": "when|action|tool|outcome"}`,LLM 每次反问必须指定瞄准哪个 anchor
3. **Server side detect**:`evidence` 里 `EvidenceTag.duration` ✓ → when anchor 满;`outcome` ✓ → outcome anchor 满;`tool` ✓ → tool anchor 满;`action` 由 LLM 自己标
4. **响应 schema 透出** `anchors_filled` → eval driver `_count_anchors()` 改读这个字段就行

预计工时:~6 小时(schema + prompt + 3 处单测)

---

## ❓ WHY #2 — Chat preference 抽取系统性漏判 (Finding #4)

### 调查结论:**LLM extractor prompt 的 preference 示例全是"光秃秃的偏好句",训练 LLM 看到混合句(偏好 + 实习 detail)倾向归到 experience**

### 根因证据

`backend/app/services/resume_copilot/memory/extractor.py:75-135` 的 `_EXTRACTOR_SYSTEM_PROMPT`:

```python
# experience 要求 3 anchors: temporal AND concrete_action AND outcome
# preference 示例(line 116-120):
#   - 想做 buy-side
#   - 只接受上海岗
#   - 不考虑国央企
```

**preference 的 3 个示例全是 "独立陈述句",没有任何实习 / 公司 / 数字 detail**。

P7 turn 2 学生原话:
> "其实我比较偏向留上海,毕竟蚂蚁那段实习在那边,对金融科技的业务场景更熟悉,尤其反欺诈 pipeline 的 AUC 提升让我觉得跟业务落地贴合得很紧。"

LLM 看到这句:
- 检查 experience 3-anchor:✓ 时间 (实习) ✓ 动作 (反欺诈 pipeline) ✓ 结果 (AUC 提升) → **能抽 experience**
- 检查 preference:句子主体是"偏向留上海",但 prompt 例子没教过混合句怎么办
- LLM 默认 "max 3 candidates" + "可在面试中被引用" → 优先选 information-rich 的 experience
- **结果**:只输出 1 条 experience 候选,preference 完全丢失

P7 step3 `memory_by_cat_after = { experience: 1, preference: 0 }` 实证了这个路径。

### 次因:dedupe 规则化不到位

`extractor.py:206-208` `_normalize_for_hash`:
```python
def _normalize_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())
```

只做 whitespace 合并 + 小写,**不剥标点 / 不剥助词** ("了" / "啊" / "呢")。

- "我偏好上海。" ≠ "我偏好上海" → 两个不同 hash → 两条 row
- 这正是 P1/P4 同事实第二次说出现 2 条 entry 的原因

### 第三因:extractor 与 dispatcher 的 hash 公式不一致

`extractor.py:211` 不带 category:
```python
def summary_hash(user_key, summary):
    payload = f"{user_key}::{_normalize_for_hash(summary)}"
```

`dispatcher.py:63-71` 带 category:
```python
def compute_summary_hash(user_key, category, summary):
    payload = f"{user_key}::{category}::{_normalize_for_hash(summary)}"
```

两个 hash 公式不对称 → legacy `student_experiences` 表跟新 `account_memory` 表 dedupe 行为不一致,跨表查重也对不上。

### 修复方向(不在本轮 blocking 范围,单列 sprint)

1. **改 prompt 示例**:加 3 个"混合句"示例:
   ```
   - 输入: "我偏向留上海,我在蚂蚁做过反欺诈 pipeline,AUC 提升 6 个点"
   - 输出: 2 条候选:
       [preference] "想留上海"
       [experience] "蚂蚁反欺诈 pipeline (2024-2025),实现 GNN 模型,AUC 提升 6 个点"
   ```
2. **加显式规则**:"如果句子同时包含 `(我想|我偏好|不考虑|只接受)` 关键词 **和** experience 三件套,**必须**输出 2 条候选,不要二选一"
3. **`_normalize_for_hash` 升级**:
   ```python
   def _normalize_for_hash(text):
       text = (text or "").strip().lower()
       text = re.sub(r"[。,!?,.!?;;:：、…\"'""''「」『』《》()()【】\[\]]+", "", text)
       text = re.sub(r"[了啊呢吧呗哦的得地]+$", "", text)  # 句末助词
       text = re.sub(r"\s+", "", text)
       return text
   ```
4. **统一 hash 公式**:`extractor.py:211` 加上 `category` 字段,跟 dispatcher 对齐

预计工时:~4 小时(prompt 改 + 3 处单测覆盖混合句 / 标点变体 / 助词变体)

---

## 修复优先级 + 时间线

| # | Finding | 严重度 | 工时 | 是否 blocking SAIF demo |
|---|---|---|---|---|
| 修复 #1 | PVSyst 红线 | 🔴 一票否决 | 3h | **是** |
| 修复 #2 | P1 全 fallback | 🔴 体验阻塞 | 4h | **是** |
| WHY #1 | Plan-mode anchor | 🟠 | 6h | 否(下 sprint) |
| WHY #2 | preference 漏判 | 🟠 | 4h | 否(下 sprint) |

**本周路径**:修复 #1 + #2 → 重跑 P1 + P8(~10 min) → 验证 P1 ≥ 80%、P8 红线 `warnings ≥ 1` → 约 SAIF 老师 demo。
**下 sprint**:WHY #1 + #2 一起做,2 天工。
