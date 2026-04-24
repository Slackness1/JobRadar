'use client';

import { useState } from 'react';
import { useDraggable } from '@/lib/useDraggable';

const PANEL_WIDTH = 180;
const PANEL_HEIGHT = 230;

interface Props {
  /** True while TTS audio is playing — drives the "speaking" pulse. */
  speaking: boolean;
  /** True while the LLM is generating — drives the Border Beam "thinking" effect. */
  thinking?: boolean;
  /** Optional status label shown under the portrait. */
  status?: string;
}

/**
 * Draggable interviewer portrait.
 * - idle         → static, soft purple hairline border
 * - `thinking`   → Border Beam (conic gradient sweeping the frame)
 * - `speaking`   → solid purple pulse ring
 */
export function AvatarView({ speaking, thinking = false, status }: Props) {
  const [hidden, setHidden] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const { style, dragHandlers, isDragging } = useDraggable({
    storageKey: 'interview.avatar.pos',
    defaultRight: 16,
    defaultTop: 80,
    width: PANEL_WIDTH,
    height: PANEL_HEIGHT + 24, // +24 leaves room for the status label below
  });

  if (hidden) return null;

  const effectiveStatus = status || (thinking ? '思考中' : speaking ? '说话中' : '聆听中');

  return (
    <div
      style={style}
      className={`z-40 select-none ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
      {...dragHandlers}
    >
      <div className="relative" style={{ width: PANEL_WIDTH }}>
        <div
          className="relative rounded-[18px] bg-[var(--soft)] shadow-lg transition-shadow duration-500"
          style={{
            overflow: 'hidden',
            // Speaking ring lives ON the frame itself so it always hugs the image edge perfectly.
            boxShadow: speaking
              ? '0 0 0 3px var(--primary), 0 0 26px 6px rgba(79, 70, 229, 0.45), 0 8px 18px -4px rgba(0,0,0,0.18)'
              : '0 8px 18px -4px rgba(0,0,0,0.18)',
            animation: speaking ? 'avatar-pulse 1.6s ease-in-out infinite' : 'none',
          }}
        >
          {/* Border Beam — wraps the portrait itself, drawn on top via z-index:2 */}
          {thinking && <div className="border-beam" style={{ borderRadius: 18 }} />}
          {imgFailed ? (
            <div
              className="flex flex-col items-center justify-center gap-3 bg-gradient-to-b from-[#f5f3ff] to-[#ede9fe]"
              style={{ width: PANEL_WIDTH, height: PANEL_HEIGHT }}
              aria-label="AI 面试官占位图"
            >
              <svg width="76" height="76" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="8" r="4" fill="var(--primary)" opacity="0.85" />
                <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" fill="var(--primary)" opacity="0.85" />
              </svg>
              <div className="text-center">
                <div className="text-[13px] font-semibold text-[var(--ink)]">AI 面试官</div>
                <div className="mt-1 text-[11px] text-[var(--muted)]">
                  放一张头像到<br />
                  <code className="text-[10px]">public/interviewer.png</code>
                </div>
              </div>
            </div>
          ) : (
            <img
              src="/interviewer.png"
              alt="AI 面试官"
              draggable={false}
              className="block object-cover"
              style={{ width: PANEL_WIDTH, height: PANEL_HEIGHT }}
              onError={() => setImgFailed(true)}
            />
          )}
          <button
            onClick={() => setHidden(true)}
            className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-[10px] text-white hover:bg-black/80"
            title="隐藏面试官"
          >
            ×
          </button>
        </div>

        {/* Status label — fixed width matching the image, centered text */}
        <div
          className="mt-1 flex items-center justify-center gap-1.5 text-[11px] text-[var(--muted)]"
          style={{ width: PANEL_WIDTH }}
        >
          <span
            className={`inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full ${
              speaking || thinking ? 'bg-[var(--primary)]' : 'bg-[var(--muted)]'
            }`}
            style={{
              animation: speaking || thinking ? 'avatar-blink 0.9s ease-in-out infinite' : 'none',
            }}
          />
          <span className="whitespace-nowrap">AI 面试官 · {effectiveStatus}</span>
        </div>
      </div>

      <style jsx>{`
        @keyframes avatar-pulse {
          0%, 100% {
            box-shadow:
              0 0 0 3px var(--primary),
              0 0 22px 6px rgba(79, 70, 229, 0.40),
              0 8px 18px -4px rgba(0, 0, 0, 0.18);
          }
          50% {
            box-shadow:
              0 0 0 4px var(--primary),
              0 0 32px 10px rgba(79, 70, 229, 0.55),
              0 8px 18px -4px rgba(0, 0, 0, 0.18);
          }
        }
        @keyframes avatar-blink {
          0%, 100% { opacity: 0.3; }
          50%      { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
