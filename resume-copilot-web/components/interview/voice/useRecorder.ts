'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { AsrSegment, AsrTranscript } from '../api';
import { encodePcmWav } from './PcmWavCapture';

export interface RecorderState {
  isRecording: boolean;
  isFinalizing: boolean;
  partialText: string;
  finalText: string;
  error: string;
}

export interface FinalizedRecording {
  text: string;
  transcript: AsrTranscript;
  audioBlob: Blob | null;
}

interface UseRecorderOpts {
  /** Called whenever the accumulated final transcript changes. */
  onFinalizedChange?: (text: string) => void;
  captureAudio?: boolean;
}

const SAMPLE_RATE = 16000;
const ASR_FINALIZE_TIMEOUT_MS = 8000;

function nowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

function appendWithoutDuplicate(base: string, addition: string): string {
  if (!base) return addition;
  if (!addition || base.endsWith(addition)) return base;
  if (addition.startsWith(base)) return addition;

  const maxOverlap = Math.min(base.length, addition.length);
  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    if (base.endsWith(addition.slice(0, overlap))) {
      return base + addition.slice(overlap);
    }
  }
  return base + addition;
}

function validTiming(event: Record<string, unknown>): { start_s: number; end_s: number } | null {
  const start = event.start_s;
  const end = event.end_s;
  if (typeof start !== 'number' || typeof end !== 'number') return null;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start) return null;
  return { start_s: start, end_s: end };
}

/**
 * Captures mic audio, streams PCM 16kHz frames over WebSocket to
 * `/api/interview/asr`, then waits for the provider's final hypothesis after
 * stop. It preserves provider timing when present and deliberately does not
 * fabricate timing when it is absent.
 */
