# 自然语言推荐 agent — 设计 (2026-06-03)

> 本 spec 只覆盖**子项①**。它属于一个更大的程序:把"岗位推荐"和"简历修改"拆成两个模块,
> 并把推荐做成自然语言驱动的 agent。整个程序分 4 个子项,各自独立走 spec→plan→实现:
>
> | 子项 | 是什么 | 状态 |
> |---|---|---|
> | **① NL 推荐 agent + tool** | chat 改造成推荐 agent,自然语言→调 tool 重捞重排→流动 feed | **本 spec** |
> | ② 梯队骨架"版图"视图 | 稳定的头/次/腰 + 在招·梯队外带 + 点击联动 feed | 另立 spec(前置设计已在 `2026-06-03-subcat-two-level-confirm-design.md` 起头) |
> | ③ GT 扩充 | 我出清单→用户过目→入库(固收/信用/FOF 缺的券商资管/理财子/保险资管) | 数据前置,另走 |
> | ④ 模块物理拆分 | 简历改写整块迁去另一条对话 | 跨对话协调,另走 |

## 背景 / 为什么做

**现状(经只读探查确认):**
- 工作台的 chat 只做**简历改写辅导**(`/chat` → `chat.generate_chat_turn`),**与推荐完全解耦**。
- 推荐是一条固定 4 段流水线(召回→三维打分→Pro 精排→4-anchor 理由),靠点 `/generate` 触发,
  读 preferences 里的赛道。**没有"对话里下指令就重排"的真路径**;换赛道得改 preference + 重新生成。
- 代码里**已躺着 `ReActAgent`(`agent/core.py`)+ 三个 tool(`agent/tools.py`:`search_candidates` /
  `inspect_jobs` / `get_company_intel`)**,但 `RECOMMENDATION_V2_ENABLED` 开启后被整段跳过
  (实测对当时选集零增益、+917s)。**子项① = 把这个休眠 agent 捞出来、轻量化、重定位成
  NL 驱动的推荐 agent。**

**痛点:** 推荐和简历改写挤在一条 chat 里太重;学生想"换个方向看看 / 我就喜欢某家的岗"时,
没有顺手的自然语言入口,只能去改赛道再等一分半的深度匹配。

## 目标

让学生在工作台中间栏用自然语言下指令(换方向 / 改偏好 / 锁定某公司),agent 调推荐 tool
从岗位库**秒级**召回+重排,流动 feed 即时更新;改的是临时**工作查询**、不动确认赛道,
满意可一键"锁定为主方向"。对话像聊天一样跟手,深度精排按需才跑。

## 已确认的设计决策

| # | 决策点 | 选定 |
|---|---|---|
| 1 | NL 重排栏 vs 梯队骨架 | **分开互补 + 点击联动**(骨架=稳定版图按确认赛道;feed=流动结果按工作查询) |
| 2 | NL 改的是什么 | **临时工作查询**(会话级过滤器),不动 confirmed preferences;满意可一键锁定为主方向 |
| 3 | 对话快慢 | **快慢分离**:对话每轮走快路(DB 召回+规则三维排,秒级);Pro 深度精排+理由只在初次生成或显式"深挖"时跑 |
| 4 | 模块拆分边界 | **只加不删**:本子项新增推荐 agent + 前端接入 + 隐藏改写入口;改写 `/chat`、`/plan` 后端保留不动 |
| 5 | tool 交互方式 | **结构化 JSON**(`response_format: json_object`)+ 确定性 dispatch,**不用原生 function-calling**——与现有 `agent/core.py`/`builder.py` 一致;1 次 LLM 调用/轮,不做多步 ReAct 循环 |
| 6 | 偏好持久化 | **三层分治**:临时工作查询(会话级,易逝)/ 锁定主方向(confirmed 赛道,动骨架)/ 平时偏好(统一记忆 `preference` 行,跨会话软偏置)。三层各归各位,绝不混 |

## 架构 — 五个单元

### Unit A — 工作查询状态(WorkingQuery)

会话级状态,独立于 confirmed preferences。形状:

```
WorkingQuery = {
  sub_cats: list[str],      # 细分方向(初始 = 确认赛道展开)
  companies: list[str],     # 偏好公司(学生"我就喜欢字节"→ 加这里, 召回置顶/过滤)
  locations: list[str],     # 地点
  exclude: list[str],       # 排除(公司/方向)
  sort: str,                # 'match' | 'fresh' | 'pay'(默认 match)
  note: str,                # 自由文本上下文(给 agent 解释用)
}
```

