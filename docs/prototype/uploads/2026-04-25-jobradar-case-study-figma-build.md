# JobRadar Case Study PDF · Figma Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Note:** This is a design/manual execution plan — most tasks are performed by the user in Figma, not by code. "Tests" are visual verification checks against the spec. "Commits" are Figma version saves + optional git commits of the spec doc itself.

**Goal:** 把 spec `2026-04-25-jobradar-case-study-design.md` 在 Figma 中落成一份 9 页 A4 PDF，可直接用于互联网大厂 AI PM 求职作品集。

**Architecture:** 一个 Figma 文件 9 个 frame（每个 A4 纵向）；复用 JobRadar 现有 design system（hifi-tokens.css）作为本地样式；5 个决策页用同一个 master component；最后导出 PDF（嵌入字体）。

**Tech Stack:** Figma · JobRadar 现有 hifi-tokens.css · GLM-4.7 + DeepSeek（产品本体，不在 PDF 制作里调用）· git（本地 spec 版本控制）

**Reference spec:** `C:\Users\cz\jobradar_design\docs\superpowers\specs\2026-04-25-jobradar-case-study-design.md`

---

## File Structure

| 文件 | 创建/修改 | 责任 |
|---|---|---|
| Figma 文件「JobRadar Case Study」 | 创建 | 9 个 page artboard，每个 A4 纵向 |
| Local Styles（color + text） | 创建 | 从 hifi-tokens.css 导入到 Figma 本地样式库 |
| Master Components | 创建 | Header / Footer / Decision Page / Funnel / 4-Layer Arch / Roadmap Timeline |
| `data/case-study-data.md` | 创建 | 数据收集结果汇总（漏斗 / 用户原话 / mock interview 数据） |
| `screenshots/*.png` | 创建 | 产品截图（hero / workspace / mock interview） |
| 导出 `JobRadar-CaseStudy-2026.pdf` | 创建 | 最终交付物 |
| `docs/superpowers/specs/2026-04-25-jobradar-case-study-design.md` | 已存在 | spec，本计划的输入 |

---

## Task 1: 初始化 Figma 文件 + 9 页 A4 artboard

**Files:**
- Create: Figma 文件「JobRadar Case Study」（个人 drafts）
- Init: 本地 git repo `C:\Users\cz\jobradar_design`（如未 init）

- [ ] **Step 1: 在本地目录初始化 git（如未做）**

```bash
cd /c/Users/cz/jobradar_design
git init
git add docs/superpowers/specs/2026-04-25-jobradar-case-study-design.md
git commit -m "spec: initial JobRadar case study design"
```

预期：commit 成功，spec 入库

- [ ] **Step 2: 在 Figma 创建新 design 文件**

操作：figma.com → 个人 drafts → New design file
命名：`JobRadar Case Study · 2026`

- [ ] **Step 3: 创建 9 个 A4 纵向 frame**

操作：在画布上按 F → 选 A4 纵向（210 × 297 mm）→ 创建 9 个 frame，水平排列
命名：`P1-Cover` / `P2-Background` / `P3-D1-Agent` / `P4-D2-Models` / `P5-D3-Funnel` / `P6-D4-JD` / `P7-D5-Trace` / `P8-Data` / `P9-Reflection`

- [ ] **Step 4: 验证**

视觉检查：9 个 frame 排开，标题清晰，每个都是 210×297mm

- [ ] **Step 5: 保存 Figma 版本快照**

操作：File → Show version history → Add to version history
命名：`v0.1 · 9 个空 artboard ready`

---

## Task 2: 把 hifi-tokens.css 导入 Figma 本地样式

**Files:**
- Source reference: `C:\Users\cz\jobradar_design\jobradar\project\hifi-tokens.css`
- Target: Figma 文件的 Local Styles

- [ ] **Step 1: 创建 Color Styles**

在 Figma 右侧 Design panel → Local Styles → Color → +
创建以下 12 个 color style（名称 / 值）：

```
parchment / #f5f4ed
ivory / #faf9f5
library-rail / #f0eee6
ink / #141413
ink-soft / #3d3d3a
olive / #5e5d59
stone / #87867f
terracotta / #c96442
terracotta-strong / #a84f34
terracotta-wash / #f8ecd9
emerald / #3f9a5d
amber-fg / #a16207
border-warm / #e8e6dc
border-cream / #f0eee6
deep-dark / #141413
```

- [ ] **Step 2: 创建 Text Styles**

字体回退：如本地无 Fraunces/Inter/JetBrains Mono，去 fonts.google.com 装上后重启 Figma desktop。

| Style 名 | Font | Weight | Size | Line height | Letter spacing |
|---|---|---|---|---|---|
| `Hero/72` | Fraunces | Medium | 72 | 98% | -3.5% |
| `H1/44` | Fraunces | Medium | 44 | 108% | -2.5% |
| `H2/32` | Fraunces | Medium | 32 | 115% | -2% |
| `H3/22` | Fraunces | Medium | 22 | 125% | 0 |
| `Body-LG/17` | Inter | Regular | 17 | 155% | 0 |
| `Body/14` | Inter | Regular | 14 | 155% | 0 |
| `Body-SM/13` | Inter | Regular | 13 | 150% | 0 |
| `Caption/12` | Inter | Regular | 12 | 140% | 0 |
| `Overline/11` | Inter | Semi Bold | 11 | 140% | 14% |
| `Label-Med/14` | Inter | Medium | 14 | 150% | 0 |
| `Label-Bold/14` | Inter | Semi Bold | 14 | 150% | 0 |
| `Mono/12` | JetBrains Mono | Regular | 12 | 150% | -2% |
| `Data-LG/36` | Fraunces | Medium | 36 | 100% | -2% |

- [ ] **Step 3: 验证 styles 已创建**

