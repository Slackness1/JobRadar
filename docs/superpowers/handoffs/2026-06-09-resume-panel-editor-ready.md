# 回交 orchestrator:简历优化 画布槽面板 + 全屏编辑器 已就绪

> 来自:简历副驾驶(分支 `hub-resume-optimize`,从 `resume-copilot` 切出)· 2026-06-09
> 对接:你的 `派发-简历优化接Hub画布槽-2026-06-09.md`

## 状态:Phase 1 + Phase 2 全做完(lint 0 / build 绿)

照你原型 `ResumeView` / `hub-editor*.jsx` 逐字段还原,全 `.hf` 赭红 token。两层(用户 2026-06-09 拍板):
- **侧面板**(画布槽):紧凑雷达版
- **全屏编辑器**:厚版逐维打分 + 反问取证深度优化

## 你要接的挂载点

**① 画布槽侧面板** — 替掉你 `CanvasSlot.tsx` 的 `ResumeSlotPlaceholder`:
```tsx
import { ResumeScorePanel } from '@/components/resume-copilot/workspace/hub/resume/ResumeScorePanel';
// active==='resume' 分支:
<ResumeScorePanel sessionId={sessionId} onExpandEditor={onExpandEditor} onClose={onClose} />
```
契约 props = 你派发文档里写的 `{ sessionId, onExpandEditor, onClose }`,一字不差。

**② 全屏编辑器** — 用户决定「编辑器自管 overlay」。`ResumeScorePanel` 的 `onExpandEditor` 由你(或挂载方)触发后渲染:
```tsx
import { ResumeEditorOverlay } from '@/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay';
{editorOpen && <ResumeEditorOverlay sessionId={sessionId} onClose={() => setEditorOpen(false)} />}
```
`ResumeEditorOverlay` 自己是 `position:fixed inset:0 z-index:60` 全屏 + `.hf data-theme="hub"`,自管内部所有态。无 sessionId / `mock` 时走离线 mock。

> 我目测页 `app/resume-copilot/hub-score/page.tsx` 已把这两步串起来(面板→展开→overlay),你可参照那 20 行接进 Hub。

## 进入路径(铁律,我已遵守)
先打分报告侧面板 → 右上角「展开编辑器」→ 全屏。**不跳过打分。**

## 组件清单(都在 `components/resume-copilot/workspace/hub/resume/`)
- `ResumeScorePanel.tsx`(侧面板)、`HubRadar.tsx`、`ResumeA4.tsx`
- `editor/ResumeEditorOverlay.tsx`(全屏三栏壳)、`A4Doc.tsx`、`LeftTemplate/LeftEdit/LeftLayout.tsx`
- `editor/EditorAIPanel.tsx`(右栏三 tab)、`EditorScoreReportThick.tsx`(厚版打分)、`ChatThread.tsx`(反问取证,无选择框)

## 后端(我已建 + 测;`hub-resume-optimize` 分支上,合并时带过去)
- `POST /sessions/{id}/score`、`POST /deep-optimize/start`、`POST /plan/turn`、**`POST /deep-optimize/write-back`(新增,E2.5)**:finalized draft → 写回 profile 段落(深度优化写回命脉,原先没接线)。
- 前端 API 封装在 `components/resume-copilot/api.ts`:`scoreResume` / `deepOptimizeStart` / `planTurn` / `deepOptimizeWriteBack`(都对齐真实 schema)。

## 合并协调(请你定)
- 我在 `hub-resume-optimize`(含 deep-optimize 后端 + 全部前端组件)。你的 `CanvasSlot.tsx` 在 `hub-shell-frontend`。
- **建议**:你冻结 `CanvasSlot` 接口后,我把 `hub-resume-optimize` rebase 到 `hub-shell-frontend`,然后我做那一行 `CanvasSlot` resume 分支的 import 替换 + 联调;或你直接 import 我这些组件。**你定 rebase 时机。**
- 设计 token:我用的 `.hf` token + hf-* 类都已在 `components/hifi/hifi-tokens.css`,无新增冲突。

## 目测(隧道里)
`http://localhost:3001/resume-copilot/hub-score?mock=1` —— 面板→展开编辑器→三栏+AI助手三tab→深度优化反问→写回高亮,全链路 mock 跑通。
