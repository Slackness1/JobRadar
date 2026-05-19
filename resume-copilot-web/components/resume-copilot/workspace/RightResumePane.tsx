'use client';

/**
 * RightResumePane — 右栏简历预览 + hover 改写 + inline diff + 编数字红警 (C-1 / C-5 / C-6 / E-3).
 *
 * Phase 2 FE-3 (2026-05-20).
 *
 * 三块:
 *   1. <ResumePreview>          只读简历 + 每条 bullet hover 出 ✏️ (C-6)
 *   2. inline <BulletRewriteDiff>  v0/v2 diff,带红警告 + plan-mode 引导
 *   3. archiveSlot              底部 ~20vh 空间给 FE-4 ArchivePanel 用
 *
 * 跨栏信号(给 MiddleChatPane 的 chat-out-thinking):走 `<RewriteProvider>` /
 * `useRewriteState()` (workspace/RewriteContext.tsx);MiddleChatPane mount
 * `<RewriteThinkingBubble />` 即可,不需要任何 prop drilling.
 *
 * Apply 链路 (P1 末尾接通):
 *   - 当前阶段:学生点 "采用 v2" → 复制 v2 文本到剪贴板 + toast 提示
 *     学生粘贴回简历对应位置
 *   - 不真改 confirmed_profile — 留给 BE-X 把 v0v2 endpoint 跟 apply 串起来
 *
 * 设计系统隔离:
 *   - 所有样式 scope `.workspace-hifi` (见 workspace-theme.css)
 *   - HiFi token 来自 `.hf` (parent scope, WorkspaceShell 已 wrap)
 */

import { useCallback, useState } from 'react';

import type { ResumeProfilePayload, ResumeCopilotSession } from '../types';
import { I, HFBtn } from '@/components/hifi/hifi-primitives';
import {
  postRewriteV0V2,
  type RewriteV0V2Out,
} from '../api';
import { useRewriteState } from './RewriteContext';
import { ResumePreview, type ActiveRewrite } from './resume/ResumePreview';
import type { FabricationWarningAction } from './resume/FabricationWarning';

export interface RightResumePaneProps {
  session: ResumeCopilotSession | null;
  profile: ResumeProfilePayload;
  isExporting: boolean;
  canExport: boolean;
  isDemo: boolean;
  /** 当前用户 X-Resume-User-Key — WorkspaceShell 串入(后续 FE-2 wire);
   *  暂未传时 api.ts 自己会从 localStorage 拿 */
  xResumeUserKey?: string;
  /** 当前关联的 target job — 关联 chat 里 active 推荐时填,用于改写 prompt 引导
   *  (后续 FE-2 wire 完后真填) */
  targetJob?: { title?: string; description?: string } | null;
  /** FE-4 ArchivePanel slot (由 WorkspaceShell 从外部传 ReactNode 进来) */
  archiveSlot?: React.ReactNode;
  /** 学生从 inline diff 里点 "切到 plan-mode" 触发 — WorkspaceShell 串到 MiddleChatPane */
  onPlanModeRequest?: (fieldPath: string, originalBullet: string) => void;
  /** 学生点档案浮条触发(FE-4) */
  onOpenArchive?: () => void;
  /** 学生点 "导出 PDF" 触发 — 由 WorkspaceShell 提供 */
  onExport?: () => void;
}

