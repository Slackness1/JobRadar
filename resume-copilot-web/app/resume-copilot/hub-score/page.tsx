'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ResumeScorePanel } from '../../../components/resume-copilot/workspace/hub/resume/ResumeScorePanel';
import { ResumeEditorOverlay } from '../../../components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay';
import {
  SAMPLE_PROFILE,
  SAMPLE_PROFILE_EN,
  DEFAULT_LAYOUT,
  type Lang,
  type LayoutState,
  type ResumeProfile,
} from '../../../components/resume-copilot/workspace/hub/resume/editor/resumeSample';

function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  const [editorOpen, setEditorOpen] = useState(false);
  // 双语简历:zh 源 + en(翻译后填充)+ 当前语言。模板/布局/显隐为共享态(下方)。
  const [zh, setZh] = useState<ResumeProfile>(SAMPLE_PROFILE);
  const [en, setEn] = useState<ResumeProfile | null>(null);
  const [lang, setLang] = useState<Lang>('zh');
  const activeProfile = lang === 'en' && en ? en : zh;
  const setActiveProfile = (p: ResumeProfile) => (lang === 'en' ? setEn(p) : setZh(p));
  // A 期:翻译先用手译示例占位;B 期 Task B5 换成真后端调用。
  const handleTranslate = () => {
    setEn(SAMPLE_PROFILE_EN);
    setLang('en');
  };
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
          profile={activeProfile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          hidden={hidden}
          lang={lang}
          onLang={setLang}
          onTranslate={handleTranslate}
        />
      </div>
      {editorOpen && (
        <ResumeEditorOverlay
          sessionId={sessionId}
          mock={mock}
          onClose={() => setEditorOpen(false)}
          profile={activeProfile}
          onProfile={setActiveProfile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          onLayout={setLayout}
          hidden={hidden}
          onToggleHidden={toggleHidden}
          lang={lang}
          onLang={setLang}
          onTranslate={handleTranslate}
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
