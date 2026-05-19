'use client';

/**
 * MiddleChatPane — 中栏 chat / plan-mode 主区 (B-1 / B-2 / B-3 / B-4 / E-3).
 *
 * FE-1 placeholder。真正实现由 FE-4 子代理来做:
 *   - chat composer 上方 mode toggle `[💬 普通 │ 📌 plan-mode]`
 *   - plan-mode 进入后 AI 列档案让学生选 (B-2 简)
 *   - plan-mode 草稿 review 入档卡 (B-3 / B-4)
 *
 * E-3 改写思考浮出动画 由 FE-3 在右栏触发 → MiddleChatPane 接收信号渲染。
 *
 * 此 placeholder 保留 chat 输入框骨架(disabled),让学生能看到位置。
 *
 * TODO(FE-4): 现 `<ResumeChatRail>` 里的 chat 区(messages list + composer +
 *             rewrite option cards)应搬到这里 ── 见 public-resume-copilot.tsx
 *             `ResumeChatRail` / `ChatMessageBubble` / `RewriteOptionCard`。
 */

import type {
  CopilotMessage,
  ResumeCopilotSession,
} from '../types';
import { HFBtn, I } from '@/components/hifi/hifi-primitives';

export type ChatComposerMode = 'normal' | 'plan';

export interface MiddleChatPaneProps {
  session: ResumeCopilotSession | null;
  chatMessages: CopilotMessage[];
  isSendingChat: boolean;
  applyingOption: string | null;
  sendChatMessage: (content: string) => Promise<void>;
  applyRewriteOption: (messageId: number, optionId: string) => Promise<void>;
  /** 当前 composer mode(B-1) — FE-4 把它从 props 转成内部 state */
  composerMode?: ChatComposerMode;
  onComposerModeChange?: (mode: ChatComposerMode) => void;
}

export function MiddleChatPane({
  session,
  chatMessages,
  isSendingChat,
  applyingOption,
  sendChatMessage,
  applyRewriteOption,
  composerMode = 'normal',
  onComposerModeChange,
}: MiddleChatPaneProps) {
  // Reserved for FE-4 wiring; reference so lint stays clean while the shell ships.
  void isSendingChat;
  void applyingOption;
  void sendChatMessage;
  void applyRewriteOption;
  void composerMode;
  void onComposerModeChange;

  const feedbackReady = session?.feedback_status === 'completed';
  const messageCount = chatMessages.length;

  return (
    <section className="workspace-hifi__pane workspace-hifi__pane--middle" aria-label="Chat 主区">
      <header className="workspace-hifi__pane-header">
        <span className="workspace-hifi__pane-header-icon" aria-hidden>
          {I.sparkle(15)}
        </span>
        <span>AI 简历助手</span>
        <span className="workspace-hifi__pane-header-count">
          {feedbackReady ? `${messageCount} 条对话` : '等待简历就绪'}
        </span>
      </header>

      <div className="workspace-hifi__pane-body" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="workspace-hifi__placeholder" style={{ flex: 1 }}>
          <span className="workspace-hifi__placeholder-todo">FE-4 占位</span>
          <span className="workspace-hifi__placeholder-title">Chat / Plan-mode 主区</span>
          <span className="workspace-hifi__placeholder-hint">
            B-1 / B-2 / B-3 / B-4 / E-3
            <br />
            原 ResumeChatRail 内的 chat 消息流 + RewriteOptionCard 将搬到这里。
          </span>
        </div>

        {/* Composer scaffold — disabled until FE-4 wires it; mainly verifies layout. */}
        <div
          style={{
            marginTop: 18,
            padding: 12,
            borderRadius: 14,
            background: 'var(--library-rail)',
            boxShadow: '0 0 0 1px var(--border-warm)',
            display: 'flex',
            alignItems: 'flex-end',
            gap: 8,
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: 'flex',
                gap: 6,
                marginBottom: 8,
                fontSize: 11.5,
                color: 'var(--stone)',
                letterSpacing: '0.04em',
              }}
            >
              <span
                style={{
                  padding: '3px 9px',
                  borderRadius: 999,
                  background: 'var(--ivory)',
                  color: 'var(--ink-soft)',
                  boxShadow: '0 0 0 1px var(--border-warm)',
                }}
              >
                💬 普通
              </span>
              <span
                style={{
                  padding: '3px 9px',
                  borderRadius: 999,
                  background: 'transparent',
                  color: 'var(--stone)',
                }}
              >
                📌 plan-mode
              </span>
            </div>
            <textarea
              rows={2}
              disabled
              placeholder="FE-4 实装后此处可输入… (Shift+Enter 换行)"
              style={{
                width: '100%',
                resize: 'none',
                border: 0,
                background: 'transparent',
                outline: 'none',
                fontSize: 14,
                lineHeight: 1.5,
                color: 'var(--ink)',
                padding: '4px 6px',
                opacity: 0.6,
              }}
            />
          </div>
          <HFBtn
            variant="primary"
            size="sm"
            disabled
            style={{ height: 36, width: 36, padding: 0, borderRadius: 10 }}
            aria-label="发送"
          >
            {I.arrowUp(14)}
          </HFBtn>
        </div>
      </div>
    </section>
  );
}
