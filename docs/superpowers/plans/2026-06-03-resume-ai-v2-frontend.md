# AI 简历助手 v2 — 前端实施计划(按用户 HiFi 设计)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans / subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** 按用户在 Claude Design 里产出的两份设计,落地 AI 简历助手 v2 的前端 —— 优先「简历打分报告」(后端已就绪),再到简历编辑页 + 深度优化 + 自由 chat。

**设计来源(已存仓库,执行时逐像素对照):**
- `docs/superpowers/designs/2026-06-03-resume-editor-ai-v2/简历打分报告.html` — **高保真**,打分报告全貌(主交付)
- `docs/superpowers/designs/2026-06-03-resume-editor-ai-v2/简历编辑页-AI助手v2-线稿.html` + `wf/*.jsx` — **线稿**,编辑页三栏 + 右栏三能力 + 3 种组织方案对比
- `colors_and_type.css` — 设计 token,**等于**仓库现有 `resume-copilot-web/components/hifi/hifi-tokens.css`(terracotta `.hf`)

**Tech Stack:** Next.js 16 App Router + React 19;HiFi 设计系统(scope `.hf`,token 在 `hifi-tokens.css`);API 走 `components/resume-copilot/api.ts` 的 `requestJson`(自动带 `X-Resume-User-Key`)。前端无 jest —— 验证 = `npm run lint`(0 error)+ `npm run build` + 人工目测。

**后端现状:** `POST /api/resume-copilot/sessions/{id}/score` 已上线(返 `ScoreReportOut`:overall_current / potential_low-high / dimensions[8] / section_gaps),诚实分 + 潜力区间 + 逐段缺口已跑通(128 测试绿)。

---

## ⚠️ 设计 vs 现有 API 的两个差距(Phase 0 先补)

逐像素对照设计后发现后端少两段文本,补了前端才能 1:1 还原:
1. 打分报告有一段**整体诊断 prose**(「简历整体质量中上:逻辑清晰…主要短板在 STAR 与成果量化…」)—— `ScoreReportOut` 目前没有 `summary` 字段。
2. 每个逐段缺口有一段**描述 paragraph**(「"协助搭建因子回测框架"缺最终结果…」)—— `SectionGap` 目前只有短 tag 列表 `gaps[]`,没有 `detail` 段。

---

## Phase 0:后端补 summary + gap detail(小,TDD)

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py`(`ScoreReportOut` 加 `summary`;`SectionGap` 加 `detail`)
- Modify: `backend/app/services/resume_copilot/scoring.py`(prompt 要 summary + 每段 detail;`ScoreReport` dataclass + 映射)
- Modify: `backend/app/routers/resume_copilot.py`(`score_resume_session` 透传 `summary`)
- Test: `backend/tests/test_resume_scoring.py`(扩 `_FakeScorer` + 断言)

- [ ] **Step 1: 改测试 — fake 返 summary + gap.detail,断言透传**

在 `tests/test_resume_scoring.py` 的 `_FakeScorer.score` 返回里加 `'summary': '整体中上,短板在 STAR'`,并给 section_gaps[0] 加 `'detail': '协助搭建因子回测框架缺最终结果'`;在 `test_score_resume_computes_overall_and_potential` 末尾加:
```python
    assert report.summary == '整体中上,短板在 STAR'
    assert report.section_gaps[0].detail == '协助搭建因子回测框架缺最终结果'
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd backend && PYTHONPATH=. /home/chuanbo/projects/JobRadar/backend/.venv/bin/python -m pytest tests/test_resume_scoring.py -k computes -x`
Expected: FAIL(`AttributeError: 'ScoreReport' object has no attribute 'summary'`)。

- [ ] **Step 3: 加字段 — schemas**

`ScoreReportOut` 加 `summary: str = ''`;`SectionGap` 加 `detail: str = ''`。

- [ ] **Step 4: 加字段 — scoring.py**

`ScoreReport` dataclass 加 `summary: str = ''`;`score_resume` 里:
```python
    section_gaps = [
        SectionGap(
            section=str(g.get('section', '') or ''),
            label=str(g.get('label', '') or ''),
            gaps=[str(x) for x in (g.get('gaps') or []) if str(x).strip()],
            detail=str(g.get('detail', '') or ''),
        )
        for g in (raw.get('section_gaps') or [])
        if str(g.get('section', '') or '').strip()
    ]
    return ScoreReport(
        ...,
        summary=str(raw.get('summary', '') or ''),
    )
