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
// backend/app/services/taxonomy/canonical.py.
// 2026-05-26 (cc4636a / Fix-1): 升级到 v2 13 canonical — 原 10 个里有 3 个
// 过宽,被拆为各 2;咨询 2 个合并重组。`key` 必须严格匹配 BE canonical 名
// (字符级,含中文标点),否则 SAIF 重罚逻辑命中不到 → 推荐里出现互联网算法 /
// 外企营销混入。改前必须读 backend/app/services/taxonomy/tracks.yaml。
export const TRACKS: Array<{ key: string; label: string; blurb: string; icon: string }> = [
  {
    key: '公募/资管·投研',
    label: '公募/资管·投研 · long-only 基本面',
    icon: '📊',
    blurb: '公募基金 / 保险资管 / 券商资管 / 银行理财子 — SAIF placement 最大头',
  },
  {
    key: '私募·基本面',
    label: '私募·基本面 · 长短仓',
    icon: '🎯',
    blurb: '阳光私募 / 对冲基金 — 高毅 / 景林 / 重阳 / 淡水泉',
  },
  {
    key: '量化',
    label: '量化 · 对冲/做市',
    icon: '📈',
    blurb: '量化私募 / 对冲基金 — 九坤 / 乾象 / 锐天 / Point72',
  },
  {
    key: '卖方研究',
    label: '卖方研究 · 券商行研',
    icon: '🔬',
    blurb: '券商研究所行业研究员 — 中信 / 中金 / 中信建投 / 招商证券',
  },
  {
    key: 'S&T·FICC·衍生品',
    label: 'S&T·FICC·衍生品 · 销售交易',
    icon: '💱',
    blurb: '销售交易 / 固收 / 衍生品 — 高盛 GBM / 大摩 / 中金 FICC',
  },
  {
    key: '投行·并购·资本市场',
    label: '投行·并购·资本市场 · IBD/M&A/ECM',
    icon: '💼',
    blurb: 'IBD / M&A / ECM / DCM — 中金 / 中信 / 高盛 / 摩根',
  },
  {
    key: '一级股权·PE/VC',
    label: '一级股权·PE/VC · 成长/buyout',
    icon: '🏛️',
    blurb: 'PE / VC / FA — 高瓴 / 凯雷 / KKR / 红杉 / 弘毅',
  },
  {
    key: '银行·总行核心',
    label: '银行·总行核心 · 管培/FMT',
    icon: '🏦',
    blurb: '国有大行 / 股份制 / 外资行总行 — 管培 / FMT / 风险条线',
  },
  {
    key: '监管·体制内',
    label: '监管·体制内 · 央行/证监',
    icon: '⚖️',
    blurb: '央行 / 证监会 / 交易所 / 国央企财金 / 公务员',
  },
  {
    key: '金融科技',
    label: '金融科技 · 蚂蚁/微众',
    icon: '⚙️',
    blurb: 'FinTech 数据 / 算法 / 风控 — 蚂蚁 / 微众 / 度小满 / 京东数科',
  },
  {
    key: '咨询·MBB+Tier2',
    label: '咨询·MBB+Tier2 · 战略咨询',
    icon: '🧠',
    blurb: 'McKinsey / BCG / Bain / Roland Berger / Oliver Wyman / 四大 FDD',
  },
  {
    key: '企业战略·管培·实业金融',
    label: '企业战略·管培·实业金融',
    icon: '🎓',
    blurb: '公司战略 / 管培生 / 实业产投 / 央国企财金 — 非金融行业的金融岗',
  },
  {
    key: '大宗·能源',
    label: '大宗·能源 · 商品/期货',
    icon: '🛢️',
    blurb: '大宗商品 / 能源 trading — LDC / Cargill / 托克 / 中石油国际',
  },
  {
    // 互联网/AI 产品 — 非金融 canonical, 单列一个可选赛道(后端 EXTRA_SELECTABLE_TRACKS
    // 放行, 不进 CANONICAL_FINANCE_TRACKS 以免触发金融 SAIF 重罚/coverage 校验)。
    // 选它 → preferred_tracks 经 subcats_for_tracks 展开成 10 个互联网/AI sub_cat,
    // 推荐/梯队/简历方法论(InternetResumeProvider)全部联动激活。
    key: '互联网/AI 产品',
    label: '互联网/AI 产品 · 用增/商业化/AI PM',
    icon: '🚀',
    blurb: '字节 / 腾讯 / 阿里 / 美团 / 小红书 + AI 大模型公司 — 用户增长 / 商业化 / 策略数据 / ToB / AI 产品 + AI 应用开发',
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
          13 个 SAIF MF 主流赛道。选了赛道后系统会重新生成推荐 + coach 按此赛道反问。
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
