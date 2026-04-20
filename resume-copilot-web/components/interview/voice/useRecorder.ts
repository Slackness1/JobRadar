'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface RecorderState {
  isRecording: boolean;
  partialText: string;
  finalText: string;
  error: string;
}

interface UseRecorderOpts {
  /** Called whenever the accumulated final transcript changes. */
  onFinalizedChange?: (text: string) => void;
}

const SAMPLE_RATE = 16000;

/**
 * Captures mic audio, streams PCM 16kHz frames over WebSocket to /api/interview/asr,
 * and surfaces interim + final transcripts.
 */
export function useRecorder(opts: UseRecorderOpts = {}) {
  const [state, setState] = useState<RecorderState>({
    isRecording: false,
    partialText: '',
    finalText: '',
    error: '',
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const finalTextRef = useRef('');

  const cleanup = useCallback(() => {
    workletRef.current?.disconnect();
    workletRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
    }
    audioCtxRef.current = null;
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* ignore */ }
      wsRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try { wsRef.current.send(JSON.stringify({ action: 'stop' })); } catch { /* ignore */ }
    }
    cleanup();
    setState((s) => ({ ...s, isRecording: false }));
  }, [cleanup]);

  const start = useCallback(async () => {
    setState({ isRecording: false, partialText: '', finalText: '', error: '' });
    finalTextRef.current = '';

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx({ sampleRate: SAMPLE_RATE });
      audioCtxRef.current = audioCtx;
      await audioCtx.audioWorklet.addModule('/worklets/pcm-worklet.js');

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${window.location.host}/api/interview/asr`);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      const source = audioCtx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(audioCtx, 'pcm-worklet');
      workletRef.current = worklet;

      worklet.port.onmessage = (evt) => {
        const pcm = evt.data as ArrayBuffer;
        if (ws.readyState === WebSocket.OPEN) ws.send(pcm);
      };

      source.connect(worklet);
      // Not connecting to destination avoids local monitor feedback.

      ws.onmessage = (evt) => {
        try {
          const event = JSON.parse(evt.data);
          switch (event.type) {
            case 'started':
              setState((s) => ({ ...s, isRecording: true }));
              break;
            case 'partial':
              setState((s) => ({ ...s, partialText: event.text || '' }));
              break;
            case 'final': {
              const piece: string = event.text || '';
              finalTextRef.current = (finalTextRef.current + piece).trim();
              setState((s) => ({ ...s, partialText: '', finalText: finalTextRef.current }));
              opts.onFinalizedChange?.(finalTextRef.current);
              break;
            }
            case 'completed':
              setState((s) => ({ ...s, isRecording: false }));
              break;
            case 'error':
              setState((s) => ({ ...s, isRecording: false, error: event.message || 'ASR 出错' }));
              break;
          }
        } catch {
          // ignore malformed events
        }
      };

      ws.onerror = () => {
        setState((s) => ({ ...s, error: '语音 WebSocket 连接失败' }));
      };

      ws.onclose = () => {
        setState((s) => ({ ...s, isRecording: false }));
      };

      setState((s) => ({ ...s, isRecording: true }));
    } catch (err) {
      cleanup();
      const msg = err instanceof Error ? err.message : '麦克风启动失败';
      setState({ isRecording: false, partialText: '', finalText: '', error: msg });
    }
  }, [cleanup, opts]);

  useEffect(() => () => cleanup(), [cleanup]);

  return { ...state, start, stop } as const;
}
