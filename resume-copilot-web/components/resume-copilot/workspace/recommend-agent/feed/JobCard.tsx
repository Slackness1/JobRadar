'use client';

/**
 * JobCard — 流动 feed 单张岗位卡 (Phase G 子项④).
 *
 *   头: #rank · 岗位名 · 公司 · 地点 · (梯队内/外 小标).
 *   分: Base 胶囊(始终展示, item.base_score) + Enhanced 胶囊
 *       —— 未深挖(used_ai 假)显示虚线占位「—」;深挖后(used_ai=true)显示
 *       terracotta 实底 enhanced_score + 4-anchor 慢路理由 + 「Pro 精排 ✓」。
 *
 *   语义铁律: pending 态 key 在 `used_ai`,不是 `enhanced_score == null`
 *   —— 后端规则项的 enhanced_score 会镜像 base_score(非 null),只有 used_ai
 *   才区分「未深挖 / 已深挖」。
 *
 *   底: 「🏢 讲讲这家」(→ 中栏对话) + 「深挖（Pro 精排）→」(→ 慢路精排)。
 *   点公司名 / 卡 → 联动左侧梯队骨架高亮;梯队外(in_skeleton===false)给内联提示。
 */

import type { JobState, RecommendFeedItem } from '../../../types';
import { ScorePill } from './ScorePill';

export interface JobCardProps {
  item: RecommendFeedItem;
  rank: number;
  deepening: boolean;
  onDeepen: (jobId: string) => void;
  onIntel: (company: string, jobId: string) => void;
  onHighlightCompany: (item: RecommendFeedItem) => void;
  /** 当前岗位的求职状态(由父级 RecommendFeedPane 持有) */
  jobState?: JobState;
  /** 标记/取消标记求职状态(不传 = 不显示三态按钮) */
  onSetJobState?: (jobId: string, state: '' | JobState) => void;
}

export function JobCard({
  item,
  rank,
  deepening,
  onDeepen,
  onIntel,
  onHighlightCompany,
  jobState,
  onSetJobState,
}: JobCardProps) {
  const deep = item.used_ai === true;
  const baseScore = item.base_score ?? item.base_match_score;
  const anchors = item.anchors ?? [];
  // 方案B: 有档位文案(互联网赛道)就显示具体档位,不再用"内/外"二元标。
  const band = item.skeleton_band || '';
  const outOfSkeleton = !band && item.in_skeleton === false;

  return (
    <div
      className={`recommend-feed__card${deep ? ' recommend-feed__card--deep' : ''}`}
    >
      <div className="recommend-feed__card-head">
        <span className="recommend-feed__rank">#{rank}</span>
        <div className="recommend-feed__card-headmain">
          <button
            type="button"
            className="recommend-feed__job-title"
            title="联动左侧梯队骨架"
            onClick={() => onHighlightCompany(item)}
          >
            {item.job_title}
          </button>
          <div className="recommend-feed__job-meta">
            {item.company} · {item.location || '地点未知'}
            {band ? (
              <span
                className={`recommend-feed__skel-badge ${
                  band === '其他梯队'
                    ? 'recommend-feed__skel-badge--out'
                    : 'recommend-feed__skel-badge--in'
                }`}
              >
                {band}
              </span>
            ) : (
              <>
                {item.in_skeleton === true && (
                  <span className="recommend-feed__skel-badge recommend-feed__skel-badge--in">
                    梯队内
                  </span>
                )}
                {item.in_skeleton === false && (
                  <span className="recommend-feed__skel-badge recommend-feed__skel-badge--out">
                    梯队外机会
                  </span>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="recommend-feed__pills">
        <ScorePill kind="base" value={baseScore} />
        {deep ? (
          <ScorePill kind="enhanced" value={item.enhanced_score} />
        ) : (
          <ScorePill kind="pending" />
        )}
        {deep && <span className="hf-pill terra">深度匹配 ✓</span>}
      </div>

      {!deep && (
        <div className="recommend-feed__subtext">
          初步匹配：按赛道吻合 / 新鲜度 / 平台梯队三维评估
        </div>
      )}

      {deep && anchors.length > 0 && (
        <div className="recommend-feed__anchors">
          <div className="hf-overline recommend-feed__anchors-title">
            为什么匹配 · 4 个理由
          </div>
          {anchors.map(([label, text], i) => (
            <div key={`${label}-${i}`} className="recommend-feed__anchor">
              <span className="recommend-feed__anchor-k">{label}</span>
              <div className="recommend-feed__anchor-v">{text}</div>
            </div>
          ))}
        </div>
      )}

      {outOfSkeleton && (
        <div className="recommend-feed__skel-hint">不在当前梯队骨架内</div>
      )}

      <div className="recommend-feed__actions">
        <button
          type="button"
          className="hf-btn ghost sm recommend-feed__act"
          onClick={() => onIntel(item.company, item.job_id)}
        >
          🏢 讲讲这家
        </button>
        {deep ? (
          <button
            type="button"
            className="hf-btn sand sm recommend-feed__act recommend-feed__act--wide"
            disabled
          >
            已深挖 ✓
          </button>
        ) : deepening ? (
          <button
            type="button"
            className="hf-btn primary sm recommend-feed__act recommend-feed__act--wide"
            disabled
          >
            <span className="hf-spin recommend-feed__spin" /> 深挖中…
          </button>
        ) : (
          <button
            type="button"
            className="hf-btn primary sm recommend-feed__act recommend-feed__act--wide"
            onClick={() => onDeepen(item.job_id)}
          >
            深挖这个岗 →
          </button>
        )}
      </div>

      {onSetJobState && (
        <div className="recommend-feed__job-states">
          <button
            type="button"
            className={`hf-btn sm ${jobState === 'saved' ? 'primary' : 'ghost'}`}
            onClick={() => onSetJobState(item.job_id, jobState === 'saved' ? '' : 'saved')}
          >
            ★ {jobState === 'saved' ? '已收藏' : '收藏想投'}
          </button>
          <button
            type="button"
            className={`hf-btn sm ${jobState === 'applied' ? 'primary' : 'sand'}`}
            onClick={() => onSetJobState(item.job_id, jobState === 'applied' ? '' : 'applied')}
          >
            {jobState === 'applied' ? '已投递 ✓' : '标记已投递'}
          </button>
          <button
            type="button"
            className={`hf-btn sm ${jobState === 'dismissed' ? 'primary' : 'ghost'}`}
            onClick={() => onSetJobState(item.job_id, jobState === 'dismissed' ? '' : 'dismissed')}
          >
            不合适
          </button>
        </div>
      )}
    </div>
  );
}
