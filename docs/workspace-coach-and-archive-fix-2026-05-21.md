# Workspace 5 Pain-points Fix Plan (2026-05-21)

> **Post-compact handoff doc**. 这一轮工作触发自学生 2026-05-21 多次反馈,部分已完成、部分进行中。compact 后接手的 agent 严格按本文档执行,**不要重新调研**,直接看 "已完成 vs 剩余" 段落就能接着干。

---

## 整体背景

学生在 dev VPS 上(`localhost:3002` SSH tunnel)交互式试用 `/resume-copilot` workspace,提出 5 块 pain points + 1 个 bug:

| # | 来源 | 痛点 | 状态 |
|---|---|---|---|
| **P4** | 学生 | 档案 23 条散 bullet,期望按 经历/项目 分组 | ✅ **已完成**(seeder v2 + DB 清洗 + 重 seed → 16 张干净卡) |
| **P2** | 学生 | Coach thinking 动画一闪而过 | ✅ **已完成**(`CoachThinkingIndicator` 加 `minVisibleMs=800ms`) |
| **P3** | 学生 | "○ 时间 ○ 行动 ○ 工具 ○ 结果" 这堆空圆是啥 | 🟡 **改了一半**(`PlanProgressBar` 加了 header + tooltip,**还没 lint/build 验证**) |
| **P1** | 学生 | 解析简历阶段没 thinking 动画 | ⬜ **未开始** |
| **A** | 学生 | "换赛道"按钮点了完全没反应 | 🟡 **进行中** — 已诊断 + 写了 `TrackPickerModal` 组件 + 半接到 parent |
| **B** | 学生 | 8 canonical track 要根据 SAIF 就业报告 update | 🟡 **后端已改 10 canonical**, 前端 TrackPickerModal 已用新列表, 但前端**未 lint/build 验证** |

---

## 已完成详情

### ✅ P4 档案 grouping(2026-05-21 已上线)

**改了什么**:
- `backend/app/services/resume_copilot/memory/seeding.py` 改成**一段实习/项目一张卡**(v2)
  - summary = "公司 · 角色 (起 - 止)"
  - `payload.behavioral_hook` = 多行 bullet
  - `linked_field_paths` = 该实习所有 bullet 的 path list(任一被改 → 整张卡 needs_resync)
- `backend/tests/test_memory_dispatcher.py` 加 3 个 seed 测试(per-experience / idempotent / reserved-keys)

**清洗动作**(已在用户 DB 执行过,不要再跑一次):
- 删 user_key `0e1f0957-a904-4e5f-b2c9-cfba8a41ed74` 的 28 条 stale `parser_seed` 行
- 重 seed sessions 58/59/60/61/63/65/66/68 → 17 张总(16 parser_seed + 1 chat)

**验证 OK**:
```bash
# 已验证, 不需要再跑:
cd backend && PYTHONPATH=. .venv/bin/python3 -c "
from app.database import SessionLocal
from app.models import AccountMemory
db = SessionLocal()
rows = db.query(AccountMemory).filter_by(user_key='0e1f0957-a904-4e5f-b2c9-cfba8a41ed74', source_module='parser_seed').all()
print(len(rows))  # should be ~16
"
```

---

### ✅ P2 Coach thinking 动画 minVisibleMs(2026-05-21 已上线)

**改了什么**:
- `resume-copilot-web/components/resume-copilot/workspace/chat/CoachThinkingIndicator.tsx`
  - 加 `minVisibleMs?: number = 800` prop
  - 内部用 `visible` state + `shownAtRef` + `hideTimeoutRef` 实现 "active=false 后至少再 stick `minVisibleMs - 已 shown 时间` 才隐藏"
  - 使用 `setTimeout(setVisible, 0)` 绕过 `react-hooks/set-state-in-effect` lint

**lint + build 已过**(commit 前再 lint 一次确认)。

---

## 剩余工作(post-compact 接着干)

> **执行顺序建议**:**A → B → P3 → P1**(按学生关心程度 + 风险)
> 全程 auto mode 开,每步做完跑 `npm run lint && npm run build` + 后端相关 `pytest` 子集,**绿了才能进下一步**。

---

### 🟡 A. "换赛道"按钮 bug 修复 + TrackPickerModal 接入