视觉检查：Local Styles 面板里 Color 有 15 项，Text 有 13 项

- [ ] **Step 4: 保存 Figma 版本**

命名：`v0.2 · design tokens imported`

---

## Task 3: 制作 Header / Footer / 页码 共享组件

**Files:**
- Create in Figma: Components page（在 Figma 文件里加一页 `_Components`）
- 3 个 main components: `Header`, `Footer`, `PageNumber`

- [ ] **Step 1: 创建 _Components 页**

操作：Pages 面板 → + → 重命名为 `_Components`（前缀下划线表示工具页）

- [ ] **Step 2: 创建 Header component**

在 _Components 页放一个 Frame（Auto Layout horizontal, padding 0）：
- 高度 24px
- 内含一个 Text 节点：`JobRadar Case Study · 周传博 · 2026`，使用 `Caption/12` 样式 + `stone` 色
- 右侧：可替换的 Text 节点 `章节标题`（使用 `Overline/11` + `terracotta` 色）

转为 Component（Cmd+Alt+K）。命名 `Header`。

- [ ] **Step 3: 创建 Footer + PageNumber component**

新 Frame（Auto Layout horizontal, justify space-between）：
- 左：Text「JobRadar · 周传博 · 2026」 (`Caption/12` + `stone`)
- 右：Text「P / 9」 (`Mono/12` + `stone`)，把 P 设为可替换 instance property

转为 Component。命名 `Footer`。

- [ ] **Step 4: 验证**

视觉检查：_Components 页里有 2 个 main component，文字使用了 Local Text Styles，颜色使用了 Local Color Styles。

- [ ] **Step 5: 保存 Figma 版本**

命名：`v0.3 · shared components ready`

---

## Task 4: 制作决策页 master template（pages 3-7 共用）

**Files:**
- Create in Figma `_Components` page: `DecisionPage` master component

这个 component 是 5 个决策页的骨架，有可替换的 instance properties。

- [ ] **Step 1: 在 _Components 页创建 Frame**

A4 大小 210×297mm。Auto Layout vertical，padding 24mm 上下、22mm 左右。

- [ ] **Step 2: 加 Header instance**

把 Task 3 的 Header component 拖入。设置章节文字 instance prop = `判断 N · ●●○○○`（5 点进度）

- [ ] **Step 3: 加决策标题**

Text 节点，`H1/44` 样式，内容占位 `【决策标题】`，颜色 `ink`。
设为 Component property "DecisionTitle"（Text）。

- [ ] **Step 4: 加上下文段**

Text 节点，`Body/14` italic，颜色 `olive`，宽度 = 父容器内宽（166mm），内容占位 `[2-3 句话上下文]`。
设为 Component property "Context"（Text）。

- [ ] **Step 5: 加选项区**

Auto Layout vertical, gap 12px，3 行：
- Row：[符号 ▢/✓] + [选项标签] + [优劣标记 +/-]
- 每行用 Auto Layout horizontal, gap 12px
- 符号是 Text Frame 24×24px，可切换 ▢ 或 ✓（✓ 时颜色 terracotta）
- 选项标签 `Body/14`，颜色 `ink`

设三个 instance prop: `OptionA`, `OptionB`, `OptionC`，并用一个 boolean `WhichSelected` 控制哪行显示 ✓ 和 terracotta 色

- [ ] **Step 6: 加"我选 X · 因为"块**

Auto Layout vertical, gap 8px：
- Header text `Label-Bold/14`：`我选 [选中项] · 因为`，色 `ink`
- Body text `Body/14`，色 `ink-soft`，内容占位 `[3-4 句推理]`

设为 instance prop "Reasoning"（Text）。

- [ ] **Step 7: 加验证 slot**

Auto Layout vertical, gap 4px：
- 短分隔线（horizontal Line, 30mm 宽，色 `border-warm`）
- 小标题 `Overline/11` + `stone`：`验证（数据 / 用户反馈）`
- Body text `Body/14`，色 `ink-soft`，内容占位 `[1-2 句结果，配 1 个数字加粗]`

设为 instance prop "Validation"（Text）。

- [ ] **Step 8: 加 Footer instance**

Task 3 的 Footer component。设页码 instance prop。

- [ ] **Step 9: 整体 Frame 转 Component**

Cmd+Alt+K。命名 `DecisionPage`。

- [ ] **Step 10: 验证**

视觉检查：_Components 页里 `DecisionPage` 有完整结构，所有 instance properties 工作正常（试着改一下文字看是否实时更新）

- [ ] **Step 11: 保存 Figma 版本**

命名：`v0.4 · decision page template ready`

---

## Task 5: 制作 3 个图表 component（Funnel / 4-Layer Arch / Roadmap Timeline）

**Files:**
- Create in Figma `_Components` page: `Funnel`, `FourLayerArch`, `RoadmapTimeline`

- [ ] **Step 1: Funnel component**

Auto Layout vertical, gap 4px。6 个横向矩形，宽度逐层递减（按比例）：
- Row 1：100% width, terracotta-strong, `注册 · 300`
- Row 2：93% width, terracotta, `上传简历 · 280 (93%)`
- Row 3：92% width, terracotta（透明度稍低）, `解析成功 → Top 5 · 277 (99%)`
- Row 4：88% width, terracotta-wash, `进入工作台 · 265 (96%)`
- Row 5：69% width, terracotta-wash, `应用 ≥1 条 AI 改写 · 208 (78%)`
- Row 6：29% width, ⚠️ amber-fg, `回访自报有投递 · 87 (33%)`

每个矩形高 32px，圆角 4px，内左侧文字 `Label-Med/14` 白色或 ink。

转 Component。命名 `Funnel`。

- [ ] **Step 2: FourLayerArch component**

Auto Layout vertical, gap 18px。4 个横向 box + fallback 箭头：

