import { Suspense } from 'react';

import { SessionsPanel } from '@/components/resume-copilot/sessions/SessionsPanel';

/**
 * `/resume-copilot/sessions` — landing page after login (P0a, 2026-05-26).
 *
 * Lists the user's resume sessions in a 3-column card grid + upload card. Click
 * a card → `/resume-copilot?sessionId=N` (workspace). The upload card → `/upload`.
 *
 * Sessions page sits inside `.hf` scope (terracotta/parchment design system),
 * styles scoped to `.rc-sessions`. Doesn't leak to `/`, `/upload`, or
 * `/interview/*`.
 */
export default function ResumeCopilotSessionsPage() {
  return (
    <Suspense
      fallback={
        <main className="p-8 text-sm" style={{ color: 'var(--ink-soft)' }}>
          Loading sessions…
        </main>
      }
    >
      <SessionsPanel />
    </Suspense>
  );
}