export function useRecorder(opts: UseRecorderOpts = {}) {
  const [state, setState] = useState<RecorderState>({
    isRecording: false,
    isFinalizing: false,
    partialText: '',
    finalText: '',
    error: '',
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const finalTextRef = useRef('');
  const partialTextRef = useRef('');
  const segmentsRef = useRef<AsrSegment[]>([]);
  const pcmChunksRef = useRef<ArrayBuffer[]>([]);
  const pcmBytesRef = useRef(0);
  const captureAudioRef = useRef(Boolean(opts.captureAudio));
  const captureSampleRateRef = useRef(SAMPLE_RATE);
  const captureStartedAtRef = useRef<number | null>(null);
  const captureStoppedAtRef = useRef<number | null>(null);
  const isFinalizingRef = useRef(false);
  const finalizeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopResolveRef = useRef<((result: FinalizedRecording | null) => void) | null>(null);
  const stopPromiseRef = useRef<Promise<FinalizedRecording | null> | null>(null);

  useEffect(() => { captureAudioRef.current = Boolean(opts.captureAudio); }, [opts.captureAudio]);

  const stopCapture = useCallback(() => {
    workletRef.current?.disconnect();
    workletRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
    }
    audioCtxRef.current = null;
  }, []);

  const closeWebSocket = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws) {
      try { ws.close(); } catch { /* ignore */ }
    }
  }, []);

  const clearFinalizeTimer = useCallback(() => {
    if (finalizeTimerRef.current) {
      clearTimeout(finalizeTimerRef.current);
      finalizeTimerRef.current = null;
    }
  }, []);

  const captureDurationS = useCallback(() => {
    const startedAt = captureStartedAtRef.current;
    if (startedAt === null) return 0;
    const endedAt = captureStoppedAtRef.current ?? nowMs();
    return Math.max(0, (endedAt - startedAt) / 1000);
  }, []);

  const buildFinalizedRecording = useCallback((): FinalizedRecording | null => {
    const finalText = finalTextRef.current.trim();
    const partialText = partialTextRef.current.trim();
    const text = appendWithoutDuplicate(finalText, partialText).trim();
    if (!text) return null;

    const segments = [...segmentsRef.current];
    const normalizedFinal = finalText.replace(/\s+/g, '');
    const normalizedAll = text.replace(/\s+/g, '');

    // Preserve a delayed/missing final hypothesis for answer submission. Do not
    // attach invented timing; Phase 0 metrics will report timing as unavailable.
    if (!segments.length) {
      segments.push({ text });
    } else if (normalizedFinal !== normalizedAll) {
      const suffix = text.slice(finalText.length).trim();
      if (suffix) segments.push({ text: suffix });
    }

    return {
      text,
      transcript: {
        audio_duration_s: captureDurationS(),
        segments,
      },
      audioBlob: captureAudioRef.current
        ? encodePcmWav(pcmChunksRef.current, captureSampleRateRef.current)
        : null,
    };
  }, [captureDurationS]);

  const finishFinalization = useCallback((error = '') => {
    clearFinalizeTimer();
    isFinalizingRef.current = false;
    const result = buildFinalizedRecording();
    const resolve = stopResolveRef.current;
    stopResolveRef.current = null;
    stopPromiseRef.current = null;

    setState((current) => ({
      ...current,
      isRecording: false,
      isFinalizing: false,
      partialText: '',
      finalText: result?.text || current.finalText,
      error: error || current.error,
    }));
    closeWebSocket();
    resolve?.(result);
  }, [buildFinalizedRecording, clearFinalizeTimer, closeWebSocket]);

  const cleanup = useCallback(() => {
    clearFinalizeTimer();
    isFinalizingRef.current = false;
    stopCapture();
    closeWebSocket();
    stopResolveRef.current?.(null);
    stopResolveRef.current = null;
    stopPromiseRef.current = null;
  }, [clearFinalizeTimer, closeWebSocket, stopCapture]);

  const stop = useCallback((): Promise<FinalizedRecording | null> => {
    if (stopPromiseRef.current) return stopPromiseRef.current;

    const ws = wsRef.current;
    if (!ws) {
      stopCapture();
      setState((current) => ({ ...current, isRecording: false, isFinalizing: false }));
      return Promise.resolve(buildFinalizedRecording());
    }

    // Stop capture first, but keep the socket alive. DashScope finalizes the
    // final sentence only after it receives this stop command.
    captureStoppedAtRef.current = nowMs();
    stopCapture();
    isFinalizingRef.current = true;
    setState((current) => ({ ...current, isRecording: false, isFinalizing: true }));

    let resolveStop: (result: FinalizedRecording | null) => void = () => {};
    const stopPromise = new Promise<FinalizedRecording | null>((resolve) => {
      resolveStop = resolve;
    });
    stopResolveRef.current = resolveStop;
    stopPromiseRef.current = stopPromise;

    if (ws.readyState !== WebSocket.OPEN) {
      finishFinalization('语音连接已关闭，已提交已识别内容。');
      return stopPromise;
    }

    try {
      ws.send(JSON.stringify({ action: 'stop' }));
    } catch {
      finishFinalization('语音识别停止失败，已提交已识别内容。');
      return stopPromise;
    }

    finalizeTimerRef.current = setTimeout(() => {
      finishFinalization('语音识别收尾超时，已提交已识别内容。');
    }, ASR_FINALIZE_TIMEOUT_MS);
    return stopPromise;
  }, [buildFinalizedRecording, finishFinalization, stopCapture]);

  const start = useCallback(async () => {
    setState({ isRecording: false, isFinalizing: false, partialText: '', finalText: '', error: '' });
    finalTextRef.current = '';
    partialTextRef.current = '';
    segmentsRef.current = [];
    pcmChunksRef.current = [];
    pcmBytesRef.current = 0;
    captureStartedAtRef.current = null;
    captureStoppedAtRef.current = null;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx({ sampleRate: SAMPLE_RATE });
      audioCtxRef.current = audioCtx;
      captureSampleRateRef.current = audioCtx.sampleRate;
      await audioCtx.audioWorklet.addModule('/worklets/pcm-worklet.js');

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${window.location.host}/api/interview/asr`);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      const source = audioCtx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(audioCtx, 'pcm-worklet');
      workletRef.current = worklet;
      captureStartedAtRef.current = nowMs();

      worklet.port.onmessage = (evt) => {
        const pcm = evt.data as ArrayBuffer;
        if (captureAudioRef.current && pcmBytesRef.current + pcm.byteLength <= 12 * 1024 * 1024) {
          pcmChunksRef.current.push(pcm.slice(0));
          pcmBytesRef.current += pcm.byteLength;
        }
        if (ws.readyState === WebSocket.OPEN) ws.send(pcm);
      };

      source.connect(worklet);

      ws.onmessage = (evt) => {
        try {
          const event = JSON.parse(evt.data) as Record<string, unknown>;
          switch (event.type) {
            case 'started':
              setState((current) => ({ ...current, isRecording: true }));
              break;
            case 'partial': {
              const text = typeof event.text === 'string' ? event.text : '';
              partialTextRef.current = text;
              setState((current) => ({ ...current, partialText: text }));
              break;
            }
            case 'final': {
              const piece = typeof event.text === 'string' ? event.text : '';
              const previous = finalTextRef.current;
              const nextText = appendWithoutDuplicate(previous, piece).trim();
              if (piece && nextText !== previous) {
                const suffix = nextText.slice(previous.length).trim() || piece;
                const timing = validTiming(event);
                segmentsRef.current.push(timing ? { ...timing, text: suffix } : { text: suffix });
              }
              finalTextRef.current = nextText;
              partialTextRef.current = '';
              setState((current) => ({ ...current, partialText: '', finalText: nextText }));
              opts.onFinalizedChange?.(nextText);
              break;
            }
            case 'completed':
              finishFinalization();
              break;
            case 'error': {
              const message = typeof event.message === 'string' ? event.message : 'ASR 出错';
              if (isFinalizingRef.current) finishFinalization(message);
              else setState((current) => ({ ...current, isRecording: false, error: message }));
              break;
            }
          }
        } catch {
          // Ignore malformed events; a later completed/close event resolves stop().
        }
      };

      ws.onerror = () => {
        if (isFinalizingRef.current) finishFinalization('语音 WebSocket 连接失败，已提交已识别内容。');
        else setState((current) => ({ ...current, error: '语音 WebSocket 连接失败' }));
      };

      ws.onclose = () => {
        if (wsRef.current === ws) wsRef.current = null;
        if (isFinalizingRef.current) finishFinalization('语音连接已关闭，已提交已识别内容。');
        else setState((current) => ({ ...current, isRecording: false }));
      };

      setState((current) => ({ ...current, isRecording: true }));
    } catch (err) {
      cleanup();
      const message = err instanceof Error ? err.message : '麦克风启动失败';
      setState({ isRecording: false, isFinalizing: false, partialText: '', finalText: '', error: message });
    }
  }, [cleanup, finishFinalization, opts]);

  useEffect(() => () => cleanup(), [cleanup]);

  return { ...state, start, stop } as const;
}
