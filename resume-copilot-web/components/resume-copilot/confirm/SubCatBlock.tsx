'use client';

/**
 * SubCatBlock — 细分方向两级勾选卡片 (Phase G Task 6)
 *
 * Renders LLM-suggested sub-categories under each selected track as controlled
 * checkboxes. Initial checked set is seeded from `suggested === true` entries,
 * sent back by POST /sub-cat-suggestions. The student can add / remove freely.
 *
 * State ownership: `confirmedSubCats` is lifted to the parent
 * (ConfirmProfilePanel) so Task 7 can include it in the PUT /preferences
 * payload without any prop drilling or context.
 *
 * Scope: `.hf .rc-confirm`.
 */

import type { SubCatTrackOptions } from '../types';

export interface SubCatBlockProps {
  /** Options returned by the backend (one entry per selected track). */
  options: SubCatTrackOptions[];
  /** Controlled: keys currently checked. */
  confirmedSubCats: string[];
  /** Called when a checkbox is toggled (add / remove). */
  onToggle: (key: string) => void;
  disabled?: boolean;
  /** True while the sub-cat fetch is in flight (shows a loading hint). */
  loading?: boolean;
}

export function SubCatBlock({
  options,
  confirmedSubCats,
  onToggle,
  disabled,
  loading,
}: SubCatBlockProps) {
  // Don't render the card if there are no tracks selected yet.
  if (!loading && options.length === 0) return null;

  const total = options.reduce((n, o) => n + o.sub_cats.length, 0);
  const checked = confirmedSubCats.length;

  return (
    <div className="rc-confirm__card rc-confirm__block">
      <div className="rc-confirm__block-head">
        <h3 className="rc-confirm__block-title">细分方向</h3>
        <span className="rc-confirm__block-hint">
          {loading
            ? 'AI 正在生成细分方向建议…'
            : `细分方向 · 已选 ${checked}/${total}`}
        </span>
      </div>

      {loading ? (
        <div className="rc-confirm__subcat-loading">
          <span className="hf-spin" aria-hidden /> 分析中…
        </div>
      ) : (
        <div className="rc-confirm__subcat-sections">
          {options.map((trackOpts) => (
            <div key={trackOpts.track} className="rc-confirm__subcat-section">
              <div className="rc-confirm__subcat-track-label">
                {trackOpts.track}
              </div>
              <div className="rc-confirm__subcat-pills">
                {trackOpts.sub_cats.map((sc) => {
                  const isChecked = confirmedSubCats.includes(sc.key);
                  return (
                    <label
                      key={sc.key}
                      className={`rc-confirm__subcat-pill${isChecked ? ' is-on' : ''}${sc.suggested ? ' is-suggested' : ''}`}
                    >
                      <input
                        type="checkbox"
                        className="rc-confirm__subcat-cb"
                        checked={isChecked}
                        disabled={disabled}
                        onChange={() => onToggle(sc.key)}
                      />
                      {sc.key}
                      {sc.suggested && !isChecked && (
                        <span className="rc-confirm__subcat-ai-dot" title="AI 建议" />
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
