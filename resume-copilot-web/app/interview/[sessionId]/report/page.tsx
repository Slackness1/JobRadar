'use client';

import { use, useEffect, useState } from 'react';
import {
  getInterviewTurns,
  getInterviewReport,
  type InterviewReportPayload,
  type TurnPayload,
  type VoiceFactMetric,
  type VoiceFactsPayload,
  type VoiceMetricsPayload,
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
              {(t.analysis_failures?.length ?? 0) > 0 && (
                <span style={missingBadgeStyle}>本题分析缺失</span>
              )}
              {t.score?.overall != null && (
                <span style={{ marginLeft: 'auto', fontWeight: 600 }}>
                  {t.score.overall}/100
                </span>
              )}
            </summary>
            <div style={{ paddingTop: 16 }}>
              {(t.analysis_failures?.length ?? 0) > 0 && (
                <p style={missingNoticeStyle}>
                  这一题的{(t.analysis_failures ?? []).map((part) => ANALYSIS_PART_LABELS[part] ?? part).join('、')}
                  没有保存成功，不是你没答好。你的回答已完整保留，可以重新生成或联系我们补上。
                </p>
              )}
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

              <VoiceFactsRow facts={t.voice_facts} legacy={t.voice_metrics} />

            </div>
          </details>
        ))}
      </section>

      <SessionVoiceSummary turns={turns} />

      {report?.weekly_plan_md && (
        <section style={cardStyle}>
          <h2 style={sectionHeaderStyle}>本周练习计划</h2>
          <p style={{ lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{report.weekly_plan_md}</p>
        </section>
      )}
    </main>
  );
}

/**
 * Session-level delivery summary.
 *
 * Averages only the turns whose speaking rate came from the same source, so the
 * number is not a blend of acoustic measurements and ASR-timing estimates.
 */
