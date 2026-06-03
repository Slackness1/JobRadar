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
  /** 讲讲这家 → 把「讲讲{公司}」当普通消息送中栏对话。 */
  onIntel: (company: string) => void;
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
        {feed.map((item, i) => (
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