#### 诊断结果

`public-resume-copilot.tsx:976` 有 `[editorOpen, setEditorOpen] = useState(false)`,但**没有任何 JSX 根据 editorOpen 渲染**。点 "换赛道" 翻 state 但啥都不出现。

#### 已经写好(尚未集成)

`resume-copilot-web/components/resume-copilot/workspace/TrackPickerModal.tsx` —— 完整组件已经写好:
- 10 张 track 卡(覆盖新 10 canonical)
- 选了 → `putResumeCopilotPreferences` + `postResumeCopilotGenerate`
- backdrop + modal + close button + footer 按钮
- 处理 busy / error state

#### 还没做(post-compact 直接动手)

1. **接入 parent**:`public-resume-copilot.tsx` 已经 `import { TrackPickerModal }`(行 79 后)。需要在文件**底部 JSX**(`<WorkspaceShell ... />` 之后)加 mount:

   ```tsx
   <TrackPickerModal
     open={editorOpen}
     sessionId={sessionId}
     currentTrack={profile?.inferred_tracks?.[0] ?? null}
     onChanged={() => {
       if (sessionId) loadSession(sessionId).catch(() => {});
     }}
     onClose={() => setEditorOpen(false)}
   />
   ```

   位置:大概在 `</WorkspaceShell>` 之后,`</main>` 之前(查 `line ~1527` 附近)。

2. **加 CSS**:在 `workspace-theme.css` 末尾加 TrackPickerModal 的样式(参考 `WorkspaceConfirmGuide` 的 backdrop / card / footer 那套 token):
   - `.workspace-hifi__track-picker-backdrop` — fixed overlay,黑 45%
   - `.workspace-hifi__track-picker-card` — 640px width,parchment 背景
   - `.workspace-hifi__track-picker-head` / `-title` / `-close` / `-sub`
   - `.workspace-hifi__track-picker-grid` — 2-col grid of cards
   - `.workspace-hifi__track-picker-item` — card style,hover terracotta border,`.is-selected` 加 terracotta 实色边框 + wash 背景,`.is-current` 加 "当前" tag
   - `.workspace-hifi__track-picker-icon` / `-text` / `-name` / `-blurb` / `-current-tag`
   - `.workspace-hifi__track-picker-error`
   - `.workspace-hifi__track-picker-footer` — flex right,2 buttons
   - `.workspace-hifi__track-picker-btn` / `--primary`

3. **验证**:
   ```bash
   cd resume-copilot-web && npm run lint  # 0 errors
   npm run build  # 通过
   ```

4. **手动验证**(用户 SSH tunnel 试):
   - 点 TopTrackBar "换赛道" → modal 出现
   - 选一个赛道 → confirm → modal 关 + 推荐自动重生成(看左栏 tab 数字刷新)

---

### 🟡 B. 8 → 10 canonical tracks(新增大宗·能源 + 战略咨询)

#### 决策依据(已读完不要再读)

读了 `/tmp/saif_reports/2025_MF.pdf`(已 download)+ 用户口述老师反馈。关键数据:

**2025 MF General(75 domestic graduates)**:
- 行业:**资管 45%** / 投行券商 14% / 实体企业 14% / 科技互联网 10% / 商业银行 9% / 监管 6%
- 职能:**投研 43%** / 管培 26% / 咨询/战略/数据 9% / 销售交易 9% / 投行 8%

**头部雇主里命中"大宗·能源"的至少 5 家**:LDC 路易达孚 / Cargill 嘉吉 / 托克 Trafigura / COSCO 中远海运 / 中石油国际 / AESC 远景动力

**用户明确要拆**:管理咨询(McKinsey 等)vs 战略咨询(通用 strategy / 公司战略组)

#### 后端已改

`backend/app/services/taxonomy/canonical.py`:
- `CANONICAL_FINANCE_TRACKS` 改成 10 个(老 8 + `管理咨询·MBB` 重命名自原 `金融咨询` + `战略咨询` 新增 + `大宗·能源` 新增)
- `TRACK_ALIASES` 拆原"金融咨询"段,加新两段(McKinsey/BCG → 管理咨询·MBB;"战略组"/"通用咨询" → 战略咨询;路易达孚/嘉吉/托克/中石油/AESC/Cargill → 大宗·能源)
- "金融咨询"作为 backward-compat alias 仍指向"管理咨询·MBB"
- `TRANSFERABLE_FOR_UMBRELLA` 替换所有"金融咨询" → "管理咨询·MBB",加 "战略咨询" 跳板

