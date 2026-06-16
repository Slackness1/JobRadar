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
  section?: string;  // 绑定的简历段路径,如 'internships.0' / 'education';undefined = 自由对话
  label?: string;    // 段落显示名(tab 标题 / 历史标题 / 锁定段横幅)
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
  /** 「待引用」低调引子(引用此段 / 选行引用挂上;不自动发问)。 */
  pendingQuote: PendingQuote | null;
  setPendingQuote: (q: PendingQuote | null) => void;
  /** 受控 tab。 */
  tab: string;
  setTab: (t: string) => void;
  /** 写回成功 → 父组件把 section 映射成 A4 lit + 合并写回后的最新 profile 到工作态。 */
  onWriteBack: (section: string, profile?: Record<string, unknown>) => void;
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

  // ── 深度优化对话 ─────────────────────────────────────────────────────────────
  // 全部会话(无上限)存 convos;同时「打开」成 tab 的是其 ≤3 个子集 openTabIds;
  // activeTabId 是当前激活 tab。三者一起持久化,刷新恢复打开态。
  const [convos, setConvos] = useState<Convo[]>([{ id: 1, messages: [], updatedAt: new Date().toISOString() }]);
  const [openTabIds, setOpenTabIds] = useState<number[]>([1]);
  const [activeTabId, setActiveTabId] = useState<number>(1);
  const nextId = useRef(2);
  const hydratedConvos = useRef(false);
  // seed/quote 按对话 id 投递(替代全局「谁激活谁抢」)。ChatThread 消费后回调删除该条,
  // 保证 seed 永不泄漏到下一个新建/切换的 tab —— 根治「新对话沿用旧内容 / 重复增生」。
  const [pendingSeedByConv, setPendingSeedByConv] = useState<Record<number, DeepOptimizeStartIn>>({});
  const [pendingQuoteByConv, setPendingQuoteByConv] = useState<Record<number, PendingQuote>>({});
  const [historyOpen, setHistoryOpen] = useState(false);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 持久化要取最新的 open 态,但 persistConvos 又不想随它们重建(避免循环依赖)。
  // 用 ref 镜像当前 open 态,落库时现读。各 setState 回调里也会同步刷新这个 ref;
  // 这个 effect 兜底保证它始终与 state 一致(不能在 render 中写 ref)。
  const openRef = useRef({ openTabIds: [1] as number[], activeTabId: 1 });
  useEffect(() => {
    openRef.current = { openTabIds, activeTabId };
  }, [openTabIds, activeTabId]);
  // 后端只有一份 plan_json;记当前占用它的 section。用 state 而非 ref,
  // 让 isPlanOwner 在 claim 后立刻经 rerender 反映,避免重启 effect ping-pong。
  const [backendPlanSection, setBackendPlanSection] = useState<string | null>(null);

  // overlay 传进来的「引用某段」一次性请求 → 路由到该段对话(复用/新建)→ 清空 overlay 全局。
  useEffect(() => {
    if (!pendingQuote) return;
    routeToSection(pendingQuote.section, pendingQuote.label || pendingQuote.section, { quote: pendingQuote });
    setPendingQuote(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuote]);

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
          section: c.section,
          label: c.label,
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
            section: typeof c.section === 'string' ? (c.section as string) : undefined,
            label: typeof c.label === 'string' ? (c.label as string) : undefined,
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

  // 新建一个绑定指定 section 的对话(addTab 变体)。返回新对话 id。
  // 满 3 个打开 tab 时顶掉当前激活槽位(被顶会话留在历史)。
  const createSectionConvo = useCallback((section: string, label: string): number => {
    const id = nextId.current++;
    const fresh: Convo = { id, messages: [], updatedAt: new Date().toISOString(), section, label };
    setConvos((cs) => {
      const next = [...cs, fresh];
      setOpenTabIds((ot) => {
        const nextOpen =
          ot.length < MAX_OPEN_EDITOR_TABS ? [...ot, id] : ot.map((x) => (x === openRef.current.activeTabId ? id : x));
        openRef.current = { openTabIds: nextOpen, activeTabId: id };
        return nextOpen;
      });
      setActiveTabId(id);
      persistConvos(next, true);
      return next;
    });
    return id;
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

  // 「优化某段 / 引用某段」统一入口:该段已有对话→切回(空才补 seed/quote);没有→新建。
  // 例外:当前激活对话恰是「空白无 section」→ 复用它认领该段(避免空白 orphan)。
  const routeToSection = useCallback(
    (section: string, label: string, payload: { seed?: DeepOptimizeStartIn; quote?: PendingQuote }): void => {
      setTab('deep');
      const existing = convos.find((c) => c.section === section);
      if (existing) {
        openConvo(existing.id);
        if (existing.messages.length === 0) {
          if (payload.seed) setPendingSeedByConv((m) => ({ ...m, [existing.id]: payload.seed! }));
          if (payload.quote) setPendingQuoteByConv((m) => ({ ...m, [existing.id]: payload.quote! }));
        }
        return;
      }
      // 空白激活对话(无 section、无消息)→ 认领该段,而不是再叠一个空白。
      const activeBlank = convos.find(
        (c) => c.id === openRef.current.activeTabId && !c.section && c.messages.length === 0,
      );
      let targetId: number;
      if (activeBlank) {
        targetId = activeBlank.id;
        setConvos((cs) => {
          const next = cs.map((c) => (c.id === activeBlank.id ? { ...c, section, label } : c));
          persistConvos(next, true);
          return next;
        });
      } else {
        targetId = createSectionConvo(section, label);
      }
      if (payload.seed) setPendingSeedByConv((m) => ({ ...m, [targetId]: payload.seed! }));
      if (payload.quote) setPendingQuoteByConv((m) => ({ ...m, [targetId]: payload.quote! }));
    },
    [convos, openConvo, createSectionConvo, persistConvos, setTab],
  );

  // 打分缺口「去深度优化这段」→ 路由到对应段对话(已有则复用,无则新建)→ 切到深度优化 tab。
  function handleOptimize(gap: ScoreSectionGap, track: string): void {
    routeToSection(gap.section, gap.label, {
      seed: { section: gap.section, label: gap.label, gaps: gap.gaps, detail: gap.detail, target_track: track },
    });
  }

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

  // ChatThread 消费完它那份 seed → 删除,避免重复 start / 泄漏到其它 tab。
  const consumeSeed = useCallback((convId: number) => {
    setPendingSeedByConv((m) => {
      if (!(convId in m)) return m;
      const next = { ...m };
      delete next[convId];
      return next;
    });
  }, []);
  const consumeQuote = useCallback((convId: number) => {
    setPendingQuoteByConv((m) => {
      if (!(convId in m)) return m;
      const next = { ...m };
      delete next[convId];
      return next;
    });
  }, []);

  // 从历史彻底删除一段会话:移出 convos + 打开集合;激活则切到其它打开 tab;永不删到 0。
  const deleteConvo = useCallback((id: number) => {
    setConvos((cs) => {
      let result = cs.filter((c) => c.id !== id);
      let nextOpen = openRef.current.openTabIds.filter((x) => x !== id);
      let nextActive =
        openRef.current.activeTabId === id ? nextOpen[nextOpen.length - 1] : openRef.current.activeTabId;
      if (result.length === 0) {
        // 删光了 → 立刻补一个空白对话(永不 0)。
        const fresh: Convo = { id: nextId.current++, messages: [], updatedAt: new Date().toISOString() };
        result = [...result, fresh];
        nextOpen = [fresh.id];
        nextActive = fresh.id;
      } else if (nextOpen.length === 0) {
        nextOpen = [result[result.length - 1].id];
        nextActive = nextOpen[0];
      }
      openRef.current = { openTabIds: nextOpen, activeTabId: nextActive };
      setOpenTabIds(nextOpen);
      setActiveTabId(nextActive);
      // 删的若是当前持有后端 plan 的那段 → 清归属,避免新建同段对话被误判已认领。
      const deletedSection = cs.find((c) => c.id === id)?.section;
      if (deletedSection) setBackendPlanSection((cur) => (cur === deletedSection ? null : cur));
      persistConvos(result, true);
      return result;
    });
    consumeSeed(id);
    consumeQuote(id);
  }, [persistConvos, consumeSeed, consumeQuote]);

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
          onDeleteConvo={deleteConvo}
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
              {k === 'deep' && (Object.keys(pendingSeedByConv).length > 0 || Object.keys(pendingQuoteByConv).length > 0) && !on && (
                <span style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--terracotta)' }} />
              )}
            </button>
          );
        })}
      </div>

      {/* 三能力内容(用 display 切换以保留各自状态)。 */}
      <div style={{ flex: 1, minHeight: 0, display: tab === 'score' ? 'flex' : 'none', flexDirection: 'column' }}>
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
                seed={pendingSeedByConv[t.id] ?? null}
                pendingQuote={pendingQuoteByConv[t.id] ?? null}
                onSeedConsumed={() => consumeSeed(t.id)}
                onQuoteConsumed={() => consumeQuote(t.id)}
                onWriteBack={onWriteBack}
                mock={mock}
                initialMsgs={t.messages}
                onMsgsChange={(msgs) => handleTabMsgs(t.id, msgs)}
                section={t.section}
                active={t.id === activeTabId}
                isPlanOwner={!!t.section && t.section === backendPlanSection}
                onClaimPlan={(s) => setBackendPlanSection(s)}
              />
            </div>
          ))}
      </div>
      {/* 自由问内容随 tab 一起藏(TABS 注释见上)。 */}
    </div>
  );
}
