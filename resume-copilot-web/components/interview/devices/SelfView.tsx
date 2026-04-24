'use client';

import { useEffect, useRef, useState } from 'react';
import { useDraggable } from '@/lib/useDraggable';

const PANEL_WIDTH = 144;
const PANEL_HEIGHT = 108;

/**
 * Fixed-position self-view webcam with drag support.
 * Fails silently if camera permission denied — the interview should still be usable.
 */
export function SelfView() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [hidden, setHidden] = useState(false);
  const { style, dragHandlers, isDragging } = useDraggable({
    storageKey: 'interview.selfview.pos',
    defaultRight: 16,
    defaultTop: typeof window !== 'undefined' ? window.innerHeight - PANEL_HEIGHT - 100 : 500,
    width: PANEL_WIDTH,
    height: PANEL_HEIGHT,
  });

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
      } catch {
        // Camera denied or unavailable — silently skip self-view.
      }
    })();

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  if (hidden) return null;

  return (
    <div
      style={style}
      className={`z-40 select-none ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
      {...dragHandlers}
    >
      <div className="relative overflow-hidden rounded-[14px] border border-[var(--border)] bg-black shadow-lg">
        <video
          ref={videoRef}
          playsInline
          muted
          className={`object-cover transition-opacity ${ready ? 'opacity-100' : 'opacity-0'}`}
          style={{ width: PANEL_WIDTH, height: PANEL_HEIGHT, transform: 'scaleX(-1)' }}
        />
        <button
          onClick={() => {
            streamRef.current?.getTracks().forEach((t) => t.stop());
            setHidden(true);
          }}
          className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-[10px] text-white hover:bg-black/80"
          title="关闭自视图"
        >
          ×
        </button>
      </div>
    </div>
  );
}
