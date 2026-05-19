'use client';

/**
 * ChatMessageBubble — HiFi-styled chat 消息气泡 (B-1).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 与老 public-resume-copilot.tsx 的 ChatMessageBubble 行为对齐,但样式走
 * `.workspace-hifi` scope —— Tailwind 在工作台外 idiom (PublicResumeCopilot 用
 * tailwind utility),内部统一 HiFi parchment / terracotta token.
 *
 * 渲染:
 *   - user 气泡:右对齐 + terracotta 实底
 *   - assistant / system 气泡:左对齐 + ivory + 边框
 *   - 如果 message.rewrite_options 非空 → 老的 RewriteOptionCard 行为以紧凑卡片渲染
 *     (B-1 阶段保留原 apply 链路;FE-3 的 v0/v2 inline diff 是右栏新链路并存)
 *
 * 注意:为了避免大幅度 port (RewriteOptionCard 200+ 行 + audit risk / warning
 * severity),这里仅渲染 v0/v2 link 出来时学生看得到的"老链路触发"提示卡,
 * 让学生点 "在右栏看差异" 跳到 RightResumePane 的 hover 改写。完整 apply 链路
 * P1 末尾接通后再统一。
 */

import type { CopilotMessage } from '../../types';

export interface ChatMessageBubbleProps {
  message: CopilotMessage;
  applyingOption: string | null;
  onApply: (messageId: number, optionId: string) => Promise<void>;
  isDemo?: boolean;
}

export function ChatMessageBubble({
  message,
  applyingOption,
  onApply,
  isDemo = false,
}: ChatMessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="workspace-hifi__chat-msg workspace-hifi__chat-msg--user">
        <div className="workspace-hifi__chat-msg-bubble">{message.content}</div>
      </div>
    );
  }

  const isSystem = message.role === 'system';
  const options = message.rewrite_options ?? [];

  return (
    <div className="workspace-hifi__chat-msg workspace-hifi__chat-msg--assistant">
      <div
        className={`workspace-hifi__chat-msg-bubble${
          isSystem ? ' is-system' : ''
        }`}
      >
        <div className="workspace-hifi__chat-msg-text">{message.content}</div>
        {options.length > 0 && (
          <div className="workspace-hifi__chat-msg-options">
            {options.map((opt) => {
              const optKey = `${message.id}:${opt.option_id}`;
              const applied = message.applied_option_id === opt.option_id;
              const disabled =
                isDemo ||
                Boolean(message.applied_option_id) ||
                applyingOption !== null;
              const isApplying = applyingOption === optKey;
              const severity = opt.warning_severity ?? 'info';
              return (
                <div
                  key={opt.option_id}
                  className={`workspace-hifi__chat-rewrite-card${
                    severity === 'severe' ? ' is-severe' : ''
                  }`}
                >
                  <div className="workspace-hifi__chat-rewrite-head">
                    <span className="workspace-hifi__chat-rewrite-label">
                      {opt.label || `方案 ${opt.option_id}`}
                    </span>
                    {opt.section && (
                      <span className="workspace-hifi__chat-rewrite-section">
                        {opt.section}
                      </span>
                    )}
                  </div>
                  {opt.warning && (
                    <div
                      className={`workspace-hifi__chat-rewrite-warn is-${severity}`}
                    >
                      {opt.warning}
                    </div>
                  )}
                  {opt.improved && opt.improved.length > 0 && (
                    <ul className="workspace-hifi__chat-rewrite-improved">
                      {opt.improved.map((line, idx) => (
                        <li key={idx}>{line}</li>
                      ))}
                    </ul>
                  )}
                  {opt.rationale && (
                    <div className="workspace-hifi__chat-rewrite-rationale">
                      理由:{opt.rationale}
                    </div>
                  )}
                  <div className="workspace-hifi__chat-rewrite-actions">
                    <button
                      type="button"
                      className="workspace-hifi__chat-rewrite-btn"
                      disabled={disabled || applied}
                      onClick={() => void onApply(message.id, opt.option_id)}
                      title={
                        severity === 'severe'
                          ? 'AI 检测到夸大或编造,请确认后再应用'
                          : applied
                            ? '已应用'
                            : '一键应用到简历'
                      }
                    >
                      {isApplying
                        ? '应用中…'
                        : applied
                          ? '已应用'
                          : severity === 'severe'
                            ? '确认无误后应用'
                            : '一键应用'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
