'use client';

/**
 * PlatformCard — 平台聚合卡 (Phase 4, 2026-05-25).
 *
 * 收起: logo + rank + 公司名 + 平台分 + 岗位数 + 匹配标签 + XHS 情报数
 * 展开: top_jobs 列表 (每行: [校/实] 岗位名 分数 → 链接)
 *
 * 复用 rec-card-logo / rec-card-tier / rec-card-priority CSS 类与 RecommendCard 对齐。
 */

import type { ResumeRecommendationPlatform } from '../../types';
import { I } from '@/components/hifi/hifi-primitives';
import { RecommendNarrativeSection } from './RecommendNarrativeSection';

function companyInitial(company: string): string {
  const trimmed = (company || '').trim();
  if (!trimmed) return '?';
  const first = trimmed[0];
  return /[A-Za-z0-9]/.test(first) ? first.toUpperCase() : first;
}

function tierSuffix(label: string): string {
  if (label === '强匹配') return 'strong';
  if (label === '可迁移') return 'transfer';
  if (label === '有差距') return 'gap';
  return '';
}

export interface PlatformCardProps {
  platform: ResumeRecommendationPlatform;
  rank: number;
  isExpanded: boolean;
  onToggle: () => void;
  /** Phase 8 — short narrative fetch 需要 sessionId。 */
  sessionId?: number;
  /** P0b — 小红书 badge 点击 + 卡内 CTA 转到 IntelDrawer (替换 inline 情报段). */
  onOpenIntel?: (
    company: string,
    ctx?: { priority?: string | null; xhsCount?: number | null },
  ) => void;
}

