'use client';

/**
 * TierLadderStrip — 档次阶梯条 (Phase G, 2026-05-31)
 *
 * 展示该赛道三档平台(头部 / 次头部 / 腰部)的分布,并标注当前学生所处:
 *   - 稳 (floor_band)  — 目前实力够到的
 *   - 匹配 (match_band) — 最合适投的
 *   - 冲刺 (stretch_band) — 有挑战性的目标
 *
 * 特殊情况:
 *   - single_band===true: 该赛道平台只有一档,不标稳/匹配/冲刺,顶部一行说明
 *   - fit===null / ladder 为空: 不渲染
 *   - data_confidence==='thin': 显示灰标"数据有限,方向性参考"
 *   - reasons 每条用 <details> 折叠;evidence 为空不显示"依据"行
 *   - upgrade_hint 非空时显示(↗ 前缀)
 */

import type { TierFit } from '../../api';

export interface TierLadderStripProps {
  data: TierFit;
}

function bandRoleLabel(
  bandName: string,
  fit: NonNullable<TierFit['fit']>,
): string | null {
  if (bandName === fit.match_band) return '匹配';
  if (bandName === fit.stretch_band) return '冲刺';
  if (bandName === fit.floor_band) return '稳';
  return null;
}

export function TierLadderStrip({ data }: TierLadderStripProps) {
  const { ladder, fit } = data;

  // Guard: nothing to render if no ladder or no fit signal
  if (!fit || !ladder || ladder.length === 0) return null;

  const isSingle = fit.single_band;

  return (
    <div className="workspace-hifi__tier-strip">
      {/* Single-band notice */}
      {isSingle && (
        <div className="workspace-hifi__tier-strip-single-notice">
          该赛道平台集中在「{fit.match_band}」档
        </div>
      )}

      {/* Data confidence caveat */}
      {fit.data_confidence === 'thin' && (
        <div className="workspace-hifi__tier-strip-thin-notice">
          数据有限，方向性参考
        </div>
      )}

      {/* Ladder bands */}
      <div className="workspace-hifi__tier-bands">
        {ladder.map((band) => {
          const role = isSingle ? null : bandRoleLabel(band.band, fit);
          const isMatch = band.band === fit.match_band;

          return (
            <div
              key={band.band}
              className={`workspace-hifi__tier-band${isMatch ? ' is-match' : ''}`}
            >
              <div className="workspace-hifi__tier-band-head">
                <span className="workspace-hifi__tier-band-name">{band.band}</span>
                {role && (
                  <span className={`workspace-hifi__tier-band-role workspace-hifi__tier-band-role--${role}`}>
                    {role}
                  </span>
                )}
                <span className="workspace-hifi__tier-band-count">{band.n_jobs} 岗</span>
              </div>
              {band.native_labels.length > 0 && (
                <div className="workspace-hifi__tier-band-sublabel">
                  {band.native_labels.join('/')}
                </div>
              )}
              {band.companies.length > 0 && (
                <div className="workspace-hifi__tier-band-companies">
                  {band.companies.slice(0, 4).join('·')}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Reasons (折叠) */}
      {fit.reasons.length > 0 && (
        <div className="workspace-hifi__tier-reasons">
          {fit.reasons.map((reason, idx) => (
            <details key={idx} className="workspace-hifi__tier-reason">
              <summary className="workspace-hifi__tier-reason-summary">
                {reason.text}
              </summary>
              {reason.evidence && (
                <div className="workspace-hifi__tier-reason-evidence">
                  依据：「{reason.evidence}」
                </div>
              )}
            </details>
          ))}
        </div>
      )}

      {/* Upgrade hint */}
      {fit.upgrade_hint && (
        <div className="workspace-hifi__tier-upgrade-hint">
          ↗ {fit.upgrade_hint}
        </div>
      )}
    </div>
  );
}
