'use client';

/**
 * TrackPickerModal — overlay that lets the student pick (or change) the
 * canonical 赛道 they're preparing for.
 *
 * 2026-05-21: fixes the broken "换赛道" button — previously TopTrackBar's
 * onChangeTrack flipped an editorOpen state that no component rendered.
 *
 * UX:
 *   - 10 canonical SAIF MF finance tracks (cards), one-tap selects
 *   - selected → PUT /preferences with preferred_tracks: [<track>]
 *   - re-trigger /generate so recommendations refresh against new track
 *   - close modal + parent re-polls session
 */

import { useState } from 'react';
import {
  postResumeCopilotGenerate,
  putResumeCopilotPreferences,
} from '../api';
import { EMPTY_PREFERENCES, type ResumePreferencePayload } from '../types';

// Keep in sync with backend CANONICAL_FINANCE_TRACKS in
// backend/app/services/taxonomy/canonical.py
// 2026-05-21: label 直接把"通俗名"加上, 让学生看 chip 名一眼能识别
// (e.g. 看到"一级市场"不知道是 IBD; 看到"一级市场 · 投行/PE/VC"立刻懂)。
// `key` 仍然是 canonical 名跟 BE 对齐, 别动。
export const TRACKS: Array<{ key: string; label: string; blurb: string; icon: string }> = [
  {
    key: '二级买方·基本面',
    label: '二级买方·基本面 · 公募/私募',
    icon: '📊',
    blurb: '公募 / 私募 / 资管 / 银行理财子 — 头部流量, 2025 MF 45% 去这',
  },
  {
    key: '量化',
    label: '量化 · 对冲/做市',
    icon: '📈',
    blurb: '量化私募 / 对冲基金 — 九坤 / 乾象 / 锐天 / Point72',
  },
  {
    key: '一级市场',
    label: '一级市场 · 投行/PE/VC',
    icon: '💼',
    blurb: '投行 IBD / PE / VC / FA — 中金 / 高瓴 / 凯雷 / 弘毅',
  },
  {
    key: '卖方研究·S&T',
    label: '卖方研究·S&T · 券商/销售交易',
    icon: '🔬',
    blurb: '券商研究所 + 销售交易 + FICC — 中信 / 中金 / 高盛 GBM',
  },
  {
    key: '银行·总行核心',
    label: '银行·总行核心 · 管培/FMT',
    icon: '🏦',
    blurb: '国有大行 / 股份制 / 外资行 — 总行管培 / FMT',
  },
  {
    key: '监管·体制内',
    label: '监管·体制内 · 央行/证监/国央企',
    icon: '🏛️',
    blurb: '央行 / 证监会 / 交易所 / 国央企 / 公务员',
  },
  {
    key: '金融科技',
    label: '金融科技 · 蚂蚁/微众',
    icon: '⚙️',
    blurb: 'FinTech 数据 / 算法 — 蚂蚁 / 微众 / 度小满',
  },
  {
    key: '管理咨询·MBB',
    label: '管理咨询·MBB · 四大',
    icon: '🧠',
    blurb: 'McKinsey / BCG / Bain / 四大 FDD',
  },
  {
    key: '战略咨询',
    label: '战略咨询 · 公司战略',
    icon: '🎯',
    blurb: '公司战略 / 通用咨询 — 非金融行业聚焦的 strategy 岗',
  },
  {
    key: '大宗·能源',
    label: '大宗·能源 · 商品/期货',
    icon: '🛢️',
    blurb: '大宗商品 / 能源 — LDC / Cargill / 托克 / 中石油国际',
  },
];

export interface TrackPickerModalProps {
  open: boolean;
  sessionId: number | null;
  currentTrack?: string | null;
  /** Existing session preferences to merge with (so we don't reset other fields). */
  currentPreferences?: ResumePreferencePayload | null;
  /** Called after preferences saved + /generate triggered, so parent re-polls. */
  onChanged: () => void;
  /** Close without saving. */
  onClose: () => void;
}

export function TrackPickerModal({
  open,
  sessionId,
  currentTrack,
  currentPreferences,
  onChanged,
  onClose,
}: TrackPickerModalProps) {
  const [selected, setSelected] = useState<string | null>(currentTrack ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleConfirm = async () => {
    if (!sessionId || !selected) return;
    setBusy(true);
    setError(null);
    try {
      const base = currentPreferences ?? EMPTY_PREFERENCES;
      await putResumeCopilotPreferences(sessionId, {
        ...base,
        preferred_tracks: [selected],
        all_skipped: false,
      });
      await postResumeCopilotGenerate(sessionId);
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="workspace-hifi__track-picker-backdrop" role="dialog" aria-modal="true">
      <div className="workspace-hifi__track-picker-card">
        <header className="workspace-hifi__track-picker-head">
          <h2 className="workspace-hifi__track-picker-title">选择你想准备的赛道</h2>
          <button
            type="button"
            className="workspace-hifi__track-picker-close"
            onClick={onClose}
            aria-label="关闭"
          >
            ✕
          </button>
        </header>
        <p className="workspace-hifi__track-picker-sub">
          10 个 SAIF MF 主流赛道。选了赛道后系统会重新生成推荐 + coach 按此赛道反问。
        </p>
        <div className="workspace-hifi__track-picker-grid">
          {TRACKS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`workspace-hifi__track-picker-item${
                selected === t.key ? ' is-selected' : ''
              }${currentTrack === t.key ? ' is-current' : ''}`}
              onClick={() => setSelected(t.key)}
              disabled={busy}
            >
              <span className="workspace-hifi__track-picker-icon" aria-hidden>{t.icon}</span>
              <div className="workspace-hifi__track-picker-text">
                <span className="workspace-hifi__track-picker-name">{t.label}</span>
                <span className="workspace-hifi__track-picker-blurb">{t.blurb}</span>
              </div>
              {currentTrack === t.key && (
                <span className="workspace-hifi__track-picker-current-tag">当前</span>
              )}
            </button>
          ))}
        </div>
        {error && (
          <div className="workspace-hifi__track-picker-error" role="alert">
            出错了:{error}
          </div>
        )}
        <footer className="workspace-hifi__track-picker-footer">
          <button
            type="button"
            className="workspace-hifi__track-picker-btn"
            onClick={onClose}
            disabled={busy}
          >
            取消
          </button>
          <button
            type="button"
            className="workspace-hifi__track-picker-btn workspace-hifi__track-picker-btn--primary"
            onClick={handleConfirm}
            disabled={busy || !selected || !sessionId}
          >
            {busy ? '保存中…' : '确认 + 重新生成推荐'}
          </button>
        </footer>
      </div>
    </div>
  );
}
