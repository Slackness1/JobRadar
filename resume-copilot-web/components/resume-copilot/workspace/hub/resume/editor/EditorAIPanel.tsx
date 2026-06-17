'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { History, Plus, Sparkles } from 'lucide-react';
import { EditorScoreReportThick } from './EditorScoreReportThick';
import { ChatThread, type ChatMsg } from './ChatThread';
import { HubHistoryPanel, reportPotential, type HistoryConvoItem, type HistoryReportItem } from './HubHistoryPanel';
import { MAX_OPEN_EDITOR_TABS, type EditorTabsMeta, type ResumeVersion } from './versionTypes';
import {
  getEditorConversations,
  putEditorConversations,
  type DeepOptimizeStartIn,
  type PendingQuote,
  type ScoreReportData,
  type ScoreSectionGap,
} from '../../../../api';

const TABS: [string, string][] = [
  ['score', '简历打分'],
  ['deep', '深度优化'],
  // 自由问后端接好前先藏(占位回声让用户一头雾水);ChatThread mode='free' 已接
  // /chat,下版本恢复 ['free', '自由问'] 即可。
];

// 一个深度优化对话(独立会话)。全部留存(无上限);打开成 tab 的是其中 ≤3 个子集。
interface Convo {
  id: number;
  messages: ChatMsg[];
  updatedAt: string; // ISO;最近改动(历史按它倒序)
}

const DEBOUNCE_MS = 800;

// 从一段对话派生标题:首条用户文本消息(去 **加粗** 截断),没有就给序号占位。
function deriveTitle(messages: ChatMsg[], fallbackIdx: number): string {
  const firstMe = messages.find((m) => m.kind === 'text' && m.who === 'me');
  if (firstMe && firstMe.kind === 'text') {
    const t = firstMe.html.replace(/\*\*(.+?)\*\*/g, '$1').trim().slice(0, 28);
    if (t) return t;
  }
  return `深度优化对话 ${fallbackIdx}`;
}

