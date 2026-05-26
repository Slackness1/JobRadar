'use client';

import { Suspense, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { ConfirmProfilePanel } from '@/components/resume-copilot/confirm/ConfirmProfilePanel';

/**
 * `/resume-copilot/confirm` — P2 standalone gateway page (2026-05-26).
 *
 * Path between `/upload` (parse complete) and `/resume-copilot` (workspace).
 * Replaces the in-workspace `WorkspaceConfirmGuide` overlay — same data flow,
 * but full-page so the student has room to read summary + pick track + pick
 * cities without crammed overlay.
 *
 * URL param: `session_id` (legacy compat: also accepts `sessionId`).
 * Suspense boundary wraps `useSearchParams()` per Next.js 16 App Router rules.
 */
export default function ResumeCopilotConfirmPage() {
  return (
    <Suspense
      fallback={
        <main className="p-8 text-sm" style={{ color: 'var(--ink-soft)' }}>
          Loading confirm…
        </main>
      }
    >
      <ConfirmPageInner />
    </Suspense>
  );
}

function ConfirmPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = useMemo(() => {
    const raw =
      searchParams.get('session_id') ?? searchParams.get('sessionId');
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [searchParams]);

  if (sessionId === null) {
    // Hard-redirect users who hit /confirm without a session — go to sessions
    // list so they can either pick an existing session or upload a new one.
    if (typeof window !== 'undefined') {
      router.replace('/resume-copilot/sessions');
    }
    return (
      <main className="p-8 text-sm" style={{ color: 'var(--ink-soft)' }}>
        缺少 session_id, 正在跳转回会话列表…
      </main>
    );
  }

  return <ConfirmProfilePanel sessionId={sessionId} />;
}
