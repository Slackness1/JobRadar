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
  // 历史记录:真实会话列表(由 HubShell 拉 listResumeCopilotSessions 注入)
  sessions?: HubSessionRow[];
  currentSessionId?: number;
  onSelectSession?: (id: number) => void;
}

export interface HubSessionRow {
  id: number;
  label: string;   // 会话名 / 赛道 / 文件名
  time: string;    // 相对时间
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

// 新对话 — 与 SideNavItem 完全同构的"标签":未选中=素色无底,选中(=当前无其它模块选中,
// 即落地/新会话态)=土红浅底 + 左竖条 + 土红图标,字号/间距/内边距全部与导航项一致。
function NewChatItem({
  active,
  collapsed,
  onNew,
}: {
  active: boolean;
  collapsed: boolean;
  onNew: () => void;
}) {
  const [hov, setHov] = useState(false);
  const iconColor = active ? 'var(--terracotta-strong)' : 'var(--ink-soft)';
  const bg = active ? 'var(--terracotta-wash)' : hov ? 'var(--library-rail)' : 'transparent';

  return (
    <button
      onClick={onNew}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={collapsed ? '新对话' : undefined}
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
      <span style={{ color: iconColor, display: 'inline-flex', flex: 'none' }}>
        <PenLine size={collapsed ? 19 : 17} strokeWidth={1.6} />
      </span>
      {!collapsed && (
        <span style={{ font: `${active ? 600 : 500} 13.5px var(--font-sans)`, flex: 1, textAlign: 'left' }}>
          新对话
        </span>
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
  sessions = [],
  currentSessionId,
  onSelectSession,
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

        {/* 新对话 — 与导航项同构,无其它模块选中时为选中态 */}
        <NewChatItem active={active === null} collapsed onNew={onNew} />

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

      {/* 新对话 + nav items — 同一容器,共享内边距与间距,新对话即首个"标签" */}
      <div
        style={{
          padding: '6px 10px 4px',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          flex: 'none',
        }}
      >
        <NewChatItem active={active === null} collapsed={false} onNew={onNew} />
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

      {/* history session list — 真实会话(listResumeCopilotSessions 注入) */}
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
        {sessions.length === 0 ? (
          <div style={{ padding: '8px 11px', font: '400 11px var(--font-sans)', color: 'var(--stone)' }}>
            还没有会话 —— 上传简历开始
          </div>
        ) : (
          sessions.map((s) => {
            const cur = s.id === currentSessionId;
            return (
              <div
                key={s.id}
                onClick={() => onSelectSession?.(s.id)}
                style={{
                  padding: '8px 11px',
                  borderRadius: 10,
                  cursor: 'pointer',
                  background: cur ? 'var(--library-rail)' : 'transparent',
                  boxShadow: cur ? '0 0 0 1px var(--border-warm)' : 'none',
                }}
              >
                <div
                  style={{
                    font: `${cur ? 600 : 500} 12.5px var(--font-sans)`,
                    color: cur ? 'var(--ink)' : 'var(--ink-soft)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {s.label}
                </div>
                <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)', marginTop: 2 }}>
                  {s.time}
                </div>
              </div>
            );
          })
        )}
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
