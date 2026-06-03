'use client';

/**
 * QueryChip — 工作查询 readout 上的条件 chip (Phase G 子项④).
 *
 *   kind="seed" → 深色实底,确认赛道,不可移除.
 *   kind="add"  → terracotta wash,学生临时加的 sub_cat,带 × 可移除.
 *   kind="excl" → 虚线描边,排除项.
 *
 * × 点击回调由父级注入(fast-path updateWorkingQuery);纯展示 + 一个按钮。
 */

export interface QueryChipProps {
  kind: 'seed' | 'add' | 'excl';
  children: React.ReactNode;
  onRemove?: () => void;
}

export function QueryChip({ kind, children, onRemove }: QueryChipProps) {
  if (kind === 'seed') {
    return (
      <span className="recommend-feed__chip recommend-feed__chip--seed">
        {children}
      </span>
    );
  }
  if (kind === 'excl') {
    return (
      <span className="recommend-feed__chip recommend-feed__chip--excl">
        <span className="recommend-feed__chip-x-static">✕</span>
        {children}
      </span>
    );
  }
  return (
    <span className="recommend-feed__chip recommend-feed__chip--add">
      {children}
      {onRemove && (
        <button
          type="button"
          className="recommend-feed__chip-x"
          title="移除"
          onClick={onRemove}
        >
          ×
        </button>
      )}
    </span>
  );
}
