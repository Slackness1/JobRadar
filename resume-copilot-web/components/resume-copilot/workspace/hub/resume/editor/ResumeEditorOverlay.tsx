'use client';
import { useState } from 'react';
import { Download, Save, X } from 'lucide-react';
import { A4Doc, type EditorSection } from './A4Doc';
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

// 中栏 A4 mock 内容 — 实习经历段被点亮("AI 刚写回")。
const MOCK_SECTIONS: EditorSection[] = [
  { title: '教育经历', lines: ['100%', '100%', '56%'] },
  {
    title: '实习经历',
    bullet: '搭建覆盖 40+ 量价因子的回测框架(2021–2023),将单因子筛选由手动改为一键批量,显著缩短迭代周期。',
  },
  { title: '项目经历', lines: ['100%', '100%', '74%'] },
  { title: '掌握技能', lines: ['100%', '56%'] },
];

// 后端 section path 前缀(如 'internships.0' / 'projects.1')→ 中栏 MOCK_SECTIONS 索引。
// MOCK_SECTIONS 顺序:0 教育经历 / 1 实习经历 / 2 项目经历 / 3 掌握技能。
const SECTION_PREFIX_TO_INDEX: Record<string, number> = {
  education: 0,
  educations: 0,
  internship: 1,
  internships: 1,
  experience: 1,
  experiences: 1,
  work: 1,
  project: 2,
  projects: 2,
  skill: 3,
  skills: 3,
};

function sectionToLitIndex(section: string): number | undefined {
  if (!section) return undefined;
  const prefix = section.split('.')[0].toLowerCase();
  return SECTION_PREFIX_TO_INDEX[prefix];
}

export interface ResumeEditorOverlayProps {
  onClose: () => void;
  /** 真实 session id;未传 / 0 → mock 模式(离线目测)。 */
  sessionId?: number;
  /** 显式强制 mock。默认:无 sessionId 时为 mock。 */
  mock?: boolean;
}

/** 简历编辑器全屏壳 — 移植自 hub-prototype ResumeEditor,右栏接 EditorAIPanel(E3)。 */
export function ResumeEditorOverlay({ onClose, sessionId = 0, mock }: ResumeEditorOverlayProps) {
  const [leftTab, setLeftTab] = useState<LeftTab>('edit');
  const [aiTab, setAiTab] = useState<string>('score');
  const [seed, setSeed] = useState<DeepOptimizeStartIn | null>(null);
  // 当前高亮("AI 刚写回")的中栏段索引。初始 1 = 实习经历(与原壳一致)。
  const [litSection, setLitSection] = useState<number>(1);

  const isMock = mock ?? !sessionId;

  // 写回成功 → 把 section 映射成 A4 lit 索引并高亮。
  const handleWriteBack = (section: string) => {
    const idx = sectionToLitIndex(section);
    if (idx !== undefined) setLitSection(idx);
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
        <span className="hf-pill" style={{ height: 24, marginLeft: 2 }}>
          中文主版
        </span>
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
            {leftTab === 'tpl' && <LeftTemplate />}
            {leftTab === 'edit' && <LeftEdit onQuote={handleQuote} />}
            {leftTab === 'layout' && <LeftLayout />}
          </div>
        </div>

        {/* CENTER — WYSIWYG */}
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--parchment)' }}>
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
            <span className="hf-pill" style={{ height: 26, fontFamily: 'var(--font-mono)' }}>
              1 页
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
            style={{
              flex: 1,
              overflow: 'auto',
              padding: '28px 0',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'flex-start',
            }}
          >
            <A4Doc sections={MOCK_SECTIONS} lit={litSection} />
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
