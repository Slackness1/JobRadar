'use client';

/**
 * RecommendTopBar — 「推荐工作台」顶栏 (Phase G 子项①).
 *
 * 对齐设计稿 nlrec-app.jsx 的 TopBar:JobRadar logo · 「推荐工作台」title ·
 * 「NL 推荐 agent」pill · 会话切换下拉(把设计稿的 Sidebar 会话列表收进来) ·
 * 右侧「简历编辑器」ghost 链接(过渡期保留的改写入口) · 用户头像.
 *
 * 设计系统:`.hf` token + 本目录 recommend-agent.css([data-theme="recommend"] scope).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import type { ResumeCopilotSessionListItem } from '../../types';

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const ms = Date.now() - new Date(dateStr).getTime();
  if (ms < 60_000) return '刚刚';
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)} 分钟前`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)} 小时前`;
  if (ms < 7 * 86_400_000) return `${Math.floor(ms / 86_400_000)} 天前`;
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function Chevron() {
  return (
    <svg
      className="recommend-session__chevron"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export interface RecommendTopBarProps {
  sessions: ResumeCopilotSessionListItem[];
  activeSessionId: number | null;
  /** 切换到某个已有会话 */
  onSelectSession: (id: number) => void;
  /** 「新会话」动作 — 没有后端落地时跳简历上传入口 */
  onNewSession: () => void;
  /** 当前确认主赛道名 — null = 尚未确认。展示在右侧切换 chip 上。 */
  currentTrack?: string | null;
  /** 点「切换赛道」chip → 父打开 TrackPickerModal(确认主赛道的唯一显式入口)。
   *  optional:不传则不渲染 chip,不破坏既有 caller。 */
  onChangeTrack?: () => void;
}

export function RecommendTopBar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  currentTrack,
  onChangeTrack,
}: RecommendTopBarProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // 点外部关闭下拉
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const active = sessions.find((s) => s.id === activeSessionId) ?? null;
  const triggerLabel = active?.name || active?.file_name || '选择会话';

  const handleSelect = useCallback(
    (id: number) => {
      setOpen(false);
      onSelectSession(id);
    },
    [onSelectSession],
  );

  const handleNew = useCallback(() => {
    setOpen(false);
    onNewSession();
  }, [onNewSession]);

  return (
    <div className="recommend-topbar">
      <span className="recommend-topbar__logo">
        <span className="recommend-topbar__logo-mark" aria-hidden>
          <span className="recommend-topbar__logo-dot" />
        </span>
        <span className="recommend-topbar__brand">JobRadar</span>
      </span>
      <span className="recommend-topbar__sep" aria-hidden>
        /
      </span>
      <span className="recommend-topbar__title">推荐工作台</span>
      <span className="hf-pill" style={{ height: 26 }}>
        NL 推荐 agent
      </span>

      {/* 会话切换下拉 */}
      <div className="recommend-session" ref={wrapRef}>
        <button
          type="button"
          className="recommend-session__trigger"
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="recommend-session__trigger-name">{triggerLabel}</span>
          <Chevron />
        </button>

        {open && (
          <div className="recommend-session__menu" role="menu">
            <button type="button" className="recommend-session__new" onClick={handleNew}>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                aria-hidden
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
              新会话
            </button>
            <div className="recommend-session__overline">会话</div>
            {sessions.length === 0 ? (
              <div className="recommend-session__empty">
                还没有简历会话 — 点「新会话」上传简历开始。
              </div>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  role="menuitem"
                  className={`recommend-session__item${
                    s.id === activeSessionId ? ' is-active' : ''
                  }`}
                  onClick={() => handleSelect(s.id)}
                >
                  <div className="recommend-session__item-name">
                    {s.name || s.file_name || `会话 ${s.id}`}
                  </div>
                  <div className="recommend-session__item-meta">
                    {timeAgo(s.updated_at) || timeAgo(s.created_at) || s.status}
                  </div>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      <span className="recommend-topbar__spacer" />

      {/* 切换主赛道入口 — confirmed 主赛道的唯一显式改动口(接 TrackPickerModal,
          内部 PUT /preferences 落库)。NL 对话永不碰 confirmed。 */}
      {onChangeTrack ? (
        <button
          type="button"
          className="recommend-topbar__track"
          onClick={onChangeTrack}
          title="切换主赛道(会重排梯队骨架与推荐)"
        >
          <span className="recommend-topbar__track-dot" aria-hidden />
          <span className="recommend-topbar__track-name">
            {currentTrack || '尚未确认主赛道'}
          </span>
          <span className="recommend-topbar__track-cta">切换赛道</span>
        </button>
      ) : null}

      {/* 简历改写入口 — 过渡期保留(只加不删),链接到现有简历工作台 */}
      <button
        type="button"
        className="hf-btn ghost sm"
        onClick={() =>
          router.push(
            activeSessionId
              ? `/resume-copilot?sessionId=${activeSessionId}`
              : '/resume-copilot',
          )
        }
      >
        简历编辑器
      </button>

      <div className="recommend-topbar__avatar" aria-hidden>
        陈
      </div>
    </div>
  );
}
