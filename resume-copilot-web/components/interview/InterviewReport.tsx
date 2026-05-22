'use client';

import type { InterviewReport } from './types';

interface Props {
  report: InterviewReport;
  targetJob: string;
  durationSeconds: number;
  onRestart: () => void;
}

function ScoreRing({ score }: { score: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = score >= 80 ? '#4ade80' : score >= 60 ? 'var(--primary)' : '#f97316';

  return (
    <div className="relative flex items-center justify-center">
      <svg width={96} height={96} className="-rotate-90">
        <circle cx={48} cy={48} r={r} fill="none" stroke="var(--border)" strokeWidth={7} />
        <circle
          cx={48} cy={48} r={r} fill="none"
          stroke={color} strokeWidth={7}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-[22px] font-bold text-[var(--ink)]">{score}</span>
    </div>
  );
}

function MetaChip({ tone, children }: { tone: 'warn' | 'info'; children: React.ReactNode }) {
  const palette = tone === 'warn'
    ? { bg: 'rgba(245,158,11,0.12)', fg: '#b45309', border: 'rgba(245,158,11,0.35)' }
    : { bg: 'rgba(99,102,241,0.10)', fg: '#4338ca', border: 'rgba(99,102,241,0.30)' };
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
      style={{ background: palette.bg, color: palette.fg, border: `1px solid ${palette.border}` }}
    >
      {children}
    </span>
  );
}

function DimensionBar({ name, score, comment }: { name: string; score: number; comment: string }) {
  const color = score >= 80 ? '#4ade80' : score >= 60 ? 'var(--primary)' : '#f97316';
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[13px] font-medium text-[var(--ink)]">{name}</span>
        <span className="text-[13px] font-semibold" style={{ color }}>{score}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--border)]">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      {comment && <p className="mt-1 text-[12px] text-[var(--muted)]">{comment}</p>}
    </div>
  );
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}分${s.toString().padStart(2, '0')}秒`;
}

export function InterviewReport({ report, targetJob, durationSeconds, onRestart }: Props) {
  const fallbackReason = report._meta?.fallback_reason;
  const isFallback = fallbackReason != null || report.overall_score == null;
  const cappedForFab = report._meta?.score_capped_for_fabrication === true;
  const mentorCount = report._meta?.mentor_fallback_count ?? 0;
  const suppressed = report._fabrication_suppressed === true;

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
      <div className="mx-auto w-full max-w-xl space-y-5">
        <div className="rounded-[20px] bg-[var(--paper)] resume-paper-shadow px-6 py-5">
          <p className="mb-1 text-[12px] font-semibold uppercase tracking-widest text-[var(--muted)]">
            面试报告
          </p>
          <h2 className="text-[18px] font-semibold text-[var(--ink)]">{targetJob}</h2>
          <p className="text-[13px] text-[var(--muted)]">面试时长：{formatDuration(durationSeconds)}</p>
        </div>

        {isFallback ? (
          <div
            className="rounded-[20px] px-6 py-5"
            style={{
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.30)',
            }}
          >
            <p className="mb-2 text-[13px] font-semibold" style={{ color: '#b45309' }}>
              ⚠️ 反馈生成中断
            </p>
            <p className="text-[14px] leading-relaxed text-[var(--ink)]">
              {report.overall_comment || '反馈系统暂时不可用，本次没有生成评分。请点击下方"重新面试"再试一次。'}
            </p>
          </div>
        ) : (
          <div className="rounded-[20px] bg-[var(--paper)] resume-paper-shadow px-6 py-5">
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-[13px] font-semibold text-[var(--muted)]">综合评分</p>
              <div className="flex flex-wrap items-center justify-end gap-1.5">
                {suppressed || cappedForFab ? (
                  <MetaChip tone="warn">⚑ 编造嫌疑 评分已下调</MetaChip>
                ) : null}
                {mentorCount >= 2 ? (
                  <MetaChip tone="warn">⚑ {mentorCount} 次依赖外部判断</MetaChip>
                ) : null}
              </div>
            </div>
            <div className="flex items-center gap-6">
              <ScoreRing score={report.overall_score as number} />
              <p className="flex-1 text-[14px] leading-relaxed text-[var(--ink)]">
                {report.overall_comment}
              </p>
            </div>
            <p
              className="mt-3 border-t border-[var(--border)] pt-2.5 text-[11px] leading-relaxed text-[var(--muted)]"
              title="AI 评分含主观判断，每次结果会有 ±5 分浮动属正常现象。看分数请关注区间（如 80-90 = 顶档）而非单个数字。"
            >
              ⓘ 评分含 ±5 分主观波动属正常 — 请参考分数区间而非单个数字
            </p>
          </div>
        )}

        {!isFallback && report.dimensions.length > 0 && (
          <div className="rounded-[20px] bg-[var(--paper)] resume-paper-shadow px-6 py-5">
            <p className="mb-4 text-[13px] font-semibold text-[var(--muted)]">各维度评分</p>
            {report.dimensions.map((d) => (
              <DimensionBar key={d.name} {...d} />
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          {report.highlights.length > 0 && (
            <div className="rounded-[20px] bg-[var(--accent-soft)] px-5 py-4">
              <p className="mb-2 text-[12px] font-semibold text-[var(--accent)]">✦ 亮点</p>
              <ul className="space-y-1">
                {report.highlights.map((h, i) => (
                  <li key={i} className="text-[13px] text-[var(--ink)]">· {h}</li>
                ))}
              </ul>
            </div>
          )}
          {report.improvements.length > 0 && (
            <div className="rounded-[20px] bg-[var(--warning-soft)] px-5 py-4">
              <p className="mb-2 text-[12px] font-semibold text-amber-600">⚡ 改进方向</p>
              <ul className="space-y-1">
                {report.improvements.map((imp, i) => (
                  <li key={i} className="text-[13px] text-[var(--ink)]">· {imp}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <button
          onClick={onRestart}
          className="w-full rounded-[12px] border border-[var(--border)] bg-[var(--paper)] py-3 text-[14px] font-medium text-[var(--ink)] hover:bg-[var(--soft)] transition-colors"
        >
          重新面试
        </button>
      </div>
    </div>
  );
}
