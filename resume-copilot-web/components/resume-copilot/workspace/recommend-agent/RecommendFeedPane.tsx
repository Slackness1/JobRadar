'use client';

/**
 * RecommendFeedPane — 「推荐工作台」右栏:流动 feed (Phase G 子项④).
 *
 * 组成:
 *   1. WorkingQueryReadout — 工作查询 readout(seed / add / excl / only / sort),
 *      所有改动走 fast-path updateWorkingQuery(无 LLM),回包同步 feed + workingQuery。
 *   2. JobCard 列表 — Base / Enhanced 双分胶囊 + 深挖 4-anchor。
 *   3. 空态 — feed 为空时给「相邻方向 / 放宽地点」引导,绝不静默空白。
 *
 * 联动:
 *   · 深挖 → postRecommendDeepen([jobId]) → 把回包 item(带 enhanced_score +
 *     anchors + used_ai=true)就地替换进 feed,展开慢路理由。
 *   · 讲讲这家 → onIntel(company) → 父级把「讲讲{公司}」当普通消息丢中栏对话。
 *   · 点公司 / 卡 → onHighlightCompany(company) → 父级 setHighlightCompany → 左栏
 *     梯队骨架高亮 + 滚动定位;梯队外岗位(in_skeleton===false)不强制高亮。
 *
 * react-compiler:所有 setState 都在 async 回调 / 事件处理器内,render 纯净。
 */

import { useCallback, useState } from 'react';

import { postRecommendDeepen, updateWorkingQuery } from '../../api';
import type { RecommendFeedItem, WorkingQuery } from '../../types';
import { JobCard } from './feed/JobCard';
import { WorkingQueryReadout } from './feed/WorkingQueryReadout';

export interface RecommendFeedPaneProps {
  sessionId: number;
  workingQuery: WorkingQuery | null;
  feed: RecommendFeedItem[];
  setFeed: (feed: RecommendFeedItem[]) => void;
  setWorkingQuery: (wq: WorkingQuery) => void;
  /** 点公司 / 卡 → 联动左侧梯队骨架(梯队外不强制高亮)。 */
  onHighlightCompany: (company: string) => void;
  /** 讲讲这家 → 把公司 + 岗位哈希交给父级(hub 里就地展开情报卡，不进对话)。 */
  onIntel: (company: string, jobId: string) => void;
}