```
`_SCORE_SYSTEM_PROMPT` 的 JSON schema 加 `"summary": "一段整体诊断 prose"` 和 section_gaps 项加 `"detail": "这段缺口的一段说明"`。

- [ ] **Step 5: router 透传**

`score_resume_session` 的 `ScoreReportOut(...)` 加 `summary=report.summary`。

- [ ] **Step 6: 跑测试确认 PASS**

Run: `cd backend && PYTHONPATH=. /home/chuanbo/projects/JobRadar/backend/.venv/bin/python -m pytest tests/test_resume_scoring.py tests/test_resume_scoring_router.py -x`
Expected: all PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas_resume_copilot.py backend/app/services/resume_copilot/scoring.py backend/app/routers/resume_copilot.py backend/tests/test_resume_scoring.py
git commit -m "feat(scoring): ScoreReport 加 summary + SectionGap.detail(对齐打分报告设计)"
```

---

## Phase A:简历打分报告前端组件(主交付 · 高保真)

逐像素照 `简历打分报告.html`。结构(从上到下):
1. **报告头**:`<h1>简历打分报告</h1>` + 副标「诚实诊断 · 不改写、不刷分」(Fraunces serif)
2. **卡片头**:AI avatar(sparkles)+「AI 简历助手 / 基于目标赛道校准的多维诊断」+ 右侧三能力 pill tabs(简历打分 on / 深度优化 / 自由问)
3. **目标赛道条**:label「目标赛道」+ track-pill(`target_track` + chevron)+「切换赛道重新打分」
4. **hero**:左 = 现状分(76px serif `overall_current` + 「现状分·老实反映当前简历」)| 潜力(`潜力 {low}–{high}` + pot-bar:实条 width=current%、斜纹 gain 从 current% 到 high%)+ summary prose;右 = 300×300 雷达 SVG(8 维)
5. **维度**:「6 表层维」2列网格(6 个 dim,meter fill 按分:≥75 `f-hi`/≥65 `f-mid`/else `f-lo`)+「2 金融独有维」(`.dim.fin`,显示 meta 描述不显 meter,但有 score)
6. **逐段缺口**:「逐段缺口·深度优化入口」,每段 = name + `gap-loc`(section,mono)+ 右侧 tag chips(`gaps[]`)+ desc(`detail`)+ CTA「去深度优化这段 →」
7. **footer**:shield + 诚实契约文案

雷达算法**逐行照搬** HTML `<script>` 里的 `drawRadar`(8 点多边形、4 环、主色 `#c96442` fill-opacity .14、fin 维标签加粗变色 `#a84f34`)。

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/scoring/ScoreReport.tsx`(主组件)
- Create: `resume-copilot-web/components/resume-copilot/scoring/ScoreRadar.tsx`(雷达 SVG,React 版 drawRadar)
- Create: `resume-copilot-web/components/resume-copilot/scoring/scoring.module.css` 或复用内联 + hifi token
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`(加 `scoreResume`)
- Modify: 类型定义处(加 `ScoreReportData` TS 类型,对齐后端 `ScoreReportOut`)

- [ ] **Step 1: api 函数**

`api.ts` 加(用现有 `requestJson`):
```ts
export interface ScoreDimension { key: string; name: string; score: number; ceiling: number; reason: string }
export interface ScoreSectionGap { section: string; label: string; gaps: string[]; detail: string }
export interface ScoreReportData {
  session_id: number; target_track: string;
  overall_current: number; overall_potential_low: number; overall_potential_high: number;
  summary: string; dimensions: ScoreDimension[]; section_gaps: ScoreSectionGap[]; used_ai: boolean;
}
export function scoreResume(sessionId: number, targetTrack = ''): Promise<ScoreReportData> {
  return requestJson<ScoreReportData>(`/api/resume-copilot/sessions/${sessionId}/score`, {
    method: 'POST', body: JSON.stringify({ target_track: targetTrack }),
  });
}
```

- [ ] **Step 2: 雷达组件 `ScoreRadar.tsx`**

把 HTML `drawRadar` 改成 React:入参 `dims: {k:string; v:number; fin?:boolean}[]`,`size=300`。用 `<svg viewBox="0 0 300 300">` + 计算点位(cx=cy=150,R=96),4 环 polygon + spokes + value polygon(`fill="#c96442" fillOpacity={0.14} stroke="#c96442" strokeWidth={2}`)+ dots + labels(fin 维 `fontWeight 600 fill #a84f34`,普通 `500 #5e5d59`)。维度短名映射:逻辑/STAR/可读/完整/量化/表达/匹配度/可防守(注意 HTML 里量化与表达调过顺序做视觉平衡 —— 照 HTML 的 RADAR 顺序)。

