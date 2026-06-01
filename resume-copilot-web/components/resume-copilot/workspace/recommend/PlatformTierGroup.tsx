'use client';

/**
 * PlatformTierGroup — 梯队骨架视图的单梯队区块 (Phase G, 2026-06-01).
 *
 * 渲染一个梯队的 header (阶梯节点 + 梯队名 + role 标签 + 家数) +
 * 该梯队下每家公司的双态卡片:
 *   hasLive=true  → ivory 背景, 展开显示"为你定制"叙事 + 在招岗列表 + 情报 CTA
 *   hasLive=false → parchment 背景, 展开显示往年招聘窗口 + 三维情报占位 + 开岗提醒
 *
 * 多卡展开: expandedCompanies 是 Set<string>, 父传入, onToggle add/delete.
 * role 三态 (match/stretch/floor) 驱动梯队 header 颜色与 dim 效果.
 *
 * 遵循 .workspace-hifi__ scope, 所有颜色走项目 token.
 */

import { I } from '@/components/hifi/hifi-primitives';
import type { PlatformSkeletonCompany, PlatformSkeletonIntel, PlatformSkeletonTier } from '../../api';

// ── role meta ────────────────────────────────────────────────────────────────

const ROLE_META = {
  match: {
    tag: '你匹配这档',
    mark: '✦',
    headerBg: 'workspace-hifi__tier-group-header--match',
    nodeCls: 'workspace-hifi__tier-group-node--match',
    pillCls: 'workspace-hifi__tier-group-pill--match',
  },
  stretch: {
    tag: '踮脚可冲',
    mark: '↑',
    headerBg: 'workspace-hifi__tier-group-header--stretch',
    nodeCls: 'workspace-hifi__tier-group-node--stretch',
    pillCls: 'workspace-hifi__tier-group-pill--stretch',
  },
  floor: {
    tag: '稳·保底',
    mark: '◆',
    headerBg: 'workspace-hifi__tier-group-header--floor',
    nodeCls: 'workspace-hifi__tier-group-node--floor',
    pillCls: 'workspace-hifi__tier-group-pill--floor',
  },
} as const;

type RoleKey = keyof typeof ROLE_META;

// ── Logo bubble ──────────────────────────────────────────────────────────────

function companyInitial(name: string): string {
  const t = name?.trim() || '?';
  const c = t[0];
  return /[A-Za-z0-9]/.test(c) ? c.toUpperCase() : c;
}

// ── Match badge ──────────────────────────────────────────────────────────────

function matchSuffix(kind: string): string {
  if (kind === '强匹配') return 'strong';
  if (kind === '可迁移') return 'transfer';
  return 'gap';
}

// ── IntelMini — 三维情报展示 (对齐设计稿 HFIntelMini) ───────────────────────

interface IntelMiniRowProps {
  label: string;
  empty?: boolean;
  children: React.ReactNode;
}

