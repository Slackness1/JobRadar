'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

// High-frequency campus-recruitment targets, grouped roughly by track.
const PRESETS: { group: string; items: string[] }[] = [
  {
    group: '互联网',
    items: ['产品经理', '数据分析师', '前端开发', '后端开发', '算法工程师', '运营'],
  },
  {
    group: '金融',
    items: ['券商研究员', '投行分析师', '量化研究员', '风控分析师', '商业银行管培生'],
  },
  {
    group: '咨询 / 快消 / 央企',
    items: ['MBB 战略咨询', '宝洁市场营销', '联合利华管培生', '中金财富管理', '中国银行总行'],
  },
];

export default function InterviewSetupPage() {
  const router = useRouter();
  const [targetJob, setTargetJob] = useState('');
  const [error, setError] = useState('');

  function handleStart(jobOverride?: string) {
    const trimmed = (jobOverride ?? targetJob).trim();
    if (!trimmed) {
      setError('请填写或选择目标岗位');
      return;
    }
    const sessionId = crypto.randomUUID();
    localStorage.setItem(`interview.pending.${sessionId}`, trimmed);
    router.push(`/interview/${sessionId}/check`);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4 py-10">
      <div className="resume-paper-shadow w-full max-w-2xl rounded-[24px] bg-[var(--paper)] px-8 py-10">
        <h1 className="mb-1 text-[22px] font-semibold text-[var(--ink)]">模拟面试</h1>
        <p className="mb-7 text-[14px] text-[var(--muted)]">
          选一个高频岗位快速开始，或者在下方自由填写你的目标岗位。
        </p>

        {/* Preset job chips */}
        <div className="mb-6 space-y-3">
          {PRESETS.map((g) => (
            <div key={g.group}>
              <div className="mb-2 text-[12px] font-medium text-[var(--muted)]">{g.group}</div>
              <div className="flex flex-wrap gap-2">
                {g.items.map((item) => {
                  const active = targetJob === item;
                  return (
                    <button
                      key={item}
                      onClick={() => { setTargetJob(item); setError(''); }}
                      onDoubleClick={() => handleStart(item)}
                      className={`rounded-full border px-3 py-1.5 text-[13px] transition-colors ${
                        active
                          ? 'border-[var(--primary)] bg-[var(--primary)] text-white'
                          : 'border-[var(--border)] text-[var(--ink)] hover:border-[var(--primary)] hover:bg-[var(--soft)]'
                      }`}
                      title="单击填入，双击直接开始"
                    >
                      {item}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <label className="mb-2 block text-[13px] font-medium text-[var(--ink)]">
          自定义岗位
        </label>
        <textarea
          className="w-full resize-none rounded-[14px] border border-[var(--border)] bg-[var(--soft)] px-4 py-3 text-[15px] text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none"
          rows={2}
          placeholder="例如：腾讯 IEG 游戏策划、华泰证券非银分析师助理、字节抖音电商 BP …"
          value={targetJob}
          onChange={(e) => { setTargetJob(e.target.value); setError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleStart(); } }}
        />
        {error && <p className="mt-1.5 text-[13px] text-red-500">{error}</p>}

        <button
          onClick={() => handleStart()}
          className="mt-5 w-full rounded-[12px] bg-[var(--primary)] py-3 text-[15px] font-semibold text-white transition-opacity hover:opacity-90 active:opacity-80"
        >
          开始面试
        </button>

        <p className="mt-4 text-center text-[12px] text-[var(--muted)]">
          面试约 10–14 轮，结束后生成详细报告 · 单击 chip 填入，双击直接开始
        </p>
      </div>
    </main>
  );
}