每个 box（A4 内宽 166mm，box 高 56mm）：
- Top label：`Label-Bold/14`：层名（如 `Layer 0 · SQL 粗筛`）
- Middle text：`Body-SM/13`：功能描述
- Right corner：`Mono/12`：`10K → 200`（数量级）
- Box 底部边框：3px terracotta

四个 box：
1. `Layer 0 · SQL 粗筛`：根据 preferences 在 SQL 库筛 / `10K → 200`
2. `Layer 1 · 规则打分`：5 子分（objective + preference + base_job + company_priority + rule） / `200 → 200`
3. `Layer 2 · 情报增强`：snapshot boost / `200 → 200`
4. `Layer 3 · LLM 重排`：DeepSeek / `200 → 5`

Box 之间加竖向 Arrow（线 + 三角箭头），右侧再加 dashed line 表示 "fallback"。

转 Component。命名 `FourLayerArch`。

- [ ] **Step 3: RoadmapTimeline component**

Auto Layout horizontal, gap 12px。5 个节点：
- 每个节点：圆点 12px + 上方时间标签 + 下方动作描述
- 节点底色：
  - `已上线` = emerald
  - `进行中` = amber-fg
  - `1-2 月 / 3-6 月 / 目标` = stone

节点内容：
1. `✓ 已上线 · 模拟面试`
2. `⚙ 进行中 · 投递插件`
3. `1-2 月 · 招聘体量预估`
4. `3-6 月 · 先投试错模式`
5. `目标 · 投递率 33% → 50%+`

节点间用 1px 灰色 dashed line 连接。

转 Component。命名 `RoadmapTimeline`。

- [ ] **Step 4: 验证**

视觉检查：_Components 页里 3 个图表 component 完整。Funnel 比例视觉对，FourLayerArch 4 层清楚，RoadmapTimeline 5 节点可读。

- [ ] **Step 5: 保存 Figma 版本**

命名：`v0.5 · chart components ready`

---

## Task 6: 数据收集（可与 Figma 制作并行）

**Files:**
- Create: `C:\Users\cz\jobradar_design\data\case-study-data.md`

这是真数据替换 mock 数据的窗口。如果暂时跑不动，跳过本 task 直接用 spec 里的 mock 数据；后期补回。

- [ ] **Step 1: SQL 查询用户漏斗**

跑 5 条 SQL（伪代码示意，按你后端 schema 调整）：

```sql
-- 注册用户数
SELECT COUNT(*) FROM users;

-- 上传过简历
SELECT COUNT(DISTINCT user_id) FROM resumes;

-- 解析成功（has parsed_data）
SELECT COUNT(DISTINCT user_id) FROM resumes WHERE parsed_data IS NOT NULL;

-- 进入工作台（visited workspace url 或 first_workspace_at IS NOT NULL）
SELECT COUNT(DISTINCT user_id) FROM workspace_sessions;

-- 至少应用过 1 条 AI 改写
SELECT COUNT(DISTINCT user_id) FROM rewrite_applications;
```

按校招 / 实习 split：在 users 表加 user_type 字段或从注册时收集。

- [ ] **Step 2: 微信回访 8-12 个用户（30 分钟 / 人）**

回访问题模板（5 个核心问题）：
1. "你是怎么知道 JobRadar 的？"
2. "用了之后印象最深的是什么？"
3. "Top 5 推荐里有没有让你眼前一亮的岗位？"
4. "AI 改写建议你接受了几条？为什么这条接受这条不接受？"
5. "你最后真的去投了吗？为什么投了 / 为什么没投？"

记录到 `data/user-interviews.md`。

- [ ] **Step 3: 加 3 个埋点**

在前端代码加事件：
- `top5_card_click`（带 rank, job_id）
- `rewrite_apply_button`（带 direction: jd-driven / quantitative / tech-stack / custom）
- `agent_trace_expand`

跑 1 周后查事件表。

- [ ] **Step 4: API log 跑统计**

```bash
# 解析 P50 耗时
grep "resume_parse" api.log | awk '{print $X}' | sort -n | awk 'NR==int(NR*0.5)'

# LLM 调用次数 / 用户
grep "llm_call" api.log | awk '{print $user_id}' | sort | uniq -c
```

- [ ] **Step 5: 算单用户成本**

```
total_glm_tokens × $0.001/1k + total_deepseek_tokens × $0.0014/1k = ¥X
÷ active_user_count = ¥Y / 用户
```

也算一个对照：假如全 LLM 暴力搜（每次 10K 岗位整包扔给 DeepSeek），单用户预估成本。

- [ ] **Step 6: Mock interview 数据**

```sql
-- 用过 mock interview 的用户
SELECT COUNT(DISTINCT user_id) FROM mock_interview_sessions;

-- 完成至少 1 轮的
SELECT COUNT(DISTINCT user_id) FROM mock_interview_sessions WHERE completed_at IS NOT NULL;

-- 用过 mock 的投递率 vs 没用的（需 self-report 数据交叉）
```

- [ ] **Step 7: 整理到 case-study-data.md**

把所有结果落到一个 md 文件，结构：
- 漏斗（按校招 / 实习 split）
- AI 质量信号（采纳率、自定义比例、trace 展开率）
- 性能 / 成本
- 留存
- 模拟面试
- 用户原话（5-8 段，标用户类型 / 是否投递）

- [ ] **Step 8: Commit**

```bash
git add data/case-study-data.md
git commit -m "data: collect real metrics for case study"
```

---

## Task 7: 制作 P1-Cover

**Files:**
- Edit Figma: `P1-Cover` artboard

- [ ] **Step 1: 在 P1-Cover 加大标题**

Text node，`Hero/72` 样式，内容 `JobRadar`。位置：上边距 32mm，水平居中或左对齐。

- [ ] **Step 2: 加副标题**