- 持久化:存在 recommendation run(或 session)上一个新 JSON 列 `working_query_json`,**与
  `preferences_json` 分开**。空/缺失 → 退回"按 confirmed 赛道"(向后兼容)。
- 初始化:进入推荐模块时,从 confirmed track/sub_cats 灌初值,**再叠加 L3 `preference` 记忆种子**
  (平时偏好的公司/地点/排除项),见「三层偏好持久化模型」。

### Unit B — 推荐 tool(复用 `agent/tools.py`)

agent 可调的 tool(尽量复用现成的,减负):

- `search_candidates(working_query) -> ranked_feed` — 按工作查询从 DB **召回**
  (`recall_candidates`,sub_cat/quality/freshness/location SQL 过滤)+ **规则三维打分**
  (`rank_jobs`,recommendation_v2 现成)。**纯规则、秒级、不调 LLM。** companies 偏好 →
  召回后置顶/加权;exclude → 过滤。返回 feed(同 `ResumeRecommendationItem` 形状,
  `final_score` 来自规则分;`used_ai=false`)。
- `get_company_intel(company) -> intel_card` — "讲讲这家"(已有情报卡装配,直接用)。

> tool 设计原则:agent 不直接写 SQL;它产出/修改结构化 `WorkingQuery`,由 `search_candidates`
> 翻成召回。意图→query 的映射是一个**可单测的纯函数层**(见 Unit C)。

### Unit C — 轻量 NL agent loop(结构化 JSON,非原生 function-calling)

**1 次 flash LLM 调用/轮**,吐结构化 JSON,确定性代码执行。**不是多步 ReAct 循环**
(老 ReAct 就是循环太慢、+917s 被砍)。沿用 `agent/core.py` 的 `response_format: json_object` 惯用法。

**LLM 输入**:学生这句话 + 当前 WorkingQuery + 方向词表(canonical sub_cats)。

**LLM 输出契约(JSON)**:

```json
{
  "intent": "refine | company_focus | intel | lock | chitchat",
  "query_delta": {
    "add_sub_cats": [], "add_companies": [], "add_locations": [],
    "exclude": [], "sort": "match | fresh | pay | null", "only": false
  },
  "remember": { "dimension": "...", "value": "..." },   // 或 null,见「三层偏好持久化」
  "reply": "已加上固收,按匹配度给你重排了 12 个"
}
```

**执行(确定性)**:
- `refine` / `company_focus` → `new_query = apply_delta(working_query, query_delta)`(**纯函数,可单测**)
  → `search_candidates(new_query)`(Unit B,规则路,秒级)→ 返回新 feed。
  `only=true` 时是"只看 X"(收窄);否则偏好是置顶/加权不是过滤(不藏岗)。
- `intel` → `get_company_intel(company)` → 返回情报卡。
- `lock` → 触发 Unit E(锁定为主方向)。
- `chitchat` → 只回话,不动 feed。
- 任一 intent 若带 `remember` → 走「三层偏好持久化」第三层(BackgroundTask 落统一记忆)。

**约束**:每轮 LLM 只调 1 次(解析),tool 至多 1–2 次,**只走规则路;绝不每句话跑 Pro 精排**。
agent base 沿用 `Subagent.invoke()` 的"绝不 raise"语义(超时/异常 → 安全降级:不改 query、
回"没太听懂,换个说法?",feed 不变,不崩对话)。

### Unit D — 快慢分离

- **快路(对话默认)**:Unit C 每轮 = 意图解析(flash, ~1-2s)+ 规则召回排(DB, 毫秒级)。
  对话跟手。
- **慢路(按需)**:feed 里学生对某批/某岗点"深挖" → 才跑 `rerank_top_n`(Pro 精排)+
  `generate_narrative`(4-anchor 理由)。复用现有 v2 慢路 + 已做的并行/快速失败优化(H1-H4)。
- 初次进入推荐模块:可跑一次完整快路出 feed(不强制 Pro),让学生先看到东西再对话细化。

### Unit E — 锁定为主方向

学生满意 → 一键把 WorkingQuery 提交成 confirmed track/sub_cats(走现有 `PUT /preferences`
通道写 `preferred_tracks`/`confirmed_sub_cats`)→ **梯队骨架(子项②)据此重塑**。这是
WorkingQuery 唯一会"落"成 confirmed 的入口,且**显式、学生主动**——平时探索不污染 confirmed。