function SessionVoiceSummary({ turns }: { turns: TurnPayload[] }) {
  const rates = turns
    .map((turn) => turn.voice_facts?.metrics?.articulation_cpm)
    .filter((metric): metric is VoiceFactMetric =>
      Boolean(metric && metric.value != null && metric.quality !== 'unavailable'));
  if (!rates.length) return null;

  const bySource = new Map<string, VoiceFactMetric[]>();
  for (const metric of rates) {
    bySource.set(metric.source, [...(bySource.get(metric.source) ?? []), metric]);
  }
  // Prefer the most trustworthy source that actually has data.
  const preferred = ['audio_artifact', 'asr_transcript', 'legacy_v1']
    .find((source) => bySource.has(source)) ?? rates[0].source;
  const group = bySource.get(preferred) ?? rates;
  const average = Math.round(
    group.reduce((sum, metric) => sum + Number(metric.value), 0) / group.length,
  );
  const labels: Record<string, string> = {
    audio_artifact: '按授权录音的实际发声时长计算',
    asr_transcript: '按转写句段时长估算',
    legacy_v1: 'v1 旧口径，含静音',
  };

  return (
    <section style={cardStyle}>
      <h2 style={sectionHeaderStyle}>语音表现</h2>
      <p>
        平均语速 {average} 字/分
        <span style={{ opacity: 0.6 }}>
          （{group.length}/{turns.length} 题有数据 · {labels[preferred] ?? preferred}）
        </span>
      </p>
      <p style={{ fontSize: 12, opacity: 0.6, marginTop: 8 }}>
        这里只呈现可复算的发音事实，不推断自信、性格或情绪。
      </p>
    </section>
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
  gap: 8,
  cursor: 'pointer',
  fontSize: 16,
  fontWeight: 500,
};

/**
 * voice-facts-v2 row: measurable delivery facts only.
 *
 * Each value keeps its provenance, so a fallback measurement (ASR sentence
 * timing instead of the consented recording) is labelled 估算 rather than shown
 * as a hard number, and a historical v1 row is labelled 旧口径. Nothing here
 * interprets the candidate — no confidence, personality or emotion.
 */
function VoiceFactsRow({
  facts,
  legacy,
}: {
  facts?: VoiceFactsPayload | null;
  legacy: VoiceMetricsPayload | null;
}) {
  const metrics = facts?.metrics;
  const parts: string[] = [];
  const value = (metric?: VoiceFactMetric) =>
    metric && metric.value != null && metric.quality !== 'unavailable' ? metric : null;

  const responseStart = value(metrics?.response_start_ms);
  if (responseStart) parts.push(`起答 ${Math.round(Number(responseStart.value))} ms`);

  const speech = value(metrics?.speech_duration_ms);
  if (speech) parts.push(`发声 ${(Number(speech.value) / 1000).toFixed(1)} 秒`);

  const cpm = value(metrics?.articulation_cpm);
  if (cpm) parts.push(`语速 ${Math.round(Number(cpm.value))} 字/分`);

  const pauses = value(metrics?.pause_count);
  if (pauses) {
    const longest = value(metrics?.pause_max_ms);
    const total = value(metrics?.pause_total_ms);
    let text = `长停顿 ${Number(pauses.value)} 次`;
    if (total) text += `，共 ${(Number(total.value) / 1000).toFixed(1)} 秒`;
    if (longest) text += `，最长 ${(Number(longest.value) / 1000).toFixed(1)} 秒`;
    parts.push(text);
  }

  const fillers = value(metrics?.filler_count);
  if (fillers) {
    const tokens = (facts?.filler_positions ?? [])
      .filter((position) => position.kind === 'hesitation')
      .map((position) => position.token);
    parts.push(
      tokens.length
        ? `语气词 ${Number(fillers.value)} 次（${[...new Set(tokens)].join('、')}）`
        : `语气词 ${Number(fillers.value)} 次`,
    );
  }

  const level = value(metrics?.input_level_dbfs);
  if (level) parts.push(`平均音量 ${Number(level.value).toFixed(1)} dBFS`);

  const clipping = value(metrics?.clipping_ratio);
  if (clipping && Number(clipping.value) >= 0.01) parts.push('录音出现削波，建议降低麦克风增益');

  const truncated = value(metrics?.answer_truncated);
  if (truncated && truncated.value === true) parts.push('本题的问题被你中途打断，只听到了前半句');

  if (!parts.length) {
    // Old sessions predate v2 and only stored the v1 numbers.
    if (legacy?.wpm != null) {
      return (
        <div style={voiceFactsStyle}>
          <span style={qualityTagStyle}>旧口径</span>
          语速 {legacy.wpm} 字/分（v1 口径：按整段录音计算，含静音）
        </div>
      );
    }
    return null;
  }

  const estimated = Object.values(metrics ?? {}).some(
    (metric) => metric?.quality === 'degraded' || metric?.quality === 'legacy',
  );
  return (
    <div style={voiceFactsStyle}>
      {estimated && <span style={qualityTagStyle}>部分为估算</span>}
      {parts.join(' · ')}
    </div>
  );
}

const voiceFactsStyle: React.CSSProperties = {
  marginTop: 12,
  fontSize: 12,
  lineHeight: 1.7,
  opacity: 0.75,
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  gap: 6,
};
const qualityTagStyle: React.CSSProperties = {
  fontSize: 11,
  padding: '1px 7px',
  borderRadius: 999,
  border: '1px solid var(--border, #d8d3c8)',
  opacity: 0.9,
};
// A lost analysis write is the system's fault, not the candidate's — say which
// part is missing rather than rendering an unexplained empty card.
const ANALYSIS_PART_LABELS: Record<string, string> = {
  score: '评分',
  reference_answer: '参考答案',
  voice_metrics: '语音指标',
};
const missingBadgeStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: '#b45309',
  background: 'rgba(245, 158, 11, 0.14)',
  borderRadius: 999,
  padding: '2px 10px',
};
const missingNoticeStyle: React.CSSProperties = {
  fontSize: 13,
  lineHeight: 1.6,
  color: '#92400e',
  background: 'rgba(245, 158, 11, 0.10)',
  border: '1px solid rgba(245, 158, 11, 0.35)',
  borderRadius: 10,
  padding: '10px 12px',
  marginBottom: 12,
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