**已用 Python script 验证 10 个 canonical 都正确 canonicalize**:
```
McKinsey → 管理咨询·MBB ✓
战略咨询 → 战略咨询 ✓
战略组 → 战略咨询 ✓
咨询 → 管理咨询·MBB ✓
路易达孚 → 大宗·能源 ✓
大宗商品 → 大宗·能源 ✓
Cargill → 大宗·能源 ✓
托克 → 大宗·能源 ✓
中石油 → 大宗·能源 ✓
金融咨询 → 管理咨询·MBB ✓ (backward-compat)
```

#### 前端已改

`TrackPickerModal.tsx` 内 `TRACKS` 数组已经包含 10 个,每个有 icon + label + blurb(参考 SAIF 报告写的人话)。

#### 还没做

1. **跑相关后端测试确认没崩**:
   ```bash
   cd backend && PYTHONPATH=. .venv/bin/pytest \
     tests/test_phase_d_track_knowledge.py \
     tests/test_recommendation_track_filter.py \
     tests/test_resume_recommendation_service.py \
     tests/test_track_importer.py \
     tests/test_recommendation_priority_tier.py 2>&1 | tail -5
   ```
   预期:全过(老 alias `金融咨询` 还在,只是指向 `管理咨询·MBB`,所以历史测试不应破)

2. **重启后端**(让新 taxonomy 加载到运行时):
   ```bash
   cd backend && pkill -f "uvicorn.*8000"; sleep 3
   nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info > /tmp/backend_eval.log 2>&1 & disown
   until curl -sf http://127.0.0.1:8000/api/health > /dev/null; do sleep 1; done; echo ready
   ```

3. **回归验证**(可选):重新跑 user session 59 的 generate,看推荐还是合理(不应该崩或退化):
   ```bash
   PYTHONPATH=. .venv/bin/python3 -c "
   import requests
   H = {'X-Resume-User-Key': '0e1f0957-a904-4e5f-b2c9-cfba8a41ed74'}
   r = requests.post('http://127.0.0.1:8000/api/resume-copilot/sessions/59/generate', headers=H, timeout=15)
   print(r.status_code, r.text[:100])
   "
   ```

---

### 🟡 P3 PlanProgressBar 加 header + tooltip(改了一半)

#### 已改

`resume-copilot-web/components/resume-copilot/workspace/chat/PlanProgressBar.tsx`:
- 加 `ANCHOR_HINTS` const(每个 anchor 的人话解释)
- 加 `.workspace-hifi__plan-progress-header` div(标题 "AI 想问你这 4 件事" + 进度 "doneCount / 4")
- 用 `.workspace-hifi__plan-progress-steps` wrap 原来的 4 个 step button
- 每个 step button 的 `title` 改成 `{LABEL} — {HINT}{(已补齐|待补充)}`

#### 还没做

1. **加 CSS** —— `workspace-theme.css` 已有 `.workspace-hifi__plan-progress`, `.workspace-hifi__plan-progress-step` 等,需要加 3 个新 class:
   - `.workspace-hifi__plan-progress-header` — flex row,space-between,title 左 count 右
   - `.workspace-hifi__plan-progress-title` — 13px,terracotta-strong,font-weight 500
   - `.workspace-hifi__plan-progress-count` — 11px,olive,mono(可选)
   - `.workspace-hifi__plan-progress-steps` — 原 step button 应该用这个 flex container 包起来(检查是否要改原 `.workspace-hifi__plan-progress` 的 flex direction,因为现在它从横排 step → 纵排 header+steps)

   **关键**:`.workspace-hifi__plan-progress` 原本可能是 `display: flex; flex-direction: row`,现在 wrap 后应该改成 `column`,steps 内部还是 row。检查 `workspace-theme.css:grep -A 5 "plan-progress {"`。

2. **lint + build**:
   ```bash
   cd resume-copilot-web && npm run lint && npm run build
   ```