Text node，`H3/22`，颜色 `olive`，内容：
`面向高校应届生的 AI 求职闭环 · 从 Top 5 推荐 → 简历改写 → 模拟面试 → 投递，每一步都有 Agent`
宽度 = 内容区宽 - 20mm，位置 = 标题下方 + 12mm

- [ ] **Step 3: 占位 Hero shot**

Frame 占位（160 × 100 mm），背景 `library-rail`，圆角 8px，居中放在页面中部。
内文字（占位）：`[Hero shot · Workspace 三栏截图 · Task 16 替换]`

- [ ] **Step 4: 加分隔线**

Horizontal line，宽 = 内容区宽，色 `border-warm`，位置 = Hero shot 下方 + 16mm

- [ ] **Step 5: 加 Hero data hook**

Text node, `H2/32`，颜色 `ink`，2 行：
- 第 1 行：`用户接受 AI 改写建议的比例 74%`（其中"74%"用 terracotta）
- 第 2 行：`其中 67% 选了「JD-driven 卖点重组」方向`（"67%" 用 terracotta）

宽度 = 内容区宽，位置 = 分隔线下方 + 12mm

- [ ] **Step 6: 加元信息表（4 行）**

Auto Layout vertical, gap 6px，4 行 K-V：
- Role · Solo PM × AI 协作
- Status · 已上线 · 内测中 · 300 用户
- Period · 2026.03 – 至今
- Stack · GLM-4.7 + DeepSeek · ReAct Agent · React · Vite

每行 K 用 `Overline/11` + `stone`，V 用 `Body/14` + `ink`。Auto Layout horizontal，K 固定宽 24mm。

位置：页面下边距 32mm 上方

- [ ] **Step 7: 加 Footer instance**

Task 3 的 Footer instance，页码 = `1`

- [ ] **Step 8: 验证**

视觉检查：
- 全页无任何 lorem ipsum / 占位文字（Hero shot 占位 OK）
- 所有 text 用了 Local Text Styles（在 Figma 选中文字看右侧 panel）
- 所有色用了 Local Color Styles
- A4 边距 24/22mm 正确

- [ ] **Step 9: 保存 Figma 版本**

命名：`v0.6 · P1 cover done`

---

## Task 8: 制作 P2-Background（4 步闭环）

**Files:**
- Edit Figma: `P2-Background` artboard

- [ ] **Step 1: 加章节标题**

Text node `H2/32`：`为什么需要 JobRadar`。色 `ink`。位置 = 顶部 24mm 边距下。

- [ ] **Step 2: 加用户痛点段**

Text node `Body/14` 行高 155%，色 `ink-soft`，宽 = 内容区宽 - 20mm：
> 应届生求职信息差——海量岗位但不知道哪个值得投，简历不知道怎么改才对得上 JD，面试不知道会问什么。我们用 4 个 Agent 解决求职 4 步：找岗位、改简历、准备面试、投递。

位置 = 标题下方 + 12mm

- [ ] **Step 3: 制作 4 步闭环主图**

Auto Layout horizontal, gap 16px，4 列 + 3 个箭头：

每列内容（Auto Layout vertical, gap 8px, padding 12px, background `ivory`, radius 12px, stroke `border-warm`）：
- 顶 `Label-Bold/14`：步骤名（找岗位 / 改简历 / 准备面试 / 投递）
- 中 `Body-SM/13`：功能（Top 5 推荐 / AI 改写 / ✦ 模拟面试 / 🔧 投递插件）
- 中 `Caption/12`：方法（4 层漏斗 / JD-driven / Voice/Device / 开发中）
- 底 `Overline/11`：状态（✓ 已上线 / ✓ 已上线 / ✓ 已上线 / ⚙ 进行中）

状态色：
- ✓ 已上线 → emerald
- ⚙ 进行中 → amber-fg

每列宽约 40mm，整图横宽 ≈ 内容区宽

每两列之间放 → 箭头（Vector，色 `stone`，宽 8mm）

位置 = 痛点段下方 + 24mm，水平居中

- [ ] **Step 4: 加 4 步注解（每列下方）**

每列下方加一行 `Caption/12` + `stone`：
- 找岗位下：`万级岗位 → 5 个真正值得投`
- 改简历下：`通用美化 → JD 反向挑卖点`
- 准备面试下：`未知焦虑 → AI 模拟练习`
- 投递下：`手动复制 → 一键投递（计划中）`

- [ ] **Step 5: 加 Footer instance**

页码 = `2`

- [ ] **Step 6: 验证**

视觉检查：4 步闭环图清晰可读，每步状态色对（emerald 3 个 + amber 1 个）

- [ ] **Step 7: 保存 Figma 版本**

命名：`v0.7 · P2 background done`

---

## Task 9: 制作 P3 · Decision 1 · Agent ReAct loop

**Files:**
- Edit Figma: `P3-D1-Agent` artboard

- [ ] **Step 1: 拖入 DecisionPage component instance**

把 Task 4 创建的 `DecisionPage` master component 拖入 `P3-D1-Agent` frame。

- [ ] **Step 2: 设置 Header 章节文字**

Header 实例的章节文字：`判断 1 · ●○○○○`

- [ ] **Step 3: 设置 DecisionTitle**

`简历解析：单次 prompt 还是多步 Agent？`

- [ ] **Step 4: 设置 Context**

> 应届生简历格式杂乱（PDF / docx / 扫描件），需要做"读 → 抽结构 → 匹配公司库 → 推断目标"四件事。单次 prompt 全做完会幻觉、漏字段、且单点失败无法定位。

- [ ] **Step 5: 设置 Options**

```
A · 单次 long prompt（简单、快、易幻觉）          [-]
B · 4 个独立 prompt 串联（可控但缺上下文）        [-]
C · ReAct loop + 4 个 tool（结构清晰、可调试）   [✓]
```

