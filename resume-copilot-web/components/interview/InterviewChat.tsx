'use client';

import { useEffect, useRef, useState } from 'react';

const SPINNER_FRAMES = ['·', '✢', '✳', '✶', '✻', '✽'] as const;

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  disabled: boolean;
  onSend: (content: string) => void;
}

export function InterviewChat({ messages, streamingContent, isStreaming, disabled, onSend }: Props) {
  const [input, setInput] = useState('');
  const [frameIdx, setFrameIdx] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingContent]);

  useEffect(() => {
    if (!isStreaming) return;
    const timer = setInterval(() => setFrameIdx((i) => (i + 1) % SPINNER_FRAMES.length), 120);
    return () => clearInterval(timer);
  }, [isStreaming]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || disabled || isStreaming) return;
    setInput('');
    onSend(trimmed);
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-[16px] px-4 py-3 text-[14px] leading-relaxed whitespace-pre-wrap ${
                msg.role === 'assistant'
                  ? 'bg-[#0b0d12] text-white/90'
                  : 'bg-[var(--soft-blue)] text-[var(--ink)]'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-[16px] bg-[#0b0d12] px-4 py-3 text-[14px] leading-relaxed text-white/90 whitespace-pre-wrap">
              {streamingContent || (
                <span className="flex items-center gap-2 text-white/40">
                  <span className="font-mono text-[15px]">{SPINNER_FRAMES[frameIdx]}</span>
                  面试官思考中…
                </span>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-[var(--border)] px-4 py-3">
        <div className="flex gap-2">
          <textarea
            className="flex-1 resize-none rounded-[12px] border border-[var(--border)] bg-[var(--soft)] px-4 py-2.5 text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none"
            rows={2}
            placeholder="输入你的回答… (Enter 发送，Shift+Enter 换行)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || isStreaming}
          />
          <button
            onClick={handleSend}
            disabled={disabled || isStreaming || !input.trim()}
            className="self-end rounded-[10px] bg-[var(--primary)] px-4 py-2.5 text-[13px] font-semibold text-white disabled:opacity-40 hover:opacity-90"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
