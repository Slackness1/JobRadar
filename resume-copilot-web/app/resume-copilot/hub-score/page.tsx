'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ResumeScorePanel } from '../../../components/resume-copilot/workspace/hub/resume/ResumeScorePanel';

function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  const [editorMsg, setEditorMsg] = useState('');
  if (!mock && !sessionId) {
    return <div style={{ padding: 40, fontFamily: 'system-ui' }}>缺少 ?session=&lt;id&gt; 或 ?mock=1</div>;
  }
  return (
    <div className="hf" data-theme="hub" style={{ minHeight: '100vh', background: 'var(--parchment)', display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ width: 500, height: '100vh', background: 'var(--ivory)', boxShadow: '-8px 0 24px rgba(0,0,0,0.06)' }}>
        <ResumeScorePanel
          sessionId={sessionId}
          mock={mock}
          onExpandEditor={() => setEditorMsg('（展开编辑器 → Phase 2 全屏 overlay）')}
          onClose={() => setEditorMsg('（关闭面板）')}
        />
      </div>
      {editorMsg && (
        <div style={{ position: 'fixed', left: 16, bottom: 16, font: '400 12px var(--font-sans)', color: 'var(--stone)' }}>{editorMsg}</div>
      )}
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