WhichSelected = C

- [ ] **Step 6: 设置 Reasoning**

> 选 ReAct loop 是因为：① 每一步失败都能精准定位；② 每一步耗时可单独优化；③ 用户能看到 trace（连接到判断 5 的透明度设计）；④ 串联结构能在中间加 fallback——比如"读 PDF"挂了可以切 OCR 兜底。

- [ ] **Step 7: 设置 Validation**

> 解析准确率 **87%**（字段无需用户纠正比例），4 步独立可调试，平均解析 P50 耗时 **6.4s**。

- [ ] **Step 8: 设置 Footer 页码**

`3`

- [ ] **Step 9: 验证**

视觉检查：
- 所有 instance properties 已填，无占位文字
- ✓ 在选项 C，色 terracotta
- 数字 87% 和 6.4s 加粗（手动加 bold style 到这两个 token）

- [ ] **Step 10: 保存 Figma 版本**

命名：`v0.8 · P3 D1 Agent done`

---

## Task 10: 制作 P4 · Decision 2 · 多模型策略

**Files:**
- Edit Figma: `P4-D2-Models` artboard

- [ ] **Step 1: 拖入 DecisionPage instance**

- [ ] **Step 2: Header 章节文字**

`判断 2 · ●●○○○`

- [ ] **Step 3: DecisionTitle**

`不是"选一个最好模型"，而是"在不同环节匹配不同模型"`

- [ ] **Step 4: Context**

> 中文场景 + 应届生用户对延迟敏感 + 内测预算有限。Anthropic / OpenAI 在国内调用慢且合规风险高，单一模型也不可能在每个任务上都最优。

- [ ] **Step 5: Options**

```
A · 全程 GPT-4 / Claude（贵 + 慢 + 中文不一定最好）        [-]
B · 全程国产单模型（省心但有任务不擅长）                    [-]
C · 按任务匹配模型 + 规则兜底                                [✓]
```

- [ ] **Step 6: Reasoning**

> 简历解析 Agent 用 **GLM-4.7**（中文长文本理解强 + 国内延迟低）；Top 5 重排用 **DeepSeek**（推理能力强 + 性价比高）；规则打分作为兜底（前一层挂了下一层照样能出结果）。**单一模型不可能在所有任务都最优——按任务匹配是 AI PM 的常态判断。**

- [ ] **Step 7: Validation**

> 解析 P50 **6.4s** / Top 5 推荐 P50 **3.8s** / 单用户单次成本 **¥0.12**。

- [ ] **Step 8: Footer 页码**

`4`

- [ ] **Step 9: 验证**

视觉检查：所有 instance properties 已填；GLM-4.7 和 DeepSeek 加粗；3 个数字加粗。

- [ ] **Step 10: 保存 Figma 版本**

命名：`v0.9 · P4 D2 Models done`

---

## Task 11: 制作 P5 · Decision 3 · 4 层漏斗（含架构图）

**Files:**
- Edit Figma: `P5-D3-Funnel` artboard

这页是 case study 最重的一页，因为含架构图。

- [ ] **Step 1: 拖入 DecisionPage instance（缩短验证 slot）**

注意：因为本页需要给架构图大空间，可以把 Reasoning 缩短，把 Validation slot 移到 4-Layer Arch 图的右下角。

- [ ] **Step 2: Header 章节文字**

`判断 3 · ●●●○○`

- [ ] **Step 3: DecisionTitle**

`Top 5 推荐：纯 LLM 暴力搜，还是 4 层漏斗？`

- [ ] **Step 4: Context**

> 岗位库万级，给每条都跑 LLM 不现实（成本 / 延迟劝退）；但纯规则又太死板，捕捉不到"应届补招、量化分析岗"这类语义匹配。

- [ ] **Step 5: Options**

```
A · 纯 LLM rerank 全表（贵 + 慢，pricing 直接劝退）        [-]
B · 纯规则打分 Top 5（快但僵、错失语义匹配）                [-]
C · 4 层漏斗：SQL 粗筛 → 规则细分 → 情报增强 → LLM 重排    [✓]
```

- [ ] **Step 6: Reasoning（缩短到 2 句）**

> 每一层各干一件擅长的事 + 每一层都有 fallback。SQL 把万级压到 200，规则排出 Top 20，LLM 只对 5 条重排——**LLM 调用降到 1/2000，但语义匹配的好处全保留**。

- [ ] **Step 7: 拖入 FourLayerArch component**

把 Task 5 的 `FourLayerArch` 拖入，放在 Reasoning 下方，居中，宽度 = 内容区宽。

- [ ] **Step 8: Validation slot**

> 单用户单次 LLM 成本 **¥0.12** vs 假设全 LLM 方案估算 **¥21.50**——**降到 1/180**。

- [ ] **Step 9: Footer 页码**

`5`

- [ ] **Step 10: 验证**

视觉检查：架构图占了页面下半部分约 50%，4 层标签清楚，fallback 箭头可见，最终验证数字 ¥0.12 vs ¥21.50 醒目。

- [ ] **Step 11: 保存 Figma 版本**

命名：`v0.10 · P5 D3 Funnel done`

---

## Task 12: 制作 P6 · Decision 4 · JD-driven 改写

**Files:**
- Edit Figma: `P6-D4-JD` artboard

- [ ] **Step 1: 拖入 DecisionPage instance**

- [ ] **Step 2: Header 章节文字**

`判断 4 · ●●●●○`

- [ ] **Step 3: DecisionTitle**

`AI 改写：套固定模板，还是按 JD 反向挑用户的卖点？`

- [ ] **Step 4: Context**

> 应届生简历"什么都想写"，但 HR 半秒看完只扫 JD 相关的关键词。改写不能"通用美化"——必须按这个具体岗位去挑用户简历里最对得上的证据。

