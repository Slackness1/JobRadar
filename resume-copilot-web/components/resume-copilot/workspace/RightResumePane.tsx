'use client';

/**
 * RightResumePane — 右栏简历预览 + 档案浮条 (A / C-6 / E-3).
 *
 * FE-1 placeholder。真正实现由 FE-3 (简历 + 改写) + FE-4 (档案) 子代理分工:
 *
 *   FE-3:
 *     - `<ResumePreview>` 渲染当前 confirmed_profile
 *     - hover bullet 出 ✏️ 改写按钮(C-6 入口之一)
 *     - inline diff v0/v2 (C-1 简化版)
 *     - 编造数字红警告 (C-5)
 *
 *   FE-4:
 *     - 档案浮条 🟢 + 展开面板(A-1/A-2/A-5/A-6/A-7)
 *
 * 此 placeholder 保留挂载点 + props 接口。
 *
 * TODO(FE-3): 现 `<EditableResumeCanvas>` 应该搬到这里(只用 preview 部分,
 *             编辑能力由 plan-mode 替代,见 §4 of design doc)。
 * TODO(FE-4): 现 `<StudentKbDrawer>` 应该重做成右栏底部档案浮条。
 */

import type { ResumeProfilePayload, ResumeCopilotSession } from '../types';
import { I } from '@/components/hifi/hifi-primitives';

export interface RightResumePaneProps {
  session: ResumeCopilotSession | null;
  profile: ResumeProfilePayload;
  isExporting: boolean;
  canExport: boolean;
  isDemo: boolean;
  /** 学生点 bullet 上的 ✏️ 触发改写(C-6)— FE-3 实装时连后端 */
  onRequestBulletRewrite?: (bulletPath: string) => void;
  /** 学生在档案浮条点开 — FE-4 实装时连 archive-panel */
  onOpenArchive?: () => void;
  /** 学生点 "导出 PDF" 触发 */
  onExport?: () => void;
}

export function RightResumePane({
  session,
  profile,
  isExporting,
  canExport,
  isDemo,
  onRequestBulletRewrite,
  onOpenArchive,
  onExport,
}: RightResumePaneProps) {
  // Reserved for FE-3 / FE-4 wiring; reference so lint stays clean while shell ships.
  void isExporting;
  void canExport;
  void onRequestBulletRewrite;
  void onOpenArchive;
  void onExport;

  const name = profile.basic_info?.name ?? profile.basic_info?.full_name ?? '';
  const summary = profile.candidate_summary?.slice(0, 60) ?? '';
  const ready = session?.has_parsed_profile === true;

  return (
    <aside className="workspace-hifi__pane workspace-hifi__pane--right" aria-label="简历预览与档案">
      <header className="workspace-hifi__pane-header">
        <span className="workspace-hifi__pane-header-icon" aria-hidden>
          {I.file(16)}
        </span>
        <span>简历预览</span>
        <span className="workspace-hifi__pane-header-count">
          {ready ? (name || '已解析') : '解析中'}
          {isDemo ? ' · DEMO' : ''}
        </span>
      </header>

      <div className="workspace-hifi__pane-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="workspace-hifi__placeholder">
          <span className="workspace-hifi__placeholder-todo">FE-3 占位</span>
          <span className="workspace-hifi__placeholder-title">简历预览 + 改写</span>
          <span className="workspace-hifi__placeholder-hint">
            C-1 / C-5 / C-6 / E-3
            <br />
            原 EditableResumeCanvas 应迁移为只读预览 + hover 改写按钮。
            {summary ? (
              <>
                <br />
                <span style={{ fontStyle: 'italic', color: 'var(--olive)' }}>
                  当前 summary:{summary}…
                </span>
              </>
            ) : null}
          </span>
        </div>

        <div className="workspace-hifi__placeholder">
          <span className="workspace-hifi__placeholder-todo">FE-4 占位</span>
          <span className="workspace-hifi__placeholder-title">📌 我的档案</span>
          <span className="workspace-hifi__placeholder-hint">
            A-1 / A-2 / A-5 / A-6 / A-7
            <br />
            收起浮条 + 🟢 小绿点;原 StudentKbDrawer 重做为内嵌面板。
          </span>
        </div>
      </div>
    </aside>
  );
}
