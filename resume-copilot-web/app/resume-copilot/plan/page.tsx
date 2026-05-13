'use client';

import { Suspense, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

import { PlanPanel } from '@/components/resume-copilot/plan/PlanPanel';

function PlanPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const sessionIdParam = searchParams.get('sessionId');
  const parsed = sessionIdParam ? Number(sessionIdParam) : NaN;
  const sessionId = Number.isFinite(parsed) && parsed > 0 ? parsed : null;

  useEffect(() => {
    if (sessionId === null) router.replace('/');
  }, [sessionId, router]);

  if (sessionId === null) {
    return <main className="p-8 text-sm text-gray-500">加载中…</main>;
  }

  return (
    <main className="h-screen flex flex-col">
      <header className="border-b px-6 py-3 flex items-center justify-between bg-white">
        <h1 className="text-base font-semibold">JobRadar · 定向简历建造</h1>
        <button
          onClick={() => router.push(`/resume-copilot?sessionId=${sessionId}`)}
          className="text-sm text-orange-700 hover:underline"
        >
          ← 回到工作台
        </button>
      </header>
      <div className="flex-1 overflow-hidden">
        <PlanPanel sessionId={sessionId} />
      </div>
    </main>
  );
}

export default function PlanPage() {
  return (
    <Suspense fallback={<main className="p-8 text-sm text-gray-500">加载中…</main>}>
      <PlanPageInner />
    </Suspense>
  );
}
