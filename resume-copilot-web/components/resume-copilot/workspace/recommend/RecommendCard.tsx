'use client';

/**
 * RecommendCard — 左栏单张推荐卡 (E-2 + D-1 + D-2/D-3 entry point).
 *
 * 状态:
 *   - 收起:logo / title / 两层分(规则 + LLM 共识) / 一句 "为什么推"
 *   - 展开:3-5 条 ✓ 强匹配 bullet + ✗ 反馈按钮 + 跳详情按钮
 *   - reject 表单:✗ 按钮按下后内嵌一张 inline 反馈卡 (RecommendRejectForm)
 *
 * 受控状态全在父 (`LeftRecommendRail`):同时只允许 1 张展开,所以本组件不
 * 维护 expanded boolean — 由父透传 `isExpanded`。
 */

import { useState } from 'react';
import type { JobState, ResumeRecommendationItem } from '../../types';
import type { RecommendRejectReason } from '../../api';
import { I } from '@/components/hifi/hifi-primitives';
import { RecommendNarrativeSection } from './RecommendNarrativeSection';
import { RecommendRejectForm } from './RecommendRejectForm';

export interface RecommendCardProps {
  item: ResumeRecommendationItem;
  rank: number;
  isExpanded: boolean;
  onToggle: () => void;
  /** Parent handles fetch + FLIP + toast — card just relays. */
  onReject: (reason: RecommendRejectReason, note: string) => Promise<void>;
  /** Plan ② Job plan-mode (2026-05-21): "🎯 针对这家定制" entry. Parent
   *  switches MiddleChatPane into plan-mode tagged with this job_id. */
  onCustomiseForJob?: (item: ResumeRecommendationItem) => void;
  /** Phase 7 — narrative section fetch 需要 sessionId。 */
  sessionId?: number;
  /** P0b — 学生点 "同辈情报" 跳到右栏 IntelDrawer (替换 inline RecommendCardIntelSection). */
  onOpenIntel?: (
    company: string,
    ctx?: { priority?: string | null; xhsCount?: number | null; jobId?: number | null; role?: string | null },
  ) => void;
  /** 岗位推荐 2.0 Task 11 — 三态按钮: 当前求职状态 (saved / applied / 其他)。 */
  currentState?: JobState;
  /** 岗位推荐 2.0 Task 11 — 更新求职状态回调。state='' 清除。 */
  onSetState?: (state: '' | JobState) => Promise<void>;
}

