'use client';

/**
 * HubPageInner — 「统一对话 Hub」路由的 sessionId 解析层.
 *
 * 解析约定对齐现有简历工作台:`?session=N` query param;缺省时回退到会话列表
 * 第一条,再退到 DEMO_SESSION_ID(只读 demo 会话). 解析完直接把 sessionId 下传
 * 给 HubShell. 全程 setState 仅在 async 回调内,render 纯净.
 */

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import {
  DEMO_SESSION_ID,
  listResumeCopilotSessions,
} from '@/components/resume-copilot/api';
import HubShell from '@/components/resume-copilot/workspace/hub/HubShell';

export function HubPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlSession = Number(searchParams.get('session') ?? 0) || null;

  // URL 带 ?session=N → 直接用(顶栏下拉软导航切换走 router.push,searchParams 变,
  // 这里同步派生,无需 effect+setState). 没带时才异步解析回退会话.
  const [resolvedId, setResolvedId] = useState<number | null>(null);
  const resolvedRef = useRef(false);

  // URL 没带 session → 解析:会话列表第一条,否则 demo 会话
  useEffect(() => {
    if (urlSession !== null || resolvedRef.current) return;
    let cancelled = false;
    listResumeCopilotSessions()
      .then((items) => {
        if (cancelled) return;
        resolvedRef.current = true;
        const firstId = items.length > 0 ? items[0].id : DEMO_SESSION_ID;
        router.replace(`/hub?session=${firstId}`);
        setResolvedId(firstId);
      })
      .catch(() => {
        if (cancelled) return;
        resolvedRef.current = true;
        setResolvedId(DEMO_SESSION_ID);
      });
    return () => {
      cancelled = true;
    };
  }, [urlSession, router]);

  const sessionId = urlSession ?? resolvedId;

  if (sessionId === null) {
    return <main className="p-8 text-sm text-[var(--muted)]">解析会话中…</main>;
  }

  return <HubShell sessionId={sessionId} />;
}
