'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Download, GitBranch, Quote, Save, X } from 'lucide-react';
import { ResumeDoc } from './ResumeDoc';
import type { Lang, LayoutState, ResumeProfile } from './resumeSample';
import { LeftTemplate } from './LeftTemplate';
import { LeftEdit } from './LeftEdit';
import { LeftLayout } from './LeftLayout';
import { EditorAIPanel } from './EditorAIPanel';
import type { ResumeVersion } from './versionTypes';
import {
  getResumeVersions,
  putResumeVersions,
  getScoreTaskStatus,
  type PendingQuote,
  type ScoreReportData,
} from '../../../../api';

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

// 简历文档 section id → 后端 section path 前缀(SECTION_PREFIX_TO_ID 的反向)。
// 引用此段 + 选行引用都用它把文档段映射回后端 path。
const ID_TO_SECTION_PREFIX: Record<string, string> = {
  edu: 'education',
  intern: 'internships',
  proj: 'projects',
  skills: 'skills',
};

// 从选区某个节点往上找最近带 data-blk 的祖先,解析出 {docId, itemIdx}。
// data-blk 形如 it:<docId>:<i> / pa:<docId>:<i> / sk:<docId> / tg:<docId> / hd:<docId>。
function resolveBlkFromNode(node: Node | null): { docId: string; itemIdx: number } | null {
  let el: HTMLElement | null =
    node && node.nodeType === Node.ELEMENT_NODE
      ? (node as HTMLElement)
      : (node?.parentElement ?? null);
  while (el) {
    const blk = el.getAttribute?.('data-blk');
    if (blk) {
      const parts = blk.split(':');
      if (parts.length >= 2 && parts[1]) {
        const itemIdx = parts.length >= 3 ? Number(parts[2]) : 0;
        return { docId: parts[1], itemIdx: Number.isFinite(itemIdx) ? itemIdx : 0 };
      }
    }
    el = el.parentElement;
  }
  return null;
}

// 选区文本估行数:按非空行计;不少于 1。
function countSelectedLines(text: string): number {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  return Math.max(1, lines.length);
}

// 深拷贝简历快照(版本互不影响)。
function snapshotProfile(p: ResumeProfile): ResumeProfile {
  return JSON.parse(JSON.stringify(p)) as ResumeProfile;
}

