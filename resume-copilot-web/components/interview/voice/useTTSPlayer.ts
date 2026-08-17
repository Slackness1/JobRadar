'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { PcmStreamPlayer } from './PcmStreamPlayer';

export interface TTSPlaybackMetrics {
  requestToHeadersMs: number | null;
  requestToFirstByteMs: number | null;
  requestToFirstAudioMs: number | null;
  streamDownloadMs: number | null;
  playbackCompleteMs: number | null;
  cancelled: boolean;
  fallbackUsed: boolean;
}

export interface TTSPlayerState {
  isPlaying: boolean;
  error: string;
  progress: number;
  metrics: TTSPlaybackMetrics;
}

const EMPTY_METRICS: TTSPlaybackMetrics = {
  requestToHeadersMs: null,
  requestToFirstByteMs: null,
  requestToFirstAudioMs: null,
  streamDownloadMs: null,
  playbackCompleteMs: null,
  cancelled: false,
  fallbackUsed: false,
};

class PcmStreamingUnavailable extends Error {}

function nowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

export function useTTSPlayer() {
  const [state, setState] = useState<TTSPlayerState>({
    isPlaying: false,
    error: '',
    progress: 0,
    metrics: EMPTY_METRICS,
  });
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const pcmPlayerRef = useRef<PcmStreamPlayer | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const rafRef = useRef<number | null>(null);
  const operationRef = useRef(0);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    pcmPlayerRef.current?.stop();
    pcmPlayerRef.current = null;
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
    operationRef.current += 1;
    cleanup();
    setState((current) => ({
      ...current,
      isPlaying: false,
      error: '',
      progress: current.isPlaying ? 1 : current.progress,
      metrics: { ...current.metrics, cancelled: current.isPlaying },
    }));
  }, [cleanup]);

  const speak = useCallback(async (text: string) => {
    operationRef.current += 1;
    const operation = operationRef.current;
    cleanup();
    if (!text.trim()) return;

    const controller = new AbortController();
    abortRef.current = controller;
    const requestStartedAt = nowMs();
    setState({ isPlaying: true, error: '', progress: 0, metrics: EMPTY_METRICS });

    const isCurrent = () => (
      operationRef.current === operation && !controller.signal.aborted
    );
    const updateMetrics = (patch: Partial<TTSPlaybackMetrics>) => {
      if (!isCurrent()) return;
      setState((current) => ({
        ...current,
        metrics: { ...current.metrics, ...patch },
      }));
    };

    const startProgressLoop = (player: PcmStreamPlayer) => {
      const tick = () => {
        if (!isCurrent() || pcmPlayerRef.current !== player) return;
        setState((current) => ({
          ...current,
          progress: Math.max(current.progress, player.progress),
        }));
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    };

    const playPcmStream = async () => {
      if (typeof window === 'undefined' || typeof AudioContext === 'undefined') {
        throw new PcmStreamingUnavailable('Web Audio is unavailable');
      }
      const response = await fetch('/api/interview/tts?format=pcm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      updateMetrics({ requestToHeadersMs: nowMs() - requestStartedAt });
      if (!response.ok) {
        throw new PcmStreamingUnavailable(
          await response.text().catch(() => `PCM TTS failed: ${response.status}`),
        );
      }
      if (!response.body || !response.headers.get('content-type')?.startsWith('audio/pcm')) {
        throw new PcmStreamingUnavailable('PCM streaming response is unavailable');
      }

      const sampleRate = Number(response.headers.get('x-audio-sample-rate'));
      if (!Number.isFinite(sampleRate) || sampleRate <= 0) {
        throw new PcmStreamingUnavailable('PCM sample rate is missing');
      }

      const player = new PcmStreamPlayer({
        sampleRate,
        onFirstAudioScheduled: (delayMs) => {
          updateMetrics({ requestToFirstAudioMs: nowMs() - requestStartedAt + delayMs });
        },
      });
      pcmPlayerRef.current = player;
      await player.prepare();
      startProgressLoop(player);

      const reader = response.body.getReader();
      let receivedFirstByte = false;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (!isCurrent()) return;
          if (!receivedFirstByte && value.byteLength > 0) {
            receivedFirstByte = true;
            updateMetrics({ requestToFirstByteMs: nowMs() - requestStartedAt });
          }
          player.append(value);
        }
      } finally {
        reader.releaseLock();
      }

      updateMetrics({ streamDownloadMs: nowMs() - requestStartedAt });
      await player.finish();
      await player.close();
      if (pcmPlayerRef.current === player) pcmPlayerRef.current = null;
    };

    const playBufferedFallback = async () => {
      updateMetrics({ fallbackUsed: true });
      const response = await fetch('/api/interview/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      updateMetrics({ requestToHeadersMs: nowMs() - requestStartedAt });
      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        throw new Error(`TTS 失败: ${response.status} ${detail}`);
      }
      const blob = await response.blob();
      if (!isCurrent()) return;

      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.ontimeupdate = () => {
        if (!Number.isFinite(audio.duration) || audio.duration <= 0) return;
        setState((current) => ({
          ...current,
          progress: Math.max(current.progress, audio.currentTime / audio.duration),
        }));
      };
      await audio.play();
      updateMetrics({ requestToFirstAudioMs: nowMs() - requestStartedAt });
      await new Promise<void>((resolve, reject) => {
        audio.onended = () => resolve();
        audio.onerror = () => reject(new Error('音频播放失败'));
      });
    };

    try {
      try {
        await playPcmStream();
      } catch (error) {
        if (isAbortError(error) || !isCurrent()) return;
        if (!(error instanceof PcmStreamingUnavailable)) throw error;
        pcmPlayerRef.current?.stop();
        pcmPlayerRef.current = null;
        await playBufferedFallback();
      }
      if (!isCurrent()) return;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      abortRef.current = null;
      setState((current) => ({
        ...current,
        isPlaying: false,
        progress: 1,
        metrics: {
          ...current.metrics,
          playbackCompleteMs: nowMs() - requestStartedAt,
        },
      }));
    } catch (error) {
      if (isAbortError(error) || !isCurrent()) return;
      const message = error instanceof Error ? error.message : '语音合成失败';
      cleanup();
      setState((current) => ({
        ...current,
        isPlaying: false,
        error: message,
        progress: 0,
      }));
    }
  }, [cleanup]);

  useEffect(() => () => {
    operationRef.current += 1;
    cleanup();
  }, [cleanup]);

  return { ...state, speak, stop } as const;
}
