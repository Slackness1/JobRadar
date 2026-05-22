'use client';

/**
 * ResizeHandle — vertical drag bar that resizes a flex/grid column.
 *
 * Sits *between* two panes in the three-column workspace grid. On mousedown,
 * captures the starting X + the current column width, then on mousemove
 * computes the new width = startWidth + delta (delta sign chooses by
 * `side`: 'left' resizes the column to the LEFT of the handle, 'right'
 * resizes the column to the RIGHT — both clamped to [minWidth, maxWidth]).
 *
 * The actual width state lives in the parent so the change can be
 * persisted to localStorage and applied to the grid template inline.
 */

import { useCallback } from 'react';

export interface ResizeHandleProps {
  /** Current column width (px), used as the baseline for drag delta. */
  width: number;
  /** Called every mousemove with the new clamped width. */
  onResize: (newWidth: number) => void;
  /** Whether this handle resizes the column on its LEFT or RIGHT. */
  side: 'left' | 'right';
  /** Lower bound for the resized column. */
  minWidth?: number;
  /** Upper bound for the resized column. */
  maxWidth?: number;
  /** Visible label / a11y. */
  ariaLabel?: string;
}

export function ResizeHandle({
  width,
  onResize,
  side,
  minWidth = 200,
  maxWidth = 640,
  ariaLabel = '拖动调整宽度',
}: ResizeHandleProps) {
  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = width;
      const direction = side === 'left' ? 1 : -1;

      const onMove = (ev: MouseEvent) => {
        const dx = (ev.clientX - startX) * direction;
        const next = Math.max(minWidth, Math.min(maxWidth, startWidth + dx));
        onResize(next);
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [width, side, minWidth, maxWidth, onResize],
  );

  // Keyboard fallback — arrow keys nudge by 16px so a11y users can resize too.
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const step = 16 * (side === 'left' ? 1 : -1);
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        onResize(Math.max(minWidth, Math.min(maxWidth, width - step)));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        onResize(Math.max(minWidth, Math.min(maxWidth, width + step)));
      }
    },
    [width, side, minWidth, maxWidth, onResize],
  );

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label={ariaLabel}
      aria-valuenow={width}
      aria-valuemin={minWidth}
      aria-valuemax={maxWidth}
      className="workspace-hifi__resize-handle"
      onMouseDown={handleMouseDown}
      onKeyDown={handleKeyDown}
    >
      <span className="workspace-hifi__resize-handle-grip" aria-hidden />
    </div>
  );
}
