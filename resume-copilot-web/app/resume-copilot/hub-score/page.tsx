'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import ResumeCanvas from '../../../components/resume-copilot/workspace/hub/ResumeCanvas';

// /resume-copilot/hub-score —— 简历优化「深链兜底页」。
// 正常入口已改成 Hub 右侧画布内嵌(见 HubShell.openView('resume') / CanvasSlot),保留
// 左侧对话不瞬移。这张全屏页只作直接带 ?session= / ?mock=1 打开的兜底/分享入口,
// 逻辑全部复用 ResumeCanvas(草稿持久化 / 翻译 / 编辑器浮层),不再各写一套。
function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  // 从 Hub 内嵌的「展开编辑器/深度优化」跳来时带 ?editor=1 → 直接展开编辑器浮层。
  const editor = params.get('editor') === '1';
  return (
    <div
      className="hf"
      data-theme="hub"
      style={{ minHeight: '100vh', background: 'var(--parchment)', display: 'flex', justifyContent: 'flex-end' }}
    >
      <div style={{ width: 500, height: '100vh', background: 'var(--ivory)', boxShadow: '-8px 0 24px rgba(0,0,0,0.06)' }}>
        <ResumeCanvas sessionId={sessionId} mock={mock} initialEditorOpen={editor} />
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div style={{ padding: 40 }}>加载中…</div>}>
      <Inner />
    </Suspense>
  );
}
