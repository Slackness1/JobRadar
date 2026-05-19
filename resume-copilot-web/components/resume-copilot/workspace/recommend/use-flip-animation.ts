'use client';

/**
 * use-flip-animation — 纯 FLIP (First / Last / Invert / Play) 实现 for the
 * 推荐栏 1.5s 柔和重排 (E-4).
 *
 * Why FLIP not framer-motion: `resume-copilot-web/package.json` 没装
 * framer-motion (检查时间 2026-05-20),为了避免 FE-2 引入 50KB+ bundle
 * 用纯 FLIP — 用 `getBoundingClientRect()` 拍前后位置,inverse-transform
 * 后 transition 到 identity。所有动画都走 GPU `transform`,不重排 paint。
 *
 * Usage:
 *
 * ```tsx
 * const flip = useFlipAnimation<string>();
 * // wrap each animated child:
 * <div ref={flip.register('job-123')} key="job-123" />
 * // before any state change that reorders/removes, call snapshot:
 * flip.snapshot();
 * // then setState — `useLayoutEffect` inside picks up the diff and animates.
 * ```
 *
 * Notes:
 *   - 只动画 enter / move / exit 中的 **move + exit**(enter 用 CSS fade-in)。
 *   - 1.5s `ease-out` per 设计 doc §2 E-4 / D-5。
 *   - exit 动画是 fade + slight slide-up,留 1.5s 让 reorder 占位回收。
 *   - 用 `transform` + `opacity`,不会触发 layout thrash。
 */

import { useCallback, useLayoutEffect, useRef } from 'react';

const FLIP_DURATION_MS = 1500;
const FLIP_EASING = 'cubic-bezier(0.22, 1, 0.36, 1)'; // ease-out-quint

interface FlipRect {
  top: number;
  left: number;
}

export interface FlipAnimationHandle<K extends string | number> {
  /** Pass to each animated element's `ref` prop, keyed by id. */
  register: (id: K) => (el: HTMLElement | null) => void;
  /** Call **before** the state change that causes reorder / removal. */
  snapshot: () => void;
}

export function useFlipAnimation<K extends string | number>(): FlipAnimationHandle<K> {
  // current live element refs, keyed by id
  const refsRef = useRef<Map<K, HTMLElement>>(new Map());
  // last-seen positions captured by snapshot()
  const prevRectsRef = useRef<Map<K, FlipRect>>(new Map());
  // whether the next layout effect should run a FLIP pass
  const pendingRef = useRef<boolean>(false);

  const register = useCallback(
    (id: K) => (el: HTMLElement | null) => {
      if (el) {
        refsRef.current.set(id, el);
      } else {
        refsRef.current.delete(id);
      }
    },
    [],
  );

  const snapshot = useCallback(() => {
    const map = new Map<K, FlipRect>();
    refsRef.current.forEach((el, id) => {
      const r = el.getBoundingClientRect();
      map.set(id, { top: r.top, left: r.left });
    });
    prevRectsRef.current = map;
    pendingRef.current = true;
  }, []);

  useLayoutEffect(() => {
    if (!pendingRef.current) return;
    pendingRef.current = false;
    const prev = prevRectsRef.current;
    if (prev.size === 0) return;

    refsRef.current.forEach((el, id) => {
      const before = prev.get(id);
      if (!before) return; // newly entered — let CSS handle fade-in
      const after = el.getBoundingClientRect();
      const dx = before.left - after.left;
      const dy = before.top - after.top;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;

      // Invert
      el.style.transition = 'none';
      el.style.transform = `translate(${dx}px, ${dy}px)`;
      // Force reflow so the browser commits the inverted position
      el.getBoundingClientRect();
      // Play
      el.style.transition = `transform ${FLIP_DURATION_MS}ms ${FLIP_EASING}`;
      el.style.transform = '';
      const clear = () => {
        el.style.transition = '';
        el.style.transform = '';
        el.removeEventListener('transitionend', clear);
      };
      el.addEventListener('transitionend', clear);
    });
  });

  return { register, snapshot };
}
