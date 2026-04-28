'use client';

import { use, useEffect, useState } from 'react';
import {
  getInterviewTurns,
  getInterviewReport,
  type InterviewReportPayload,
  type TurnPayload,
} from '@/components/interview/api';

export default function InterviewReportPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const [turns, setTurns] = useState<TurnPayload[]>([]);
  const [report, setReport] = useState<InterviewReportPayload | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const turnsResult = await getInterviewTurns(sessionId);
        if (!cancelled) setTurns(turnsResult);
        // Find report id from URL or query param
        const params = new URLSearchParams(window.location.search);
        const reportId = params.get('reportId');
        if (reportId) {
          const reportResult = await getInterviewReport(parseInt(reportId, 10));
          if (!cancelled) setReport(reportResult);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId]);

  if (error) return <main style={{ padding: 32 }}>加载失败：{error}</main>;

  return (
    <main
      style={{
        maxWidth: 880,
        margin: '0 auto',
        padding: '40px 24px',
        fontFamily: 'var(--font-fraunces, Fraunces), serif',
      }}
    >
      <h1 style={{ fontSize: 32, marginBottom: 24 }}>面试反馈</h1>

      {report?.weakness_profile && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>整体表现</h2>
          <div style={{ fontSize: 56, fontWeight: 600, color: 'var(--terracotta, #c96442)' }}>
            {report.weakness_profile.avg_score ?? '—'}
            <span style={{ fontSize: 18, opacity: 0.6 }}> /100</span>
          </div>
          {report.weakness_profile.weak_topics.length > 0 && (
            <p style={{ marginTop: 16 }}>
              <strong>重点提升：</strong>
              {report.weakness_profile.weak_topics.join('、')}
            </p>
          )}
          {report.weakness_profile.strong_topics.length > 0 && (
            <p>
              <strong>已展现的强项：</strong>
              {report.weakness_profile.strong_topics.join('、')}
            </p>
          )}
        </section>
      )}

      <section style={cardStyle}>
        <h2 style={sectionHeaderStyle}>逐题回放</h2>
        {turns.length === 0 && <p style={{ opacity: 0.6 }}>没有可显示的题目记录。</p>}
        {turns.map((t) => (
          <details key={t.turn_index} style={detailStyle}>
            <summary style={summaryStyle}>
              <span>第 {t.turn_index + 1} 题</span>
              {t.score?.overall != null && (
                <span style={{ marginLeft: 'auto', fontWeight: 600 }}>
                  {t.score.overall}/100
                </span>
              )}
            </summary>
            <div style={{ paddingTop: 16 }}>
              <p><strong>题目：</strong>{t.question}</p>
              <p><strong>你的回答：</strong>{t.user_answer || <em style={{opacity:0.5}}>（未作答）</em>}</p>

              {t.score && (
                <div style={scoreCardStyle}>
                  {t.score.hits.length > 0 && (
                    <div>
                      <strong style={{ color: '#16a34a' }}>✓ 命中</strong>
                      <div>{t.score.hits.join('、')}</div>
                    </div>
                  )}
                  {t.score.misses.length > 0 && (
                    <div>
                      <strong style={{ color: '#dc2626' }}>✗ 缺失</strong>
                      <div>{t.score.misses.join('、')}</div>
                    </div>
                  )}
                  {t.score.bonuses.length > 0 && (
                    <div>
                      <strong style={{ color: '#ca8a04' }}>★ 加分</strong>
                      <div>{t.score.bonuses.join('、')}</div>
                    </div>
                  )}
                </div>
              )}

              {t.reference_answer && (
                <div style={referenceStyle}>
                  <strong>📖 如果是面霸会怎么答</strong>
                  <p style={{ marginTop: 8 }}>{t.reference_answer}</p>
                </div>
              )}

              {t.voice_metrics && t.voice_metrics.wpm != null && (
                <div style={{ marginTop: 12, fontSize: 12, opacity: 0.7 }}>
                  语速 {t.voice_metrics.wpm} 字/分
                  {t.voice_metrics.filler_rate != null && ` · 填充词 ${t.voice_metrics.filler_rate}/分钟`}
                  {t.voice_metrics.confidence_score != null && ` · 自信度 ${t.voice_metrics.confidence_score}/100`}
                </div>
              )}
            </div>
          </details>
        ))}
      </section>

      {/* Voice averages (if any turn had voice metrics) */}
      {turns.some((t) => t.voice_metrics?.wpm != null) && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>语音表现</h2>
          {(() => {
            const voiceTurns = turns.filter((t) => t.voice_metrics?.wpm != null);
            const avgWpm = Math.round(
              voiceTurns.reduce((s, t) => s + (t.voice_metrics!.wpm ?? 0), 0) / voiceTurns.length,
            );
            return <p>平均语速 {avgWpm} 字/分（理想区间 200-260 字/分）</p>;
          })()}
        </section>
      )}

      {report?.weekly_plan_md && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>本周练习计划</h2>
          <p style={{ lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{report.weekly_plan_md}</p>
        </section>
      )}
    </main>
  );
}

const cardStyle: React.CSSProperties = {
  background: 'var(--paper, #fff)',
  borderRadius: 16,
  padding: 24,
  marginBottom: 16,
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
};
const sectionHeaderStyle: React.CSSProperties = {
  fontSize: 20,
  marginBottom: 16,
  borderBottom: '1px solid var(--border, #e5e5e5)',
  paddingBottom: 8,
};
const detailStyle: React.CSSProperties = {
  borderBottom: '1px solid var(--border, #e5e5e5)',
  padding: '12px 0',
};
const summaryStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  cursor: 'pointer',
  fontSize: 16,
  fontWeight: 500,
};
const scoreCardStyle: React.CSSProperties = {
  background: 'rgba(201, 100, 66, 0.05)',
  borderRadius: 12,
  padding: 16,
  marginTop: 12,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};
const referenceStyle: React.CSSProperties = {
  background: 'rgba(245, 158, 11, 0.08)',
  borderLeft: '3px solid #ca8a04',
  borderRadius: 8,
  padding: 16,
  marginTop: 12,
};
