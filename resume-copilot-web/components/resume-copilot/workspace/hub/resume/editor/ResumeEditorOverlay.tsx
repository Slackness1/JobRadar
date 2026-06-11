'use client';
import { useEffect, useRef, useState } from 'react';
import { Download, Save, X } from 'lucide-react';
import { ResumeDoc } from './ResumeDoc';
import type { Lang, LayoutState, ResumeProfile } from './resumeSample';
import { LeftTemplate } from './LeftTemplate';
import { LeftEdit } from './LeftEdit';
import { LeftLayout } from './LeftLayout';
import { EditorAIPanel } from './EditorAIPanel';
import type { DeepOptimizeStartIn } from '../../../../api';

type LeftTab = 'tpl' | 'edit' | 'layout';

const L_TABS: [LeftTab, string][] = [
  ['tpl', '模板'],
  ['edit', '简历编辑'],
  ['layout', '布局'],
];

// 后端 section path 前缀(如 'internships.0' / 'projects.1')→ 简历文档 section id。
// SAMPLE_PROFILE.sections id:edu / str / intern / proj / skills / honor。
const SECTION_PREFIX_TO_ID: Record<string, string> = {
  education: 'edu',
  educations: 'edu',
  internship: 'intern',
  internships: 'intern',
  experience: 'intern',
  experiences: 'intern',
  work: 'intern',
  project: 'proj',
  projects: 'proj',
  skill: 'skills',
  skills: 'skills',
};

function sectionToLitId(section: string): string | undefined {
  if (!section) return undefined;
  const prefix = section.split('.')[0].toLowerCase();
  return SECTION_PREFIX_TO_ID[prefix];
}

export interface ResumeEditorOverlayProps {
  onClose: () => void;
  /** 真实 session id;未传 / 0 → mock 模式(离线目测)。 */
  sessionId?: number;
  /** 显式强制 mock。默认:无 sessionId 时为 mock。 */
  mock?: boolean;
  /** 受控简历状态(与侧面板预览共用同一数据源,由 hub 页面上提)。 */
  profile: ResumeProfile;
  onProfile: (p: ResumeProfile) => void;
  template: string;
  onTemplate: (id: string) => void;
  layout: LayoutState;
  onLayout: (l: LayoutState) => void;
  hidden: Set<string>;
  onToggleHidden: (id: string) => void;
  lang: Lang;
  /** 仅用于切回中文;切到 'en' 必须走 onTranslate(en 可能为 null)。 */
  onLang: (l: Lang) => void;
  onTranslate: () => void;
  /** 翻译进行中 — EN 切换按钮显示「翻译中…」并禁用。 */
  translating?: boolean;
}

