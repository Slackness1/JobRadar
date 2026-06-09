import { Suspense } from 'react';

import { HubPageInner } from './hub-page-inner';

export default function HubPage() {
  return (
    <Suspense
      fallback={
        <main className="p-8 text-sm text-[var(--muted)]">载入 Hub…</main>
      }
    >
      <HubPageInner />
    </Suspense>
  );
}
