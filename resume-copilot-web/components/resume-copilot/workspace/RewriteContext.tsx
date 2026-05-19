'use client';

/**
 * RewriteContext — 跨栏改写状态广播 (E-3 chat-out-thinking + right-pane inline diff).
 *
 * Phase 2 FE-3 (2026-05-20).
 *
 * Background:
 *   - 学生在 RightResumePane 点 bullet hover 的 ✏️ → 触发 v0/v2 rewrite
 *   - 同时 MiddleChatPane 顶部要出 "AI 正在思考改写..." (E-3)
 *   - 不想做 prop drilling (跨过 WorkspaceShell) — 也不想让 RightResumePane
 *     和 MiddleChatPane 互相 import
 *
 * Solution:
 *   - 一个轻量 React Context, provider 放在 WorkspaceShell 外层 (或顶部 div),
 *     RightResumePane 既写也读 (writer),`<RewriteThinkingBubble>` 只读 (reader).
 *   - FE-4 在 MiddleChatPane 顶部 mount `<RewriteThinkingBubble />` 即可,
 *     不需要拿任何额外 prop.
 *
 * Status flow:
 *   idle  -> thinking (RightResumePane 调 API 时 setRequesting)
 *         -> done    (API 200, 显示 v0/v2 后 setSuccess)
 *         -> idle    (5s 后自动归 idle, 或学生关闭 diff 时 reset)
 *         -> error   (API 失败, 显示错误)
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

export type RewriteStatus = 'idle' | 'thinking' | 'done' | 'error';

export interface RewriteStateSnapshot {
  status: RewriteStatus;
  /** 当前正在改写的 bullet 原文 (display in chat bubble) */
  originalBullet?: string;
  /** done 状态下 v0 echo 文本 */
  v0?: string;
  /** done 状态下 v2 改写文本 (needs_plan_mode=true 时该字段为 undefined) */
  v2?: string;
  /** 出错时的错误提示 */
  errorMessage?: string;
  /** field path,用作展示 hint(e.g. "internships.0.bullets.2") */
  fieldPath?: string;
}

interface RewriteContextValue extends RewriteStateSnapshot {
  beginThinking(args: { originalBullet: string; fieldPath: string }): void;
  markDone(args: { v0: string; v2?: string }): void;
  markError(message: string): void;
  reset(): void;
}

const noop = () => {};

const RewriteContext = createContext<RewriteContextValue>({
  status: 'idle',
  beginThinking: noop,
  markDone: noop,
  markError: noop,
  reset: noop,
});

const AUTO_RESET_MS = 6000;

export function RewriteProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<RewriteStateSnapshot>({ status: 'idle' });
  // Track timers so re-triggering before auto-reset cancels the previous one.
  const autoResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearAutoReset = useCallback(() => {
    if (autoResetTimer.current) {
      clearTimeout(autoResetTimer.current);
      autoResetTimer.current = null;
    }
  }, []);

  const beginThinking = useCallback(
    ({ originalBullet, fieldPath }: { originalBullet: string; fieldPath: string }) => {
      clearAutoReset();
      setState({
        status: 'thinking',
        originalBullet,
        fieldPath,
        v0: undefined,
        v2: undefined,
        errorMessage: undefined,
      });
    },
    [clearAutoReset],
  );

  const markDone = useCallback(
    ({ v0, v2 }: { v0: string; v2?: string }) => {
      clearAutoReset();
      setState((previous) => ({
        ...previous,
        status: 'done',
        v0,
        v2,
        errorMessage: undefined,
      }));
      autoResetTimer.current = setTimeout(() => {
        setState({ status: 'idle' });
        autoResetTimer.current = null;
      }, AUTO_RESET_MS);
    },
    [clearAutoReset],
  );

  const markError = useCallback(
    (message: string) => {
      clearAutoReset();
      setState((previous) => ({
        ...previous,
        status: 'error',
        errorMessage: message,
      }));
      autoResetTimer.current = setTimeout(() => {
        setState({ status: 'idle' });
        autoResetTimer.current = null;
      }, AUTO_RESET_MS);
    },
    [clearAutoReset],
  );

  const reset = useCallback(() => {
    clearAutoReset();
    setState({ status: 'idle' });
  }, [clearAutoReset]);

  const value = useMemo<RewriteContextValue>(
    () => ({
      ...state,
      beginThinking,
      markDone,
      markError,
      reset,
    }),
    [state, beginThinking, markDone, markError, reset],
  );

  return <RewriteContext.Provider value={value}>{children}</RewriteContext.Provider>;
}

export function useRewriteState(): RewriteContextValue {
  return useContext(RewriteContext);
}
