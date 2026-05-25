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
import { RecommendCardIntelSection } from './RecommendCardIntelSection';

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
}

export function PlatformCard({ platform, rank, isExpanded, onToggle }: PlatformCardProps) {
  const initial = companyInitial(platform.company);
  const tSuffix = tierSuffix(platform.tier_label);
  const priorityLetter = platform.priority_letter;
  const hasMoreJobs = platform.n_jobs > platform.top_jobs.length;

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
            {platform.n_xhs_insights > 0 && (
              <span
                className="workspace-hifi__platform-card-xhs"
                title={`小红书有 ${platform.n_xhs_insights} 条同辈情报`}
              >
                小红书×{platform.n_xhs_insights}
              </span>
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
          <div className="workspace-hifi__platform-jobs">
          {platform.top_jobs.map((job) => (
            <a
              key={job.job_id}
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
          ))}
          {hasMoreJobs && (
            <span className="workspace-hifi__platform-jobs-more">
              + {platform.n_jobs - platform.top_jobs.length} 个岗位（切到校招/实习 tab 查看全部）
            </span>
          )}
          </div>
          <div className="workspace-hifi__platform-intel-wrap">
            <RecommendCardIntelSection
              company={platform.company}
              isVisible={isExpanded}
            />
          </div>
        </div>
      )}
    </article>
  );
}
