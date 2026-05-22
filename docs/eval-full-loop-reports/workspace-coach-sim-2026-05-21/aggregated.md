# Workspace Coach Real-User Simulation — 合并报告 (2026-05-21)

> 3 个 subagent 并行,每个扮一组 SAIF MF persona,跑完整流程:上传 → 确认 → 推荐 → coach 聊 4-7 轮 → 入档。  
> Worker A 跑 P1/P2/P3,Worker B 跑 P4/P5/P6,Worker C 跑 P7/P8(含红线 P8)。  
> 原始 bug 总计 35 条,去重后 21 个独立问题。

## 🚨 4 个 BLOCKER(SAIF 老师 demo 当场会戳穿)

### B1. P8 红线人 fabrication 防御**失效**(Worker C)
学生说"我独立完成 50MW 光伏 / 节约 100 万欧元"(明显本科生短期实习不可能做的事),coach 第 1 回合就给草稿、`risk_flags: []`,还把"参与"升级成"独立完成",然后入档 `confidence=1.0, user_confirmed=true`。后续 RAG 还会把这个虚构事实喂给其它推荐和面试。  
**根因:** `_detect_fabricated_numbers` 只查"AI 编了简历里没的数字",没有"简历上的数字本身是否离谱"这一层。学院评测的核心红线测试 100% 不过。

### B2. P7 推荐 20 条全是蚂蚁(Worker C)
P7 学生明确说想看 蚂蚁 + 字节 + 腾讯 + 平安,实际推荐 20 条全部来自蚂蚁(其中"蚂蚁集团"和"蚂蚁科技集团股份有限公司"还是同一家公司两个法人名,没去重)。**学生 30 秒内判定工具坏**。

### B3. 任何"外部"赛道名都会让推荐变 0 条(Worker A,P2)
学生(或老师 / persona JSON / 外部表单)填了赛道名 `"卖方研究 TMT (sell-side research)"`(我们 persona JSON 里的原话),推荐返回 0 条,trace 留一句"很抱歉,候选池里没有匹配"再加"建议你关注券商官网"假装没事。重新存成 `"卖方研究·S&T"` 立刻给 13 条。  
**根因:** canonical key 严丝合缝,任何字符串变体(自然语言 / 老师文档 / 外部 import)都进不去。学院 demo 用 persona 试一次就空白。

### B4. P8 + P7 简历 parser **丢核心技能 + 凭空多个 "C"**(Workers A + C)
| Persona | 真实简历技能 | parser 输出 |
|---|---|---|
| P2 | Python (pandas/matplotlib), SQL, Wind API, DCF | `["Python", "C", "SQL"]` |
| P3 | LSTM / Transformer / GRU, PyTorch | `["Python", "C", "SQL", "PyTorch"]`(LSTM 全丢) |
| P7 | LightGBM, XGBoost, GraphSAGE, GAT, GCN | `["Python", "Java", "C", "SQL", ...]`(全丢) |
| P8 | LightGBM, XGBoost, 时间序列分析, 电力市场, DCF/IRR | `["Python", "C", "SQL"]`(LightGBM 全丢) |

**4/8 persona 同时撞,而且"C"在简历里从来没出现过** — 是 skill extractor 的 false-positive 规则。P8 的整个学生差异化("能源 + LightGBM + 电价")被 parser 自己抹掉,下游推荐 / coach / 改写全用不到。

---

## 🟡 6 个 MAJOR(系统性,多 persona 复现)

### M1. Coach 把后台 tag 名直接说给学生(Worker B,P4 + P5 多次)
真实复现的 AI 回答:  
> "我准备写的版本里有 **tech_unverified**,需要先补一下出处。"  

`tech_unverified` 是后台 pipeline 内部标签,prompt 模板没翻译就漏出去了。同一个 bug 也以 `leadership_unverified` / `overclaim` 形态在 P1 / P7 复现。这是所有 worker 看到的"最让学生骂街"的 pattern。

### M2. Coach 死循环 — 学生回答了 AI 还问同一个问题(全部 3 个 worker 都见)
P7:连续 2 轮 word-for-word 同一个问题。P5:`open_questions` 数组累积 3 份完全一样的 `tech_unverified` 问题。学生提供了"12 次访谈 / 8 份画像"这种具体数字,coach 还回"请给我能直接引用的具体数字"。学生 → "我刚刚给的就是啊?"

### M3. 没有"定下来"出口 — 草稿永远关不掉(Worker B,P6)
学生说"差不多就这样吧,定下来。",coach 当成新的 clarification turn,reset 回 clarifying。**目前 API 路径没有任何方法能让一个 item 走到 done**。意味着 demo 时如果想展示"4 段实习全聊完",根本聊不完第一段。

### M4. Draft 是**覆盖**不是**累加**(Worker B P4 + P6,Worker A P3)
学生第 1 轮聊出"4 部门轮岗 + Top 5 + return offer" → 第 2 轮加了"12 次客户访谈" → 第 2 轮 draft 把前面那段叙事**整段删掉**只剩客户访谈。Coach 模式的核心价值就是"逐步叠加",这条破了。

### M5. Coach 完全没有编造数字检测(Worker A,P1)
学生在 chat 里现编 "200 SKU"、"12 经销商"、"约 15%" — 全进 draft + 入档 `confidence=0.9`,**0 个 risk_flag**。`CLAUDE.md` 明文写 fabrication detection 是 non-negotiable,但只接到了 rewrite 路径,coach 路径完全裸奔。学生即使不是 P8 红线人,也能凭空编出一份漂亮简历。

### M6. `matched_track_label` 是骗人的(Worker A,P1 + P3)
13/13 华泰证券 sell-side 岗位全标"二级买方·基本面"(就是把学生选的 track 复制粘贴到每个 job 上)。学生看到会觉得"每条推荐都误归类",直接质疑系统判断能力。