- [ ] **Step 5: Options**

```
A · 给 3 个固定方向（强量化/强因果/强影响）—— 太死板         [-]
B · JD-driven 反向匹配 + 量化数字加强                          [✓]
C · AI 自动改 → 失控                                          [-]
```

- [ ] **Step 6: Reasoning**

> HR 决策窗口是"JD 关键词命中率"——所以 AI 必须从 JD 反推回去挑证据，不能 generic。**互联网岗位重数字 + 项目影响力；研究 / 战略岗位重方法论 + 推理路径；工程岗位重技术栈 + 系统设计。** 因岗而异，不一刀切。

- [ ] **Step 7: 加 JD-driven 流程小图**

在 Reasoning 下方加一个 Auto Layout horizontal frame, gap 24px：
- 左 box（40mm 宽）：`Body-SM/13`，标题 `目标 JD 关键词`，下方 3 行示例：`A/B 实验`、`Python`、`数据分析`
- 中部 → 箭头 + 文字 `反向匹配`
- 右 box：标题 `用户简历段落`，下方 3 行：`蚂蚁风控 · A/B 实验 380+`、`Python · LightGBM`、`数据分析师 · 上海`
- 右 box 用 terracotta 高亮命中关键词

- [ ] **Step 8: Validation**

> JD-driven 卖点重组采纳率 **74%** / 量化加强 **68%** / 技术栈对齐 **71%** / 仅 **8%** 用了"自定义"slot——AI 推得够准。

- [ ] **Step 9: Footer 页码**

`6`

- [ ] **Step 10: 验证**

视觉检查：4 个数字加粗，JD-driven 流程图能看懂。

- [ ] **Step 11: 保存 Figma 版本**

命名：`v0.11 · P6 D4 JD-driven done`

---

## Task 13: 制作 P7 · Decision 5 · Trace 折叠

**Files:**
- Edit Figma: `P7-D5-Trace` artboard

- [ ] **Step 1: 拖入 DecisionPage instance**

- [ ] **Step 2: Header 章节文字**

`判断 5 · ●●●●●`

- [ ] **Step 3: DecisionTitle**

`AI 黑盒还是开盒？给用户看推理过程的代价是什么`

- [ ] **Step 4: Context**

> LLM 推理过程对懂的人是"信任凭证"，对不懂的人是"信息过载"。怎么平衡？

- [ ] **Step 5: Options**

```
A · 完全不显（最简洁但被怀疑"AI 是不是瞎推"）          [-]
B · 默认展开实时打印（懂行的爱，小白蒙）                [-]
C · 折叠默认隐藏 + 终端风格实时打印                    [✓]
```

- [ ] **Step 6: Reasoning**

> 终端风格是关键——**视觉上跟"工程师在看 log"一样可信**，但不强迫普通用户去理解；展开率本身就是数据信号（高质量用户筛选器）。

- [ ] **Step 7: 加 Trace 截图占位**

Frame 80×60mm，背景 `deep-dark`，圆角 12px，内含示意终端文本（`Mono/12` 色 `warm-silver`）：
```
$ parser.run(file=resume.pdf)
✓ read_pdf → 3 pages
✓ extract_sections → ok
▸ match_companies...
```

位置：Reasoning 下方居中

- [ ] **Step 8: Validation**

> trace 展开率 **8%**——远低于预期 30%，但展开过的用户 D7 留存 **38% vs 22%**（高 1.7 倍）。trace 不是大众功能，是高质量用户筛选器。

- [ ] **Step 9: Footer 页码**

`7`

- [ ] **Step 10: 验证**

视觉检查：trace 截图占位风格像真终端，3 个数字加粗。

- [ ] **Step 11: 保存 Figma 版本**

命名：`v0.12 · P7 D5 Trace done`

---

## Task 14: 制作 P8 · 数据验证

**Files:**
- Edit Figma: `P8-Data` artboard

- [ ] **Step 1: 加章节标题**

Text node `H2/32`：`数据验证 · 我的判断对了吗？`，色 `ink`，位置 = 顶部 24mm 边距下。

- [ ] **Step 2: 拖入 Funnel component**

Task 5 的 `Funnel` instance，位置 = 标题下方 + 12mm。
**（注：如有 Task 6 真数据，覆盖 mock 数据。否则用 spec 里的 mock 值）**

- [ ] **Step 3: 加漏斗下方"关键反差"小字注解**

Text node `Body-SM/13` italic，色 `ink-soft`：
> 96% 进工作台 → 78% 应用改写 → 仅 33% 真去投。**校招改最多（83%）但投得最少（24%）；实习改最少（72%）但投得最多（46%）。**

宽 = 内容区宽，位置 = Funnel 下方 + 8mm

- [ ] **Step 4: 加 5 个判断验证表**

Table（Auto Layout vertical），6 行 × 4 列：

| # | 判断 | 我赌的 | 实际 | 评分 |
|---|---|---|---|---|
| 1 | Agent ReAct loop | 解析准 + 可观测 | 87% 解析准确率，4 步独立可调试 | ✅ |
| 2 | 多模型策略 | 中文延迟低 | 6.4s 解析 / 3.8s 推荐 | ✅ |
| 3 | 4 层漏斗 | 成本可控 | ¥0.12 vs ¥21.50（1/180） | ✅✅ |
| 4 | JD-driven 改写 | 比固定模板准 | 74% 采纳率，仅 8% 用自定义 | ✅ |
| 5 | Trace 折叠 | 不打扰 + 增信任 | 展开率 8%，展开者留存 1.7× | ⚠️ 部分 |

行高 8mm，cell padding 4mm，文字 `Body-SM/13`。✅/⚠️ 用对应 emerald/amber-fg 色 emoji。

- [ ] **Step 5: 加用户原话 3 段**

