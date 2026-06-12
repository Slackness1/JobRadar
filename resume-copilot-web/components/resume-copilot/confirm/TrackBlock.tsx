'use client';

/**
 * TrackBlock — "想准备的赛道" card for the Confirm Profile page (P2).
 *
 * Renders 10 canonical SAIF MF tracks as a 2-col chip grid (pill chip for the
 * active track + plain text for the rest, matching design hifi-ws-tracks.jsx
 * `HFTrackList`). Right-hand "全部 10 个 →" link opens a selection modal that
 * shows all 10 tracks as full cards (matching `HFTrackModal`).
 *
 * The modal is *selection-only* — it just calls `onChange(key)` and closes.
 * Persistence (PUT /preferences) happens batched in the parent panel when the
 * student clicks "确认进入工作台". This differs from the workspace's
 * `TrackPickerModal` (which auto-PUTs + re-generates on every change).
 *
 * Track icons come from `components/hifi/hifi-primitives.tsx` `I.{name}`. Falls
 * back to `I.target` if the icon name isn't registered.
 *
 * Scope: `.hf .rc-confirm`.
 */

import { useState } from 'react';

import { I } from '@/components/hifi/hifi-primitives';
import { TRACKS } from '../workspace/TrackPickerModal';

// `TRACKS` exports `{ key, label, blurb, icon }` from TrackPickerModal — `icon`
// there is an emoji glyph for the workspace overlay. For the new confirm page
// we want SVG icons (per design). Map track key → I.{name} icon name. Keep
// keys in sync with backend CANONICAL_FINANCE_TRACKS.
//
// Missing icons (microscope / landmark / scale / cpu / barrel) fall back to
// available primitives — chosen to read semantically close. Adding new SVGs
// to hifi-primitives is out of scope for P2.
const TRACK_ICON: Record<string, keyof typeof I> = {
  '二级买方·基本面': 'barChart',
  '量化': 'trending',
  '一级市场': 'briefcase',
  '卖方研究·S&T': 'search',     // microscope unavailable → 用 search 近义
  '银行·总行核心': 'shield',    // landmark unavailable → 用 shield 近义
  '监管·体制内': 'shield',      // scale unavailable → 用 shield 近义
  '金融科技': 'bolt',           // cpu unavailable → 用 bolt 近义
  '管理咨询·MBB': 'users',
  '战略咨询': 'target',
  '大宗·能源': 'pin',           // barrel unavailable → 用 pin 近义
};

// 把 `TrackPickerModal.TRACKS.label` (含通俗名) 拆出 title + kind 两段, 让
// chip 显得清爽 (设计上 active chip 主标 + " · " 副 kind).
function splitLabel(label: string): { title: string; kind: string } {
  // label 形如 "二级买方·基本面 · 公募/私募"
  const idx = label.indexOf(' · ');
  if (idx === -1) return { title: label, kind: '' };
  return { title: label.slice(0, idx), kind: label.slice(idx + 3) };
}

export interface TrackBlockProps {
  /** Currently selected track key (canonical Chinese name). */
  activeTrackKey: string | null;
  /** Called when student clicks any chip OR confirms inside the modal. */
  onChange: (key: string) => void;
  /** Whether each track was inferred from the resume by the AI. */
  inferredKeys: Set<string>;
  disabled?: boolean;
}

