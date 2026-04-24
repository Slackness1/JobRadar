'use client';

import { useEffect } from 'react';
import { useRecorder } from '../voice/useRecorder';

const EXPECTED_PHRASE = '我确认参加面试';

/** Strip punctuation / whitespace / full-width spaces, keep CJK + digits + ascii word chars. */
function normalize(text: string) {
  return text.replace(/[^一-鿿\w]/g, '');
}

function matchesPhrase(recognized: string) {
  const normExpected = normalize(EXPECTED_PHRASE);
  const normRecognized = normalize(recognized);
  return normRecognized.includes(normExpected);
}

interface Props {
  passed: boolean;
  onPassed: () => void;
}

/**
 * Mic test via full ASR: user reads a fixed phrase; we pass only when the
 * recognized transcription contains the expected phrase. This validates the
 * entire audio-in pipeline, not just microphone volume.
 */
export function MicTest({ passed, onPassed }: Props) {
  const { isRecording, partialText, finalText, error, start, stop } = useRecorder();
  const liveText = finalText + (partialText ? ` ${partialText}` : '');

  // Check for phrase match on every transcript update
  useEffect(() => {
    if (passed) return;
    const combined = finalText + partialText;
    if (combined && matchesPhrase(combined)) {
      onPassed();
      stop();
    }
  }, [finalText, partialText, passed, onPassed, stop]);

  return (
    <DeviceCard
      icon="🎤"
      title="麦克风"
      passed={passed}
      hint={
        error ? error :
        passed ? '识别成功' :
        isRecording ? `正在聆听… 请清晰朗读上方这句话` :
        '点击开始录音，朗读下方短语'
      }
    >
      <div className="flex w-full flex-col gap-2">
        <div className="flex items-center gap-2">
          {!isRecording && !passed && (
            <button
              onClick={start}
              className="rounded-[10px] bg-[var(--primary)] px-3 py-1.5 text-[12px] font-semibold text-white hover:opacity-90"
            >
              开始录音
            </button>
          )}
          {isRecording && (
            <>
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" />
              <button
                onClick={stop}
                className="rounded-[10px] border border-[var(--border)] px-3 py-1 text-[12px] text-[var(--muted)] hover:bg-[var(--soft)]"
              >
                停止
              </button>
            </>
          )}
          <code className="rounded-[6px] bg-[var(--soft)] px-2 py-0.5 text-[12px] font-semibold text-[var(--ink)]">
            {EXPECTED_PHRASE}
          </code>
        </div>
        <div className="min-h-[22px] rounded-[8px] bg-[var(--soft)] px-2.5 py-1 text-[12px]">
          {liveText.trim() ? (
            <>
              <span className="text-[var(--ink)]">{finalText}</span>
              {partialText && <span className="text-[var(--muted)]">{finalText ? ' ' : ''}{partialText}</span>}
            </>
          ) : (
            <span className="text-[var(--muted)]">（等待识别…）</span>
          )}
        </div>
      </div>
    </DeviceCard>
  );
}

function DeviceCard({
  icon, title, passed, hint, children,
}: {
  icon: string;
  title: string;
  passed: boolean;
  hint: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={`rounded-[20px] border-2 bg-[var(--paper)] p-5 transition-colors ${
      passed ? 'border-green-400' : 'border-[var(--border)]'
    }`}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[20px]">{icon}</span>
          <span className="text-[14px] font-semibold text-[var(--ink)]">{title}</span>
        </div>
        {passed && <span className="text-[13px] font-semibold text-green-600">✓ 已通过</span>}
      </div>
      <div className="mb-2 min-h-[80px] flex items-center">{children}</div>
      <p className="text-[12px] text-[var(--muted)]">{hint}</p>
    </div>
  );
}

export { DeviceCard };
