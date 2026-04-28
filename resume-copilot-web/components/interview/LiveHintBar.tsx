'use client';

import { useEffect, useRef, useState } from 'react';
import { getLatestScore, type LatestScorePayload } from './api';

const POLL_INTERVAL_MS = 1500;
const HINT_VISIBLE_MS = 4000;

export function LiveHintBar({
  sessionId,
  suppressed,
}: {
  sessionId: string;
  suppressed: boolean;  // hide while AI is speaking (Border Beam visible)
}) {
  const [hint, setHint] = useState<string>('');
  const [visible, setVisible] = useState(false);
  const lastShownTurnRef = useRef<number>(-1);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const result: LatestScorePayload | null = await getLatestScore(sessionId);
        if (cancelled || !result) return;
        if (result.turn_index <= lastShownTurnRef.current) return;
        lastShownTurnRef.current = result.turn_index;
        setHint(result.hint);
        setVisible(true);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
        hideTimerRef.current = setTimeout(() => setVisible(false), HINT_VISIBLE_MS);
      } catch {
        // silent — polling errors don't surface
      }
    };
    const interval = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [sessionId]);

  if (suppressed || !visible || !hint) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: 'calc(100% + 12px)',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(201, 100, 66, 0.12)',
        border: '1px solid rgba(201, 100, 66, 0.3)',
        borderRadius: 12,
        padding: '8px 16px',
        fontSize: 13,
        color: 'var(--terracotta, #c96442)',
        whiteSpace: 'nowrap',
        animation: 'live-hint-fade 4s ease-in-out',
        pointerEvents: 'none',
      }}
    >
      {hint}
      <style jsx>{`
        @keyframes live-hint-fade {
          0% { opacity: 0; transform: translateX(-50%) translateY(-4px); }
          15% { opacity: 1; transform: translateX(-50%) translateY(0); }
          85% { opacity: 1; transform: translateX(-50%) translateY(0); }
          100% { opacity: 0; transform: translateX(-50%) translateY(-4px); }
        }
      `}</style>
    </div>
  );
}
