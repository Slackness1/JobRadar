'use client';

import { useState } from 'react';
import { DeviceCard } from './MicTest';
import { useTTSPlayer } from '../voice/useTTSPlayer';

const TEST_TEXT = '你好，这是扬声器测试。如果能听到我的声音，请点击下方按钮确认。';

interface Props {
  passed: boolean;
  onPassed: () => void;
}

export function SpeakerTest({ passed, onPassed }: Props) {
  const tts = useTTSPlayer();
  const [hasPlayed, setHasPlayed] = useState(false);

  function handlePlay() {
    tts.speak(TEST_TEXT);
    setHasPlayed(true);
  }

  return (
    <DeviceCard
      icon="🔊"
      title="扬声器"
      passed={passed}
      hint={
        tts.error ? tts.error :
        passed ? '听到测试音' :
        !hasPlayed ? '点击播放测试音' :
        tts.isPlaying ? '播放中…' :
        '听到了？点确认'
      }
    >
      <div className="flex w-full items-center gap-3">
        <button
          onClick={handlePlay}
          disabled={tts.isPlaying}
          className="flex h-12 w-12 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--paper)] hover:bg-[var(--soft)] disabled:opacity-40"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" className="text-[var(--primary)]">
            <path d="M8 5v14l11-7z" />
          </svg>
        </button>
        {hasPlayed && !tts.isPlaying && !passed && (
          <button
            onClick={onPassed}
            className="rounded-[10px] bg-[var(--primary)] px-3 py-1.5 text-[12px] font-semibold text-white hover:opacity-90"
          >
            听到了
          </button>
        )}
        {tts.isPlaying && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--primary)]" />
            <span className="text-[12px] text-[var(--muted)]">播放中</span>
          </div>
        )}
      </div>
    </DeviceCard>
  );
}