/** 简历编辑器全屏壳 — 移植自 hub-prototype ResumeEditor,右栏接 EditorAIPanel(E3)。 */
export function ResumeEditorOverlay({
  onClose,
  sessionId = 0,
  mock,
  profile,
  onProfile,
  template,
  onTemplate,
  layout,
  onLayout,
  hidden,
  onToggleHidden,
  lang,
  onLang,
  onTranslate,
  translating = false,
}: ResumeEditorOverlayProps) {
  const [leftTab, setLeftTab] = useState<LeftTab>('edit');
  const [aiTab, setAiTab] = useState<string>('score');
  const [seed, setSeed] = useState<DeepOptimizeStartIn | null>(null);
  // 当前高亮("AI 刚写回")的简历段 id。初始 intern = 实习经历(与原壳一致)。
  const [litSectionId, setLitSectionId] = useState<string | undefined>('intern');
  // 中栏实测页数(简历文档自量上报)。
  const [pages, setPages] = useState(1);
  // 中栏 A4 文档(794px)缩放到可用宽度。
  const [scale, setScale] = useState(1);
  const stageRef = useRef<HTMLDivElement>(null);

  const isMock = mock ?? !sessionId;

  // 按可用宽度把 794px A4 文档缩放进中栏(zoom 同时缩布局盒,避免横向溢出)。
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const fit = () => setScale(Math.min(1, (el.clientWidth - 48) / 794));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // 写回成功 → 把 section 映射成简历段 id 并高亮。
  const handleWriteBack = (section: string) => {
    const id = sectionToLitId(section);
    if (id) setLitSectionId(id);
  };

  // E2/E3 接线前,引用此段仅 no-op(壳态)。
  const handleQuote = (k: string) => {
    void k;
  };

  return (
    <div
      className="hf"
      data-theme="hub"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 60,
        background: 'var(--parchment)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 顶栏 */}
      <div
        style={{
          height: 52,
          flex: 'none',
          background: 'var(--ivory)',
          borderBottom: '1px solid var(--border-warm)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 18px',
          gap: 12,
        }}
      >
        <span style={{ font: '500 13px var(--font-sans)', color: 'var(--ink-soft)' }}>简历编辑器</span>
        <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 9, boxShadow: '0 0 0 1px var(--border-warm)', marginLeft: 2 }}>
          {(['zh', 'en'] as const).map((l) => (
            <button
              key={l}
              disabled={l === 'en' && translating}
              onClick={() => (l === 'en' ? onTranslate() : onLang('zh'))}
              style={{
                cursor: l === 'en' && translating ? 'not-allowed' : 'pointer',
                border: 'none', borderRadius: 7, padding: '4px 12px',
                font: `${lang === l ? 600 : 500} 11.5px var(--font-sans)`,
                color: lang === l ? 'var(--ink)' : 'var(--olive)',
                background: lang === l ? 'var(--ivory)' : 'transparent',
                boxShadow: lang === l ? '0 0 0 1px var(--border-strong)' : 'none',
                opacity: l === 'en' && translating ? 0.6 : 1,
              }}
            >
              {l === 'zh' ? '中文' : translating ? '翻译中…' : 'EN'}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="hf-btn ghost sm" style={{ marginLeft: 'auto', gap: 6 }} aria-label="关闭">
          <X size={13} /> 返回主工作台
        </button>
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

      {/* 三栏 */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '296px minmax(0,1fr) 396px', minHeight: 0 }}>
        {/* LEFT */}
        <div
          style={{
            borderRight: '1px solid var(--border-warm)',
            background: 'var(--ivory)',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
          }}
        >
          <div style={{ padding: '12px 14px 0', flex: 'none' }}>
            <div
              style={{
                display: 'flex',
                gap: 3,
                padding: 3,
                background: 'var(--library-rail)',
                borderRadius: 11,
                boxShadow: '0 0 0 1px var(--border-warm)',
              }}
            >
              {L_TABS.map(([k, t]) => (
                <button
                  key={k}
                  onClick={() => setLeftTab(k)}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    cursor: 'pointer',
                    font: `${leftTab === k ? 600 : 500} 12px var(--font-sans)`,
                    padding: '6px 0',
                    borderRadius: 8,
                    color: leftTab === k ? 'var(--ink)' : 'var(--olive)',
                    background: leftTab === k ? 'var(--ivory)' : 'transparent',
                    boxShadow: leftTab === k ? '0 0 0 1px var(--border-strong)' : 'none',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, minHeight: 0, padding: '12px 14px' }}>
            {leftTab === 'tpl' && <LeftTemplate value={template} onChange={onTemplate} />}
            {leftTab === 'edit' && <LeftEdit profile={profile} onProfile={onProfile} onQuote={handleQuote} />}
            {leftTab === 'layout' && (
              <LeftLayout
                layout={layout}
                onLayout={onLayout}
                modules={profile.sections.map((s) => ({ id: s.id, label: s.label }))}
                hidden={hidden}
                onToggleHidden={onToggleHidden}
                pages={pages}
              />
            )}
          </div>
        </div>

        {/* CENTER — WYSIWYG */}
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0, background: 'var(--parchment)' }}>
          <div
            style={{
              height: 46,
              flex: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '0 16px',
              borderBottom: '1px solid var(--border-warm)',
              background: 'var(--ivory)',
            }}
          >
            <span
              className={`hf-pill${pages > 1 ? ' amber' : ''}`}
              style={{ height: 26, fontFamily: 'var(--font-mono)' }}
            >
              {pages > 1 ? `${pages} 页 · 超 ${pages - 1} 页` : '1 页'}
            </span>
            <span style={{ font: '500 12px var(--font-sans)', color: 'var(--olive)' }}>WYSIWYG · 所见即所导出</span>
            <span style={{ marginLeft: 'auto' }} />
            <button className="hf-btn ghost sm" style={{ gap: 6 }}>
              <Save size={13} /> 保存
            </button>
            <button className="hf-btn dark sm" style={{ gap: 6 }}>
              <Download size={13} /> 下载 PDF
            </button>
          </div>
          <div
            ref={stageRef}
            style={{
              flex: 1,
              minHeight: 0,
              overflow: 'auto',
              padding: '28px 0',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'flex-start',
            }}
          >
            <div style={{ zoom: scale }}>
              <ResumeDoc
                profile={profile}
                templateId={template}
                layout={layout}
                hidden={hidden}
                litSectionId={litSectionId}
                onPages={setPages}
              />
            </div>
          </div>
        </div>

        {/* RIGHT — AI 简历助手 v2(E3) */}
        <EditorAIPanel
          sessionId={sessionId}
          seed={seed}
          setSeed={setSeed}
          tab={aiTab}
          setTab={setAiTab}
          onWriteBack={handleWriteBack}
          mock={isMock}
        />
      </div>
    </div>
  );
}
