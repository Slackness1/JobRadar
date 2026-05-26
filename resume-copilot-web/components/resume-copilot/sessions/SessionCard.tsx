'use client';

/**
 * SessionCard — one resume session in the Sessions page grid.
 *
 * Structure (top-down):
 *   ResumeThumb (visual anchor)
 *   name row + track chip
 *   4-stat grid (公司 / 岗位 / 情报 / 改写) — P0a 占位 "0" or "—"
 *   top picks chips (P0a 占位 — 空数组)
 *   时间 row (创建 / 更新)
 *   actions (进入工作台 / 切换到此会话 / ⋯)
 *
 * Data shape mirrors the design's HFSessionCard (`s: { id, name, current, ... }`)
 * but uses real backend types (ResumeCopilotSessionListItem) + a few derived
 * fields (trackTitle / trackIcon / coverColor) that P0a defaults sensibly.
 */

import { I } from '@/components/hifi/hifi-primitives';
import type { ResumeCopilotSessionListItem } from '../types';

import { ResumeThumb } from './ResumeThumb';

type IconKey =
  | 'target'
  | 'barChart'
  | 'briefcase'
  | 'trending'
  | 'users'
  | 'radar';

export interface SessionCardData extends ResumeCopilotSessionListItem {
  /** Whether this is the current session (URL ?sessionId match). */
  isCurrent?: boolean;
  /** Pretty track title (derived — defaults to "尚未选定赛道"). */
  trackTitle?: string;
  /** Icon key for the track chip (defaults to 'target'). */
  trackIcon?: IconKey;
  /** Background gradient color for the thumb corner accent. */
  coverColor?: string;
  /** Stat aggregates — P0a 占位都填 0 (后续 P2 真接). */
  stats?: {
    companies: number;
    jobs: number;
    intel: number;
    rewrites: number;
  };
  /** Top picks chip labels — P0a 占位空数组 (后续 P2 真接). */
  topPicks?: string[];
}

interface SessionCardProps {
  data: SessionCardData;
  /** Click on the card body / "切换到此会话" button. */
  onSwitch: (sessionId: number) => void;
  /** Click on "⋯" — opens action menu (P0a: no-op stub). */
  onMore?: (sessionId: number) => void;
}

function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return iso;
  const diffMs = Date.now() - ts;
  if (diffMs < 0) return '刚刚';
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diffMs < 5 * minute) return '刚刚';
  if (diffMs < hour) return `${Math.floor(diffMs / minute)} 分钟前`;
  if (diffMs < day) return `${Math.floor(diffMs / hour)} 小时前`;
  if (diffMs < 7 * day) return `${Math.floor(diffMs / day)} 天前`;
  if (diffMs < 30 * day) return `${Math.floor(diffMs / day / 7)} 周前`;
  if (diffMs < 365 * day) return `${Math.floor(diffMs / day / 30)} 月前`;
  return new Date(iso).toLocaleDateString('zh-CN');
}

const ICON_FALLBACK = I.target;

function renderTrackIcon(key: IconKey | undefined, size = 13) {
  const fn = key && I[key as keyof typeof I];
  if (typeof fn === 'function') {
    return (fn as (s?: number) => React.ReactElement)(size);
  }
  return ICON_FALLBACK(size);
}

export function SessionCard({ data, onSwitch, onMore }: SessionCardProps) {
  const {
    id,
    name,
    file_name,
    is_archived,
    isCurrent = false,
    trackTitle = '尚未选定赛道',
    trackIcon = 'target',
    coverColor = 'var(--terracotta-wash)',
    stats,
    topPicks = [],
    created_at,
    updated_at,
  } = data;

  const displayName = (name && name.trim()) || file_name || `会话 #${id}`;
  const thumbTag = trackTitle.split('·').pop()?.trim() || 'JobRadar';

  // P0a stats 占位 — 不做聚合,默认 0 (前端 hard-code，符合任务规范)。
  const companies = stats?.companies ?? 0;
  const jobs = stats?.jobs ?? 0;
  const intel = stats?.intel ?? 0;
  const rewrites = stats?.rewrites ?? 0;

  const handleEnter = () => onSwitch(id);
  const handleMore = (e: React.MouseEvent) => {
    e.stopPropagation();
    onMore?.(id);
  };

  return (
    <div
      className="rc-sessions__card"
      data-current={isCurrent ? 'true' : 'false'}
      data-archived={is_archived ? 'true' : 'false'}
      data-testid="rc-session-card"
    >
      {isCurrent ? (
        <span className="rc-sessions__current-badge">
          {I.check(10)} 当前会话
        </span>
      ) : null}
      {is_archived ? (
        <span className="rc-sessions__archived-badge">归档</span>
      ) : null}

      <ResumeThumb accentColor={coverColor} name={displayName} tag={thumbTag} />

      <div className="rc-sessions__card-body">
        <div>
          <div className="rc-sessions__card-name-row">
            <span className="rc-sessions__card-name" title={displayName}>
              {displayName}
            </span>
          </div>
          <div style={{ marginTop: 4 }}>
            <span className="rc-sessions__track-chip" data-size="sm">
              <span className="rc-sessions__track-chip-icon" aria-hidden>
                {renderTrackIcon(trackIcon, 11)}
              </span>
              {trackTitle}
            </span>
          </div>
        </div>

        <div className="rc-sessions__card-stats">
          {[
            ['公司', companies],
            ['岗位', jobs],
            ['情报', intel],
            ['改写', rewrites],
          ].map(([label, value]) => (
            <div key={String(label)} className="rc-sessions__card-stat">
              <div className="rc-sessions__card-stat-value">
                {value || '—'}
              </div>
              <div className="rc-sessions__card-stat-label">{label}</div>
            </div>
          ))}
        </div>

        <div>
          <div className="hf-overline" style={{ fontSize: 9, marginBottom: 4 }}>
            Top 推荐
          </div>
          {topPicks.length > 0 ? (
            <div className="rc-sessions__card-toppicks">
              {topPicks.slice(0, 4).map((p) => (
                <span key={p} className="rc-sessions__card-toppick">
                  {p}
                </span>
              ))}
            </div>
          ) : (
            <div className="rc-sessions__card-toppicks-empty">
              暂无 — 进入工作台生成
            </div>
          )}
        </div>

        <div className="rc-sessions__card-time">
          <span>创建 · {formatRelative(created_at)}</span>
          <span className="rc-sessions__card-time-updated">
            {I.history(11)} {formatRelative(updated_at)}
          </span>
        </div>

        <div className="rc-sessions__card-actions">
          {isCurrent ? (
            <button
              type="button"
              onClick={handleEnter}
              className="hf-btn primary sm rc-sessions__card-action-primary"
              style={{
                display: 'inline-flex',
                gap: 6,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {I.arrowRight(13)} 进入工作台
            </button>
          ) : (
            <button
              type="button"
              onClick={handleEnter}
              className="hf-btn ghost sm rc-sessions__card-action-primary"
              style={{
                display: 'inline-flex',
                gap: 6,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              切换到此会话 {I.arrowRight(12)}
            </button>
          )}
          <button
            type="button"
            onClick={handleMore}
            className="hf-btn ghost sm rc-sessions__card-action-more"
            title="更多"
            aria-label="更多操作"
          >
            ⋯
          </button>
        </div>
      </div>
    </div>
  );
}