---

## 🟢 11 个 MINOR(可入 backlog,不堵 demo)

- **parser 公司名乱:** P1/P4/P7/P8 把 "中信证券研究所·消费组" 截断成 "中信证券研究所";P5 反过来把 "投资银行部·大型企业组·Summer Analyst" 全塞 `role` 里 — 解析逻辑两个方向都跑偏
- **parser 合并 bullet 边界:** P7 蚂蚁那段 4 条 bullets 被合并成 2 条,P7 学生 JSON 里的 `flow_padding_internship.bullet_index=3`(故意放的水分 bullet)直接消失,这个测试场景根本测不到
- **大宗·能源赛道库存只有 1 条岗(麦肯锡)** — canonical 接通了但 crawler 还没填料
- **inferred_tracks 语言不稳定:** P3 返回 `["Finance", "量化", "Asset Management", "Private Equity"]` (3 个英文),不匹配任何 canonical key → confirm 页面 chip 一个都预勾不上
- **inferred_tracks 推方向错:** P2 简历明写"目标卖方研究首席助理",inferred_tracks 给"二级买方·基本面" — 加上 B3 的赛道 key drift 就形成"系统给你猜错方向 + 你按猜的存了 → 0 推荐"的死循环
- **finalize 后 `current_item_id` 跳回 self_intro(item 0)** — 学生想聊下一段实习,AI 突然问"你的 self_intro 草稿里 overclaim 怎么来的"(然而 self_intro 根本没有草稿)
- **plan/start 状态不确定** — 同一份代码,P1 直接进 clarifying,P2 进 awaiting_plan_approval 要 approve。前端没法稳定知道下一步该不该按 approve
- **HTTP 500 + 静默 replan** — P6 turn 2 一次 500,replay 成功,但成功的请求**静默地把所有 item UUIDs 全换了一遍**,学生看到进度被重置但没任何提示
- **P5 推荐 mid-list 混入 3 个麦肯锡咨询岗** — 学生 preferred_tracks 明写"投行 IBD",中段冒出 BusinessAnalyst
- **basic_info 字段是字符串 "None"** — P3 里 phone/github/linkedin 全是字符串 "None" 而不是 null,UI 会显示"电话:None"
- **matched_track_key 被小写化** — `"FinTech 数据 / 算法"` 存成 `"fintech 数据 / 算法"`,任何大小写敏感的等值 join 会断

---

## 推荐修复顺序(按"演示风险 × 修复成本"排)

**先修(SAIF demo 前必须):**

1. **B4 parser 丢技能 + 凭空 "C"** — 一上来 confirm 页面就让学生看到 `["Python","C","SQL"]`,信任直接归零。修改:parse prompt 加 "完整复制 skills.technical,绝不删减;不允许添加简历未出现的 token"。半天。
2. **B3 赛道 key drift → 0 推荐** — `PUT /preferences` 加 canonicalize_track + 后端返 `{"unknown_tracks": [...]}` 让前端能提示。或者在 ConfirmGuide 不允许学生输入自由文本(已经是 chip 多选,但 import 路径仍然能进自由字符串)。半天。
3. **M3 没有 "定下来" 出口** — `/plan/turn` 加 finalize 意图分类(regex "就这样|定下来|可以|用这版|ok" → 自动 transition item 到 done + 推 current_item_id)。1-2 小时。
4. **M1 后台 tag 漏到前端** — `_format_assistant_reply` 加翻译表 `{tech_unverified: "技术细节缺出处", leadership_unverified: "你的主导度需要佐证"}`。1 小时。

**中等紧急(影响信任度,demo 后第一周):**

5. **B1 P8 红线** — `recommendation.py` + `chat.py` 加 plausibility 层:`本科 × 实习 ≤ 6 月 × 项目 ≥ 50MW / 投资 ≥ 1 亿` → 强制 clarifying + `audit_risks: [{kind:"implausible_scale", blocking:true}]`。1-2 天(需要校准阈值)。
6. **M5 coach 路径接 fabrication 检测** — 把 rewrite 路径用的 `_detect_fabricated_numbers` 抽出来公共调用,coach draft 前过一遍。半天。
7. **M4 draft 覆盖 → 累加** — `propose_next_action` draft 阶段的 prompt 加 "在以下已有 draft 基础上 EXTEND,不要重写:`<prior_draft.text>`"。半天。
8. **M2 死循环** — 写入 `open_questions` 前 hash dedup;同问题问过 1 次后必须换角度。1 小时。
9. **B2 P7 蚂蚁去重 + 多样性** — 公司名 canonicalizer + per-employer ≤ 3。1 天。

**Minor 一拨清(半天能干完):**

10. minor 11 条作为 hygiene batch — parser 公司/role 字段拆分 + inferred_tracks 强制 canonical + basic_info "None" → null + matched_track_key 保留大小写 + 推荐 narrow track 加硬过滤。

---

## 端到端**仍然 OK 的部分**(给老师汇报时可以放心说)

- 上传 → parse → confirm 三段式 → preferences → /generate → 拉到推荐 → /memory 自动 seed → coach kickoff:全流程 **100% 跑通**,3 个 worker × 8 personas 没有失败
- focus_id 路由到对应 plan item:三个 worker 都验证过(P1 selects 中信证券 → item 锁正确;P5 selects 高盛 → 锁正确;P6 selects 乾象 → 锁正确;P8 selects PVSyst 那段 → 锁正确)
- DELETE /plan → POST /plan/start 重启:工作
- POST /memory → GET /memory 往返:工作,无重复
- 我今天上午改的 archive un-archive + 入库时间显示 + AIOrb 动画 + ConfirmGuide 三段式:都没回归
