'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface TTSPlayerState {
  isPlaying: boolean;
  error: string;
}

/**
 * Fetches MP3 bytes from /api/interview/tts and plays via <audio>.
 * Supports cancellation (stop) and a simple `speak(text)` API.
 */
export function useTTSPlayer() {
  const [state, setState] = useState<TTSPlayerState>({ isPlaying: false, error: '' });
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const cleanup = useCallback(() => {
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
    setState({ isPlaying: false, error: '' });
  }, [cleanup]);

  const speak = useCallback(async (text: string) => {
    cleanup();
    if (!text.trim()) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setState({ isPlaying: true, error: '' });

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

      audio.onended = () => {
        setState({ isPlaying: false, error: '' });
      };
      audio.onerror = () => {
        setState({ isPlaying: false, error: '音频播放失败' });
      };

      await audio.play();
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : '语音合成失败';
      setState({ isPlaying: false, error: msg });
    }
  }, [cleanup]);

  useEffect(() => () => cleanup(), [cleanup]);

  return { ...state, speak, stop } as const;
}