Auto Layout vertical, gap 12px，3 个 quote box：
- 每 quote box：左侧 3px terracotta line + Auto Layout vertical
- 内 quote 文字 `Body-SM/13` italic 色 `ink-soft`
- 下 attribution 文字 `Caption/12` 色 `stone`

3 段内容（来自 spec）：
1. "挺有用的。之前我在拉勾刷一直只看互联网，用了 JobRadar 才发现像华泰、中信这种券商也在招数据分析的实习..." — 数据分析实习用户 · 已投 4 家
2. "它根据岗位帮我重新调过一段实习经历，把我做过的 A/B 实验放到最前面..." — 互联网产品方向校招用户 · 改了 6 版简历
3. "产品挺好的，但说实话这两个月我也还在准备阶段..." — 量化方向校招用户 · 暂时没回来

- [ ] **Step 6: 加「我做错了什么」slot**

Auto Layout vertical, padding 12mm, background `terracotta-wash`, radius 12px, 顶部加一个 ⚠️ icon + Label `我做错了什么`（`Label-Bold/14` + `terracotta-strong`）

内文 `Body-SM/13` 色 `ink-soft`：

> 我以为 AI 解决的是"推荐准不准 + 改写好不好"。
>
> 数据显示前 4 步几乎全过（96% 进工作台、78% 应用改写），但只有 33% 真去投——中间掉了 45 个百分点。校招用户改最多（83%）却投得最少（24%）；实习用户改最少（72%）却投得最多（46%）。
>
> **我们已经把模拟面试做出来了，数据显示用过的人投递率从 25% 提升到 51%——验证了"投递信心"确实是关键瓶颈**。下一步要解决的是"按按钮"这个动作本身——所以投递插件正在开发。
>
> 下一版的北极星指标从"AI 推荐准确率"换成"投递转化率"。

位置：表格下方

- [ ] **Step 7: 加 Footer 页码**

`8`

- [ ] **Step 8: 验证**

视觉检查：
- 漏斗 + 表格 + quotes + 错判 slot 都在页内（不溢出 A4）
- 错判 slot 视觉上"突出"（terracotta-wash 背景显眼）
- 5 行验证表读起来流畅

- [ ] **Step 9: 保存 Figma 版本**

命名：`v0.13 · P8 Data validation done`

---

## Task 15: 制作 P9 · 反思 + 路线图 + 联系方式

**Files:**
- Edit Figma: `P9-Reflection` artboard

- [ ] **Step 1: 加章节标题**

Text node `H2/32`：`反思 · AI 时代 PM 的工作方式`，色 `ink`，位置 = 顶部 24mm 边距下。

- [ ] **Step 2: 加「我学到的 3 件事」**

Auto Layout vertical, gap 16px。3 个段落，每段：
- 上方加粗标题 `Label-Bold/14`：`1. AI 时代，PM 的判断比执行更值钱`
- 下方正文 `Body-SM/13` 行高 165% 色 `ink-soft`：（spec 里的 50-80 字内容）

3 个标题 + 内容来自 spec 第 9 节。

- [ ] **Step 3: 加「我作为 AI PM 的工作方式」**

Auto Layout vertical, gap 8px，3 个 bullet：
- • **判断 · 执行分离**：我定义问题、做取舍、判断 AI 输出好坏；AI 负责把判断变成代码、设计、文案。
- • **快循环**：1 周原型 → 1 周用户测试 → 改判断。不写 200 页 PRD，写 5 个判断 + ship 出去看反应。
- • **数据先于直觉**：每个判断都预设一个"如果错了我会看到什么"——准备好被打脸，比假装永远对值钱。

每行 `Body-SM/13` 行高 165% 色 `ink-soft`。bold 部分加粗。

- [ ] **Step 4: 拖入 RoadmapTimeline component**

Task 5 的 `RoadmapTimeline` instance，位置 = "工作方式"下方 + 16mm。

- [ ] **Step 5: 加联系方式（页脚一行）**

Text node `Mono/12` 色 `ink`：

`+86 195-2279-3128  ·  cz9z@outlook.com  ·  github.com/Slackness1`

居中，位置 = 距底部 24mm 上方

- [ ] **Step 6: 加 Footer 页码**

`9`

- [ ] **Step 7: 验证**

视觉检查：
- 3 段反思 / 3 个 bullet / 路线图 / 联系方式 都在页内
- 联系方式整行可读，间距均匀
- 路线图 5 个节点完整

- [ ] **Step 8: 保存 Figma 版本**

命名：`v0.14 · P9 Reflection done`

---

## Task 16: 截图替换 + Hero shot 优化

**Files:**
- Create: `screenshots/hero-workspace.png` and other product screenshots
- Edit Figma: `P1-Cover`, `P2-Background`, `P7-D5-Trace` artboards

- [ ] **Step 1: 截 JobRadar 真实 Workspace 三栏视图**

打开你的 JobRadar 产品 → Workspace 页面 → 浏览器里 Cmd+Shift+P → screenshot of viewport
保存为 `C:\Users\cz\jobradar_design\screenshots\hero-workspace.png`
分辨率：至少 2560×1600（Retina），bg 包含 parchment 边

- [ ] **Step 2: 截 Mock Interview 截图**

打开 Mock Interview 页面，截 1 张干净的（最好是 Device Check 完成、AI Interviewer 上半身的样子）
保存为 `screenshots/mock-interview.png`

- [ ] **Step 3: 截 Agent trace 真实截图**

打开 Upload 流程，触发解析，trace 折叠时和展开时各截 1 张。
保存为 `screenshots/trace-collapsed.png` 和 `screenshots/trace-expanded.png`

- [ ] **Step 4: P1-Cover 替换 Hero shot**

