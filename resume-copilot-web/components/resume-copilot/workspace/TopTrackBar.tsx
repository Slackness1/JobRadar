'use client';

/**
 * TopTrackBar — 顶部赛道 sticky bar (E-5 + P0a redesign 2026-05-26).
 *
 * P0a HiFi redesign — switched from the simple "当前赛道 · 适配度" lozenge to
 * the full HFWSTopBar:
 *
 *   左:  HFLogo + breadcrumb + session-chip (avatar + name + chevron → SessionMenu)
 *   中:  (Coach 模式徽章占位 — P0b 真接,P0a 不渲染)
 *   右:  Track chip (点开 TrackPickerModal) + N 公司 · M 岗 计数 + 导出按钮 + user avatar
 *
 * Props 接口向后兼容 (trackName / fitScore / onChangeTrack 仍然支持),新增 session /
 * job-count / export / sessionId 等 — 所有新 props 都 optional,FE 老 caller 不破。
 */

import { useState } from 'react';

import { HFBtn, HFLogo, I } from '@/components/hifi/hifi-primitives';

import { SessionMenu } from './SessionMenu';
import type { ResumeCopilotSession, ResumeRecommendationResult } from '../types';

export interface TopTrackBarProps {
  // ── Track + score (legacy E-5 signature, kept stable) ─────────────────────
  /** 当前选中的赛道名,例如 "公募行研·买方基本面"。null = 尚未选定 */
  trackName: string | null;
  /** 适配度评分 0-10。null = 尚未计算(P2-1 之前都是 placeholder) */
  fitScore: number | null;
  /** 点击「换赛道」chip 时回调 — 父打开 TrackPickerModal */
  onChangeTrack?: () => void;

  // ── P0a additions (all optional — workspace-shell will pass them) ─────────
  /** 当前 session — 用于 session-chip 显示名 + SessionMenu 高亮 */
  session?: ResumeCopilotSession | null;
  /** 推荐结果 — 用来算 "N 公司 · M 岗" 计数 */
  recommendations?: ResumeRecommendationResult | null;
  /** 「导出」按钮 callback (loading 状态分开) */
  onExport?: () => void;
  isExporting?: boolean;
  canExport?: boolean;
  // ── Fix-1 (2026-05-26): Coach 模式徽章 ────────────────────────────────────
  /** 非 null 时顶栏中部显 terracotta 胶囊 "🎯 Coach 模式 · 公司名"。
   *  对齐设计 `hifi-ws-app.jsx::HFWSTopBar` 第 129-150 行 — P1 漏画了。 */
  coachCompany?: string | null;
}

function countCompanies(recs: ResumeRecommendationResult | null | undefined): number {
  if (!recs?.items?.length) return 0;
  const set = new Set<string>();
  for (const it of recs.items) {
    const c = (it.company || '').trim();
    if (c) set.add(c);
  }
  return set.size;
}

function countJobs(recs: ResumeRecommendationResult | null | undefined): number {
  return recs?.items?.length ?? 0;
}

function sessionShortLabel(session: ResumeCopilotSession | null | undefined): string {
  if (!session) return '未选会话';
  const raw = (session.name && session.name.trim()) || session.file_name || `会话 #${session.id}`;
  return raw.length > 18 ? `${raw.slice(0, 16)}…` : raw;
}

function sessionInitial(session: ResumeCopilotSession | null | undefined): string {
  const raw = (session?.name && session.name.trim()) || session?.file_name || '?';
  // First non-whitespace char of session name (Chinese-friendly).
  const ch = raw.replace(/^\s+/, '').charAt(0);
  return ch ? ch.toUpperCase() : '?';
}

export function TopTrackBar({
  trackName,
  fitScore,
  onChangeTrack,
  session,
  recommendations,
  onExport,
  isExporting,
  canExport,
  coachCompany,
}: TopTrackBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const displayTrack = trackName ?? '尚未选定赛道';
  const scoreLabel = fitScore != null ? fitScore.toFixed(1) : '--';

  const companies = countCompanies(recommendations);
  const jobs = countJobs(recommendations);

  return (
    <div className="workspace-hifi__top-bar" data-testid="workspace-top-bar">
      {/* Left: logo + breadcrumb + session chip */}
      <span className="workspace-hifi__top-bar-logo">
        <HFLogo size="sm" />
      </span>
      <span className="workspace-hifi__top-bar-crumb-sep" aria-hidden>/</span>
      <span className="workspace-hifi__top-bar-crumb">Resume Copilot</span>
      <span className="workspace-hifi__top-bar-crumb-sep" aria-hidden>/</span>

      <button
        type="button"
        className="workspace-hifi__top-bar-session-chip"
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        onClick={() => setMenuOpen((v) => !v)}
        data-testid="workspace-session-chip"
      >
        <span className="workspace-hifi__top-bar-session-avatar" aria-hidden>
          {sessionInitial(session)}
        </span>
        <span className="workspace-hifi__top-bar-session-name">
          {sessionShortLabel(session)}
        </span>
        <span className="workspace-hifi__top-bar-session-chevron" aria-hidden>
          {I.chevron(12)}
        </span>
        <SessionMenu
          open={menuOpen}
          currentSessionId={session?.id ?? null}
          onClose={() => setMenuOpen(false)}
        />
      </button>

      {/* Fix-1 (2026-05-26): Coach 模式徽章 — 对齐设计 hifi-ws-app.jsx:129-150 */}
      {coachCompany ? (
        <span
          className="workspace-hifi__top-bar-coach-badge"
          aria-label={`当前 Coach 模式 · ${coachCompany}`}
        >
          <span className="workspace-hifi__top-bar-coach-badge-icon" aria-hidden>
            {I.target(14)}
          </span>
          <span className="workspace-hifi__top-bar-coach-badge-label">Coach 模式</span>
          <span className="workspace-hifi__top-bar-coach-badge-sep" aria-hidden>
            ·
          </span>
          <span className="workspace-hifi__top-bar-coach-badge-company">
            {coachCompany}
          </span>
        </span>
      ) : null}

      <div className="workspace-hifi__top-bar-actions">
        {/* Right: track chip → TrackPickerModal */}
        <button
          type="button"
          className="workspace-hifi__top-bar-track-chip"
          onClick={onChangeTrack}
          data-testid="workspace-track-chip"
          title="点击切换赛道"
        >
          <span className="workspace-hifi__top-bar-track-icon" aria-hidden>
            {I.target(12)}
          </span>
          <span>{displayTrack}</span>
          <span style={{ color: 'var(--stone)', marginLeft: 4 }}>
            · 适配度{' '}
            <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{scoreLabel}</span>
            <span style={{ color: 'var(--stone)' }}>/10</span>
          </span>
        </button>

        {/* Count: 公司 · 岗 */}
        <span className="workspace-hifi__top-bar-count" aria-label="推荐覆盖">
          <span className="workspace-hifi__top-bar-count-num">{companies}</span>
          <span>公司 ·</span>
          <span className="workspace-hifi__top-bar-count-num">{jobs}</span>
          <span>岗</span>
        </span>

        {/* Export */}
        {onExport ? (
          <HFBtn
            variant="ghost"
            size="sm"
            onClick={onExport}
            disabled={!canExport || !!isExporting}
            icon={I.upload(13)}
          >
            {isExporting ? '导出中…' : '导出'}
          </HFBtn>
        ) : null}

        {/* User avatar */}
        <div className="workspace-hifi__top-bar-user-avatar" aria-hidden>
          {I.user(14)}
        </div>
      </div>
    </div>
  );
}
