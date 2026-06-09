'use client';
import { useState } from 'react';
import {
  Radar,
  Layers,
  FileText,
  Mic,
  User,
  PenLine,
  ChevronLeft,
  ExternalLink,
  ChevronRight,
  History,
} from 'lucide-react';
import type { HubModule } from './hub-types';

// ──────────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────────

interface HubSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  active: HubModule | null;   // 高亮项
  onNav: (key: HubModule) => void;
  onNew: () => void;
}

// ──────────────────────────────────────────────────────────────────────────────
// Nav config
// ──────────────────────────────────────────────────────────────────────────────

interface NavItem {
  key: HubModule;
  label: string;
  Icon: React.ElementType;
  jump?: boolean;          // 外链徽标（模拟面试跳新页面）
}

const NAV: NavItem[] = [
  { key: 'feed',      label: '职位推荐', Icon: Radar },
  { key: 'skeleton',  label: '梯队骨架', Icon: Layers },
  { key: 'resume',    label: '简历优化', Icon: FileText },
  { key: 'interview', label: '模拟面试', Icon: Mic,  jump: true },
  { key: 'profile',   label: '个人档案', Icon: User },
];

// 静态历史记录占位
// TODO(next): 接会话独立实体后端
const SESSIONS: [string, string][] = [
  ['券商资管 · 固收方向', '刚刚'],
  ['量化私募 · 研究岗', '昨天'],
  ['央国企 · 战略', '3 天前'],
];

// ──────────────────────────────────────────────────────────────────────────────
// SideNavItem
// ──────────────────────────────────────────────────────────────────────────────

