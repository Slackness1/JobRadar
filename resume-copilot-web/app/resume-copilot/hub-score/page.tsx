'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ResumeScorePanel } from '../../../components/resume-copilot/workspace/hub/resume/ResumeScorePanel';
import { ResumeEditorOverlay } from '../../../components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay';

function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  const [editorOpen, setEditorOpen] = useState(false);
  if (!mock && !sessionId) {
    return <div style={{ padding: 40, fontFamily: 'system-ui' }}>缺少 ?session=&lt;id&gt; 或 ?mock=1</div>;
  }
  return (
    <div className="hf" data-theme="hub" style={{ minHeight: '100vh', background: 'var(--parchment)', display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ width: 500, height: '100vh', background: 'var(--ivory)', boxShadow: '-8px 0 24px rgba(0,0,0,0.06)' }}>
        <ResumeScorePanel
          sessionId={sessionId}
          mock={mock}
          onExpandEditor={() => setEditorOpen(true)}
        />
      </div>
      {editorOpen && (
        <ResumeEditorOverlay sessionId={sessionId} mock={mock} onClose={() => setEditorOpen(false)} />
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
