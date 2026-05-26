'use client';

/**
 * IntelTabs — IntelDrawer 内的 4 tab 切换 (原话 / 待遇 / 要求 / 面试题).
 *
 * 选中态:下边 2px terracotta 线 + count pill 实心 terracotta + 白字。
 * 1:1 复刻 hifi-ws-intel.jsx::HFIntelTabs.
 */

import type { ReactNode } from 'react';

export type IntelTabId = 'quotes' | 'comp' | 'req' | 'qa';

export interface IntelTabDef {
  id: IntelTabId;
  icon: ReactNode;
  label: string;
  count: number | null;
}

export interface IntelTabsProps {
  active: IntelTabId;
  onChange: (id: IntelTabId) => void;
  tabs: IntelTabDef[];
}

export function IntelTabs({ active, onChange, tabs }: IntelTabsProps) {
  return (
    <div className="workspace-hifi__intel-tabs" role="tablist">
      {tabs.map((t) => {
        const isActive = active === t.id;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t.id)}
            className={`workspace-hifi__intel-tab${isActive ? ' is-active' : ''}`}
          >
            <span className="workspace-hifi__intel-tab-icon" aria-hidden>
              {t.icon}
            </span>
            <span>{t.label}</span>
            {t.count != null && (
              <span className="workspace-hifi__intel-tab-count">{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