## 三层偏好持久化模型(关键)

"偏好"分三层,落三个地方,**绝不混**:

| 层 | 是什么 | 落哪 | 谁触发 | 影响 |
|---|---|---|---|---|
| **L1 临时工作查询** | "今天想看看固收" | `working_query_json`(会话级,易逝) | 每句 NL(`query_delta`) | 只动当前 feed |
| **L2 锁定主方向** | "就按这个方向投" | `preferences`(confirmed 赛道) | 学生**显式**点"锁定"(Unit E) | 重塑梯队骨架 |
| **L3 平时偏好** | "我一直偏好外资行""不考虑国企""base 必须上海" | **`account_memory` 的 `preference` 行**(统一记忆,现成) | agent 识别出**稳定/泛化**偏好(`remember`) | 跨会话长期软偏置 |

**L3 写入(铁律:account_memory 写入路径唯一,绝不直插):**
- agent 吐的 `remember:{dimension,value}` **不直接写库**。对话回完后**起一个 BackgroundTask 跑记忆抽取**
  (复用改写 chat 已有的抽取模式),由它走 `memory/dispatcher.py::write_memory(category='preference')`
  落库——自带 dedup(`summary_hash`)、reserved-key 拦截(`__demo__`/`__guest__`)、**supersede**
  (`superseded_by_id`,学生改主意时新偏好覆盖旧)。`PreferencePayload{dimension, value}` 已存在
  (`memory/schemas.py`)。**一条写入路径,不绕。**
- 只把**稳定/泛化**的当 L3(如"我一直/从不/必须…");一次性的"今天看看 X"留在 L1,不升 L3。

**L3 读回(平时偏好如何回来影响排序),两条路都已存在:**
1. **深挖(Pro 精排)**:`StudentMemoryProvider`(`memory/provider.py`)已把 `preference` 记忆按
   `use_count` 注进 `PURPOSE_RERANK_JOB` 上下文。
2. **快路(规则排)**:进推荐模块初始化 WorkingQuery 时,读活跃 `preference` 行**灌初值**
   (偏好公司/地点/排除项做种子)→ 学生一进来 feed 就已按平时口味软偏置过。

→ 因此 L3 是 L1 的"默认起点":每次新会话的工作查询,从平时偏好种子起步,再被当下 NL 临时调整。

## 端点

新增,与简历改写端点分开(给④铺路):

- `POST /sessions/{id}/recommend-chat` — body `{message: str}`。跑 Unit C 一轮,返回
  `{reply: str, feed: list[item] | null, working_query: {...}, intent: str}`。
- `GET /sessions/{id}/working-query` — 读当前工作查询(前端初始化/回显)。
- `POST /sessions/{id}/recommend-deepen` — body `{job_ids?: list, scope?: 'top'}`。触发慢路
  (Pro 精排+理由)对指定批次,返回带 narrative 的 items。
- 锁定复用现有 `PUT /sessions/{id}/preferences`(前端在 Unit E 调它)。

改写的 `/chat`、`/plan`、`/plan/turn` 端点**一行不动**。

## 数据流(端到端)

```
进入推荐模块
  → 初始化 WorkingQuery = confirmed 赛道 + L3 preference 记忆种子(平时口味)
  → 快路出初始 feed (规则召回排)
  → 学生 NL: "多来点固收"
      → POST /recommend-chat
      → 意图解析(flash) → {intent:refine, query_delta:+固收, remember:null}
      → apply_delta → search_candidates(WorkingQuery) → 新 feed (秒级)
      → 回 {reply:"已加固收,重排 12 个", feed, working_query}
  → 学生 NL: "我一直不考虑国企"
      → {intent:refine, query_delta:{exclude:[国企]}, remember:{dimension:'company_type', value:'非国企'}}
      → feed 立即生效 + BackgroundTask → write_memory(preference) 落 L3(下次自动带上)
  → 学生点某岗"深挖"
      → POST /recommend-deepen → Pro 精排+理由(StudentMemoryProvider 注入 L3)→ 带 narrative 的 item
  → 学生"就按这个" → 锁定
      → PUT /preferences(WorkingQuery → confirmed)
      → 梯队骨架(子项②)重塑
```