---

### ⬜ P1 解析简历阶段也加 thinking 动画(还没做)

#### 设计

复用 `CoachThinkingIndicator` 的 pattern,做一个 `ParserThinkingIndicator`(或直接复用 `CoachThinkingIndicator` 加 `phase="parsing"`)。在 `RightResumePane` 的"解析中"placeholder 旁边 mount。

#### 实现步骤

1. **拓展 CoachThinkingIndicator phase**(或新组件 — 倾向前者):
   - 在 `CoachThinkingPhase` type 加 `'parsing'`
   - `PHASE_HINTS` 加 `parsing: { label: 'AI 正在解析你的简历', sub: '抽取教育 / 实习 / 项目 / 技能 → 写入 confirmed_profile (约 30 秒)' }`

2. **RightResumePane 接入**:
   - 在 `placeholder`(`ready === false` 的分支)替换为:
     ```tsx
     <CoachThinkingIndicator
       active={!ready}
       phase="parsing"
       minVisibleMs={800}
     />
     ```
   - 注意:RightResumePane 的 placeholder 现在是 `<div className="workspace-hifi__placeholder">` 多行结构,需要替换或并存

3. **lint + build** + 强刷浏览器:上传新简历,30 秒 parse 期间应该看到 thinking bubble + 计时

---

## 全 pipeline 验证

修完上面 4 件事后:

```bash
# 后端
cd backend && PYTHONPATH=. .venv/bin/pytest \
  tests/test_memory_dispatcher.py \
  tests/test_memory_endpoints.py \
  tests/test_resume_recommendation_service.py \
  tests/test_rewrite_v0_v2.py \
  tests/test_chat_service.py \
  tests/test_phase_d_track_knowledge.py \
  tests/test_recommendation_track_filter.py 2>&1 | tail -3

# 前端
cd resume-copilot-web && npm run lint 2>&1 | tail -3
npm run build 2>&1 | tail -3
```

**通过标准**:
- 后端测试全过(>180 个)
- 前端 lint 0 errors,build 绿
- 手动验证(用户 SSH tunnel):
  1. 上传新简历 → 看 parse thinking 动画 + 计时
  2. workspace 进来 → 顶部点"换赛道" → modal 出 → 选一个 → 推荐重生成
  3. 进 coach → 4 anchor 上面有 header "AI 想问你这 4 件事" + tooltip
  4. coach 反问 → thinking 动画 stick 至少 800ms

---

## 文件清单(post-compact 一眼定位)

### 已改但未 commit

**Backend**:
- `backend/app/services/taxonomy/canonical.py` — 10 canonical + 新 aliases ✅ 已生效需重启
- `backend/app/services/resume_copilot/memory/seeding.py` — v2 per-experience ✅ 已生效已 reseed

**Frontend**:
- `resume-copilot-web/components/resume-copilot/workspace/chat/CoachThinkingIndicator.tsx` — minVisibleMs ✅ lint 过
- `resume-copilot-web/components/resume-copilot/workspace/chat/PlanProgressBar.tsx` — 加 header + ANCHOR_HINTS 🟡 **CSS 未加,lint 未跑**
- `resume-copilot-web/components/resume-copilot/workspace/TrackPickerModal.tsx` — 新文件,完整 ✅
- `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx` — 已 `import { TrackPickerModal }` 🟡 **未 mount JSX**

### 没改

- `RightResumePane.tsx` — P1 解析动画接入未做
- `workspace-theme.css` — TrackPickerModal CSS + PlanProgressBar header CSS 都没加

### 数据状态(不要再清/seed)

- user `0e1f0957-...` 现有 17 条 memory rows(16 parser_seed v2 + 1 chat),整洁状态保持

---

## 给 post-compact agent 的 3 条硬约束

1. **不要重新调研**,直接看本文档"已完成 vs 剩余"段对照动手
2. **每步**lint + 相关 pytest 子集**绿了**再进下一步
3. **重启 backend** 必须用 `cd backend && pkill ... && nohup .venv/bin/uvicorn ...` 完整命令(别忘了 cd 否则 .venv 找不到)

完成后给用户一句话汇报:**"5 件事都做完了,刷新浏览器试"**。
