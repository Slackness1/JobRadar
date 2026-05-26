'use client';

/**
 * SessionsToolbar — filter tabs (使用中 / 归档 / 全部) + 搜索占位 + 排序选择。
 *
 * P0a: 搜索框只占位 (没有实际过滤逻辑); 排序下拉真接 — 父组件根据 sort 值在
 * `useMemo` 里排序; filter 也真接 — 父按 is_archived 切。
 */

import { I } from '@/components/hifi/hifi-primitives';

export type SessionFilter = 'active' | 'archived' | 'all';
export type SessionSort = 'updated' | 'created' | 'name';

interface FilterTab {
  id: SessionFilter;
  label: string;
  count: number;
}

interface SessionsToolbarProps {
  filter: SessionFilter;
  onFilterChange: (next: SessionFilter) => void;
  sort: SessionSort;
  onSortChange: (next: SessionSort) => void;
  activeCount: number;
  archivedCount: number;
}

export function SessionsToolbar({
  filter,
  onFilterChange,
  sort,
  onSortChange,
  activeCount,
  archivedCount,
}: SessionsToolbarProps) {
  const tabs: FilterTab[] = [
    { id: 'active', label: '使用中', count: activeCount },
    { id: 'archived', label: '归档', count: archivedCount },
    { id: 'all', label: '全部', count: activeCount + archivedCount },
  ];

  return (
    <div className="rc-sessions__toolbar" data-testid="rc-sessions-toolbar">
      <div className="rc-sessions__filter-tabs">
        {tabs.map((t) => (
          <button
            type="button"
            key={t.id}
            onClick={() => onFilterChange(t.id)}
            className="rc-sessions__filter-tab"
            data-active={filter === t.id ? 'true' : 'false'}
            aria-pressed={filter === t.id}
          >
            {t.label}
            <span className="rc-sessions__filter-tab-count">{t.count}</span>
          </button>
        ))}
      </div>

      <div className="rc-sessions__search" aria-disabled="true">
        <span style={{ display: 'inline-flex' }} aria-hidden>
          {I.search(13)}
        </span>
        <span>搜会话名 / 赛道 / 公司…</span>
      </div>

      <div className="rc-sessions__toolbar-spacer" />

      <span className="rc-sessions__sort-label">排序</span>
      <select
        value={sort}
        onChange={(e) => onSortChange(e.target.value as SessionSort)}
        className="rc-sessions__sort-select"
        aria-label="排序方式"
      >
        <option value="updated">最近更新</option>
        <option value="created">最近创建</option>
        <option value="name">名称</option>
      </select>
    </div>
  );
}