// 版本保存时间的友好展示。
function fmtSavedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60_000) return '刚刚';
  const sameDay = new Date().toDateString() === d.toDateString();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  if (sameDay) return `今天 ${hh}:${mm}`;
  const mo = d.getMonth() + 1;
  const da = d.getDate();
  return `${mo} 月 ${da} 日 ${hh}:${mm}`;
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
  /** 保存(落本地草稿 + flush)。宿主页注入。 */
  onSave?: () => void;
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
  onSave,
  lang,
  onLang,
  onTranslate,
  translating = false,
}: ResumeEditorOverlayProps) {
  const [leftTab, setLeftTab] = useState<LeftTab>('edit');
  const [aiTab, setAiTab] = useState<string>('score');
  // 「待引用」低调引子 — 引用此段 / 选行引用挂在这里,不自动发问;
  // 用户在深度优化输入框打字发送时才据此启动深度优化。
  const [pendingQuote, setPendingQuote] = useState<PendingQuote | null>(null);
  // 中间文档选区浮条:有选中文本时显示「已选 N 行 · 引用」。
  const [selChip, setSelChip] = useState<{ top: number; left: number; lines: number } | null>(null);
  // 暂存当前选区解析结果(点「引用」时落成 pendingQuote)。
  const pendingSelRef = useRef<PendingQuote | null>(null);
  // 中间文档容器(限定只在文档内的选区才触发)。
  const docRef = useRef<HTMLDivElement>(null);
  // 当前高亮("AI 刚写回")的简历段 id。只在真实写回(深度优化落笔)后亮;
  // 初始绝不预亮 —— 之前硬编码初始亮在实习经历, 没写回也顶着"AI 刚写回"是撒谎。
  const [litSectionId, setLitSectionId] = useState<string | undefined>(undefined);
  // 中栏实测页数(简历文档自量上报)。
  const [pages, setPages] = useState(1);
  // 中栏 A4 文档(794px)缩放到可用宽度。
  const [scale, setScale] = useState(1);
  const stageRef = useRef<HTMLDivElement>(null);

  const isMock = mock ?? !sessionId;

  // ── 简历版本 ──────────────────────────────────────────────────────────────
  // 显式保存才记一版(快照当前 profile);一版对应一份打分报告(可为 null=未打分)。
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [currentVid, setCurrentVid] = useState<string>('');
  // 打分面板当前展示的是哪一版的报告(切版本时,目标版无报告就留旧报告不切)。
  const [shownReportVid, setShownReportVid] = useState<string>('');
  const [verOpen, setVerOpen] = useState(false);
  const [versionsReady, setVersionsReady] = useState(false);
  // 版本组写库(整组替换);demo / 只读 403 静默吞掉。
  const persistVersions = useCallback(
    (next: ResumeVersion[]) => {
      if (isMock || !sessionId) return;
      putResumeVersions(sessionId, next as unknown[]).catch(() => {
        /* demo / 只读 session 403 → 内存态继续 */
      });
    },
    [isMock, sessionId],
  );

  // 挂载:从后端水合版本组;空则用当前 profile 起一版 V1(尽量补一份现有报告)。
  useEffect(() => {
    let alive = true;
    const seedInitial = async (): Promise<ResumeVersion> => {
      let report: ScoreReportData | null = null;
      if (!isMock && sessionId) {
        // 只认服务端「已完成」的真实打分(它打的是库里完整简历)。不读 localStorage 短缓存
        // —— 那个缓存可能是简历还空时打的 0 分,会被当成 V1 成绩误显(实测 cz9z V1=0 即此因)。
        // 没有就留 null → 进编辑器自动给当前简历打一次真分(见 EditorScoreReportThick 自动打分)。
        try {
          const st = await getScoreTaskStatus(sessionId);
          if (st.status === 'done' && st.report) report = st.report;
        } catch {
          /* 没有就 null,自动/显式重新打分再补 */
        }
      }
      return {
        id: 'v1',
        label: 'V1',
        savedAt: new Date().toISOString(),
        profile: snapshotProfile(profile),
        report,
      };
    };
    const hydrate = async () => {
      if (isMock || !sessionId) {
        if (!alive) return;
        const v1 = await seedInitial();
        if (!alive) return;
        setVersions([v1]);
        setCurrentVid(v1.id);
        setShownReportVid(v1.id);
        setVersionsReady(true);
        return;
      }
      try {
        const { versions: raw } = await getResumeVersions(sessionId);
        if (!alive) return;
        const list = (raw as ResumeVersion[]) ?? [];
        if (list.length) {
          setVersions(list);
          const last = list[list.length - 1];
          setCurrentVid(last.id);
          // 展示报告默认取「最新一个有报告的版本」,没有就停在最新版。
          const lastWithReport = [...list].reverse().find((v) => v.report);
          setShownReportVid((lastWithReport ?? last).id);
          setVersionsReady(true);
          return;
        }
      } catch {
        /* 取版本失败 → 退回内存态 V1 */
      }
      if (!alive) return;
      const v1 = await seedInitial();
      if (!alive) return;
      setVersions([v1]);
      setCurrentVid(v1.id);
      setShownReportVid(v1.id);
      setVersionsReady(true);
      persistVersions([v1]);
    };
    void hydrate();
    return () => {
      alive = false;
    };
    // 只在挂载 / session 切换时水合一次(profile 后续变动不重水合)。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, isMock]);

  // 显式保存 → 记一版(快照当前 profile,新版本暂无报告 → 打分面板停旧报告 → 转“不一致”)。
  // "已保存 ✓" 瞬时反馈(点击时亮起 ~1.6s, 不走 effect)。
  const [justSaved, setJustSaved] = useState(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSave = () => {
    onSave?.();
    setVersions((vs) => {
      const n = vs.length + 1;
      const v: ResumeVersion = {
        id: `v${n}-${Date.now().toString(36)}`,
        label: `V${n}`,
        savedAt: new Date().toISOString(),
        profile: snapshotProfile(profile),
        report: null,
      };
      const next = [...vs, v];
      setCurrentVid(v.id);
      persistVersions(next);
      return next;
    });
    setJustSaved(true);
    if (savedTimer.current) clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setJustSaved(false), 1600);
  };

  // 切版本 → 载入该版 profile;该版有报告就切到它,没有就留旧报告(不 blank)。
  const switchVersion = (v: ResumeVersion) => {
    setCurrentVid(v.id);
    onProfile(snapshotProfile(v.profile));
    if (v.report) setShownReportVid(v.id);
    setVerOpen(false);
  };

  // 重新打分跑出报告 → 盖到当前版本上,并把打分面板切到当前版。
  const handleRescored = (report: ScoreReportData) => {
    setVersions((vs) => {
      const next = vs.map((v) => (v.id === currentVid ? { ...v, report } : v));
      persistVersions(next);
      return next;
    });
    setShownReportVid(currentVid);
  };

  const currentVersion = versions.find((v) => v.id === currentVid);
  const shownVersion = versions.find((v) => v.id === shownReportVid);
  const shownReport = shownVersion?.report ?? null;
  const reportStale = Boolean(currentVid) && shownReportVid !== currentVid;

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

  // 「引用此段」改造:不再 setSeed 自动发问。只挂一个低调「待引用」引子,
  // 把该段内容作为引用文字 + section/label 记下 → 切到深度优化 tab。
  // 真正启动深度优化交给用户在输入框主动发第一句(见 ChatThread)。
  const handleQuote = (sectionId: string, itemIdx: number) => {
    const sec = profile.sections.find((s) => s.id === sectionId);
    const item =
      sec && sec.type === 'timeline' ? sec.items[itemIdx] : undefined;
    const label = [sec?.label, item?.org].filter(Boolean).join(' · ') || '这段经历';
    const prefix = ID_TO_SECTION_PREFIX[sectionId] ?? sectionId;
    // 引用文字:该 item 的描述 + bullet(没有就用 sub / 标题兜底)。
    const text =
      item
        ? [item.sub, item.desc, ...(item.bullets ?? [])].filter(Boolean).join('\n') || label
        : label;
    setPendingQuote({ text, section: `${prefix}.${itemIdx}`, label, target_track: '' });
    setAiTab('deep');
  };

  // 中间文档选区监听:在文档容器内选中 ≥1 行文本 → 浮出「已选 N 行 · 引用」。
  useEffect(() => {
    const onSelChange = () => {
      const sel = window.getSelection();
      const doc = docRef.current;
      if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !doc) {
        setSelChip(null);
        pendingSelRef.current = null;
        return;
      }
      const range = sel.getRangeAt(0);
      // 只认完全落在中间文档容器内的选区(右栏对话 / 左栏 tab 不触发)。
      if (!doc.contains(range.commonAncestorContainer)) {
        setSelChip(null);
        pendingSelRef.current = null;
        return;
      }
      const text = sel.toString();
      if (!text.trim()) {
        setSelChip(null);
        pendingSelRef.current = null;
        return;
      }
      const blk = resolveBlkFromNode(range.startContainer);
      const docId = blk?.docId ?? '';
      const sec = docId ? profile.sections.find((s) => s.id === docId) : undefined;
      const itemIdx = blk?.itemIdx ?? 0;
      const item = sec && sec.type === 'timeline' ? sec.items[itemIdx] : undefined;
      const label = [sec?.label, item?.org].filter(Boolean).join(' · ') || '简历片段';
      const prefix = docId ? ID_TO_SECTION_PREFIX[docId] ?? docId : '';
      pendingSelRef.current = {
        text: text.trim(),
        section: prefix ? `${prefix}.${itemIdx}` : '',
        label,
        target_track: '',
      };
      // 浮条位置:选区末端附近,换算成相对文档容器(可滚动)的坐标。
      const rects = range.getClientRects();
      const last = rects.length ? rects[rects.length - 1] : range.getBoundingClientRect();
      const box = doc.getBoundingClientRect();
      setSelChip({
        top: last.bottom - box.top + doc.scrollTop + 6,
        left: Math.max(8, last.right - box.left + doc.scrollLeft - 60),
        lines: countSelectedLines(text),
      });
    };
    document.addEventListener('selectionchange', onSelChange);
    return () => document.removeEventListener('selectionchange', onSelChange);
  }, [profile]);

  const handleSelQuote = () => {
    if (pendingSelRef.current) {
      setPendingQuote(pendingSelRef.current);
      setAiTab('deep');
    }
    setSelChip(null);
    window.getSelection()?.removeAllRanges();
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
          {/* overflow: 滚动链条在这层闭合 — 子组件自身 overflow:auto 但没有高度约束,
              少了这层会让长内容(多段实习/项目)溢出被全屏壳裁掉、永远滚不到(2026-06-12 反馈) */}
          <div style={{ flex: 1, minHeight: 0, padding: '12px 14px', overflow: 'auto' }}>
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
            <span style={{ marginLeft: 'auto' }} />
            {/* 版本切换器 · 在「保存」左边 */}
            <div style={{ position: 'relative' }}>
              <button
                className="hf-btn ghost sm"
                style={{ gap: 6 }}
                onClick={() => setVerOpen((v) => !v)}
                title="简历版本 · 显式保存记一版"
              >
                <GitBranch size={13} />
                {currentVersion?.label ?? 'V1'}
                {reportStale && (
                  <span
                    style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--amber-fg)' }}
                  />
                )}
                <ChevronDown size={11} />
              </button>
              {verOpen && (
                <>
                  <div
                    onClick={() => setVerOpen(false)}
                    style={{ position: 'fixed', inset: 0, zIndex: 40 }}
                  />
                  <div
                    className="hub-pop"
                    style={{
                      position: 'absolute',
                      top: 'calc(100% + 7px)',
                      right: 0,
                      zIndex: 41,
                      width: 256,
                      background: 'var(--ivory)',
                      borderRadius: 14,
                      boxShadow: 'var(--sh-paper)',
                      padding: 6,
                      transformOrigin: '90% 0',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '6px 8px 8px' }}>
                      <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex' }}>
                        <GitBranch size={13} />
                      </span>
                      <span className="hf-overline" style={{ color: 'var(--olive)' }}>
                        简历版本
                      </span>
                      <span
                        style={{
                          marginLeft: 'auto',
                          font: '400 10.5px var(--font-sans)',
                          color: 'var(--stone)',
                        }}
                      >
                        显式保存
                      </span>
                    </div>
                    {versions
                      .slice()
                      .reverse()
                      .map((v) => {
                        const on = v.id === currentVid;
                        return (
                          <button
                            key={v.id}
                            onClick={() => switchVersion(v)}
                            style={{
                              width: '100%',
                              textAlign: 'left',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 10,
                              padding: '9px 10px',
                              borderRadius: 10,
                              cursor: 'pointer',
                              marginBottom: 2,
                              border: 'none',
                              background: on ? 'var(--terracotta-wash)' : 'transparent',
                              boxShadow: on ? '0 0 0 1px #eccfb6' : 'none',
                            }}
                            onMouseEnter={(e) => {
                              if (!on) e.currentTarget.style.background = 'var(--library-rail)';
                            }}
                            onMouseLeave={(e) => {
                              if (!on) e.currentTarget.style.background = 'transparent';
                            }}
                          >
                            <span
                              style={{
                                flex: 'none',
                                width: 30,
                                height: 30,
                                borderRadius: 8,
                                display: 'grid',
                                placeItems: 'center',
                                font: '600 12px var(--font-mono)',
                                color: on ? '#fff' : 'var(--ink-soft)',
                                background: on ? 'var(--terracotta)' : 'var(--ivory)',
                                boxShadow: on ? 'none' : '0 0 0 1px var(--border-warm)',
                              }}
                            >
                              {v.label}
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ font: `${on ? 600 : 500} 12.5px var(--font-sans)`, color: 'var(--ink)' }}>
                                {v.label === 'V1' ? '初始版' : `保存于 ${fmtSavedAt(v.savedAt)}`}
                              </div>
                              <div
                                style={{
                                  font: '400 10.5px var(--font-mono)',
                                  color: v.report ? 'var(--emerald)' : 'var(--stone)',
                                  marginTop: 2,
                                }}
                              >
                                {v.report ? `已打分 · ${v.report.overall_current}` : '未打分'}
                              </div>
                            </div>
                            {on && (
                              <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex', flex: 'none' }}>
                                <Check size={14} />
                              </span>
                            )}
                          </button>
                        );
                      })}
                  </div>
                </>
              )}
            </div>
            <button
              className="hf-btn ghost sm"
              style={{ gap: 6, color: justSaved ? 'var(--olive)' : undefined }}
              onClick={handleSave}
              title="保存当前编辑(本地, 刷新不丢)· 记一版"
            >
              <Save size={13} /> {justSaved ? '已保存 ✓' : '保存'}
            </button>
            <button
              className="hf-btn dark sm"
              style={{ gap: 6 }}
              onClick={() => window.print()}
              title="导出 PDF(浏览器打印 → 另存为 PDF)"
            >
              <Download size={13} /> 下载 PDF
            </button>
          </div>
          <div
            ref={(el) => {
              stageRef.current = el;
              docRef.current = el;
            }}
            style={{
              position: 'relative',
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
            {/* 选行引用浮条:跟随选区,点了挂成低调引用条 */}
            {selChip && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={handleSelQuote}
                style={{
                  position: 'absolute',
                  top: selChip.top,
                  left: selChip.left,
                  zIndex: 5,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  height: 28,
                  padding: '0 11px',
                  borderRadius: 999,
                  cursor: 'pointer',
                  font: '600 11.5px var(--font-sans)',
                  color: 'var(--ivory)',
                  background: 'var(--terracotta)',
                  border: 'none',
                  boxShadow: '0 4px 14px rgba(201,100,66,0.32)',
                }}
              >
                <Quote size={12} /> 已选 {selChip.lines} 行 · 引用
              </button>
            )}
          </div>
        </div>

        {/* RIGHT — AI 简历助手 v2(E3) */}
        <EditorAIPanel
          sessionId={sessionId}
          pendingQuote={pendingQuote}
          setPendingQuote={setPendingQuote}
          tab={aiTab}
          setTab={setAiTab}
          onWriteBack={handleWriteBack}
          mock={isMock}
          // 版本对应 + 重新打分
          versionsReady={versionsReady}
          versions={versions}
          shownReport={shownReport}
          shownVName={shownVersion?.label}
          currentVName={currentVersion?.label}
          reportStale={reportStale}
          currentProfile={profile}
          targetTrack={shownReport?.target_track}
          onRescored={handleRescored}
          // 历史:点报告项 → 切到那一版报告
          onOpenReportVid={(vid) => {
            const v = versions.find((x) => x.id === vid);
            if (v?.report) setShownReportVid(vid);
            setAiTab('score');
          }}
        />
      </div>

      {/* 打印副本 — 「下载 PDF」走 window.print(),只打印这份 1:1 的 A4 文档。
          直挂 body(避开编辑器 fixed 壳 / 中栏 zoom 缩放 / overflow 裁剪),
          屏幕上离屏隐藏但仍参与排版(才能算对分页);打印态由 resume-doc.css
          的 @media print 接管:隐藏整个 app,只显示这份。所见即所得。 */}
      {typeof document !== 'undefined' &&
        createPortal(
          <div className="hf rdoc-print-portal" data-theme="hub" aria-hidden>
            <ResumeDoc profile={profile} templateId={template} layout={layout} hidden={hidden} />
          </div>,
          document.body,
        )}
    </div>
  );
}