把 Task 7 的占位 frame 删掉，拖入 `hero-workspace.png`：
- 缩放到 160 × 100 mm
- 圆角 8px
- 加阴影：Y=18 blur=52 spread=0 alpha=0.08（与 .hf-card.paper 一致）
- 居中

- [ ] **Step 5: P7 替换 trace 截图**

把 Task 13 的占位 trace frame 删掉，换成真截图（`trace-expanded.png`），保持 deep-dark 背景视觉

- [ ] **Step 6: P2 可加 mock interview 小图**

可选：在 4 步闭环图的"准备面试"列下方放一个小 mock interview 截图缩略图（30×20mm）

- [ ] **Step 7: 验证**

视觉检查：所有 3-4 处截图都用了真实图，无占位。截图清晰可读，色调与页面一致。

- [ ] **Step 8: Commit screenshots**

```bash
cd /c/Users/cz/jobradar_design
git add screenshots/
git commit -m "screenshots: add product screenshots for case study"
```

- [ ] **Step 9: 保存 Figma 版本**

命名：`v0.15 · screenshots integrated`

---

## Task 17: 全篇 cross-page 一致性 review + 数字校对

**Files:**
- Review: 全 9 页 Figma artboard

- [ ] **Step 1: 数字一致性扫描**

打开所有 9 页，用一个清单交叉检查每个出现的数字是否一致：

| 数字 | 出现的页 | 一致？ |
|---|---|---|
| 300 用户 | P1, P8 | □ |
| 87% 解析准确率 | P3, P8 | □ |
| 6.4s 解析 P50 | P3, P4, P8 | □ |
| 3.8s 推荐 P50 | P4, P8 | □ |
| ¥0.12 / ¥21.50 / 1/180 | P5, P8 | □ |
| 74% 改写采纳 | P1, P6, P8 | □ |
| 8% trace 展开 | P7, P8 | □ |
| 33% 投递率 | P8, P9 | □ |
| 51% vs 25% mock interview 差距 | P8 错判 slot | □ |

如果某数字在不同页不一致，回去改一致。

- [ ] **Step 2: 视觉一致性扫描**

- 5 个决策页（P3-P7）视觉布局完全一致（同一 master component 的 instance）
- 所有页共用 Header / Footer style
- 所有页边距 24mm 上下、22mm 左右
- terracotta 出现在每页都不超过 5 个地方

- [ ] **Step 3: 文字校对**

通读全 9 页文本，找：
- 错别字
- 全角 / 半角混用（特别是数字和单位之间）
- "我以为"是否对应到"实际"

- [ ] **Step 4: 联系方式核对**

P9 联系方式必须是：`+86 195-2279-3128 · cz9z@outlook.com · github.com/Slackness1`

- [ ] **Step 5: 保存 Figma 版本**

命名：`v1.0-rc1 · ready for export`

---

## Task 18: PDF 导出 + 跨平台测试 + 最终归档

**Files:**
- Create: `JobRadar-CaseStudy-2026.pdf`

- [ ] **Step 1: Figma 导出 PDF**

操作：File → Export → Export as PDF
- 选中 9 个 page artboard
- Quality: 2x（高 DPI）
- ✅ 勾选 "Embed fonts"（重要！）
- 保存到：`C:\Users\cz\jobradar_design\JobRadar-CaseStudy-2026.pdf`

- [ ] **Step 2: 在 Mac 打开测试**

操作：把 PDF 用 macOS Preview 打开
检查：
- 9 页都在
- 中文显示正常（不是方块或乱码）
- Fraunces / Inter / JetBrains Mono 字体正确
- terracotta 颜色正确（不是色偏）

- [ ] **Step 3: 在 Windows 打开测试**

操作：用 Edge / Chrome 内置 PDF viewer 打开
同样的检查清单

- [ ] **Step 4: 打印测试（可选）**

操作：随便打 1-2 页 → 检查灰度可读性，terracotta 在黑白打印下不消失

- [ ] **Step 5: 文件大小检查**

PDF 大小应该在 5-15 MB 范围。如果 > 30MB：
- Figma 重新导出，Quality 改 1x
- 或检查是否有未压缩的高分辨率图片

- [ ] **Step 6: Commit final PDF**

```bash
cd /c/Users/cz/jobradar_design
git add JobRadar-CaseStudy-2026.pdf
git commit -m "feat: final case study PDF v1.0"
```

- [ ] **Step 7: 保存 Figma 版本**

命名：`v1.0 · final · exported as PDF`

- [ ] **Step 8: 备份 Figma 文件**

操作：File → Save local copy → 保存到 `C:\Users\cz\jobradar_design\JobRadar-Case-Study.fig`

```bash
git add JobRadar-Case-Study.fig
git commit -m "feat: archive Figma source file"
```

---

## 完成 ✅

最终交付物：
- `C:\Users\cz\jobradar_design\JobRadar-CaseStudy-2026.pdf` —— 投简历用的 PDF
- `C:\Users\cz\jobradar_design\JobRadar-Case-Study.fig` —— Figma 源文件（备份 / 后续改）
- `C:\Users\cz\jobradar_design\docs\superpowers\specs\2026-04-25-jobradar-case-study-design.md` —— 设计 spec
- `C:\Users\cz\jobradar_design\docs\superpowers\plans\2026-04-25-jobradar-case-study-figma-build.md` —— 本计划
- `C:\Users\cz\jobradar_design\data\case-study-data.md` —— 真实数据
- `C:\Users\cz\jobradar_design\screenshots\` —— 产品截图

**总工时估算**：
- Figma 制作（Tasks 1-5, 7-15, 16, 17）：约 3 个全工作日
- 数据收集（Task 6）：1 周等埋点跑数据 + 实操约 1 天
- 导出 + 测试（Task 18）：0.5 小时

**下一步**：投简历时附上 PDF。可以同时在 GitHub README 链接 PDF 给招聘方下载。
