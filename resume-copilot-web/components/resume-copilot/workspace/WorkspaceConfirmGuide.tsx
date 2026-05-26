'use client';

/**
 * WorkspaceConfirmGuide — @deprecated P2 (2026-05-26)
 *
 * Originally an in-workspace overlay shown when a session landed on
 * `/resume-copilot` but `has_confirmed_profile === false`. P2 replaced it
 * with the standalone `/resume-copilot/confirm?session_id=N` page (lots more
 * room for the parse summary + track + city pickers).
 *
 * `WorkspaceShell` no longer imports this component — the redirect happens
 * via `useEffect` in the shell itself. This file is kept as a redirect-only
 * stub in case any out-of-tree caller still imports it (no known callers in
 * this repo). On mount it pushes to `/resume-copilot/confirm` so the legacy
 * `<WorkspaceConfirmGuide sessionId={...}/>` invocation still leads the
 * student to the new flow rather than rendering nothing.
 *
 * Don't add new functionality here. New work should go into:
 *   - `app/resume-copilot/confirm/page.tsx` (route entry)
 *   - `components/resume-copilot/confirm/ConfirmProfilePanel.tsx` (shell)
 *   - `components/resume-copilot/confirm/{ResumeSummaryCard,TrackBlock,CityBlock}.tsx`
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export interface WorkspaceConfirmGuideProps {
  sessionId: number;
  /** No-op in stub form (kept for prop compatibility). */
  onConfirmed?: () => void;
}

/** @deprecated P2 — use `/resume-copilot/confirm?session_id=N` instead. */
export function WorkspaceConfirmGuide({ sessionId }: WorkspaceConfirmGuideProps) {
  const router = useRouter();
  useEffect(() => {
    router.replace(`/resume-copilot/confirm?session_id=${sessionId}`);
  }, [router, sessionId]);
  // Render nothing — the new page paints immediately after the redirect.
  return null;
}
