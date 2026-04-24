import { Suspense } from 'react';

import { PublicResumeCopilot } from '@/components/resume-copilot/public-resume-copilot';

export default function ResumeCopilotPage() {
  return (
    <Suspense fallback={<main className="p-8 text-sm text-[var(--muted)]">Loading Resume Copilot...</main>}>
      <PublicResumeCopilot />
    </Suspense>
  );
}
