'use client';

/**
 * WorkingQueryReadout — 流动 feed 栏头部的「工作查询」可视化 (Phase G 子项④).
 *
 * 头行: 「流动 feed · 按工作查询 · {count} 个在招」(无「锁定为主方向」按钮 —
 *   切换赛道是顶栏的活,子项⑤). 下方 chip 行:
 *     seed_sub_cats → seed chip(不可移除)
 *     sub_cats      → add chip(× → remove_sub_cat)
 *     exclude       → excl chip
 *     only(true)    → only=… 深色 pill(点 → clear_only)
 *   右端: 排序指示 「排序：匹配/新鲜度/薪资 ▾」,点击循环 match→fresh→pay→match。
 *
 * 所有更新走 fast-path(updateWorkingQuery, 无 LLM),回包同步 feed + workingQuery;
 * 本组件只发意图,实际调用 + setState 由父级 RecommendFeedPane 在事件回调里做。
 */

import type { WorkingQuery } from '../../../types';
import { QueryChip } from './QueryChip';

const SORT_CYCLE = ['match', 'fresh', 'pay'] as const;
const SORT_LABEL: Record<string, string> = {
  match: '匹配',
  fresh: '新鲜度',
  pay: '薪资',
};

function nextSort(cur: string): string {
  const i = SORT_CYCLE.indexOf(cur as (typeof SORT_CYCLE)[number]);
  return SORT_CYCLE[(i + 1) % SORT_CYCLE.length];
}

export interface WorkingQueryReadoutProps {
  workingQuery: WorkingQuery;
  feedCount: number;
  onRemoveSubCat: (subCat: string) => void;
  onClearOnly: () => void;
  onSetSort: (sort: string) => void;
}

export function WorkingQueryReadout({
  workingQuery,
  feedCount,
  onRemoveSubCat,
  onClearOnly,
  onSetSort,
}: WorkingQueryReadoutProps) {
  const wq = workingQuery;
  const sortLabel = SORT_LABEL[wq.sort] ?? '匹配';

  return (
    <div className="recommend-feed__head">
      <div className="recommend-feed__head-row">
        <span className="recommend-feed__head-title">在招岗位</span>
        <span className="recommend-feed__head-sub">
          按你的工作查询 · 共 {feedCount} 个
        </span>
      </div>

      <div className="recommend-feed__chips">
        <span className="recommend-feed__chips-overline">工作查询</span>

        {wq.seed_sub_cats.map((s) => (
          <QueryChip key={`seed-${s}`} kind="seed">
            {s}
          </QueryChip>
        ))}

        {wq.sub_cats.map((s) => (
          <QueryChip
            key={`add-${s}`}
            kind="add"
            onRemove={() => onRemoveSubCat(s)}
          >
            {s}
          </QueryChip>
        ))}

        {wq.exclude.map((s) => (
          <QueryChip key={`excl-${s}`} kind="excl">
            {s}
          </QueryChip>
        ))}

        {wq.only && (
          <button
            type="button"
            className="recommend-feed__only-pill"
            title="点开放开"
            onClick={onClearOnly}
          >
            only=是<span className="recommend-feed__only-x">×</span>
          </button>
        )}

        <button
          type="button"
          className="recommend-feed__sort"
          title="切换排序"
          onClick={() => onSetSort(nextSort(wq.sort))}
        >
          排序：{sortLabel} ▾
        </button>
      </div>
    </div>
  );
}