// 落库友好相对时间(历史行用)。
function fmtRel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  const sameDay = new Date().toDateString() === d.toDateString();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  if (sameDay) return `今天 ${hh}:${mm}`;
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 ${hh}:${mm}`;
}

export interface EditorAIPanelProps {
  sessionId: number;
  /** 当前深度优化播种(从打分缺口 CTA 构造)。null = 还没选段。 */
  seed: DeepOptimizeStartIn | null;
  setSeed: (s: DeepOptimizeStartIn | null) => void;
  /** 「待引用」低调引子(引用此段 / 选行引用挂上;不自动发问)。 */
  pendingQuote: PendingQuote | null;
  setPendingQuote: (q: PendingQuote | null) => void;
  /** 受控 tab。 */
  tab: string;
  setTab: (t: string) => void;
  /** 写回成功 → 父组件把 section 映射成 A4 lit。 */
  onWriteBack: (section: string) => void;
  /** 无真实 session 时走样例。 */
  mock?: boolean;
  // ── 版本对应 + 重新打分(从 overlay 上提)──────────────────────────────────
  versionsReady?: boolean;
  versions?: ResumeVersion[];
  shownReport?: ScoreReportData | null;
  shownVName?: string;
  currentVName?: string;
  reportStale?: boolean;
  currentProfile?: import('./resumeSample').ResumeProfile;
  targetTrack?: string;
  onRescored?: (report: ScoreReportData) => void;
  /** 历史浮层点报告项 → 切到那一版报告。 */
  onOpenReportVid?: (vid: string) => void;
}

/** 简历编辑器右栏「AI 简历助手 v2」三能力壳:简历打分 / 深度优化 / 自由问。 */
export function EditorAIPanel({
  sessionId,
  seed,
  setSeed,
  pendingQuote,
  setPendingQuote,
  tab,
  setTab,
  onWriteBack,
  mock = false,
  versionsReady = false,
  versions = [],
  shownReport,
  shownVName,
  currentVName,
  reportStale = false,
  currentProfile,
  targetTrack,
  onRescored,
  onOpenReportVid,
}: EditorAIPanelProps): JSX.Element {
  // 打分缺口「去深度优化这段」→ 构造 seed(带真实目标赛道)→ 切到深度优化 tab(gap→deep 串联)。
  function handleOptimize(gap: ScoreSectionGap, track: string): void {
    setSeed({
      section: gap.section,
      label: gap.label,
      gaps: gap.gaps,
      detail: gap.detail,
      target_track: track,
    });
    setTab('deep');
  }

  // ── 深度优化对话 ─────────────────────────────────────────────────────────────
  // 全部会话(无上限)存 convos;同时「打开」成 tab 的是其 ≤3 个子集 openTabIds;
  // activeTabId 是当前激活 tab。三者一起持久化,刷新恢复打开态。
  const [convos, setConvos] = useState<Convo[]>([{ id: 1, messages: [], updatedAt: new Date().toISOString() }]);
  const [openTabIds, setOpenTabIds] = useState<number[]>([1]);
  const [activeTabId, setActiveTabId] = useState<number>(1);
  const nextId = useRef(2);
  const hydratedConvos = useRef(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 持久化要取最新的 open 态,但 persistConvos 又不想随它们重建(避免循环依赖)。
  // 用 ref 镜像当前 open 态,落库时现读。各 setState 回调里也会同步刷新这个 ref;
  // 这个 effect 兜底保证它始终与 state 一致(不能在 render 中写 ref)。
  const openRef = useRef({ openTabIds: [1] as number[], activeTabId: 1 });
  useEffect(() => {
    openRef.current = { openTabIds, activeTabId };
  }, [openTabIds, activeTabId]);

  // 整组对话 + 打开态写库(debounce);demo / 只读 403 静默吞掉。
  // 数组里:每个会话一条 {id, messages, updatedAt, title};末尾追一条 __meta__ 记打开态。
  const persistConvos = useCallback(
    (list: Convo[], immediate = false) => {
      if (mock || !sessionId) return;
      // 水合完成前不落库,避免初始空 tab 的 onMsgsChange 把后端真实对话覆盖成空。
      if (!hydratedConvos.current) return;
      if (flushTimer.current) clearTimeout(flushTimer.current);
      const doPut = () => {
        const { openTabIds: ot, activeTabId: at } = openRef.current;
        const body: unknown[] = list.map((c, i) => ({
          id: c.id,
          messages: c.messages,
          updatedAt: c.updatedAt,
          title: deriveTitle(c.messages, i + 1),
        }));
        const meta: EditorTabsMeta = { __meta__: true, openTabIds: ot, activeTabId: at };
        body.push(meta);
        putEditorConversations(sessionId, body).catch(() => {
          /* demo / 只读 403 → 内存态继续 */
        });
      };
      if (immediate) doPut();
      else flushTimer.current = setTimeout(doPut, DEBOUNCE_MS);
    },
    [mock, sessionId],
  );

  // 挂载:从后端水合会话组 + 打开态(空则保留默认 1 tab)。
  useEffect(() => {
    let alive = true;
    if (mock || !sessionId) {
      hydratedConvos.current = true;
      return;
    }
    getEditorConversations(sessionId)
      .then(({ conversations }) => {
        if (!alive) return;
        const raw = (conversations as Array<Record<string, unknown>>) ?? [];
        // 会话本体:数字 id 的条目(无上限留存)。
        const list: Convo[] = raw
          .filter((c) => c && typeof c.id === 'number')
          .map((c) => ({
            id: c.id as number,
            messages: Array.isArray(c.messages) ? (c.messages as ChatMsg[]) : [],
            updatedAt: typeof c.updatedAt === 'string' ? c.updatedAt : new Date().toISOString(),
          }));
        if (!list.length) return; // 没有真实会话 → 沿用默认 1 tab
        // 打开态元记录(新格式);取不到就回退「前 3 个会话作为打开 tab」(兼容旧格式)。
        const meta = raw.find((c) => c && (c as { __meta__?: boolean }).__meta__ === true) as
          | EditorTabsMeta
          | undefined;
        const ids = new Set(list.map((c) => c.id));
        let open = (meta?.openTabIds ?? []).filter((id) => ids.has(id)).slice(0, MAX_OPEN_EDITOR_TABS);
        if (!open.length) open = list.slice(0, MAX_OPEN_EDITOR_TABS).map((c) => c.id);
        let active = meta?.activeTabId;
        if (active === undefined || !open.includes(active)) active = open[0];
        setConvos(list);
        setOpenTabIds(open);
        setActiveTabId(active);
        nextId.current = Math.max(...list.map((c) => c.id)) + 1;
      })
      .catch(() => {
        /* 取对话失败 → 默认 1 tab */
      })
      .finally(() => {
        if (alive) hydratedConvos.current = true;
      });
    return () => {
      alive = false;
    };
  }, [mock, sessionId]);

  // 卸载:清 timer,别丢最后一段未落库的对话。
  useEffect(() => {
    return () => {
      if (flushTimer.current) clearTimeout(flushTimer.current);
    };
  }, []);

  // 新建会话:总是新开一段对话;打开 tab 不足 3 → 作为新 tab;已 3 → 顶掉当前激活 tab 的槽位
  //(被顶掉的会话不删,留在历史)。新会话恒为激活。
  const addTab = useCallback(() => {
    const id = nextId.current++;
    const fresh: Convo = { id, messages: [], updatedAt: new Date().toISOString() };
    setConvos((cs) => {
      const next = [...cs, fresh];
      setOpenTabIds((ot) => {
        const nextOpen =
          ot.length < MAX_OPEN_EDITOR_TABS
            ? [...ot, id]
            : ot.map((x) => (x === openRef.current.activeTabId ? id : x));
        openRef.current = { openTabIds: nextOpen, activeTabId: id };
        return nextOpen;
      });
      setActiveTabId(id);
      persistConvos(next, true);
      return next;
    });
  }, [persistConvos]);

  // 打开一段已有会话(从历史点入):已打开 → 切到它;不足 3 → 新增 tab;已 3 → 顶掉激活槽位。
  const openConvo = useCallback((id: number) => {
    setOpenTabIds((ot) => {
      let nextOpen: number[];
      if (ot.includes(id)) nextOpen = ot;
      else if (ot.length < MAX_OPEN_EDITOR_TABS) nextOpen = [...ot, id];
      else nextOpen = ot.map((x) => (x === openRef.current.activeTabId ? id : x));
      openRef.current = { openTabIds: nextOpen, activeTabId: id };
      return nextOpen;
    });
    setActiveTabId(id);
    // 打开态变了 → 落库(用当前 convos 快照)。
    setConvos((cs) => {
      persistConvos(cs, true);
      return cs;
    });
  }, [persistConvos]);

  // 关闭一个 tab(右键):移出打开集合,但会话留在历史(不删消息)。永不关到 0。
  const closeTab = useCallback((id: number) => {
    setOpenTabIds((ot) => {
      if (ot.length <= 1) return ot;
      const nextOpen = ot.filter((x) => x !== id);
      setActiveTabId((cur) => (cur === id ? nextOpen[nextOpen.length - 1] : cur));
      const nextActive = openRef.current.activeTabId === id ? nextOpen[nextOpen.length - 1] : openRef.current.activeTabId;
      openRef.current = { openTabIds: nextOpen, activeTabId: nextActive };
      return nextOpen;
    });
    setConvos((cs) => {
      persistConvos(cs, true);
      return cs;
    });
  }, [persistConvos]);

  // 某段会话的消息变动 → 更新内存(刷新 updatedAt)+ debounce 落库。
  const handleTabMsgs = useCallback(
    (id: number, msgs: ChatMsg[]) => {
      setConvos((cs) => {
        const next = cs.map((c) => (c.id === id ? { ...c, messages: msgs, updatedAt: new Date().toISOString() } : c));
        persistConvos(next);
        return next;
      });
    },
    [persistConvos],
  );

  // 当前打开成 tab 的会话(按 openTabIds 顺序)。
  const openConvos = openTabIds
    .map((id) => convos.find((c) => c.id === id))
    .filter((c): c is Convo => Boolean(c));

  // ── 历史浮层数据(从「全部会话」+ 版本报告派生)──────────────────────────────
  // 会话历史无上限,按 updatedAt 倒序(最新在前);标注已打开 / 当前激活。
  const convoItems: HistoryConvoItem[] = convos
    .slice()
    .sort((a, b) => (b.updatedAt > a.updatedAt ? 1 : b.updatedAt < a.updatedAt ? -1 : b.id - a.id))
    .map((c, i) => ({
      id: c.id,
      title: deriveTitle(c.messages, i + 1),
      date: fmtRel(c.updatedAt) || `对话 ${i + 1}`,
      active: c.id === activeTabId && openTabIds.includes(c.id),
      open: openTabIds.includes(c.id),
    }));

  const reportItems: HistoryReportItem[] = versions
    .filter((v) => v.report)
    .slice()
    .reverse()
    .map((v) => {
      const r = v.report as ScoreReportData;
      return {
        vid: v.id,
        track: r.target_track || '目标赛道',
        score: r.overall_current,
        potential: reportPotential(r),
        date: v.label,
        // 「当前」= 这一版正是打分面板此刻展示的报告版本。
        current: v.label === shownVName,
      };
    });

  return (
    <div
      style={{
        position: 'relative',
        borderLeft: '1px solid var(--border-warm)',
        background: 'var(--ivory)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '13px 16px',
          borderBottom: '1px solid var(--border-warm)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flex: 'none',
        }}
      >
        <span
          style={{
            width: 28,
            height: 28,
            flex: 'none',
            borderRadius: 999,
            display: 'grid',
            placeItems: 'center',
            color: '#faf9f5',
            background:
              'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)',
            boxShadow: '0 4px 12px rgba(201,100,66,0.26)',
          }}
        >
          <Sparkles size={15} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>AI 简历助手 v2</div>
          <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)' }}>
            诚实打分 · 反问取证 · 写回即刷新
          </div>
        </div>
        {/* 历史记录入口(右侧)*/}
        <button
          onClick={() => setHistoryOpen((v) => !v)}
          title="历史记录 · 会话与简历打分报告"
          aria-label="历史记录"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            height: 34,
            padding: '0 13px 0 11px',
            borderRadius: 999,
            cursor: 'pointer',
            border: 'none',
            background: historyOpen ? 'var(--terracotta-wash)' : 'var(--ivory)',
            boxShadow: historyOpen
              ? '0 0 0 1px #eccfb6'
              : '0 0 0 1px var(--border-warm), 0 2px 8px rgba(15,23,42,0.04)',
            color: historyOpen ? 'var(--terracotta-strong)' : 'var(--ink-soft)',
            transition: 'background .14s, box-shadow .14s, color .14s',
          }}
        >
          <History size={16} />
          <span style={{ font: '600 12.5px var(--font-sans)' }}>历史记录</span>
        </button>
      </div>

      {historyOpen && (
        <HubHistoryPanel
          top={108}
          right={16}
          convos={convoItems}
          reports={reportItems}
          // 初始分段跟随当前 AI 面板 tab:报告 tab→打分报告;其余(深度对话)→会话历史。
          initialSegment={tab === 'score' ? 'report' : 'convo'}
          onClose={() => setHistoryOpen(false)}
          onOpenConvo={(id) => {
            // 已打开→切到它;不足 3→新开 tab;已 3→顶掉激活槽位(被顶的留在历史)。
            openConvo(id);
            setTab('deep');
            setHistoryOpen(false);
          }}
          onNew={() => {
            addTab();
            setTab('deep');
          }}
          onOpenReport={(vid) => {
            onOpenReportVid?.(vid);
            setHistoryOpen(false);
          }}
        />
      )}

      {/* 三能力切换 */}
      <div
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid var(--border-warm)',
          display: 'flex',
          gap: 6,
          flex: 'none',
        }}
      >
        {TABS.map(([k, t]) => {
          const on = tab === k;
          return (
            <button
              key={k}
              onClick={() => setTab(k)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                height: 30,
                padding: '0 12px',
                borderRadius: 999,
                cursor: 'pointer',
                font: `${on ? 600 : 500} 12px var(--font-sans)`,
                background: on ? 'var(--terracotta)' : 'var(--ivory)',
                color: on ? 'var(--ivory)' : 'var(--ink-soft)',
                boxShadow: on ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
              }}
            >
              {t}
              {k === 'deep' && (seed || pendingQuote) && !on && (
                <span style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--terracotta)' }} />
              )}
            </button>
          );
        })}
      </div>

      {/* 三能力内容(用 display 切换以保留各自状态)。
          minWidth:0 + overflowX:hidden:打分报告内部 maxWidth 720 > 右栏 396,
          不加 minWidth:0 时 flex 子项 min-width:auto 会被撑到 720、向左溢出串进中栏
          (推荐线 handoff BUG-1)。 */}
      <div style={{ flex: 1, minHeight: 0, minWidth: 0, overflowX: 'hidden', display: tab === 'score' ? 'flex' : 'none', flexDirection: 'column' }}>
        <EditorScoreReportThick
          sessionId={sessionId}
          onOptimize={handleOptimize}
          mock={mock}
          // 版本就绪后才受控(传 reportOverride);未就绪退回自动轮询保留原行为。
          reportOverride={versionsReady ? (shownReport ?? null) : undefined}
          shownVName={shownVName}
          currentVName={currentVName}
          stale={reportStale}
          currentProfile={currentProfile}
          targetTrack={targetTrack}
          onRescored={onRescored}
        />
      </div>
      {/* 深度优化:每个对话 tab 一个 ChatThread,display 切换以保留各自滚动/输入态。 */}
      <div style={{ flex: 1, minHeight: 0, display: tab === 'deep' ? 'flex' : 'none', flexDirection: 'column' }}>
        {/* 对话 tab 条 */}
        <div
          style={{
            flex: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 14px',
            borderBottom: '1px solid var(--border-warm)',
            background: 'var(--ivory)',
          }}
        >
          <span className="hf-overline" style={{ fontSize: 9.5, flex: 'none' }}>
            对话
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            {openConvos.map((t, i) => {
              const on = activeTabId === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTabId(t.id)}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    if (openTabIds.length > 1) closeTab(t.id);
                  }}
                  title={openTabIds.length > 1 ? '点击切换 · 右键关闭(会话留在历史)' : '点击切换'}
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 8,
                    cursor: 'pointer',
                    border: 'none',
                    font: '600 12.5px var(--font-mono)',
                    display: 'grid',
                    placeItems: 'center',
                    transition: 'background .14s, box-shadow .14s, color .14s',
                    background: on ? 'var(--terracotta)' : 'var(--ivory)',
                    color: on ? '#fff' : 'var(--ink-soft)',
                    boxShadow: on ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
                  }}
                >
                  {i + 1}
                </button>
              );
            })}
            {/* 「+」始终可用:满 3 时顶掉当前激活 tab 槽位(被顶会话不删,留在历史)。 */}
            <button
              onClick={addTab}
              title={openTabIds.length < MAX_OPEN_EDITOR_TABS ? '新建对话' : '新建对话(替换当前标签 · 旧对话留在历史)'}
              aria-label="新建对话"
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                cursor: 'pointer',
                display: 'grid',
                placeItems: 'center',
                border: 'none',
                color: 'var(--stone)',
                background: 'transparent',
                boxShadow: 'inset 0 0 0 1px var(--border-strong)',
              }}
            >
              <Plus size={14} />
            </button>
          </div>
          {openTabIds.length > 1 && (
            <span style={{ marginLeft: 'auto', font: '400 10.5px var(--font-sans)', color: 'var(--stone)' }}>
              右键关闭
            </span>
          )}
        </div>
        {/* 每个打开的 tab 一个独立 ChatThread(各自水合 + 落库;关闭后会话仍留在历史) */}
        {openConvos.map((t) => (
            <div
              key={t.id}
              style={{
                flex: 1,
                minHeight: 0,
                display: t.id === activeTabId ? 'flex' : 'none',
                flexDirection: 'column',
              }}
            >
              <ChatThread
                sessionId={sessionId}
                mode="deep"
                // seed 只喂当前激活 tab,别让后台 tab 也被同一缺口起头。
                seed={t.id === activeTabId ? seed : null}
                pendingQuote={t.id === activeTabId ? pendingQuote : null}
                setPendingQuote={setPendingQuote}
                onWriteBack={onWriteBack}
                mock={mock}
                initialMsgs={t.messages}
                onMsgsChange={(msgs) => handleTabMsgs(t.id, msgs)}
              />
            </div>
          ))}
      </div>
      {/* 自由问内容随 tab 一起藏(TABS 注释见上)。 */}
    </div>
  );
}