/** 格式化发布/收录时间为可读相对日期字符串。 */
function formatPosted(postedAt?: string, isPublish?: boolean): string {
  if (!postedAt) return '';
  const d = new Date(postedAt);
  if (Number.isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  const rel = days <= 0 ? '今天' : days === 1 ? '昨天' : `${days} 天前`;
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${isPublish ? '发布于' : '收录于'} ${md}（${rel}）`;
}

/** First letter of company for the logo placeholder — there's no logo CDN in
 *  this codebase yet, so we render a colored letter circle. */
function companyInitial(company: string): string {
  const trimmed = (company || '').trim();
  if (!trimmed) return '?';
  // CJK first char is most recognizable; otherwise uppercase first ASCII char.
  const first = trimmed[0];
  return /[A-Za-z0-9]/.test(first) ? first.toUpperCase() : first;
}

function ruleScoreLabel(item: ResumeRecommendationItem): string {
  // 两层分 (D-4 之后 snapshot 删了,只剩 规则 / LLM 共识)
  // - 规则 = base_match_score (objective + preference + base_job ……)
  // - LLM 共识 = enhanced_score - base_match_score 的 delta (LLM 反复打分共识)
  return String(item.base_match_score || 0);
}

function llmScoreLabel(item: ResumeRecommendationItem): string {
  // Show the enhanced score (after LLM consensus rerank) as the "LLM 共识" pillar.
  return String(item.enhanced_score || item.final_score || 0);
}

function primaryReason(item: ResumeRecommendationItem): string {
  // 一句 "为什么推" — 优先 why_recommended[0],没有就 fallback target_direction.
  if (item.why_recommended && item.why_recommended.length > 0) {
    return item.why_recommended[0];
  }
  if (item.target_direction) {
    return `方向:${item.target_direction}`;
  }
  if (item.matched_track_label) {
    return `赛道匹配:${item.matched_track_label}`;
  }
  return '基于赛道 + 经历匹配';
}

function priorityTone(letter: string): 'A' | 'B' | 'C' | 'D' | '' {
  if (letter === 'A' || letter === 'B' || letter === 'C' || letter === 'D') return letter;
  return '';
}

/** 2026-05-22 P4: 把 location 自由文本归一化成 office region chip。
 *  4 个 region 与 parser inferred_offices 对齐(hk/sg/mainland/global),
 *  外加 remote 表 work-from-home。 */
type RegionKey = 'hk' | 'sg' | 'mainland' | 'remote' | 'global';
function regionChip(location: string): { key: RegionKey; label: string } | null {
  const raw = (location || '').trim();
  if (!raw) return null;
  const l = raw.toLowerCase();
  if (/(香港|hong\s*kong|\bhk\b)/i.test(raw)) return { key: 'hk', label: 'HK' };
  if (/(新加坡|singapore|\bsg\b)/i.test(raw)) return { key: 'sg', label: 'SG' };
  if (/(远程|远端|remote|wfh|work\s*from\s*home)/i.test(l)) return { key: 'remote', label: '远程' };
  // 常见大陆城市 — 给个短 label,其他不匹配就当 global 兜底
  const mainlandCities = [
    ['北京', '北京'], ['上海', '上海'], ['深圳', '深圳'], ['广州', '广州'],
    ['杭州', '杭州'], ['南京', '南京'], ['苏州', '苏州'], ['成都', '成都'],
    ['武汉', '武汉'], ['西安', '西安'], ['重庆', '重庆'], ['天津', '天津'],
    ['青岛', '青岛'], ['厦门', '厦门'], ['长沙', '长沙'], ['合肥', '合肥'],
  ];
  for (const [needle, label] of mainlandCities) {
    if (raw.includes(needle)) return { key: 'mainland', label };
  }
  // 兜底:如果含「中国」就当 mainland,否则当 global
  if (/(中国|mainland|china)/i.test(raw)) return { key: 'mainland', label: '大陆' };
  return { key: 'global', label: raw.length > 6 ? raw.slice(0, 6) : raw };
}

export function RecommendCard({
  item,
  rank,
  isExpanded,
  onToggle,
  onReject,
  onCustomiseForJob,
  sessionId,
  onOpenIntel,
  currentState,
  onSetState,
}: RecommendCardProps) {
  const [rejectOpen, setRejectOpen] = useState(false);

  const whyBullets = (item.why_recommended ?? []).slice(0, 5);
  const tone = priorityTone(item.priority_letter ?? '');
  const tierLabel = item.tier_label || '';
  const region = regionChip(item.location);

  const handleHeaderClick = () => {
    if (rejectOpen) {
      // Don't collapse the card while reject form is open — let cancel/submit handle it.
      return;
    }
    onToggle();
  };

  return (
    <article
      className={`workspace-hifi__rec-card${isExpanded ? ' is-expanded' : ''}`}
      data-priority={tone}
      data-job-id={item.job_id}
    >
      <button
        type="button"
        className="workspace-hifi__rec-card-header"
        onClick={handleHeaderClick}
        aria-expanded={isExpanded}
      >
        <div
          className="workspace-hifi__rec-card-logo"
          aria-hidden
          data-priority={tone}
        >
          {companyInitial(item.company)}
        </div>
        <div className="workspace-hifi__rec-card-headline">
          <div className="workspace-hifi__rec-card-rank">{rank}.</div>
          <div className="workspace-hifi__rec-card-title" title={item.job_title}>
            {item.job_title}
          </div>
          <div className="workspace-hifi__rec-card-company">
            <span>{item.company}</span>
            {region && (
              <span
                className={`workspace-hifi__rec-card-region workspace-hifi__rec-card-region--${region.key}`}
                title={item.location}
              >
                <span aria-hidden>📍</span>
                <span>{region.label}</span>
              </span>
            )}
          </div>
        </div>
        <div className="workspace-hifi__rec-card-scores" aria-label="两层分">
          <span
            className="workspace-hifi__rec-card-score workspace-hifi__rec-card-score--rule"
            title="规则分 (基于赛道 + 偏好 + 经历的可解释分)"
          >
            <span className="workspace-hifi__rec-card-score-label">规则</span>
            <span className="workspace-hifi__rec-card-score-value">{ruleScoreLabel(item)}</span>
          </span>
          <span
            className="workspace-hifi__rec-card-score workspace-hifi__rec-card-score--llm"
            title="LLM 共识分 (rerank 后的共识)"
          >
            <span className="workspace-hifi__rec-card-score-label">共识</span>
            <span className="workspace-hifi__rec-card-score-value">{llmScoreLabel(item)}</span>
          </span>
          {tone && (
            <span
              className={`workspace-hifi__rec-card-priority workspace-hifi__rec-card-priority--${tone}`}
              aria-label={`投递分层 ${tone}`}
              title={
                tone === 'A' ? '优先投: 强匹配 + 顶级品牌' :
                tone === 'B' ? '推荐投: 强匹配,或顶级品牌可迁移' :
                tone === 'C' ? '拓展投: 可迁移或信号不足' :
                '不建议: 错位或低质量'
              }
            >
              {tone}
            </span>
          )}
        </div>
      </button>

      {!isExpanded && (
        <div className="workspace-hifi__rec-card-summary">
          {tierLabel && (
            <span
              className={`workspace-hifi__rec-card-tier workspace-hifi__rec-card-tier--${
                tierLabel === '强匹配' ? 'strong' :
                tierLabel === '可迁移' ? 'transfer' : 'gap'
              }`}
            >
              {tierLabel}
            </span>
          )}
          {item.in_skeleton === true && (
            <span
              className="workspace-hifi__rec-card-skeleton-chip workspace-hifi__rec-card-skeleton-chip--in"
              title="该公司在本赛道 GT 梯队骨架内"
            >
              梯队内
            </span>
          )}
          {item.in_skeleton === false && (
            <span
              className="workspace-hifi__rec-card-skeleton-chip workspace-hifi__rec-card-skeleton-chip--out"
              title="该公司不在本赛道 GT 梯队骨架内，属于骨架外机会"
            >
              梯队外机会
            </span>
          )}
          {(item.industry_tags ?? []).slice(0, 2).map((tag) => (
            <span key={tag} className="workspace-hifi__industry-chip">
              {tag}
            </span>
          ))}
          <span className="workspace-hifi__rec-card-why-one">{primaryReason(item)}</span>
          {item.posted_at && (
            <span className="hf-cap">{formatPosted(item.posted_at, item.posted_is_publish)}</span>
          )}
        </div>
      )}

      {isExpanded && (
        <div className="workspace-hifi__rec-card-body">
          {sessionId !== undefined && (
            <RecommendNarrativeSection
              sessionId={sessionId}
              jobId={String(item.job_id)}
              isVisible={isExpanded}
            />
          )}

          <div className="workspace-hifi__rec-card-body-section">
            <div className="workspace-hifi__rec-card-body-title">为什么推</div>
            {whyBullets.length > 0 ? (
              <ul className="workspace-hifi__rec-card-bullets">
                {whyBullets.map((b, idx) => (
                  <li key={`why-${idx}`}>
                    <span aria-hidden className="workspace-hifi__rec-card-bullet-check">✓</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="workspace-hifi__rec-card-bullets-empty">
                还没有详细推荐理由 — 看右侧规则分 + 共识分。
              </p>
            )}
          </div>

          {item.risks && item.risks.length > 0 && (
            <div className="workspace-hifi__rec-card-body-section">
              <div className="workspace-hifi__rec-card-body-title">需要注意</div>
              <ul className="workspace-hifi__rec-card-risks">
                {item.risks.slice(0, 3).map((r, idx) => (
                  <li key={`risk-${idx}`}>
                    <span aria-hidden className="workspace-hifi__rec-card-bullet-warn">!</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {onOpenIntel && (
            <button
              type="button"
              className="workspace-hifi__intel-cta-row"
              onClick={(e) => {
                e.stopPropagation();
                const numericJobId = Number(item.job_id);
                onOpenIntel(item.company, {
                  priority: tone || null,
                  xhsCount: null,
                  jobId: Number.isFinite(numericJobId) ? numericJobId : null,
                  role: item.job_title || null,
                });
              }}
            >
              <span aria-hidden style={{ display: 'inline-flex' }}>{I.book(14)}</span>
              <span style={{ flex: 1, textAlign: 'left' }}>
                查看 {item.company} · 同辈情报抽屉
              </span>
              <span aria-hidden style={{ display: 'inline-flex' }}>{I.arrowRight(12)}</span>
            </button>
          )}

          {!rejectOpen && (
            <div className="workspace-hifi__rec-card-actions">
              {item.detail_url && (
                <a
                  className="workspace-hifi__rec-card-action workspace-hifi__rec-card-action--ghost"
                  href={item.detail_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看岗位
                  <span aria-hidden style={{ display: 'inline-flex' }}>{I.arrowRight(12)}</span>
                </a>
              )}
              {onCustomiseForJob && (
                <button
                  type="button"
                  className="workspace-hifi__rec-card-action workspace-hifi__rec-card-action--customise"
                  onClick={() => onCustomiseForJob(item)}
                  title="进入 coach 把简历针对这家的 JD 定制一遍"
                >
                  <span aria-hidden>🎯</span>
                  <span>针对这家定制</span>
                </button>
              )}
              {onSetState && (
                <>
                  <button
                    type="button"
                    className={`hf-btn sm ${currentState === 'saved' ? 'primary' : 'ghost'}`}
                    onClick={() => onSetState(currentState === 'saved' ? '' : 'saved')}
                  >
                    ★ {currentState === 'saved' ? '已收藏' : '收藏想投'}
                  </button>
                  <button
                    type="button"
                    className={`hf-btn sm ${currentState === 'applied' ? 'primary' : 'sand'}`}
                    onClick={() => onSetState(currentState === 'applied' ? '' : 'applied')}
                  >
                    {currentState === 'applied' ? '已投递 ✓' : '标记已投递'}
                  </button>
                </>
              )}
              <button
                type="button"
                className="workspace-hifi__rec-card-action workspace-hifi__rec-card-action--reject"
                onClick={() => setRejectOpen(true)}
              >
                <span aria-hidden>✗</span>
                <span>不合适</span>
              </button>
            </div>
          )}

          {rejectOpen && (
            <RecommendRejectForm
              onCancel={() => setRejectOpen(false)}
              onSubmit={async (reason, note) => {
                await onReject(reason, note);
                // On success parent removes this card from the list (FLIP exit),
                // so we don't reset rejectOpen — component will unmount.
              }}
            />
          )}
        </div>
      )}
    </article>
  );
}
