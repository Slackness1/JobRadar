'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';

interface Position {
  left: number;
  top: number;
}

interface Options {
  /** localStorage key for persisting the position. */
  storageKey: string;
  /** Initial distance from the right edge of the viewport. */
  defaultRight: number;
  /** Initial distance from the top edge of the viewport. */
  defaultTop: number;
  /** Panel width — used to derive default left and to clamp within viewport. */
  width: number;
  /** Panel height — used to clamp within viewport. */
  height: number;
}

/**
 * Makes a fixed-positioned overlay (avatar/self-view) draggable and remembers its
 * position across reloads. Clicks on `<button>` descendants are ignored so the
 * close button still works.
 */
export function useDraggable({ storageKey, defaultRight, defaultTop, width, height }: Options) {
  const [pos, setPos] = useState<Position | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null);

  // Reading localStorage and window size can't happen during render (no window on SSR).
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const saved = (() => {
      try {
        const raw = localStorage.getItem(storageKey);
        if (!raw) return null;
        const p = JSON.parse(raw) as Position;
        if (typeof p.left !== 'number' || typeof p.top !== 'number') return null;
        return clampToViewport(p, width, height);
      } catch {
        return null;
      }
    })();
    if (saved) {
      setPos(saved);
      return;
    }
    const left = Math.max(8, window.innerWidth - defaultRight - width);
    setPos({ left, top: defaultTop });
  }, [storageKey, defaultRight, defaultTop, width, height]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if ((e.target as HTMLElement).closest('button')) return;
      if (!pos) return;
      dragStart.current = { x: e.clientX, y: e.clientY, left: pos.left, top: pos.top };
      setIsDragging(true);
      try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* ignore */ }
      e.preventDefault();
    },
    [pos],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      const s = dragStart.current;
      if (!s) return;
      const next = clampToViewport(
        { left: s.left + (e.clientX - s.x), top: s.top + (e.clientY - s.y) },
        width,
        height,
      );
      setPos(next);
    },
    [width, height],
  );

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (!dragStart.current) return;
      dragStart.current = null;
      setIsDragging(false);
      try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* ignore */ }
      if (pos) {
        try { localStorage.setItem(storageKey, JSON.stringify(pos)); } catch { /* ignore */ }
      }
    },
    [storageKey, pos],
  );

  const style: React.CSSProperties = pos
    ? {
        position: 'fixed',
        left: `${pos.left}px`,
        top: `${pos.top}px`,
        right: 'auto',
        bottom: 'auto',
        touchAction: 'none',
        cursor: isDragging ? 'grabbing' : 'grab',
      }
    : { visibility: 'hidden' };

  return {
    style,
    isDragging,
    dragHandlers: { onPointerDown, onPointerMove, onPointerUp },
  };
}

function clampToViewport(p: Position, w: number, h: number): Position {
  const maxLeft = Math.max(0, window.innerWidth - w);
  const maxTop = Math.max(0, window.innerHeight - h);
  return {
    left: Math.min(maxLeft, Math.max(0, p.left)),
    top: Math.min(maxTop, Math.max(0, p.top)),
  };
}
