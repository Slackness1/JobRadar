'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ScoreReport } from '../../../components/resume-copilot/scoring/ScoreReport';
import { scoreResume, type ScoreReportData } from '../../../components/resume-copilot/api';

// 设计稿 简历打分报告.html 的样例数据 —— ?mock=1 时渲染,供视觉对照(无需后端/LLM)。
const MOCK: ScoreReportData = {
  session_id: 0,
  target_track: '量化私募 · 研究',
  overall_current: 69,
  overall_potential_low: 83,
  overall_potential_high: 88,
  summary:
    '简历整体质量中上:逻辑清晰、可读性与专业表达突出。主要短板在 STAR 应用 与 成果量化——核心经历缺可核实的结果与数字锚点,拉低了佐证充分度。建议优先补强九坤实习与校园项目两段。',
  dimensions: [
    { key: 'logic', name: '逻辑清晰', score: 82, ceiling: 88, reason: '' },
    { key: 'star', name: 'STAR 应用', score: 58, ceiling: 84, reason: '核心经历缺可核实的 Result' },
    { key: 'readability', name: '内容可读', score: 84, ceiling: 88, reason: '' },
    { key: 'completeness', name: '内容完整', score: 70, ceiling: 80, reason: '' },
    { key: 'expression', name: '专业表达', score: 80, ceiling: 86, reason: '' },
    { key: 'quantification', name: '成果量化', score: 54, ceiling: 82, reason: '缺数字锚点' },
    { key: 'track_fit', name: '赛道匹配度', score: 66, ceiling: 82, reason: '' },
    { key: 'defensibility', name: '佐证充分度', score: 60, ceiling: 80, reason: '角色表述偏弱、缺佐证' },
  ],
  section_gaps: [
    {
      section: 'internships.0',
      label: '九坤投资 · 量化研究实习',
      gaps: ['STAR 缺 Result', '佐证不足'],
      detail:
        '「协助搭建因子回测框架」缺最终结果——框架覆盖多少因子、回测哪段区间、带来什么变化都没写;且「协助」角色缺佐证,面试一追问就露。',
    },
    {
      section: 'projects.1',
      label: '校园量化策略项目',
      gaps: ['成果无量化锚点'],
      detail: '通篇没有数字锚点:回测区间、收益、调仓频次全缺,直接拖低成果量化与赛道匹配度两维。',
    },
  ],
  used_ai: false,
};

function ScorePageInner() {
  const params = useSearchParams();
  const isMock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');

  const [report, setReport] = useState<ScoreReportData | null>(isMock ? MOCK : null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(!isMock);

  useEffect(() => {
    if (isMock || !sessionId) return;
    let alive = true;
    scoreResume(sessionId)
      .then((r) => { if (alive) { setReport(r); setError(''); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : '打分失败'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [isMock, sessionId]);

  if (!isMock && !sessionId) {
    return <div style={{ padding: 40, fontFamily: 'system-ui', color: '#5e5d59' }}>缺少 ?session=&lt;id&gt;(或加 ?mock=1 看样例)</div>;
  }
  if (loading) return <div style={{ padding: 40, fontFamily: 'system-ui', color: '#5e5d59' }}>打分中…</div>;
  if (error) return <div style={{ padding: 40, fontFamily: 'system-ui', color: '#b53333' }}>打分失败:{error}</div>;
  if (!report) return null;

  return (
    <div style={{ minHeight: '100vh', background: '#f5f4ed', padding: '40px 24px 64px' }}>
      <ScoreReport report={report} onDeepOptimize={(s) => console.log('deep-optimize', s)} />
    </div>
  );
}

export default function ScorePage() {
  return (
    <Suspense fallback={<div style={{ padding: 40 }}>加载中…</div>}>
      <ScorePageInner />
    </Suspense>
  );
}