export function TrackBlock({ activeTrackKey, onChange, inferredKeys, disabled }: TrackBlockProps) {
  const [modalOpen, setModalOpen] = useState(false);
  return (
    <div className="rc-confirm__card rc-confirm__block">
      <div className="rc-confirm__block-head">
        <h3 className="rc-confirm__block-title">想准备的赛道</h3>
        <span className="rc-confirm__block-hint">AI 已根据简历预先勾选, 你可以加 / 减</span>
        <button
          type="button"
          className="rc-confirm__block-link"
          onClick={() => setModalOpen(true)}
          disabled={disabled}
        >
          全部 {TRACKS.length} 个 {I.arrowRight(12)}
        </button>
      </div>
      <div className="rc-confirm__track-grid">
        {TRACKS.map((t) => {
          const { title, kind } = splitLabel(t.label);
          const isActive = activeTrackKey === t.key;
          const inferred = inferredKeys.has(t.key);
          const iconName = TRACK_ICON[t.key] ?? 'target';
          const renderIcon = I[iconName] as ((s?: number) => React.ReactNode) | undefined;
          return (
            <button
              key={t.key}
              type="button"
              role="radio"
              aria-checked={isActive}
              className={`rc-confirm__track-chip${isActive ? ' is-active' : ''}`}
              onClick={() => onChange(t.key)}
              disabled={disabled}
              title={t.blurb}
            >
              <span className="rc-confirm__track-chip-icon">
                {renderIcon ? renderIcon(16) : I.target(16)}
              </span>
              <span>
                {title}
                {kind ? <span className="rc-confirm__track-chip-kind"> · {kind}</span> : null}
              </span>
              {isActive && inferred && <span className="rc-confirm__track-chip-badge">AI</span>}
            </button>
          );
        })}
      </div>
      {modalOpen && (
        <TrackSelectionModal
          // `key` on the parent's active track resets the modal's internal
          // selected state every time it opens — avoids needing useEffect to
          // re-sync (which collides with React 19's set-state-in-effect lint).
          key={activeTrackKey ?? '__none__'}
          currentTrackKey={activeTrackKey}
          onClose={() => setModalOpen(false)}
          onConfirm={(key) => {
            onChange(key);
            setModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TrackSelectionModal — selection-only modal (no auto-PUT + no /generate).
// Differs from `workspace/TrackPickerModal` which auto-saves on confirm.
// ─────────────────────────────────────────────────────────────────────────────

interface TrackSelectionModalProps {
  currentTrackKey: string | null;
  onClose: () => void;
  onConfirm: (key: string) => void;
}

/**
 * Modal is mounted only when open=true (parent gates with `{modalOpen && …}`)
 * and rekeys on every reopen via `key={currentTrackKey}` — so internal state
 * is naturally reset each time. No effect needed.
 */
function TrackSelectionModal({
  currentTrackKey,
  onClose,
  onConfirm,
}: TrackSelectionModalProps) {
  const [selected, setSelected] = useState<string | null>(currentTrackKey);

  return (
    <div
      className="rc-confirm__modal-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="rc-confirm__modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="rc-confirm__modal-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="rc-confirm__modal-title">选择你想准备的赛道</h2>
            <div className="rc-confirm__modal-sub">
              {TRACKS.length} 个赛道（金融 + 互联网/AI）。选了赛道后系统会按此赛道给推荐 + Coach 反问。
            </div>
          </div>
          <button
            type="button"
            className="rc-confirm__modal-close"
            onClick={onClose}
            aria-label="关闭"
          >
            {I.close(15)}
          </button>
        </div>

        <div className="rc-confirm__modal-grid">
          {TRACKS.map((t) => {
            const { title, kind } = splitLabel(t.label);
            const isSelected = selected === t.key;
            const isCurrent = currentTrackKey === t.key;
            const iconName = TRACK_ICON[t.key] ?? 'target';
            const renderIcon = I[iconName] as ((s?: number) => React.ReactNode) | undefined;
            return (
              <button
                key={t.key}
                type="button"
                className={`rc-confirm__modal-card-item${isSelected ? ' is-selected' : ''}`}
                onClick={() => setSelected(t.key)}
              >
                <span className="rc-confirm__modal-card-icon">
                  {renderIcon ? renderIcon(20) : I.target(20)}
                </span>
                <div className="rc-confirm__modal-card-body">
                  <div className="rc-confirm__modal-card-title">
                    <span className="rc-confirm__modal-card-title-text">{title}</span>
                    {kind ? (
                      <span style={{ fontSize: 12, color: 'var(--olive)' }}>· {kind}</span>
                    ) : null}
                  </div>
                  <div className="rc-confirm__modal-card-blurb">{t.blurb}</div>
                </div>
                {isCurrent && <span className="rc-confirm__modal-current-tag">当前</span>}
              </button>
            );
          })}
        </div>

        <div className="rc-confirm__modal-foot">
          <div className="rc-confirm__modal-foot-status">
            <span className="rc-confirm__modal-foot-status-name">
              {TRACKS.find((t) => t.key === selected)?.label ?? '—'}
            </span>
          </div>
          <button type="button" className="hf-btn ghost" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="hf-btn primary"
            disabled={!selected}
            onClick={() => selected && onConfirm(selected)}
            style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}
          >
            {I.check(14)} 确认选这个赛道
          </button>
        </div>
      </div>
    </div>
  );
}
