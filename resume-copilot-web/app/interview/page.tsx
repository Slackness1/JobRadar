'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function InterviewSetupPage() {
  const router = useRouter();
  const [targetJob, setTargetJob] = useState('');
  const [error, setError] = useState('');

  function handleStart() {
    const trimmed = targetJob.trim();
    if (!trimmed) {
      setError('请填写目标岗位');
      return;
    }
    const sessionId = crypto.randomUUID();
    localStorage.setItem(`interview.pending.${sessionId}`, trimmed);
    router.push(`/interview/${sessionId}`);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4">
      <div className="resume-paper-shadow w-full max-w-lg rounded-[24px] bg-[var(--paper)] px-8 py-10">
        <h1 className="mb-1 text-[22px] font-semibold text-[var(--ink)]">模拟面试</h1>
        <p className="mb-8 text-[14px] text-[var(--muted)]">
          输入你的目标岗位，AI 面试官将进行真实对话式面试，并在结束后给出详细反馈。
        </p>

        <label className="mb-2 block text-[13px] font-medium text-[var(--ink)]">
          目标岗位
        </label>
        <textarea
          className="w-full resize-none rounded-[14px] border border-[var(--border)] bg-[var(--soft)] px-4 py-3 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none"
          rows={2}
          placeholder="例如：蚂蚁集团数据分析师、互联网产品经理、券商研究员…"
          value={targetJob}
          onChange={(e) => { setTargetJob(e.target.value); setError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleStart(); } }}
        />
        {error && <p className="mt-1.5 text-[13px] text-red-500">{error}</p>}

        <button
          onClick={handleStart}
          className="mt-5 w-full rounded-[12px] bg-[var(--primary)] py-3 text-[15px] font-semibold text-white transition-opacity hover:opacity-90 active:opacity-80"
        >
          开始面试
        </button>

        <p className="mt-4 text-center text-[12px] text-[var(--muted)]">
          面试约 10–14 轮，结束后生成详细报告
        </p>
      </div>
    </main>
  );
}
