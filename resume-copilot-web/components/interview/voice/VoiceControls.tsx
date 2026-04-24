'use client';

import { useEffect, useRef } from 'react';
import { useRecorder } from './useRecorder';

interface Props {
  disabled: boolean;
  onSubmit: (text: string) => void;
}

/**
 * Voice input panel: mic button, live transcript, submit-on-stop.
 * When the user stops recording and there's a final transcript, onSubmit is called.
 */
export function VoiceControls({ disabled, onSubmit }: Props) {
  const { isRecording, partialText, finalText, error, start, stop } = useRecorder();
  const submittedRef = useRef(false);

  // When recording stops with a non-empty final transcript, submit it.
  useEffect(() => {
    if (!isRecording && finalText && !submittedRef.current) {
      submittedRef.current = true;
      onSubmit(finalText);
    }
    if (isRecording) submittedRef.current = false;
  }, [isRecording, finalText, onSubmit]);

  const liveText = finalText + (partialText ? ` ${partialText}` : '');

  return (
    <div className="border-t border-[var(--border)] px-4 py-3">
      <div className="flex items-start gap-3">
        <button
          onClick={isRecording ? stop : start}
          disabled={disabled}
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border transition-all ${
            isRecording
              ? 'animate-pulse border-red-400 bg-red-500 text-white'
              : 'border-[var(--border)] bg-[var(--paper)] text-[var(--ink)] hover:bg-[var(--soft)]'
          } ${disabled ? 'cursor-not-allowed opacity-40' : ''}`}
          title={isRecording ? '停止录音' : '开始录音'}
        >
          {isRecording ? (
            <svg width="16" height="16" viewBox="0 0 16 16"><rect x="3" y="3" width="10" height="10" rx="1" fill="currentColor" /></svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10a7 7 0 0 1-14 0M12 17v4M8 21h8" strokeLinecap="round" />
            </svg>
          )}
        </button>

        <div className="flex-1 rounded-[12px] border border-[var(--border)] bg-[var(--soft)] px-4 py-2.5 min-h-[48px] text-[14px] text-[var(--ink)]">
          {liveText.trim() ? (
            <span>
              <span className="text-[var(--ink)]">{finalText}</span>
              {partialText && <span className="text-[var(--muted)]">{finalText ? ' ' : ''}{partialText}</span>}
            </span>
          ) : (
            <span className="text-[var(--muted)]">
              {isRecording ? '正在聆听，说完后点红色按钮发送…' : error || '点击麦克风开始语音作答'}
            </span>
          )}
        </div>
      </div>
      {error && !isRecording && (
        <p className="mt-1.5 text-[12px] text-red-500">{error}</p>
      )}
    </div>
  );
}