function IntelMiniRow({ label, empty, children }: IntelMiniRowProps) {
  return (
    <div
      className={[
        'workspace-hifi__intel-mini-row',
        empty ? 'workspace-hifi__intel-mini-row--empty' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <span className={`workspace-hifi__intel-mini-label${empty ? ' workspace-hifi__intel-mini-label--empty' : ''}`}>
        {label}
      </span>
      <div className="workspace-hifi__intel-mini-content">{children}</div>
    </div>
  );
}

function IntelMini({ intel, nInsights }: { intel: PlatformSkeletonIntel; nInsights: number }) {
  const compEmpty = intel.comp_empty;
  const requirements = intel.threshold?.requirements ?? [];
  const prospectsText = intel.outlook?.summary ?? null;
  const compSummary = intel.compensation?.summary ?? null;

  return (
    <div className="workspace-hifi__intel-mini">
      {/* 门槛 */}
      {requirements.length > 0 && (
        <IntelMiniRow label="门槛">
          <div className="workspace-hifi__intel-mini-tags">
            {requirements.map((r) => (
              <span key={r} className="workspace-hifi__intel-mini-tag">{r}</span>
            ))}
          </div>
        </IntelMiniRow>
      )}

      {/* 前景 */}
      {prospectsText && (
        <IntelMiniRow label="前景">
          <span className="workspace-hifi__intel-mini-quote">&ldquo;{prospectsText}&rdquo;</span>
        </IntelMiniRow>
      )}

      {/* 待遇 — 诚实留白沉底 */}
      {compEmpty ? (
        <IntelMiniRow label="待遇" empty>
          同龄人讨论中暂未提及
          <span className="workspace-hifi__intel-mini-empty-sub">
            {intel.comp_empty_note || `${nInsights} 条情报集中在门槛 / 前景`} · 不编造数字
          </span>
        </IntelMiniRow>
      ) : (
        <IntelMiniRow label="待遇">{compSummary}</IntelMiniRow>
      )}
    </div>
  );
}

// ── Company card (dual mode) ─────────────────────────────────────────────────

interface CompanyCardProps {
  company: PlatformSkeletonCompany;
  isExpanded: boolean;
  onToggle: (name: string) => void;
  onOpenIntel?: (company: string, ctx?: { n_insights?: number }) => void;
  dim: boolean;
}

function CompanyCard({ company, isExpanded, onToggle, onOpenIntel, dim }: CompanyCardProps) {
  const initial = companyInitial(company.name);
  const mSuffix = matchSuffix(company.match);

  const introPrefix = company.has_live ? '✦' : '◇';
  const hasIntel = company.n_insights > 0;

  return (
    <article
      className={[
        'workspace-hifi__tier-company-card',
        isExpanded ? 'is-expanded' : '',
        company.has_live ? 'has-live' : 'no-live',
        dim && !isExpanded ? 'is-dimmed' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {/* Card header (always visible) */}
      <div
        role="button"
        tabIndex={0}
        className="workspace-hifi__tier-company-header"
        onClick={() => onToggle(company.name)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle(company.name);
          }
        }}
        aria-expanded={isExpanded}
        aria-label={`${company.name} — ${company.has_live ? `在招 ${company.n_live} 岗` : '本季暂无对口岗'}，${isExpanded ? '收起' : '展开'}`}
      >
        {/* Logo bubble */}
        <div className="workspace-hifi__tier-company-logo" aria-hidden>
          {initial}
        </div>

        {/* Info block */}
        <div className="workspace-hifi__tier-company-info">
          {/* Row 1: name + score/chevron */}
          <div className="workspace-hifi__tier-company-headline">
            <span className="workspace-hifi__tier-company-name">{company.name}</span>
            <span className="workspace-hifi__tier-company-chevron-wrap" aria-hidden>
              <span
                className={`workspace-hifi__platform-card-chevron${isExpanded ? ' is-open' : ''}`}
              >
                {I.chevron(11)}
              </span>
            </span>
          </div>

          {/* Row 2: live badge + match + insights */}
          <div className="workspace-hifi__tier-company-badges">
            {/* Live / no-live badge */}
            {company.has_live ? (
              <span className="workspace-hifi__tier-live-badge workspace-hifi__tier-live-badge--live">
                <span className="workspace-hifi__tier-live-dot" aria-hidden />
                在招 {company.n_live} 岗
              </span>
            ) : (
              <span className="workspace-hifi__tier-live-badge workspace-hifi__tier-live-badge--none">
                <span className="workspace-hifi__tier-live-dot workspace-hifi__tier-live-dot--none" aria-hidden />
                本季暂无对口岗
              </span>
            )}

            {/* Match tier */}
            <span className={`workspace-hifi__rec-card-tier workspace-hifi__rec-card-tier--${mSuffix}`}>
              {company.match}
            </span>

            {/* Insights badge */}
            {hasIntel && (
              <button
                type="button"
                className="workspace-hifi__tier-insight-badge"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenIntel?.(company.name, { n_insights: company.n_insights });
                }}
                aria-label={`查看 ${company.name} 的 ${company.n_insights} 条同辈情报`}
              >
                情报×{company.n_insights}
              </button>
            )}
          </div>

          {/* Collapsed intro */}
          {!isExpanded && (
            <div className="workspace-hifi__tier-company-intro">
              <span
                className={`workspace-hifi__tier-intro-mark${company.has_live ? ' is-live' : ''}`}
                aria-hidden
              >
                {introPrefix}
              </span>{' '}
              {company.has_live
                ? `在招 ${company.n_live} 个对口岗位`
                : '本季未开对口岗 · 按赛道梯队收录'}
            </div>
          )}
        </div>
      </div>

      {/* Expanded body */}
      {isExpanded && (
        <div className="workspace-hifi__tier-company-expanded">
          {company.has_live ? (
            /* ── LIVE branch ─────────────────────────────────────────── */
            <>
              {/* "为你定制" header block */}
              <div className="workspace-hifi__tier-customised-block">
                <div className="workspace-hifi__tier-customised-head">
                  <span className="workspace-hifi__tier-customised-icon" aria-hidden>✦</span>
                  <span className="workspace-hifi__tier-customised-title">为你定制</span>
                  {hasIntel && (
                    <span className="workspace-hifi__tier-customised-meta">
                      {company.n_insights} 条情报支撑
                    </span>
                  )}
                </div>
                <div className="workspace-hifi__tier-customised-body">
                  在招 {company.n_live} 个对口岗位
                  {company.jobs.length > 0 && (
                    <> · 推荐查看 <strong>{company.jobs[0].title.split('·')[0].trim()}</strong></>
                  )}
                  。
                </div>
              </div>

              {/* Job list */}
              {company.jobs.length > 0 && (
                <div className="workspace-hifi__tier-jobs-list">
                  {company.jobs.map((job) => (
                    <a
                      key={job.id}
                      className="workspace-hifi__tier-job-row"
                      href={job.detail_url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className="workspace-hifi__platform-job-type">{/* campus label */}校</span>
                      <span className="workspace-hifi__tier-job-title">{job.title}</span>
                      <span className="workspace-hifi__tier-job-arrow" aria-hidden>
                        {I.arrowRight(10)}
                      </span>
                    </a>
                  ))}
                </div>
              )}

              {/* Intel CTA */}
              {hasIntel && onOpenIntel && (
                <button
                  type="button"
                  className="workspace-hifi__intel-cta-row"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenIntel(company.name, { n_insights: company.n_insights });
                  }}
                >
                  <span aria-hidden style={{ display: 'inline-flex' }}>{I.book(14)}</span>
                  <span style={{ flex: 1, textAlign: 'left' }}>
                    同辈情报 · {company.n_insights} 条洞察
                  </span>
                  <span aria-hidden style={{ display: 'inline-flex' }}>{I.arrowRight(12)}</span>
                </button>
              )}

              {/* Actions */}
              <div className="workspace-hifi__tier-company-actions">
                <button type="button" className="workspace-hifi__tier-action-btn workspace-hifi__tier-action-btn--primary">
                  {I.target(13)} 针对这家定制
                </button>
                <a
                  className="workspace-hifi__tier-action-btn workspace-hifi__tier-action-btn--ghost"
                  href="#"
                  onClick={(e) => e.preventDefault()}
                >
                  查看岗位
                </a>
              </div>
            </>
          ) : (
            /* ── SKELETON branch (no live jobs) ──────────────────────── */
            <>
              {/* Hiring window block */}
              <div className="workspace-hifi__tier-window-block">
                <span className="workspace-hifi__tier-window-icon" aria-hidden>
                  {I.history(15)}
                </span>
                <div className="workspace-hifi__tier-window-body">
                  <div className="workspace-hifi__tier-window-title">本季未开对口岗 · 往年招聘窗口</div>
                  {company.hiring_window ? (
                    <div className="workspace-hifi__tier-window-text">{company.hiring_window}</div>
                  ) : (
                    <div className="workspace-hifi__tier-window-text">招聘窗口数据整理中</div>
                  )}
                </div>
              </div>

              {/* Intel mini (三维情报) */}
              {company.intel != null ? (
                <IntelMini intel={company.intel} nInsights={company.n_insights} />
              ) : (
                <div className="workspace-hifi__tier-intel-mini-empty">
                  暂无同辈情报 — 这家是按赛道梯队补全的骨架公司，等到有同学讨论会自动汇入。
                </div>
              )}

              {/* Actions */}
              <div className="workspace-hifi__tier-company-actions">
                {hasIntel && onOpenIntel ? (
                  <button
                    type="button"
                    className="workspace-hifi__tier-action-btn workspace-hifi__tier-action-btn--primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenIntel(company.name, { n_insights: company.n_insights });
                    }}
                  >
                    {I.book(13)} 看 {company.n_insights} 条同辈情报
                  </button>
                ) : (
                  <div />
                )}
                <button
                  type="button"
                  className="workspace-hifi__tier-action-btn workspace-hifi__tier-action-btn--ghost"
                >
                  🔔 开岗提醒我
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </article>
  );
}

// ── PlatformTierGroup ────────────────────────────────────────────────────────

export interface PlatformTierGroupProps {
  tier: PlatformSkeletonTier;
  expandedCompanies: Set<string>;
  onToggle: (name: string) => void;
  onOpenIntel?: (company: string, ctx?: { n_insights?: number }) => void;
  isFirst: boolean;
  isLast: boolean;
}

export function PlatformTierGroup({
  tier,
  expandedCompanies,
  onToggle,
  onOpenIntel,
  isFirst,
  isLast,
}: PlatformTierGroupProps) {
  const role = (ROLE_META[tier.role as RoleKey] ?? ROLE_META.floor);
  const liveCount = tier.companies.filter((c) => c.has_live).length;

  return (
    <div className="workspace-hifi__tier-group">
      {/* Ladder spine */}
      <div
        className={[
          'workspace-hifi__tier-group-spine',
          isFirst ? 'is-first' : '',
          isLast ? 'is-last' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        aria-hidden
      />

      {/* Tier node (circle) */}
      <div
        className={`workspace-hifi__tier-group-node ${role.nodeCls}`}
        aria-hidden
      >
        {tier.tier}
      </div>

      {/* Tier header */}
      <div className={`workspace-hifi__tier-group-header ${role.headerBg}`}>
        <span className="workspace-hifi__tier-group-label">{tier.label}</span>
        <span className="workspace-hifi__tier-group-band">{tier.band}</span>
        <span className={`workspace-hifi__tier-group-pill ${role.pillCls}`}>
          <span className="workspace-hifi__tier-group-pill-mark" aria-hidden>
            {role.mark}
          </span>
          {role.tag}
        </span>
        <span className="workspace-hifi__tier-group-count">
          {tier.companies.length} 家
          {liveCount > 0 && (
            <span className="workspace-hifi__tier-group-count-live"> · {liveCount} 在招</span>
          )}
        </span>
      </div>

      {/* Company cards */}
      <div className="workspace-hifi__tier-group-cards">
        {tier.companies.map((c) => (
          <CompanyCard
            key={c.name}
            company={c}
            isExpanded={expandedCompanies.has(c.name)}
            onToggle={onToggle}
            onOpenIntel={onOpenIntel}
            dim={tier.role === 'floor'}
          />
        ))}
      </div>
    </div>
  );
}
