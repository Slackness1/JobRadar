'use client';
import { useEffect, useRef, useState } from 'react';
import { HubRadar, type RadarDatum } from './HubRadar';
import { ResumeDoc } from './editor/ResumeDoc';
import { TEMPLATES, type Lang, type LayoutState, type ResumeProfile } from './editor/resumeSample';
import { scoreResume, type ScoreReportData } from '../../../api';

export interface ResumeScorePanelProps {
  sessionId: number;
  onExpandEditor: () => void;
  onClose?: () => void;
  /** 无 session 时渲染原型样例,供独立目测 */
  mock?: boolean;
  /** 受控简历状态(与全屏编辑器共用同一数据源)。 */
  profile: ResumeProfile;
  template: string;
  onTemplate: (id: string) => void;
  layout: LayoutState;
  hidden: Set<string>;
  lang: Lang;
  onLang: (l: Lang) => void;
  onTranslate: () => void;
}

// 8 维 → 雷达短标签 + 金融维标记(对齐原型 R_RADAR 顺序)
const RADAR_META: { key: string; k: string; fin?: boolean }[] = [
  { key: 'logic', k: '逻辑' }, { key: 'star', k: 'STAR' }, { key: 'readability', k: '可读' },
  { key: 'completeness', k: '完整' }, { key: 'expression', k: '表达' }, { key: 'quantification', k: '量化' },
  { key: 'track_fit', k: '匹配度', fin: true }, { key: 'defensibility', k: '佐证', fin: true },
];

const MOCK: ScoreReportData = {
  session_id: 0, target_track: '量化私募 · 研究', overall_current: 72,
  overall_potential_low: 80, overall_potential_high: 85, summary: '',
  dimensions: [
    { key: 'logic', name: '逻辑清晰', score: 78, ceiling: 86, reason: '' },
    { key: 'star', name: 'STAR 应用', score: 58, ceiling: 84, reason: '' },
    { key: 'readability', name: '内容可读', score: 84, ceiling: 88, reason: '' },
    { key: 'completeness', name: '内容完整', score: 70, ceiling: 80, reason: '' },
    { key: 'expression', name: '专业表达', score: 80, ceiling: 86, reason: '' },
    { key: 'quantification', name: '成果量化', score: 52, ceiling: 82, reason: '' },
    { key: 'track_fit', name: '赛道匹配度', score: 64, ceiling: 82, reason: '' },
    { key: 'defensibility', name: '佐证充分度', score: 55, ceiling: 80, reason: '' },
  ],
  section_gaps: [
    { section: 'internships.0', label: '九坤投资 · 量化研究实习', gaps: ['STAR 缺 Result', '佐证不足'], detail: '' },
    { section: 'projects.1', label: '校园量化策略项目', gaps: ['成果无量化锚点'], detail: '' },
  ],
  used_ai: false,
};