export function PlatformCard({
  platform,
  rank,
  isExpanded,
  onToggle,
  sessionId,
  onOpenIntel,
}: PlatformCardProps) {
  const initial = companyInitial(platform.company);
  const tSuffix = tierSuffix(platform.tier_label);
  const priorityLetter = platform.priority_letter;
  const hasMoreJobs = platform.n_jobs > platform.top_jobs.length;
  const xhsCount = platform.n_xhs_insights || 0;

  const openIntel = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onOpenIntel?.(platform.company, {
      priority: priorityLetter || null,
      xhsCount,
    });
  };

  return (
    <article
      className={`workspace-hifi__platform-card${isExpanded ? ' is-expanded' : ''}`}
      data-priority={priorityLetter || undefined}
    >
      <button
        type="button"
        className="workspace-hifi__platform-card-header"
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-label={`${platform.company} — ${platform.n_jobs} 个岗位，${isExpanded ? '收起' : '展开'}`}
      >
        <div
          className="workspace-hifi__rec-card-logo"
          aria-hidden
          data-priority={priorityLetter || undefined}
        >
          {initial}
        </div>
        <div className="workspace-hifi__platform-card-info">
          <div className="workspace-hifi__platform-card-headline">
            <span className="workspace-hifi__platform-card-rank">{rank}.</span>
            <span className="workspace-hifi__platform-card-name">{platform.company}</span>
          </div>
          <div className="workspace-hifi__platform-card-badges">
            {tSuffix && (
              <span className={`workspace-hifi__rec-card-tier workspace-hifi__rec-card-tier--${tSuffix}`}>
                {platform.tier_label}
              </span>
            )}
            {priorityLetter && (
              <span className={`workspace-hifi__rec-card-priority workspace-hifi__rec-card-priority--${priorityLetter}`}>
                {priorityLetter}
              </span>
            )}
            <span className="workspace-hifi__platform-card-score">{platform.platform_score}</span>
            <span className="workspace-hifi__platform-card-n-jobs">{platform.n_jobs} 个岗</span>
            {xhsCount > 0 && (
              onOpenIntel ? (
                <button
                  type="button"
                  className="workspace-hifi__platform-card-xhs-btn"
                  onClick={openIntel}
                  title={`小红书 ${xhsCount} 条同辈情报 — 点开右栏抽屉`}
                  aria-label={`查看 ${platform.company} 的 ${xhsCount} 条同辈情报`}
                >
                  <span className="workspace-hifi__platform-card-xhs">
                    小红书×{xhsCount}
                  </span>
                </button>
              ) : (
                <span
                  className="workspace-hifi__platform-card-xhs"
                  title={`小红书有 ${xhsCount} 条同辈情报`}
                >
                  小红书×{xhsCount}
                </span>
              )
            )}
          </div>
        </div>
        <span
          className={`workspace-hifi__platform-card-chevron${isExpanded ? ' is-open' : ''}`}
          aria-hidden
        >
          {I.chevron(11)}
        </span>
      </button>

      {isExpanded && (
        <div className="workspace-hifi__platform-expanded">
          {/* P0b — "为你定制" 高亮叙事盒 (替换原 inline 情报段) */}
          {xhsCount > 0 && (
            <div className="workspace-hifi__platform-card-customised">
              <div className="workspace-hifi__platform-card-customised-head">
                <span className="workspace-hifi__platform-card-customised-icon" aria-hidden>
                  ✦
                </span>
                <span className="workspace-hifi__platform-card-customised-title">
                  为你定制
                </span>
                <span className="workspace-hifi__platform-card-customised-meta">
                  {xhsCount} 条情报支撑
                </span>
              </div>
              <div className="workspace-hifi__platform-card-customised-body">
                {sessionId !== undefined && platform.top_jobs[0] ? (
                  <RecommendNarrativeSection
                    sessionId={sessionId}
                    jobId={String(platform.top_jobs[0].job_id)}
                    isVisible={isExpanded}
                    mode="short"
                  />
                ) : (
                  <span>
                    {platform.n_jobs} 个岗位 · 小红书有 {xhsCount} 条同辈洞察 — 点右上情报抽屉看完整原话。
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="workspace-hifi__platform-jobs">
          {platform.top_jobs.map((job) => (
            <div key={job.job_id} className="workspace-hifi__platform-job-cell">
              <a
                className="workspace-hifi__platform-job-row"
                href={job.detail_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span
                  className={`workspace-hifi__platform-job-type${job.is_internship ? ' is-intern' : ''}`}
                >
                  {job.is_internship ? '实' : '校'}
                </span>
                <span className="workspace-hifi__platform-job-title">{job.job_title}</span>
                {(job.industry_tags ?? []).slice(0, 2).map((tag) => (
                  <span
                    key={tag}
                    className="workspace-hifi__industry-chip workspace-hifi__industry-chip--mini"
                  >
                    {tag}
                  </span>
                ))}
                <span className="workspace-hifi__platform-job-score">{job.final_score}</span>
                <span aria-hidden className="workspace-hifi__platform-job-arrow">
                  {I.arrowRight(10)}
                </span>
              </a>
              {sessionId !== undefined && (
                <RecommendNarrativeSection
                  sessionId={sessionId}
                  jobId={String(job.job_id)}
                  isVisible={isExpanded}
                  mode="short"
                />
              )}
            </div>
          ))}
          {hasMoreJobs && (
            <span className="workspace-hifi__platform-jobs-more">
              + {platform.n_jobs - platform.top_jobs.length} 个岗位（切到校招/实习 tab 查看全部）
            </span>
          )}
          </div>
          {xhsCount > 0 && onOpenIntel && (
            <button
              type="button"
              className="workspace-hifi__intel-cta-row"
              onClick={openIntel}
            >
              <span aria-hidden style={{ display: 'inline-flex' }}>{I.book(14)}</span>
              <span style={{ flex: 1, textAlign: 'left' }}>
                同辈情报 · {xhsCount} 条洞察 (原话 / 待遇 / 真题)
              </span>
              <span aria-hidden style={{ display: 'inline-flex' }}>{I.arrowRight(12)}</span>
            </button>
          )}
        </div>
      )}
    </article>
  );
}