export function RecommendFeedPane({
  sessionId,
  workingQuery,
  feed,
  setFeed,
  setWorkingQuery,
  onHighlightCompany,
  onIntel,
}: RecommendFeedPaneProps) {
  // 正在精排的岗位 id(单张转 spinner);其余卡照常。
  const [deepeningId, setDeepeningId] = useState<string | null>(null);

  // ── 工作查询 fast-path(无 LLM) ──────────────────────────────────────────
  const applyWorkingQueryOp = useCallback(
    async (op: {
      remove_sub_cat?: string;
      clear_only?: boolean;
      sort?: string;
    }) => {
      try {
        const resp = await updateWorkingQuery(sessionId, op);
        setFeed(resp.feed);
        setWorkingQuery(resp.working_query);
      } catch {
        // fast-path 失败静默:保留当前 feed / workingQuery 不动。
      }
    },
    [sessionId, setFeed, setWorkingQuery],
  );

  const handleRemoveSubCat = useCallback(
    (subCat: string) => {
      void applyWorkingQueryOp({ remove_sub_cat: subCat });
    },
    [applyWorkingQueryOp],
  );

  const handleClearOnly = useCallback(() => {
    void applyWorkingQueryOp({ clear_only: true });
  }, [applyWorkingQueryOp]);

  const handleSetSort = useCallback(
    (sort: string) => {
      void applyWorkingQueryOp({ sort });
    },
    [applyWorkingQueryOp],
  );

  // ── 深挖(慢路精排) ──────────────────────────────────────────────────────
  const handleDeepen = useCallback(
    async (jobId: string) => {
      setDeepeningId(jobId);
      try {
        const resp = await postRecommendDeepen(sessionId, [jobId]);
        const updated = resp.items.find((it) => it.job_id === jobId);
        if (updated) {
          setFeed(
            feed.map((it) => (it.job_id === jobId ? updated : it)),
          );
        }
      } catch {
        // 精排失败:保留原卡(规则分),仅退出 spinner。
      } finally {
        setDeepeningId(null);
      }
    },
    [sessionId, feed, setFeed],
  );

  // ── 点公司 / 卡 → 联动骨架(梯队外不强制高亮) ──────────────────────────
  const handleHighlight = useCallback(
    (item: RecommendFeedItem) => {
      if (item.in_skeleton === false) return; // 内联提示在卡上,父级不高亮
      onHighlightCompany(item.company);
    },
    [onHighlightCompany],
  );

  // ── Match-tier 分组(优雅降级) ────────────────────────────────────────────
  // 按原始 feed 顺序把每张卡分进三个桶,同时记住全局 index(i),
  // 保证 JobCard 的 rank 联动不因分组而错位。
  const TIER_ORDER = ['strong', 'transferable', 'explore'] as const;
  type Tier = (typeof TIER_ORDER)[number];

  const TIER_META: Record<Tier, { title: string; sub: string }> = {
    strong: { title: '强匹配', sub: '最贴合你目标方向' },
    transferable: { title: '可迁移', sub: '相邻赛道,有迁移可能' },
    explore: { title: '探索机会', sub: '语义发现,可拓展投递池' },
  };

  // 构建分组:{ tier -> Array<{ item, globalIndex }> }
  const grouped = new Map<Tier, Array<{ item: RecommendFeedItem; globalIndex: number }>>();
  for (const tier of TIER_ORDER) grouped.set(tier, []);
  feed.forEach((item, i) => {
    const tier: Tier =
      item.match_tier === 'transferable' || item.match_tier === 'explore'
        ? item.match_tier
        : 'strong'; // undefined / 'strong' / 未知值 → strong
    grouped.get(tier)!.push({ item, globalIndex: i });
  });

  // 有内容的 tier 数
  const activeTiers = TIER_ORDER.filter((t) => (grouped.get(t)?.length ?? 0) > 0);
  const showGroupHeaders = activeTiers.length >= 2;

  return (
    <div className="recommend-feed">
      {workingQuery && (
        <WorkingQueryReadout
          workingQuery={workingQuery}
          feedCount={feed.length}
          onRemoveSubCat={handleRemoveSubCat}
          onClearOnly={handleClearOnly}
          onSetSort={handleSetSort}
        />
      )}

      <div className="recommend-feed__list">
        {showGroupHeaders
          ? // ≥2 个 tier 有内容:按段渲染
            activeTiers.map((tier) => {
              const entries = grouped.get(tier)!;
              const meta = TIER_META[tier];
              return (
                <div key={tier} className="recommend-feed__tier-group">
                  <div className="recommend-feed__tier-header">
                    <span className="recommend-feed__tier-title">{meta.title}</span>
                    <span className="recommend-feed__tier-sub">{meta.sub}</span>
                  </div>
                  {entries.map(({ item, globalIndex }) => (
                    <JobCard
                      key={item.job_id}
                      item={item}
                      rank={globalIndex + 1}
                      deepening={deepeningId === item.job_id}
                      onDeepen={handleDeepen}
                      onIntel={onIntel}
                      onHighlightCompany={handleHighlight}
                    />
                  ))}
                </div>
              );
            })
          : // 只有一个 tier(或全 strong):扁平渲染,和改前完全一致
            feed.map((item, i) => (
              <JobCard
                key={item.job_id}
                item={item}
                rank={i + 1}
                deepening={deepeningId === item.job_id}
                onDeepen={handleDeepen}
                onIntel={onIntel}
                onHighlightCompany={handleHighlight}
              />
            ))}

        {feed.length === 0 && (
          <div className="recommend-feed__empty">
            <div className="recommend-feed__empty-title">
              这方向库里暂无在招
            </div>
            <div className="recommend-feed__empty-sub">
              要不要看相邻方向，或放宽地点？
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