function SideNavItem({
  item,
  active,
  collapsed,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onClick: (key: HubModule) => void;
}) {
  const [hov, setHov] = useState(false);

  const iconColor = active ? 'var(--terracotta-strong)' : 'var(--ink-soft)';
  const bg = active
    ? 'var(--terracotta-wash)'
    : hov
    ? 'var(--library-rail)'
    : 'transparent';

  return (
    <button
      onClick={() => onClick(item.key)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={collapsed ? item.label : undefined}
      style={{
        position: 'relative',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        padding: collapsed ? '10px 0' : '9px 11px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        borderRadius: 10,
        cursor: 'pointer',
        background: bg,
        boxShadow: active ? '0 0 0 1px #eccfb6' : 'none',
        color: active ? 'var(--ink)' : 'var(--ink-soft)',
        transition: 'background .14s',
        border: 0,
        outline: 'none',
      }}
    >
      {/* left accent bar when selected + expanded */}
      {active && !collapsed && (
        <span
          style={{
            position: 'absolute',
            left: -1,
            top: 8,
            bottom: 8,
            width: 2.5,
            borderRadius: 2,
            background: 'var(--terracotta)',
          }}
        />
      )}

      {/* icon */}
      <span style={{ color: iconColor, display: 'inline-flex', flex: 'none' }}>
        <item.Icon size={collapsed ? 19 : 17} strokeWidth={1.6} />
      </span>

      {/* label + badges — hidden in collapsed mode */}
      {!collapsed && (
        <>
          <span
            style={{
              font: `${active ? 600 : 500} 13.5px var(--font-sans)`,
              flex: 1,
              textAlign: 'left',
            }}
          >
            {item.label}
          </span>

          {/* monochrome external-link badge for 模拟面试 — no colorful badge */}
          {item.jump && (
            <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>
              <ExternalLink size={13} strokeWidth={1.7} />
            </span>
          )}
        </>
      )}
    </button>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// HubSidebar (exported)
// ──────────────────────────────────────────────────────────────────────────────

export default function HubSidebar({
  collapsed,
  onToggle,
  active,
  onNav,
  onNew,
}: HubSidebarProps) {
  // ── Collapsed state (width 64) ───────────────────────────────────────────
  if (collapsed) {
    return (
      <div
        style={{
          width: 64,
          flex: 'none',
          // --border not in tokens → substitute --border-warm
          borderRight: '1px solid var(--border-warm)',
          background: 'var(--ivory)',
          display: 'flex',
          flexDirection: 'column',
          padding: '14px 10px',
          gap: 6,
        }}
      >
        {/* logo dot (toggle expand) */}
        <button
          onClick={onToggle}
          title="展开侧边栏"
          style={{
            width: 30,
            height: 30,
            margin: '0 auto 6px',
            borderRadius: 9,
            background: 'var(--deep-dark)',
            position: 'relative',
            cursor: 'pointer',
            border: 0,
            outline: 'none',
          }}
        >
          <span
            style={{
              position: 'absolute',
              width: 8,
              height: 8,
              borderRadius: 999,
              background: 'var(--terracotta)',
              top: 11,
              left: 11,
              boxShadow: '0 0 0 3px rgba(201,100,66,0.22)',
            }}
          />
        </button>

        {/* 新对话 */}
        <button
          onClick={onNew}
          title="新对话"
          style={{
            width: 40,
            height: 40,
            margin: '0 auto 4px',
            borderRadius: 10,
            background: 'transparent',
            color: 'var(--terracotta-strong)',
            display: 'grid',
            placeItems: 'center',
            cursor: 'pointer',
            boxShadow: 'none',
            border: 0,
            outline: 'none',
          }}
        >
          <PenLine size={16} strokeWidth={1.6} />
        </button>

        {/* nav icons */}
        {NAV.map((n) => (
          <SideNavItem
            key={n.key}
            item={n}
            active={active === n.key}
            collapsed
            onClick={onNav}
          />
        ))}

        {/* bottom avatar */}
        <div style={{ marginTop: 'auto', display: 'grid', placeItems: 'center', paddingTop: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 999,
              background: 'var(--terracotta)',
              color: '#fff',
              display: 'grid',
              placeItems: 'center',
              font: '600 13px var(--font-sans)',
            }}
          >
            陈
          </div>
        </div>
      </div>
    );
  }

  // ── Expanded state (width 252) ───────────────────────────────────────────
  return (
    <div
      style={{
        width: 252,
        flex: 'none',
        // --border not in tokens → substitute --border-warm
        borderRight: '1px solid var(--border-warm)',
        background: 'var(--ivory)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        height: '100%',
      }}
    >
      {/* brand + collapse toggle */}
      <div
        style={{
          padding: '14px 14px 8px',
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          flex: 'none',
        }}
      >
        {/* brand wordmark — 纯文字,无方块 logo(对齐设计稿 HFLogo) */}
        <div className="hf-logo">
          <span className="hf-logo__word">JobRadar</span>
        </div>

        {/* collapse button */}
        <button
          onClick={onToggle}
          title="收起侧边栏"
          style={{
            marginLeft: 'auto',
            width: 28,
            height: 28,
            borderRadius: 8,
            display: 'grid',
            placeItems: 'center',
            color: 'var(--stone)',
            cursor: 'pointer',
            boxShadow: '0 0 0 1px var(--border-warm)',
            border: 0,
            outline: 'none',
            background: 'transparent',
          }}
        >
          <ChevronLeft size={15} strokeWidth={1.7} />
        </button>
      </div>

      {/* 新对话 — 动作按钮(ghost/描边),不用选中态的 wash + accent bar,避免与激活模块"双高亮" */}
      <div style={{ padding: '6px 12px 4px', flex: 'none' }}>
        <button
          onClick={onNew}
          style={{
            position: 'relative',
            width: '100%',
            height: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-start',
            gap: 10,
            paddingLeft: 13,
            borderRadius: 10,
            cursor: 'pointer',
            background: 'transparent',
            boxShadow: 'none',
            color: 'var(--ink)',
            border: 0,
            outline: 'none',
          }}
        >
          <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex', flex: 'none' }}>
            <PenLine size={16} strokeWidth={1.6} />
          </span>
          <span style={{ font: '600 13.5px var(--font-sans)' }}>新对话</span>
        </button>
      </div>

      {/* nav items */}
      <div
        style={{
          padding: '6px 10px 4px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          flex: 'none',
        }}
      >
        {NAV.map((n) => (
          <SideNavItem
            key={n.key}
            item={n}
            active={active === n.key}
            collapsed={false}
            onClick={onNav}
          />
        ))}
      </div>

      {/* divider */}
      <hr className="hf-hr" style={{ margin: '8px 14px', flex: 'none' }} />

      {/* resume switcher — 静态展示占位，>1 份简历时显形 */}
      {/* TODO(next): 接会话独立实体后端 */}
      <div style={{ padding: '0 12px 8px', flex: 'none' }}>
        <button
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            padding: '8px 11px',
            borderRadius: 10,
            cursor: 'pointer',
            // --library-rail exists in tokens
            background: 'var(--library-rail)',
            boxShadow: '0 0 0 1px var(--border-warm)',
            border: 0,
            outline: 'none',
          }}
        >
          <span style={{ color: 'var(--stone)', display: 'inline-flex', flex: 'none' }}>
            <FileText size={15} strokeWidth={1.6} />
          </span>
          <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
            <div
              style={{
                font: '600 12px var(--font-sans)',
                color: 'var(--ink)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              简历 · 中文主版
            </div>
            <div style={{ font: '400 10px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>
              当前画像 · 切换简历(2)
            </div>
          </div>
          <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>
            <ChevronRight size={13} strokeWidth={1.7} />
          </span>
        </button>
      </div>

      {/* history section header */}
      {/* TODO(next): 接会话独立实体后端 */}
      <div
        style={{
          padding: '0 16px 6px',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          flex: 'none',
        }}
      >
        <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>
          <History size={12} strokeWidth={1.6} />
        </span>
        <span className="hf-overline" style={{ fontSize: 9.5 }}>
          历史记录 · 此简历下的会话
        </span>
      </div>

      {/* history session list — static mock rows */}
      {/* TODO(next): 接会话独立实体后端 */}
      <div
        style={{
          padding: '0 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          overflow: 'auto',
          minHeight: 0,
          flex: '1 1 auto',
        }}
      >
        {SESSIONS.map(([label, time], i) => (
          <div
            key={i}
            style={{
              padding: '8px 11px',
              borderRadius: 10,
              cursor: 'pointer',
              background: i === 0 ? 'var(--library-rail)' : 'transparent',
              boxShadow: i === 0 ? '0 0 0 1px var(--border-warm)' : 'none',
            }}
          >
            <div
              style={{
                font: `${i === 0 ? 600 : 500} 12.5px var(--font-sans)`,
                color: i === 0 ? 'var(--ink)' : 'var(--ink-soft)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {label}
            </div>
            <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)', marginTop: 2 }}>
              {time}
            </div>
          </div>
        ))}
      </div>

      {/* bottom identity — persistent profile entry */}
      <button
        onClick={() => onNav('profile')}
        style={{
          marginTop: 'auto',
          // --border not in tokens → substitute --border-warm
          borderTop: '1px solid var(--border-warm)',
          borderRight: 0,
          borderBottom: 0,
          borderLeft: 0,
          padding: '11px 13px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          cursor: 'pointer',
          background: 'transparent',
          textAlign: 'left',
          width: '100%',
          outline: 'none',
          flex: 'none',
        }}
      >
        {/* avatar */}
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 999,
            background: 'var(--terracotta)',
            color: '#fff',
            display: 'grid',
            placeItems: 'center',
            font: '600 13px var(--font-sans)',
            flex: 'none',
          }}
        >
          陈
        </div>

        {/* name + tagline */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 13px var(--font-sans)', color: 'var(--ink)' }}>陈思远</div>
          <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)' }}>
            它记得你 · 点开看档案
          </div>
        </div>

        <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>
          <ChevronRight size={13} strokeWidth={1.7} />
        </span>
      </button>
    </div>
  );
}
