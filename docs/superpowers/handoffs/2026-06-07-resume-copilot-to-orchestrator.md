# Handoff → Orchestrator:简历优化模块 现状 + 接口契约 + 待规划项

> 来源会话:`简历副驾驶`(worktree `.worktrees/resume-copilot`,分支 `resume-copilot`)
> 日期:2026-06-07
> 目的:把"简历优化"这条线截至今天的设计 + 已建后端 + 待办,交给 orchestrator 统一规划;
> 并对接你那份 `统一对话 Hub 外壳设计`(简历优化在那里是"接口位/占位,另一分支")——本文就是那个分支的内部说明 + 接口契约。

---

## 0. 一句话

「简历优化」= **诚实打分 → 反问取证深度优化 → WYSIWYG 编辑/导出** 三件套。
**打分(前后端)+ 深度优化后端 已建完**;前端(深度优化面板 + chip 外壳 + 编辑页)**等用户出 HiFi**,暂未动。
另有一条**独立副产**:OfferShow 薪资行情管线(已落库 3843 条,代码未提交,需你定怎么归并)。

---

## 1. 设计形态(已与用户确认)

简历优化是 Hub 的一个 skill 模块,在右槽(画布槽)里是**三栏视图**:

```
┌────────────┬──────────────────────┬──────────────────┐
│ 左 tab     │  中:WYSIWYG 预览      │ 右:AI 助手 v2    │
│ 模板/编辑/ │  A4 = 将导出的 PDF    │ chip 切三能力     │
│ 布局       │                      │ 打分/深度优化/自由 │
└────────────┴──────────────────────┴──────────────────┘
```

核心哲学:**诚实打分 + 反问取证**(分数老实反映现状,提分只能靠反问把学生真实细节问出来再改——绝不 AI 编内容刷分)。完整设计见 `docs/superpowers/specs/2026-06-03-resume-editor-page-design.md`。

**本会话锁定的新决策(补充进 spec):**
- 深度优化**一次只聚焦一段经历**,且**锁定目标赛道(subcat)**——这样 subcat 知识库才能排上用场。
- 打分维度 **8 个(6 通用 + 2 金融)**;其中「面试可防守性」→ **改名「佐证充分度」**并重构语义(静态简历测不出面试表现,真正测的是"声明有没有足够支撑、经得起追问")。
- 模板默认 = 纯净无色单栏;5 模板命名:素白单栏/蓝栏双侧/深首横幅/墨绿弧顶/浅青色块。
- 编辑页左 tab 顺序 `模板 | 简历编辑(默认) | 布局`。

---

## 2. 已建(可用 / 已测 / 已提交)

**全部在分支 `resume-copilot`,后端 TDD 全绿。**

| 模块 | 交付物 | 状态 |
|---|---|---|
| 打分后端 | `scoring.py` + `scoring_rubric.py` + `POST /sessions/{id}/score` | ✅ 8 维+现状/潜力区间+逐段缺口 |
| 打分前端 | `components/resume-copilot/scoring/ScoreReport.tsx`+雷达+`/resume-copilot/score?mock=1` | ✅ 可独立查看 |
| 深度优化后端 | `deep_optimize.py`(seed_plan_from_gap / gap驱动反问 / 定向改写)+ `POST /sessions/{id}/deep-optimize/start` | ✅ Task1-4,复用 plan/改写/记忆管道 |
| 维度语义修正 | 「佐证充分度」 | ✅ 后端+前端文案同步 |

本会话提交(分支 `resume-copilot`):`70d3db3` `d6f5781` `f25847a` `4efcca7`。

---

## 3. 接口契约 — 给 Hub「画布槽」挂载用

你那份 Hub 设计里简历优化是占位。挂载契约:

- **入口路由**:`/resume-copilot/editor`(编辑页三栏,未建)/ 当前可先挂已建的 `/resume-copilot/score`(打分报告)。
- **画布槽需要的状态**:`sessionId`(resume_copilot session)+ `X-Resume-User-Key`(账号 key,owner 守卫用)。Hub 切到"简历优化"模块时把当前 session 传进去即可。
- **已可调的后端 API**(都带 owner + `_assert_not_demo` 守卫):
  - `POST /api/resume-copilot/sessions/{id}/score` → 打分报告
  - `POST /api/resume-copilot/sessions/{id}/deep-optimize/start` → 播种深度优化(入参 `{section,label,gaps[],detail,target_track}`)
  - 反问续走现成 `POST .../plan/turn`;改写写回走现成 `.../chat/apply-rewrite`
- **chip 集合协调点**:用户本轮定**这次只做 2 个 chip:①深度搜索 ②简历优化**。你的 Hub 设计列的是 `职位推荐/梯队骨架/简历优化`——**chip 命名与集合需要你我对齐一次**(谁是这版要上的、文案统一)。

---

## 4. 待规划项(请 orchestrator 排期)

**A. 简历优化前端(等用户 HiFi)** — 用户明确"先做 HiFi 测效果再定前端形态",暂不动:
- 深度优化面板(流式反问,**无选择框**)+ chip 外壳(C·composer chip 驱动,已拍板)
- 编辑页三栏 + WYSIWYG 单源 HTML→PDF(Track A,解决"导出≠预览";大件)

**B. 知识库接进深度优化(纯后端,可立即排)** — 用户认可方向,自己在 check ContextRegistry:
- 现状:深度优化的反问(`plan_turn`)+ 改写(`propose_rewrite_v0_v2`)**都没接** ContextRegistry/知识库,"锁定赛道"目前只是传字符串。
- 要做:大概率加一个 `PURPOSE_RESUME_OPTIMIZE`,让 podcast/track-rubric provider 按"深度优化"场景返对口内容 → 反问被赛道考察点引导、改写参照赛道 rubric。
- 内容侧提醒:`track_resume_rubrics` 金融赛道还薄;podcast(金融招聘洞察)现成对口,先接 podcast。

**C. OfferShow 薪资行情管线(独立副产,需你定归并)** ⚠️:
- 已建:`salary_intel/normalizer.py`(置信度分级解析,20 测试)+ `OfferShowSalary` 模型 + Alembic `d8e9f0a1b2c3` + `scripts/ingest_offershow_salaries.py`;**已落 dev DB 3843 条**(94 家 GT 公司,带赛道/档位标签)。
- **问题**:这些文件目前在**主 clone 的工作区,未提交**——因为主 clone 当时停在 `phase_g_decision_telemetry` 分支 + 有别人未提交 WIP,`models.py` 混了两边改动,我没法干净只提交我的。**需要你决定怎么落**(单开 salary-intel 分支 / 等 telemetry 合了再补 / patch-stage)。
- 覆盖结论:OfferShow 适合金融科技/量化开发/投行/银行薪资;公募投研+买方 quant/PE 薄,得靠别的源。详见 sync `2026-06-06-offershow-抓取方案-handoff.md §12`。

---

## 5. 协调红线(沿用 CLAUDE.md)

- 简历优化后端改动都在 `resume-copilot` 分支,不碰别人 WIP;记忆写入仍走唯一路径(`extract_for_chat_turn`),改写仍带编数字红线(硬契约 2)。
- 薪资管线动了主 clone 的 `models.py`(追加 `OfferShowSalary`)——归并时注意别和 telemetry 分支的 `models.py` 改动冲突。
