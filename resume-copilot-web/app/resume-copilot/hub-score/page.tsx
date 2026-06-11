'use client';
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ResumeScorePanel } from '../../../components/resume-copilot/workspace/hub/resume/ResumeScorePanel';
import { ResumeEditorOverlay } from '../../../components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay';
import {
  SAMPLE_PROFILE,
  DEFAULT_LAYOUT,
  profilePayloadToResumeProfile,
  type LayoutState,
  type ResumeProfile,
} from '../../../components/resume-copilot/workspace/hub/resume/editor/resumeSample';
import {
  getResumeCopilotConfirmedProfile,
  getResumeCopilotParsedProfile,
} from '../../../components/resume-copilot/api';

function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  const [editorOpen, setEditorOpen] = useState(false);
  // 共享简历状态:面板预览 + 全屏编辑器同一数据源。mock=1 用示例;真实 ?session=N
  // 时下方 effect 拉后端 confirmed(回退 parsed)profile 映射后覆盖。
  const [profile, setProfile] = useState<ResumeProfile>(SAMPLE_PROFILE);

  // 真实会话:拉真简历 profile 喂进编辑器/预览(确认版优先,回退解析版)。
  useEffect(() => {
    if (mock || !sessionId) return;
    let cancelled = false;
    getResumeCopilotConfirmedProfile(sessionId)
      .then((r) => {
        if (!cancelled && r?.profile) setProfile(profilePayloadToResumeProfile(r.profile));
      })
      .catch(() => {
        getResumeCopilotParsedProfile(sessionId)
          .then((r) => {
            if (!cancelled && r?.profile) setProfile(profilePayloadToResumeProfile(r.profile));
          })
          .catch(() => {
            /* 都拿不到则保持示例,不致崩 */
          });
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, mock]);
  const [template, setTemplate] = useState<string>('classic');
  const [layout, setLayout] = useState<LayoutState>(DEFAULT_LAYOUT);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const toggleHidden = (id: string) =>
    setHidden((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

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
          profile={profile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          hidden={hidden}
        />
      </div>
      {editorOpen && (
        <ResumeEditorOverlay
          sessionId={sessionId}
          mock={mock}
          onClose={() => setEditorOpen(false)}
          profile={profile}
          onProfile={setProfile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          onLayout={setLayout}
          hidden={hidden}
          onToggleHidden={toggleHidden}
        />
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