/** 简历优化画布槽侧面板:契约 props {sessionId,onExpandEditor,onClose}(orchestrator 传)。 */
export function ResumeScorePanel({
  sessionId,
  onExpandEditor,
  onClose,
  mock = false,
  profile,
  template,
  onTemplate,
  layout,
  hidden,
  lang,
  onLang,
  onTranslate,
}: ResumeScorePanelProps) {
  const [view, setView] = useState<'score' | 'preview'>('score');
  const [report, setReport] = useState<ScoreReportData | null>(mock ? MOCK : null);
  const [loading, setLoading] = useState(!mock);
  const [error, setError] = useState('');
  // 预览缩放 + 页数
  const [pages, setPages] = useState(1);
  const [scale, setScale] = useState(0.5);
  const previewRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mock || !sessionId) return;
    let alive = true;
    scoreResume(sessionId)
      .then((r) => { if (alive) { setReport(r); setError(''); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : '打分失败'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [mock, sessionId]);

  // 把 794px A4 缩放进侧栏预览宽度(进入预览 tab 时挂载量宽)。
  useEffect(() => {
    if (view !== 'preview') return;
    const el = previewRef.current;
    if (!el) return;
    const fit = () => setScale(Math.min(1, (el.clientWidth - 32) / 794));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [view]);

  const radarData: RadarDatum[] = report
    ? RADAR_META.map((m) => ({ k: m.k, fin: m.fin, v: report.dimensions.find((d) => d.key === m.key)?.score ?? 0 }))
    : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* chrome */}
      <div style={{ padding: '13px 16px 0', background: 'var(--ivory)', borderBottom: '1px solid var(--border-warm)', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>简历优化</div>
            <div style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>诚实打分 + 深度优化 · 写回实时刷新</div>
          </div>
          <button className="hf-btn ghost sm" style={{ gap: 6 }} onClick={onExpandEditor}>展开编辑器</button>
          {onClose && <button className="hf-btn ghost sm" onClick={onClose} aria-label="关闭">✕</button>}
        </div>
        <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 11, boxShadow: '0 0 0 1px var(--border-warm)', margin: '12px 0 13px' }}>
          {([['score', '打分报告'], ['preview', '简历预览']] as const).map(([k, t]) => (
            <button key={k} onClick={() => setView(k)} style={{
              flex: 1, textAlign: 'center', cursor: 'pointer', border: 'none',
              font: `${view === k ? 600 : 500} 12.5px var(--font-sans)`, padding: '7px 0', borderRadius: 8,
              color: view === k ? 'var(--ink)' : 'var(--olive)', background: view === k ? 'var(--ivory)' : 'transparent',
              boxShadow: view === k ? '0 0 0 1px var(--border-strong), 0 1px 2px rgba(0,0,0,0.04)' : 'none',
            }}>{t}</button>
          ))}
        </div>
      </div>

      {loading && <div style={{ padding: 40, color: 'var(--stone)', font: '400 13px var(--font-sans)' }}>打分中…</div>}
      {error && <div style={{ padding: 40, color: 'var(--terracotta-strong)', font: '400 13px var(--font-sans)' }}>打分失败:{error}</div>}

      {report && view === 'score' && (
        <div style={{ flex: 1, overflow: 'auto', padding: 16, background: 'var(--parchment)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <span className="hf-overline" style={{ fontSize: 9.5 }}>目标赛道</span>
            <span className="hf-pill terra" style={{ height: 26 }}>{report.target_track || '未定'} ▾</span>
            <span style={{ marginLeft: 'auto', font: '500 11px var(--font-sans)', color: 'var(--stone)' }}>切换重打分</span>
          </div>
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 16 }}>
            <div style={{ flex: 'none', textAlign: 'center' }}>
              <div style={{ font: '500 46px/0.9 var(--font-mono)', color: 'var(--ink)' }}>{report.overall_current}</div>
              <div style={{ font: '500 11px var(--font-sans)', color: 'var(--olive)', marginTop: 4 }}>现状分</div>
              <div className="hf-pill" style={{ height: 24, marginTop: 9, fontFamily: 'var(--font-mono)' }}>潜力 {report.overall_potential_low}–{report.overall_potential_high}</div>
            </div>
            <div style={{ flex: 1, background: 'var(--ivory)', borderRadius: 14, boxShadow: 'var(--sh-ring)', display: 'flex', justifyContent: 'center', padding: 8 }}>
              <HubRadar size={172} data={radarData} />
            </div>
          </div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>逐段缺口 · 深度优化入口</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {report.section_gaps.map((g, i) => (
              <div key={i} style={{ borderRadius: 13, padding: '12px 13px', background: 'var(--ivory)', boxShadow: 'var(--sh-ring)' }}>
                <div style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>{g.label}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
                  {g.gaps.map((t, j) => <span key={j} className="hf-pill" style={{ height: 22, fontSize: 10.5, whiteSpace: 'nowrap' }}>{t}</span>)}
                </div>
                <button className="hf-btn sand sm" style={{ height: 30 }} onClick={onExpandEditor}>去深度优化这段 →</button>
              </div>
            ))}
          </div>
          <div style={{ font: '400 10.5px/1.5 var(--font-sans)', color: 'var(--stone)', textAlign: 'center', marginTop: 12 }}>只诊断、不改写 · 提分靠深度优化反问取证</div>
        </div>
      )}

      {report && view === 'preview' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--parchment)' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border-warm)', background: 'var(--ivory)', display: 'flex', alignItems: 'center', gap: 7, flex: 'none' }}>
            <span className={`hf-pill${pages > 1 ? ' amber' : ''}`} style={{ height: 26, fontFamily: 'var(--font-mono)' }}>
              {pages > 1 ? `${pages} 页` : '1 页'}
            </span>
            <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 9, boxShadow: '0 0 0 1px var(--border-warm)' }}>
              {(['zh', 'en'] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => (l === 'en' ? onTranslate() : onLang('zh'))}
                  style={{
                    cursor: 'pointer', border: 'none', borderRadius: 7, padding: '3px 10px',
                    font: `${lang === l ? 600 : 500} 11px var(--font-sans)`,
                    color: lang === l ? 'var(--ink)' : 'var(--olive)',
                    background: lang === l ? 'var(--ivory)' : 'transparent',
                    boxShadow: lang === l ? '0 0 0 1px var(--border-strong)' : 'none',
                  }}
                >
                  {l === 'zh' ? '中文' : 'EN'}
                </button>
              ))}
            </div>
            {/* 真模板下拉:原生 select 罩在 pill 样式上 */}
            <span className="hf-pill" style={{ height: 26, position: 'relative', paddingRight: 22 }}>
              模板 · {TEMPLATES.find((t) => t.id === template)?.name ?? '素白单栏'} ▾
              <select
                value={template}
                onChange={(e) => onTemplate(e.target.value)}
                aria-label="切换模板"
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer', border: 'none' }}
              >
                {TEMPLATES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </span>
            <button className="hf-btn dark sm" style={{ marginLeft: 'auto', height: 28 }} onClick={onExpandEditor}>下载 PDF</button>
          </div>
          <div ref={previewRef} style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '18px 0', display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
            <div style={{ zoom: scale }}>
              <ResumeDoc profile={profile} templateId={template} layout={layout} hidden={hidden} onPages={setPages} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
