'use client';

import { useEffect, useRef, useState } from 'react';
import { DeviceCard } from './MicTest';

interface Props {
  passed: boolean;
  onPassed: () => void;
}

export function CameraTest({ passed, onPassed }: Props) {
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: 'user' },
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
        setReady(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : '无法访问摄像头');
      }
    })();

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <DeviceCard
      icon="📷"
      title="摄像头"
      passed={passed}
      hint={
        error ? error :
        passed ? '画面正常' :
        ready ? '能看到自己？点下方确认' : '正在启动摄像头…'
      }
    >
      <div className="flex w-full items-center gap-3">
        <video
          ref={videoRef}
          playsInline
          muted
          className="h-[72px] w-[96px] shrink-0 rounded-[10px] border border-[var(--border)] bg-black object-cover"
        />
        {ready && !passed && (
          <button
            onClick={onPassed}
            className="rounded-[10px] bg-[var(--primary)] px-3 py-1.5 text-[12px] font-semibold text-white hover:opacity-90"
          >
            能看到自己
          </button>
        )}
      </div>
    </DeviceCard>
  );
}
