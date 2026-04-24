'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface TTSPlayerState {
  isPlaying: boolean;
  error: string;
  progress: number; // 0 → 1, advances with audio.currentTime
}

/**
 * Fetches MP3 bytes from /api/interview/tts and plays via <audio>.
 * Supports cancellation (stop) and a simple `speak(text)` API.
 */
export function useTTSPlayer() {
  const [state, setState] = useState<TTSPlayerState>({ isPlaying: false, error: '', progress: 0 });
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const rafRef = useRef<number | null>(null);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const stop = useCallback(() => {
    cleanup();
    setState({ isPlaying: false, error: '', progress: 0 });
  }, [cleanup]);

  const speak = useCallback(async (text: string) => {
    cleanup();
    if (!text.trim()) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setState({ isPlaying: true, error: '', progress: 0 });

    try {
      const res = await fetch('/api/interview/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(`TTS 失败: ${res.status} ${detail}`);
      }
      const blob = await res.blob();
      if (controller.signal.aborted) return;

      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;

      // Tick progress smoothly via rAF (ontimeupdate fires only ~4x/sec).
      const tick = () => {
        if (!audioRef.current || audioRef.current !== audio) return;
        const duration = audio.duration;
        if (duration > 0 && isFinite(duration)) {
          const p = Math.min(1, Math.max(0, audio.currentTime / duration));
          setState((s) => (s.progress === p ? s : { ...s, progress: p }));
        }
        rafRef.current = requestAnimationFrame(tick);
      };

      audio.onplay = () => {
        rafRef.current = requestAnimationFrame(tick);
      };
      audio.onended = () => {
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
        setState({ isPlaying: false, error: '', progress: 1 });
      };
      audio.onerror = () => {
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
        setState({ isPlaying: false, error: '音频播放失败', progress: 0 });
      };

      await audio.play();
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : '语音合成失败';
      setState({ isPlaying: false, error: msg, progress: 0 });
    }
  }, [cleanup]);

  useEffect(() => () => cleanup(), [cleanup]);

  return { ...state, speak, stop } as const;
}