- [ ] **Step 3: 主组件 `ScoreReport.tsx`**

入参 `{ report: ScoreReportData; onDeepOptimize?: (section: string) => void; onSwitchTrack?: () => void }`。逐像素照 HTML;所有颜色用 `var(--…)` token(已在 hifi-tokens.css);包在 `.hf` scope 下(整页若是新路由,在 layout 包 `<div className="hf">`)。dim fill 等级函数:`score>=75?'f-hi':score>=65?'f-mid':'f-lo'`。潜力斜纹:`left: ${current}%; width: ${high-current}%`。图标用现有 lucide-react(sparkles/target/git-branch/align-left/list-checks/pen-line/bar-chart-3/compass/shield-check/shield/arrow-right/refresh-cw/chevron-down)。

- [ ] **Step 4: 维度名 → 图标 + 等级映射表**

8 维固定:logic→git-branch、star→target、readability→align-left、completeness→list-checks、expression→pen-line、quantification→bar-chart-3、track_fit→compass(fin)、defensibility→shield-check(fin)。fin 两维渲染成 `.dim.fin` 卡(显 `dim-meta` 描述 + score,不显 meter,meta 文案:track_fit=「这段经历对「{target_track}」的对口程度」,defensibility=「这句话面试官追问时是否站得住」)。

- [ ] **Step 5: 挂载点**

本期先做**可独立查看的报告组件**。挂载方式二选一(执行时按右栏组织决策定,见 Phase 待定):
- 临时:在 `/resume-copilot/sessions` 或工作台加「简历打分」入口,点开拉 `scoreResume(sessionId)` 渲染 `<ScoreReport>`。
- 若右栏组织已定为 chip(见开放决策),则作为右栏「简历打分」chip 的内容。

- [ ] **Step 6: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -20`
Expected: lint 0 error;build 成功。

- [ ] **Step 7: 人工目测(请用户确认)**

起 dev(`npm run dev`,:3001),用一个有 confirmed profile 的 session 打开打分报告,对照 `简历打分报告.html` 检查:雷达 8 维、6+2 维卡、潜力斜纹条、逐段缺口 CTA、诚实契约 footer。**让用户目测确认后再提交。**

- [ ] **Step 8: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/scoring/ resume-copilot-web/components/resume-copilot/api.ts
git commit -m "feat(scoring-fe): 简历打分报告组件 — 8维雷达+现状/潜力分+逐段缺口(照 HiFi 设计)"
```

---

## Phase B+:简历编辑页 + 深度优化 + 自由 chat(线稿 → 后续)

参照 `简历编辑页-AI助手v2-线稿.html` + `wf/wf-editor.jsx`(三栏框架 / 三个左 tab)/ `wf/wf-scoring.jsx`(右栏打分)/ `wf/wf-variations.jsx`(右栏组织 3 方案)。这是 Track A(编辑页/导出)+ B2/B3 的大工程,等 Phase A 落地 + 下面开放决策定了再拆细 plan。线稿已明确的:
- **三栏**:左 300(模板/编辑/布局 tab)| 中 1fr(WYSIWYG A4 预览 + 页数徽章 + 保存/下载 PDF)| 右 380(AI 助手 v2)
- **左②编辑**:分模块就地编辑,每条 bullet 旁「引用此段」小按钮 → 喂右栏 AI
- **左③布局**:排版滑块 + 模块显隐勾选 + 超页提醒(2页徽章)
- **右栏**:三能力 chip(简历打分 / 深度优化 / 自由问),打分块复用 Phase A 组件

---

## 开放决策(执行 Phase B 前需你定)

**右栏三能力怎么组织?** 线稿给了 3 个并排方案让你选(`wf-variations.jsx`):
- **A 顶部 Tab 切换** — 强分隔,一次一能力
- **B 流式串联(单 thread)** — 打分→优化在一条对话流里
- **C composer chip 驱动** — 底部输入框上方 chip 切能力(**主框架 EditorFrame 当前用的就是这个**)

我倾向 **C**(跟你主框架一致 + 跟岗位推荐侧 composer chip 逻辑统一)。你定一个我再拆 Phase B 细化 plan。
