'use client';

/**
 * RewriteThinkingBubble — chat-side "AI 正在思考改写" 浮出 (E-3).
 *
 * Phase 2 FE-3 (2026-05-20).
 *
 * 这个组件由 RightResumePane 触发(改写 API call 进行中 → `status='thinking'`),
 * 但在 MiddleChatPane 顶部渲染 —— 让学生**左眼读思考 / 右眼看变化**(E-3 体感).
 *
 * 使用方法 (给 FE-4):
 *   - 在 MiddleChatPane 组件 body 顶部直接 mount:
 *     ```tsx
 *     import { RewriteThinkingBubble } from './chat/RewriteThinkingBubble';
 *     ...
 *     <RewriteThinkingBubble />
 *     ```
 *   - 不需要任何 prop —— 内部走 RewriteContext (workspace/RewriteContext.tsx).
 *   - WorkspaceShell 必须用 `<RewriteProvider>` wrap 三栏 grid,否则该组件渲染 null.
 *
 * Status:
 *   - idle    -> 渲染 null (不占视觉空间)
 *   - thinking -> 出 "AI 正在思考改写..." + Border Beam 描边
 *   - done    -> 出 "改写完成 ✓" (短暂显示后由 Context 自动归 idle)
 *   - error   -> 出 "改写失败" + 错误详情
 *
 * Design system:
 *   - 受 `.hf` token 控制,在 `.workspace-hifi` scope 内
 *   - Border Beam class `.border-beam` 来自 `app/globals.css`
 */

import { I } from '@/components/hifi/hifi-primitives';
import { useRewriteState } from '../RewriteContext';

export interface RewriteThinkingBubbleProps {
  /** 允许外层自定义 wrapper className(可选,通常不需要) */
  className?: string;
}

export function RewriteThinkingBubble({ className }: RewriteThinkingBubbleProps) {
  const { status, originalBullet, fieldPath, errorMessage } = useRewriteState();

  if (status === 'idle') {
    return null;
  }

  const isThinking = status === 'thinking';
  const isDone = status === 'done';
  const isError = status === 'error';

  // Truncate original bullet to a sensible quote length so the bubble stays compact.
  const quote = originalBullet
    ? originalBullet.length > 60
      ? originalBullet.slice(0, 60) + '…'
      : originalBullet
    : '';

  return (
    <div
      className={`workspace-hifi__rewrite-bubble${
        isThinking ? ' is-thinking' : isDone ? ' is-done' : ' is-error'
      }${className ? ` ${className}` : ''}`}
      role="status"
      aria-live="polite"
    >
      {isThinking && <span className="border-beam" aria-hidden />}
      <span
        className="workspace-hifi__rewrite-bubble-icon"
        aria-hidden
      >
        {isDone ? I.check(14) : isError ? I.close(14) : I.sparkle(14)}
      </span>
      <div className="workspace-hifi__rewrite-bubble-body">
        <span className="workspace-hifi__rewrite-bubble-title">
          {isThinking && 'AI 正在思考改写…'}
          {isDone && '改写完成 ✓'}
          {isError && '改写失败'}
        </span>
        {(quote || fieldPath || errorMessage) && (
          <span className="workspace-hifi__rewrite-bubble-meta">
            {isError && errorMessage ? errorMessage : null}
            {!isError && quote ? `「${quote}」` : null}
            {!isError && fieldPath ? (
              <span className="workspace-hifi__rewrite-bubble-path"> · {fieldPath}</span>
            ) : null}
          </span>
        )}
      </div>
    </div>
  );
}
