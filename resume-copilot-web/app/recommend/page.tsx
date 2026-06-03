import { Suspense } from 'react';

import { RecommendPageInner } from './recommend-page-inner';

export default function RecommendPage() {
  return (
    <Suspense
      fallback={
        <main className="p-8 text-sm text-[var(--muted)]">载入推荐工作台…</main>
      }
    >
      <RecommendPageInner />
    </Suspense>
  );
}