## 组件 / 待改文件(指引,非最终清单)

- `backend/app/services/resume_copilot/agent/` — 复活 + 减负 `ReActAgent`(`core.py`);
  意图解析(flash,输出 Unit C 的 JSON 契约);tool 复用 `tools.py`。
- `backend/app/services/resume_copilot/` — 新建 `recommend_chat.py`(Unit C orchestrator);
  `working_query.py`(WorkingQuery 模型 + **`apply_delta` 纯函数** + 从 `preference` 记忆灌初值)。
- `backend/app/services/memory/` — L3 写入复用 `dispatcher.write_memory(category='preference')`;
  recommend-chat 轮后的 BackgroundTask 抽取(复用现有 chat 抽取模式),**不新增写入路径**。
- `backend/app/routers/resume_copilot.py` — 新增 `recommend-chat` / `working-query` /
  `recommend-deepen` 路由(只加)。
- `backend/app/models*.py` / Alembic — `working_query_json` 列(新 migration,idempotent 检查)。
- `backend/app/services/phase_g/recommendation_v2/` — 复用 `recall.py` / `scoring.py`,companies
  偏好的置顶/加权可能加一档(小改,软信号风格)。
- `resume-copilot-web/components/resume-copilot/workspace/` — 中间栏接 `recommend-chat`(从改写
  chat 切到推荐 agent);feed 栏读 `recommend-chat` 返回;"锁定为主方向"按钮;"深挖"入口;
  **隐藏改写入口**(不删组件)。

## 错误处理 / 边界

- tool 空结果 → agent 回"这方向库里暂无在招,要不要看相邻方向 / 放宽地点",并给 1-2 个建议,
  **绝不静默空白**。
- 意图不清(解析置信低)→ agent 反问一句,不乱改 WorkingQuery。
- 意图解析 LLM 失败 → 降级:不改 WorkingQuery,回"没太听懂,换个说法?",feed 不变(不崩)。
- companies 偏好命中 0 岗 → 仍展示"该公司当前无在招",不假装有。
- **铁律:平时对话绝不写 confirmed preferences**(L2);只有 Unit E 显式锁定才写。
- **铁律:L3 偏好绝不直插 `account_memory`**;只经 `dispatcher.write_memory`(唯一写入路径,
  带 dedup/reserved-key 拦截/supersede)。
- **铁律:`search_candidates` 不藏岗**——exclude 是学生显式要的才排;偏好是置顶不是过滤(除非
  学生说"只看 X" `only=true`)。
- L3 只收**稳定/泛化**偏好;一次性"今天看看 X"留 L1,不升 L3(避免记忆被噪声污染)。

## 测试

- 纯函数 `apply_delta(query, delta)`:加/排除/改 sort/`only` 收窄 各分支;脏 delta(空/赛道外)忽略不崩。
- `search_candidates`:给定 WorkingQuery → 召回集合正确(sub_cat/地点过滤、companies 置顶、
  exclude 生效、不藏其余)。
- WorkingQuery 初始化:给定若干 `preference` 记忆行 → 正确灌成种子(L3→L1)。
- agent 端到端(mock LLM):一串 NL("换固收"→"只看头部券商资管"→"锁定")→ feed 正确演化,
  且**confirmed preferences 全程不被写**,直到显式锁定。
- L3 写入:`remember` 走 `write_memory` 落 `preference` 行;稳定偏好升 L3、一次性查询不升;
  重复偏好 supersede 旧行;reserved-key(`__demo__`/`__guest__`)被拦。
- 快慢分离:`recommend-chat` 不触发 Pro 调用;`recommend-deepen` 才触发。
- 向后兼容:`working_query_json` 缺失 → 退回按 confirmed 赛道,行为同现状。

## 不在本设计内(YAGNI / 另立)

- **子项 ②③④ 本身**:骨架版图视图、GT 扩充、改写模块物理拆分,各自单独 spec。本子项只到
  "新增推荐 agent + 前端接入 + 隐藏改写入口 + 端点分开"。
- **自由文本赛道映射为空**的修复:新学生走 canonical 选择器不受影响;旧 persona 会话的映射是
  另一条数据质量线。
- **每轮都跑 Pro 精排**:明确不做(老 ReAct 因此被砍)。深度精排只按需。
- WorkingQuery → confirmed 的**自动晋升**:只做显式"锁定"按钮,不做自动判定(YAGNI)。