export function RightResumePane({
  session,
  profile,
  isExporting,
  canExport,
  isDemo,
  xResumeUserKey,
  targetJob,
  archiveSlot,
  onPlanModeRequest,
  onOpenArchive,
  onExport,
}: RightResumePaneProps) {
  // referenced — header surfaces session readiness; xResumeUserKey reserved for
  // future direct header injection (api.ts pulls from localStorage today).
  void xResumeUserKey;

  // ── inline rewrite state ────────────────────────────────────────────────────
  const [activeRewrite, setActiveRewrite] = useState<ActiveRewrite | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const rewriteCtx = useRewriteState();

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3200);
  }, []);

  const handleRequestRewrite = useCallback(
    async (fieldPath: string, bulletText: string, section: string) => {
      if (!session?.id) {
        showToast('简历还没解析完成,稍候再试。');
        return;
      }
      if (isDemo) {
        showToast('Demo 简历是只读 — 上传自己的简历后即可改写。');
        return;
      }
      // 1. Optimistically open the diff panel in loading state.
      setActiveRewrite({
        fieldPath,
        originalBullet: bulletText,
        loading: true,
        result: null,
        error: null,
      });
      // 2. Broadcast to chat-side thinking bubble (E-3).
      rewriteCtx.beginThinking({ originalBullet: bulletText, fieldPath });

      try {
        const result: RewriteV0V2Out = await postRewriteV0V2(session.id, {
          bullet_text: bulletText,
          field_path: fieldPath,
          target_job_description: targetJob?.description ?? '',
          target_title: targetJob?.title ?? '',
          section,
        });
        setActiveRewrite({
          fieldPath,
          originalBullet: bulletText,
          loading: false,
          result,
          error: null,
        });
        rewriteCtx.markDone({
          v0: result.v0?.text ?? bulletText,
          v2: result.v2?.needs_plan_mode ? undefined : result.v2?.text,
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setActiveRewrite({
          fieldPath,
          originalBullet: bulletText,
          loading: false,
          result: null,
          error: `改写失败:${msg}`,
        });
        rewriteCtx.markError(msg || '改写失败,请稍后重试。');
      }
    },
    [session?.id, isDemo, rewriteCtx, showToast, targetJob],
  );

  const handleDismissRewrite = useCallback(() => {
    setActiveRewrite(null);
    rewriteCtx.reset();
  }, [rewriteCtx]);

  const handleAcceptRewrite = useCallback(
    // (originalText, fieldPath) intentionally accepted but unused at this stage
    // — apply 链路 P1 末尾接通后 BE-X 会用到;签名先留齐方便对接.
    async (v2Text: string, ..._unusedRest: unknown[]) => {
      void _unusedRest;
      if (!v2Text) {
        showToast('v2 文本为空,无法采用。');
        return;
      }
      try {
        if (navigator?.clipboard?.writeText) {
          await navigator.clipboard.writeText(v2Text);
          showToast('已复制 v2 到剪贴板,粘贴到简历对应位置即可。完整 apply 链路 P1 末尾接通。');
        } else {
          // Fallback: legacy execCommand
          const ta = document.createElement('textarea');
          ta.value = v2Text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          try {
            document.execCommand('copy');
            showToast('已复制 v2 到剪贴板,粘贴到简历对应位置即可。');
          } finally {
            document.body.removeChild(ta);
          }
        }
        // 关闭 diff (学生采纳后就不需要再看了)
        setActiveRewrite(null);
        rewriteCtx.reset();
      } catch {
        showToast('复制失败,请手动选中 v2 文本复制。');
      }
    },
    [rewriteCtx, showToast],
  );

  const handlePlanModeRequest = useCallback(
    (fieldPath: string, originalBullet: string) => {
      onPlanModeRequest?.(fieldPath, originalBullet);
      showToast('已请求切到 plan-mode 聊这段经历。');
      // 关闭 diff,让学生去 chat 区
      setActiveRewrite(null);
      rewriteCtx.reset();
    },
    [onPlanModeRequest, rewriteCtx, showToast],
  );

  const handleWarningAction = useCallback(
    (action: FabricationWarningAction, detail: string) => {
      // C-5: 不能 suppress warnings — 这里只显示学生选择,真正修复值仍由学生回到
      // 简历手填(plan-mode / 档案补充). FE-3 阶段 callback 落到 toast,后续
      // BE 接通 apply 链路时再串回服务端 (e.g. 自动清掉数字 / 进 plan-mode).
      const label =
        action === 'fill_real'
          ? '请填实数(回到原 bullet 编辑该数字)'
          : action === 'delete_number'
          ? '将删掉编造数字(P1 末尾接通后自动改 v2 文本)'
          : action === 'vague'
          ? '已采纳模糊版 — 注意:AI 仍在 v2 写了未核实数字'
          : `已记你选择:${action}`;
      showToast(`${label} · ${detail}`);
    },
    [showToast],
  );

  // ── render ──────────────────────────────────────────────────────────────────

  const name = profile.basic_info?.name ?? profile.basic_info?.full_name ?? '';
  const ready = session?.has_parsed_profile === true;

  return (
    <aside
      className="workspace-hifi__pane workspace-hifi__pane--right"
      aria-label="简历预览与档案"
    >
      <header className="workspace-hifi__pane-header">
        <span className="workspace-hifi__pane-header-icon" aria-hidden>
          {I.file(16)}
        </span>
        <span>简历预览</span>
        <span className="workspace-hifi__pane-header-count">
          {ready ? (name || '已解析') : '解析中'}
          {isDemo ? ' · DEMO' : ''}
        </span>
        {onExport ? (
          <HFBtn
            variant="ghost"
            size="sm"
            disabled={!canExport || isExporting}
            onClick={onExport}
            style={{ marginLeft: 8, height: 30, padding: '0 10px', fontSize: 12 }}
            title={canExport ? '导出 PDF 简历' : '解析完成后可导出'}
          >
            {isExporting ? '导出中…' : '导出 PDF'}
          </HFBtn>
        ) : null}
      </header>

      <div className="workspace-hifi__pane-body workspace-hifi__pane-body--right">
        {ready ? (
          <ResumePreview
            profile={profile}
            activeRewrite={activeRewrite}
            onRequestRewrite={handleRequestRewrite}
            onAcceptRewrite={handleAcceptRewrite}
            onDismissRewrite={handleDismissRewrite}
            onPlanModeRequest={handlePlanModeRequest}
            onWarningAction={handleWarningAction}
            isDemo={isDemo}
          />
        ) : (
          <div className="workspace-hifi__placeholder">
            <span className="workspace-hifi__placeholder-todo">解析中</span>
            <span className="workspace-hifi__placeholder-title">简历正在 parse</span>
            <span className="workspace-hifi__placeholder-hint">
              后端正在抽取教育 / 实习 / 项目 / 技能,稍候即可看到预览 + 改写入口。
            </span>
          </div>
        )}

        {/* ── Archive slot (FE-4) ────────────────────────────────────────────── */}
        <div className="workspace-hifi__archive-slot">
          {archiveSlot ? (
            archiveSlot
          ) : (
            <div className="workspace-hifi__archive-stub">
              <button
                type="button"
                className="workspace-hifi__archive-stub-btn"
                onClick={onOpenArchive}
                aria-label="打开档案面板"
              >
                <span className="workspace-hifi__archive-stub-dot" aria-hidden />
                📌 我的档案
                <span className="workspace-hifi__archive-stub-hint">
                  (FE-4 重做为内嵌面板)
                </span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Toast (兼容老 PublicResumeCopilot 没有全局 toast 系统的情况) */}
      {toast ? (
        <div className="workspace-hifi__toast" role="status" aria-live="polite">
          {toast}
        </div>
      ) : null}
    </aside>
  );
}
