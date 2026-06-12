'use client';

/**
 * HubShell — 统一对话 Hub 外壳: 三栏(侧边栏 + 对话主轴 + 画布槽)+ arm/fire 状态机.
 *
 * 铁律(来自用户明确、反复强调的要求): **两步交互**.
 *   1. 点模块 chip / 侧边栏 / 落地卡 = 只「激活」(armed) —— 高亮 + 露「说一句就开始」
 *      引导, **什么都不跑**, 右栏不变.
 *   2. 说一句话 = 才「激发交付物」(fire) —— 落学生发言 + 跑该模块技能.
 *   绝不把它退化成「点一下就跑」.
 *
 * 例外: 个人档案(profile)不是「跑技能」, 是你自己的档案 —— 点开直接看,
 *   没有思考卡, 没有结果卡(spec exception).
 *
 * 真实接缝(本任务只留口):
 *   - NL 路由 / postRecommendChat → Task 6(当前用最小关键词兜底, 非破坏).
 *   - 右栏真实 CanvasSlot → Task 7(当前占位 div 预留宽度).
 *   - 模拟面试全屏间 router.push → Task 10.
 *
 * Token: 全部取自 `.hf`(外层 className="hf").对话主轴复用推荐工作台的
 *   Turn / TraceCard / MemoryToast / Composer —— 这些类 scope 在 `[data-theme="recommend"]`,
 *   故中栏额外挂一层 data-theme="recommend" 让其 CSS 命中.
 */

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import './hub-theme.css';
import '../recommend-agent/recommend-agent.css';

import HubSidebar from './HubSidebar';
import DeepThinkCard from './DeepThinkCard';
import SkillBar from './SkillBar';
import HubLanding from './HubLanding';
import CanvasSlot from './CanvasSlot';
import { Composer, type ComposerChip } from '../recommend-agent/chat/Composer';
import { Turn } from '../recommend-agent/chat/Turn';
import { TraceCard } from '../recommend-agent/chat/TraceCard';
import { MemoryToast } from '../recommend-agent/chat/MemoryToast';
import {
  createHubConversation,
  getHubConversationDetail,
  getPlatformsByTier,
  getResumeCopilotConfirmedProfile,
  getResumeCopilotParsedProfile,
  getStudentKbIndex,
  getWorkingQuery,
  listHubConversations,
  listResumeCopilotSessions,
  postRecommendChat,
  putHubConversationDetail,
  scoreResume,
  updateWorkingQuery,
} from '../../api';
import { cacheScoreReport } from './scoreCache';
import type { RecommendFeedItem, RecommendTurnResponse, WorkingQuery } from '../../types';
import type { HubModule, HubSlot, HubMessage, ResultCardData } from './hub-types';
import type { HubConvRow, HubSessionRow } from './HubSidebar';

// 相对时间(刚刚 / N 分钟前 / N 小时前 / 昨天 / N 天前 / 日期)
// 后端存 naive UTC, 序列化出来不带时区标记(`2026-06-12T08:17:48.271168`)——
// 不补 Z 浏览器会按本地时区(CST)解析, 每条凭空老 8 小时(修「都是七八小时前」)。
function relTime(iso: string | null): string {
  if (!iso) return '';
  let s = iso.includes('T') ? iso : iso.replace(' ', 'T');
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s += 'Z';
  const t = new Date(s).getTime();
  if (Number.isNaN(t)) return '';
  const m = Math.floor((Date.now() - t) / 60000);
  if (m < 1) return '刚刚';
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const d = Math.floor(h / 24);
  if (d === 1) return '昨天';
  if (d < 30) return `${d} 天前`;
  return new Date(t).toLocaleDateString('zh-CN');
}

// ── 技能文案 — AI 的「开始跑」一声(每模块一句)──────────────────────────────────
const SAY: Record<HubModule, string> = {
  feed: '好，我按你确认的赛道把<b>职位推荐</b>跑一遍。',
  skeleton: '好，我把<b>梯队骨架</b>拉出来分一下档。',
  resume: '好，我给你的<b>简历</b>做一次诚实打分 + 缺口定位。',
  interview: '好，我按你的目标赛道备一场<b>模拟面试</b>。',
  // profile 不跑技能, 走 PROFILE_SAY
  profile: '',
};

// 个人档案不是「跑技能」—— 点开直接看(确认/纠正闭环)
const PROFILE_SAY =
  '帮你打开<b>个人档案</b> —— 确认信息在上，AI 推断待确认在下，确认/否掉一眼可点。';

// 结果卡文案的真实上下文 —— 每个模块技能跑完后用真实后端数据填,不再写死。
interface ResultCtx {
  // feed: working_query.seed_sub_cats + 真实召回 / 匹配条数
  tracks?: string[];
  feedLen?: number;
  // skeleton: 真实赛道名 + GT 公司总数 + 分档标签
  subCat?: string;
  skeletonCount?: number;
  skeletonBands?: string[];
  // resume: 真实现状分 + 潜力区间 + 有缺口的经历段数
  resumeCurrent?: number;
  resumePotLow?: number;
  resumePotHigh?: number;
  resumeGaps?: number;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// 技能跑完落在对话里的「产出」卡文案(每模块一张)
function RESULT_FOR(key: HubModule, ctx?: ResultCtx): ResultCardData {
  switch (key) {
    case 'feed': {
      const tracks = (ctx?.tracks ?? []).filter(Boolean);
      const n = ctx?.feedLen ?? 0;
      const trackText = tracks.length > 0 ? escapeHtml(tracks.join(' · ')) : '你确认的赛道';
      return {
        title: '岗位匹配已就绪',
        body:
          n > 0
            ? `按 <b>${trackText}</b> 评估 ${n} 个在招、匹配 ${n} 个，已排出第一版列表。`
            : `按 <b>${trackText}</b> 跑了一遍，这一版暂时没匹配到合适的在招岗位，换个说法或调整赛道再试试。`,
        cta: '查看岗位',
      };
    }
    case 'skeleton': {
      const cnt = ctx?.skeletonCount ?? 0;
      const scText = ctx?.subCat ? escapeHtml(ctx.subCat) : '你确认的赛道';
      const bands = (ctx?.skeletonBands ?? []).filter(Boolean);
      const bandText = bands.length > 0 ? escapeHtml(bands.join(' / ')) : '头部 / 主力 / 腰部';
      return {
        title: '梯队全景已铺好',
        body:
          cnt > 0
            ? `<b>${scText}</b> 共 <b>${cnt}</b> 家公司，按 ${bandText} 分了档，匹配档已高亮。`
            : `<b>${scText}</b> 这一版暂时没铺出梯队公司，确认赛道后再看。`,
        cta: '查看全景',
      };
    }
    case 'resume': {
      const cur = ctx?.resumeCurrent;
      if (cur == null) {
        return {
          title: '简历打分完成',
          body: '已生成诚实打分与逐段缺口定位，点开看现状分、潜力区间和可补缺口。',
          cta: '查看打分报告',
        };
      }
      const lo = ctx?.resumePotLow;
      const hi = ctx?.resumePotHigh;
      const gaps = ctx?.resumeGaps ?? 0;
      const potText = lo != null && hi != null ? ` · 潜力 ${lo}–${hi}` : '';
      const gapText =
        gaps > 0 ? `${gaps} 段经历有可补的缺口，已定位到逐段入口。` : '逐段缺口已定位到入口。';
      return {
        title: '简历打分完成',
        body: `现状 <b>${cur}</b>${potText}，${gapText}`,
        cta: '查看打分报告',
      };
    }
    case 'interview':
      return {
        title: '面试间准备好了',
        body: '按 <b>投研 · 券商资管</b> 配了考官与题库，记忆延续同一会话；进入后全屏，结束自动回 Hub。',
        cta: '进入面试',
      };
    default:
      return { title: '', body: '', cta: '' };
  }
}

// 激活某模块后 composer 上方的引导文案
const ARM_HINT: Record<HubModule, { label: string; tip: string }> = {
  feed: { label: '职位推荐', tip: '说一句就开始 —— 例如「给我推荐一下岗位」' },
  skeleton: { label: '梯队骨架', tip: '说一句就开始 —— 例如「看看券商资管的梯队」' },
  resume: { label: '简历优化', tip: '说一句就开始 —— 例如「帮我的简历打个分」' },
  interview: { label: '模拟面试', tip: '说一句就开始 —— 例如「按券商资管面我一场」' },
  profile: { label: '个人档案', tip: '' },
};

// 对话主轴下方的快捷 chip
const QUICK_CHIPS: ComposerChip[] = [
  { key: 'q-feed', label: '给我推荐一下岗位' },
  { key: 'q-skeleton', label: '看看券商资管的梯队' },
  { key: 'q-resume', label: '帮我的简历打个分' },
];

// 对话标题 = 第一条学生发言(去标签截 24 字); 没有学生发言退首条 turn。
// 修「历史对话以赛道命名分不清谁是谁」—— 标题长在对话自己身上, 不再借简历的赛道名。
function stripHtml(html: string): string {
  return String(html || '').replace(/<[^>]+>/g, '').trim();
}
function deriveConvTitle(messages: HubMessage[]): string {
  for (const m of messages) {
    if (m.kind === 'turn' && m.who === 'me') {
      const t = stripHtml(m.html);
      if (t) return t.slice(0, 24);
    }
  }
  for (const m of messages) {
    if (m.kind === 'turn') {
      const t = stripHtml(m.html);
      if (t) return t.slice(0, 24);
    }
  }
  return '对话';
}

let msgSeq = 0;
const nextId = () => `hub-${++msgSeq}`;
// 水合历史对话后, 把全局序号推过已有 id, 防止新消息 id 与水合 id 撞(同一份简历重放时
// 旧 id 形如 hub-7, 新消息得从 8 起)。
function bumpSeqFromIds(ids: string[]) {
  for (const id of ids) {
    const n = Number(String(id).replace(/^hub-/, ''));
    if (Number.isFinite(n) && n > msgSeq) msgSeq = n;
  }
}

// ── 结果卡 — 技能跑完落在对话里的「产出」. 点 CTA 才进入那个模块的视图(永不瞬移). ──
function ResultCard({
  data,
  opened,
  onOpen,
}: {
  data: ResultCardData;
  opened: boolean;
  onOpen: () => void;
}) {
  return (
    <div
      className="hf-slide"
      style={{
        marginLeft: 37,
        marginTop: 2,
        background: 'var(--ivory)',
        borderRadius: 16,
        padding: '14px 16px',
        boxShadow: 'var(--sh-ring)',
        maxWidth: 462,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
        <span style={{ color: 'var(--emerald)', display: 'inline-flex' }}>
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </span>
        <span style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>{data.title}</span>
      </div>
      <div
        style={{
          font: '400 12.5px/1.6 var(--font-sans)',
          color: 'var(--ink-soft)',
          marginBottom: 12,
        }}
        dangerouslySetInnerHTML={{ __html: data.body }}
      />
      <button
        type="button"
        className={opened ? 'hf-btn sand sm' : 'hf-btn primary sm'}
        onClick={onOpen}
        style={{ width: '100%', gap: 6 }}
      >
        {opened ? '已打开 · 再看一次' : data.cta}
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </button>
    </div>
  );
}

// ── HubShell ─────────────────────────────────────────────────────────────────
export default function HubShell({ sessionId }: { sessionId: number }) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [sessions, setSessions] = useState<HubSessionRow[]>([]); // 侧栏真实历史会话
  const [userName, setUserName] = useState(''); // 真实候选人姓名(profile.basic_info.name)
  const [active, setActive] = useState<HubSlot>('none'); // 当前打开的画布槽
  const [armed, setArmed] = useState<HubModule | null>(null); // 被「激活」但还没说话触发的模块
  const [started, setStarted] = useState(false); // 离开落地态?
  const [msgs, setMsgs] = useState<HubMessage[]>([]);
  const [thinking, setThinking] = useState(false);

  // ── 真实数据态(Task 6) ──────────────────────────────────────────────────
  const [workingQuery, setWorkingQuery] = useState<WorkingQuery | null>(null);
  const [feed, setFeed] = useState<RecommendFeedItem[]>([]);
  const [memoryPills, setMemoryPills] = useState<string[]>([]);
  // deepening 预留给 Task 7 画布的深挖态(本任务只持有, 不渲染)
  const [, setDeepening] = useState<string | null>(null);
  // feed 卡点选公司 → 梯队骨架卡高亮 + 滚动定位(Task 8 透传给 CanvasSlot 的骨架 Pane)
  const [highlightCompany, setHighlightCompany] = useState<string | null>(null);

  const busy = useRef(false); // 防双触发
  const completed = useRef<Set<string>>(new Set()); // skillrun id → 已落结果卡(防重)
  // skillrun id → 真实 recommend-chat 结果(动画跑完时据此落结果卡, 防 race)
  const respById = useRef<Map<string, RecommendTurnResponse>>(new Map());
  // skillrun id → skeleton / resume 技能的真实结果卡上下文(同 race-safe 落卡)
  const ctxById = useRef<Map<string, ResultCtx>>(new Map());
  // skillrun id → 请求未回时挂起的 onComplete(动画先跑完就等请求)
  const pendingComplete = useRef<Map<string, () => void>>(new Map());
  // 学生最近一句话(armed fire 时拿来当 recommend-chat 的 message)
  const lastUserText = useRef<string>('');
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // ── 多对话持久化(简历是 base, 一份简历下多个对话)─────────────────────────
  // convs = 当前简历名下的对话列表(侧栏历史); activeConvId = 正在聊的对话行。
  // 「新对话」= activeConvId 置空, 下一句话 create 插新行 —— 旧对话原样保留,
  // 不再像单槽时代被覆盖毁掉。
  const [convs, setConvs] = useState<HubConvRow[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  // convLoaded = 进场水合完成(之前不落库, 防空数组覆盖真源);
  // lastSavedConv = 最近一次落库的 JSON(防水合回声 + 防重复落同样内容);
  // pending* + saveBusy = 待落库快照: 短防抖合并同轮连续消息, 卸载时同步 flush ——
  // 修「聊完马上跳页, 1.2s 防抖被 unmount 掐掉, 整笔存档丢失」的根因。
  const convLoaded = useRef(false);
  const activeConvIdRef = useRef<number | null>(null);
  const lastSavedConv = useRef<string>('');
  const pendingJson = useRef<string | null>(null);
  const pendingMsgs = useRef<HubMessage[]>([]);
  const saveBusy = useRef(false);
  const flushRef = useRef<() => void>(() => {});

  const push = (m: HubMessage) => setMsgs((cur) => [...cur, m]);

  // 滚到底
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, thinking]);

  // 侧栏历史:拉本人真实会话(不是写死占位)
  useEffect(() => {
    let cancelled = false;
    listResumeCopilotSessions()
      .then((items) => {
        if (cancelled) return;
        setSessions(
          items.map((s) => ({
            id: s.id,
            label: s.name?.trim() || s.track || s.file_name || `会话 ${s.id}`,
            time: relTime(s.updated_at || s.created_at),
          })),
        );
      })
      .catch(() => {
        /* 拉不到则空列表,显示「还没有会话」 */
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // ── 进场拉真实 working query + 记忆(派生 2–3 条记忆 pill 文案) ───────────
  useEffect(() => {
    let cancelled = false;
    getWorkingQuery(sessionId)
      .then((r) => {
        if (!cancelled) setWorkingQuery(r.working_query);
      })
      .catch(() => {
        if (!cancelled) setWorkingQuery(null);
      });
    getStudentKbIndex()
      .then((r) => {
        if (cancelled) return;
        const pills = (r.items ?? [])
          .map((it) => (it.summary ?? '').trim())
          .filter(Boolean)
          .slice(0, 3);
        setMemoryPills(pills);
      })
      .catch(() => {
        if (!cancelled) setMemoryPills([]);
      });
    // 真实候选人姓名: confirmed 优先, 回退 parsed; 用于问候 + 侧栏头像/名(去写死「陈思远」)
    getResumeCopilotConfirmedProfile(sessionId)
      .catch(() => getResumeCopilotParsedProfile(sessionId))
      .then((r) => {
        if (cancelled) return;
        const nm = (r?.profile?.basic_info?.name ?? '').trim();
        if (nm) setUserName(nm);
      })
      .catch(() => {
        /* 拉不到姓名则保持空 → 落「同学」 */
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // 刷新当前简历名下的对话列表(侧栏「历史对话」)。每次落库成功后也调一次 ——
  // 修「历史出现得不稳定/要刷新页面才看到」: 列表跟着每轮对话即时更新。
  function refreshConvs() {
    listHubConversations(sessionId)
      .then((r) => {
        setConvs(
          (r.conversations ?? []).map((c) => ({
            id: c.id,
            title: c.title || '对话',
            time: relTime(c.updated_at),
          })),
        );
      })
      .catch(() => {
        /* 拉不到先留旧列表 */
      });
  }

  // 把待落库快照真正写进后端: 无 activeConvId → create 插新行(=「新对话」第一笔);
  // 有 → PUT 到自己的对话行。串行化(saveBusy)防 create 重入; finally 里若又积了
  // 新快照则连环 flush。失败(demo 只读 403/网络)留前端态不阻断。
  async function flushSaveNow() {
    if (saveBusy.current) return;
    const json = pendingJson.current;
    if (!json || json === lastSavedConv.current) return;
    const messages = pendingMsgs.current;
    saveBusy.current = true;
    pendingJson.current = null;
    try {
      if (activeConvIdRef.current == null) {
        const r = await createHubConversation(sessionId, deriveConvTitle(messages), messages);
        activeConvIdRef.current = r.id;
        setActiveConvId(r.id);
      } else {
        await putHubConversationDetail(sessionId, activeConvIdRef.current, messages);
      }
      lastSavedConv.current = json;
      refreshConvs();
    } catch {
      /* demo 只读 / 网络 → 留前端态 */
    } finally {
      saveBusy.current = false;
      if (pendingJson.current && pendingJson.current !== lastSavedConv.current) {
        void flushSaveNow();
      }
    }
  }
  // flushRef 让卸载清理函数永远拿到最新闭包(不能在 render 里写 ref, 放 effect)。
  useEffect(() => {
    flushRef.current = () => void flushSaveNow();
  });
  // 卸载(跳模拟面试/编辑页/切简历)时同步 flush 待落库快照 —— 修旧版 1.2s 防抖
  // 被 router.push 掐掉、整笔对话丢失的根因。SPA 内跳页 JS 还活着, fetch 能送达。
  useEffect(() => {
    return () => {
      flushRef.current();
    };
  }, []);

  // ── 进会话: 拉这份简历名下的对话列表, 默认续上最新一个对话(切回来能看到记录)──
  // 全部消息都重放, skillrun 带 settled 标 → 思考卡渲染成完成折叠态(轨迹可点开看,
  // 不重播动画、不重触发结果卡)。没有对话则按空白落地。
  useEffect(() => {
    let cancelled = false;
    listHubConversations(sessionId)
      .then(async (r) => {
        if (cancelled) return;
        const list = r.conversations ?? [];
        setConvs(
          list.map((c) => ({ id: c.id, title: c.title || '对话', time: relTime(c.updated_at) })),
        );
        const latest = list[0];
        if (!latest || latest.message_count === 0) return;
        const detail = await getHubConversationDetail(sessionId, latest.id);
        if (cancelled) return;
        const arr = Array.isArray(detail.messages) ? (detail.messages as HubMessage[]) : [];
        if (arr.length > 0) {
          bumpSeqFromIds(arr.map((m) => m.id));
          lastSavedConv.current = JSON.stringify(arr);
          activeConvIdRef.current = latest.id;
          setActiveConvId(latest.id);
          setMsgs(arr);
          setStarted(true);
        }
      })
      .catch(() => {
        /* 拉不到 → 按空白落地, 不阻断 */
      })
      .finally(() => {
        if (!cancelled) convLoaded.current = true;
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // ── 对话变动 → 记快照 + 短防抖落库。skillrun(思考路径)也入库 —— 打上 settled 标,
  //   回放时渲染成定格完成态(修「思考过程不保存」: 路径本身是交付物的一部分)。
  //   水合完成前不落(convLoaded)、空对话不落、内容没变不重复落。防抖只为合并同一轮
  //   连续 push 的几条消息(400ms); 跳页/卸载由上面的 unmount flush 兜底, 不会再丢。
  useEffect(() => {
    if (!convLoaded.current) return;
    const persistable = msgs.map((m) =>
      m.kind === 'skillrun' && !m.settled ? { ...m, settled: true } : m,
    );
    if (persistable.length === 0) return;
    const json = JSON.stringify(persistable);
    if (json === lastSavedConv.current) return;
    pendingJson.current = json;
    pendingMsgs.current = persistable;
    const t = window.setTimeout(() => flushRef.current(), 400);
    return () => window.clearTimeout(t);
  }, [msgs, sessionId]);

  // ── 切到这份简历名下的另一个对话(侧栏历史点选): 先存当前, 再整段重放目标对话──
  function selectConversation(convId: number) {
    if (convId === activeConvId) return;
    flushRef.current();
    getHubConversationDetail(sessionId, convId)
      .then((detail) => {
        const arr = Array.isArray(detail.messages) ? (detail.messages as HubMessage[]) : [];
        bumpSeqFromIds(arr.map((m) => m.id));
        pendingJson.current = null;
        lastSavedConv.current = JSON.stringify(arr);
        activeConvIdRef.current = convId;
        setActiveConvId(convId);
        setMsgs(arr);
        setStarted(arr.length > 0);
        setActive('none');
        setArmed(null);
        setThinking(false);
        busy.current = false;
        completed.current = new Set();
        respById.current = new Map();
        ctxById.current = new Map();
        pendingComplete.current = new Map();
      })
      .catch(() => {
        /* 拉不到则留在当前对话 */
      });
  }

  // 把真实 working query + 召回结果织进某条 skillrun 的「我的理解 / 计数」覆盖
  function applyFeedResp(skillrunId: string, resp: RecommendTurnResponse) {
    respById.current.set(skillrunId, resp);
    const tracks = resp.working_query?.seed_sub_cats ?? [];
    const feedLen = resp.feed?.length ?? 0;
    setMsgs((cur) =>
      cur.map((m) =>
        m.id === skillrunId && m.kind === 'skillrun'
          ? {
              ...m,
              understandOverride: { tracks, memory: memoryPills },
              // 节点序号: 1 = 检索岗位, 3 = 排出推荐(对齐 deep-think-meta feed 节点顺序)
              outputOverride: {
                1: `召回 ${feedLen} → 去重 ${feedLen}`,
                3: feedLen > 0 ? '第一版 Top 已就绪' : '本版暂无匹配',
              },
            }
          : m,
      ),
    );
  }

  // ── 跑技能: 每个模块 = 对话里跑一次技能 → 落结果卡 → 点开才进视图 ──
  function runSkill(key: HubModule) {
    if (busy.current) return;

    if (key === 'profile') {
      // 个人档案不是「跑技能」, 直接看(无思考卡、无结果卡)
      setStarted(true);
      push({ id: nextId(), kind: 'turn', who: 'ai', html: PROFILE_SAY });
      setActive('profile');
      return;
    }

    busy.current = true;
    setStarted(true);
    setActive('none'); // 收回全宽对话看它「想」—— 永不瞬移进面板
    push({ id: nextId(), kind: 'turn', who: 'ai', html: SAY[key] });
    const skillrunId = nextId();
    push({ id: skillrunId, kind: 'skillrun', module: key });

    // 职位推荐: 动画播放的同时, 并发打真后端 recommend-chat. 结果织回这条 skillrun,
    // 落结果卡时(动画 + 请求都完成)再据此渲染真实赛道 / 计数.
    if (key === 'feed') {
      const text = lastUserText.current || '给我推荐一下岗位';
      postRecommendChat(sessionId, text)
        .then(async (resp) => {
          // recommend-chat 只在「这句话改变了查询条件」时才回新列表;首次「给我推荐」
          // 与已确认赛道一致 → 无 delta → feed 为空. 此时主动 reseed,把当前赛道下
          // 实际在招的岗位拉出来铺满右栏(否则学生看到 0 个在招, 其实库里有).
          let feedItems = resp.feed ?? [];
          let wq = resp.working_query ?? null;
          if (feedItems.length === 0) {
            try {
              const r = await updateWorkingQuery(sessionId, { reseed: true });
              feedItems = r.feed ?? [];
              if (r.working_query) wq = r.working_query;
            } catch {
              /* reseed 失败则保持空, 走「暂无匹配」文案 */
            }
          }
          setFeed(feedItems);
          if (wq) setWorkingQuery(wq);
          applyFeedResp(skillrunId, { ...resp, feed: feedItems, working_query: wq ?? resp.working_query });
          // 动画若已先跑完, 这里补落结果卡.
          const waiter = pendingComplete.current.get(skillrunId);
          if (waiter) {
            pendingComplete.current.delete(skillrunId);
            waiter();
          }
        })
        .catch(async () => {
          // 对话接口被拒(典型: demo 只读会话 403) → 退到只读 reseed,
          // 仍按会话画像铺出在招岗; reseed 也失败才落「暂无匹配」.
          let feedItems: RecommendTurnResponse['feed'] = [];
          let wq = workingQuery ?? null;
          try {
            const r = await updateWorkingQuery(sessionId, { reseed: true });
            feedItems = r.feed ?? [];
            if (r.working_query) wq = r.working_query;
          } catch {
            /* 仍失败则保持空 */
          }
          setFeed(feedItems ?? []);
          if (wq) setWorkingQuery(wq);
          applyFeedResp(skillrunId, {
            intent: 'recommend',
            reply: '',
            feed: feedItems ?? [],
            working_query: wq ?? {
              seed_sub_cats: [],
              sub_cats: [],
              companies: [],
              locations: [],
              exclude: [],
              sort: 'match',
              only: false,
              note: '',
            },
            trace: { intent: 'recommend', query_delta: {}, remember_note: '' },
            remembered: null,
          });
          const waiter = pendingComplete.current.get(skillrunId);
          if (waiter) {
            pendingComplete.current.delete(skillrunId);
            waiter();
          }
        });
    }

    // 梯队骨架: 并发拉真实 platform-skeleton(读缓存情报, 不打实时 LLM, 便宜),
    // 结果卡用真实赛道 + GT 公司总数 + 分档标签. race-safe 同 feed.
    if (key === 'skeleton') {
      const finish = (ctx: ResultCtx) => {
        ctxById.current.set(skillrunId, ctx);
        const waiter = pendingComplete.current.get(skillrunId);
        if (waiter) {
          pendingComplete.current.delete(skillrunId);
          waiter();
        }
      };
      getPlatformsByTier(sessionId)
        .then((sk) => {
          const count = (sk.tiers ?? []).reduce((n, t) => n + (t.companies?.length ?? 0), 0);
          const bands = (sk.tiers ?? []).map((t) => t.band).filter(Boolean);
          finish({ subCat: sk.sub_cat || '', skeletonCount: count, skeletonBands: bands });
        })
        .catch(() => finish({}));
    }

    // 简历优化: 并发打真实诚实打分(LLM). 结果卡用真实现状分 + 潜力区间 + 缺口段数;
    // 同时把分缓存下来给打分报告页复用, 避免一次交互打两遍 LLM.
    if (key === 'resume') {
      const finish = (ctx: ResultCtx) => {
        ctxById.current.set(skillrunId, ctx);
        const waiter = pendingComplete.current.get(skillrunId);
        if (waiter) {
          pendingComplete.current.delete(skillrunId);
          waiter();
        }
      };
      scoreResume(sessionId)
        .then((sc) => {
          cacheScoreReport(sessionId, sc);
          finish({
            resumeCurrent: sc.overall_current,
            resumePotLow: sc.overall_potential_low,
            resumePotHigh: sc.overall_potential_high,
            resumeGaps: (sc.section_gaps ?? []).length,
          });
        })
        .catch(() => finish({}));
    }

    // busy 在 onSkillComplete(DeepThinkCard 跑完)时清; 这里只是安全兜底.
    setTimeout(() => {
      busy.current = false;
    }, 8000);
  }

  // 技能跑完 → 落结果卡(产出, 不是落点). 按 skillrun id guard, 防 onComplete 重入.
  function onSkillComplete(skillrunId: string, key: HubModule) {
    busy.current = false;
    if (completed.current.has(skillrunId)) return;

    // 职位推荐: 结果卡用真实赛道 + 计数. 若请求还没回, 挂起等它(race-safe).
    if (key === 'feed') {
      const resp = respById.current.get(skillrunId);
      if (!resp) {
        // 动画先跑完 → 注册一个待请求回来再落卡的回调.
        pendingComplete.current.set(skillrunId, () => onSkillComplete(skillrunId, key));
        return;
      }
      completed.current.add(skillrunId);
      const ctx: ResultCtx = {
        tracks: resp.working_query?.seed_sub_cats ?? [],
        feedLen: resp.feed?.length ?? 0,
      };
      push({ id: nextId(), kind: 'result', module: key, data: RESULT_FOR(key, ctx) });
      return;
    }

    // 梯队骨架 / 简历优化: 结果卡用真实后端数据. 请求没回则挂起等它(race-safe).
    if (key === 'skeleton' || key === 'resume') {
      const ctx = ctxById.current.get(skillrunId);
      if (!ctx) {
        pendingComplete.current.set(skillrunId, () => onSkillComplete(skillrunId, key));
        return;
      }
      completed.current.add(skillrunId);
      push({ id: nextId(), kind: 'result', module: key, data: RESULT_FOR(key, ctx) });
      return;
    }

    completed.current.add(skillrunId);
    push({ id: nextId(), kind: 'result', module: key, data: RESULT_FOR(key) });
  }

  // ── 激活语义: 点 chip / 侧边栏 / 落地卡 = 只「激活」(高亮 + 引导), 说一句话才「激发」──
  function armModule(key: HubModule) {
    if (key === 'profile') {
      runSkill('profile'); // 档案不是交付物, 点开直接看
      return;
    }
    setArmed((cur) => (cur === key ? null : key)); // 再点一次取消激活
  }

  // ── feed 卡联动 ──────────────────────────────────────────────────────────
  // 点 feed 公司 / 卡 → 联动梯队骨架卡高亮 + 滚动定位(若骨架视图已打开).
  function onHighlightCompany(company: string) {
    setHighlightCompany(company.trim() || null);
  }

  // 「讲讲这家」→ 情报回流对话主轴.
  // 诚实铁律: 没有结构化情报时显式说「暂无 · 不编造」, 绝不杜撰公司情报.
  // ctx.n_insights 来自骨架卡(同辈情报条数), 是唯一可信的结构化信号.
  function skelIntel(company: string, ctx?: { n_insights?: number }) {
    const name = company.trim();
    if (!name) return;
    setStarted(true);
    push({ id: nextId(), kind: 'turn', who: 'me', html: `讲讲${escapeHtml(name)}` });

    const n = ctx?.n_insights ?? 0;
    setThinking(true);
    // 短暂「思考」后落 trace + AI 回复 + 情报块(或诚实留白).
    window.setTimeout(() => {
      setThinking(false);
      if (n > 0) {
        push({
          id: nextId(),
          kind: 'trace',
          trace: {
            intent: 'intel',
            query_delta: { company: name, n_insights: n },
            remember_note: '',
          },
        });
        push({
          id: nextId(),
          kind: 'turn',
          who: 'ai',
          html: `<b>${escapeHtml(name)}</b> 命中 ${n} 条同辈情报，已在右侧骨架卡按门槛 / 前景 / 待遇聚合 —— 待遇没人提到的就诚实留白，不编数字。`,
        });
        push({
          id: nextId(),
          kind: 'intel',
          text: `共 ${n} 条同辈情报，覆盖门槛与前景为主；展开 <b>${escapeHtml(name)}</b> 的骨架卡看三维明细。`,
        });
      } else {
        // 无结构化情报 → 诚实, 不编造.
        push({
          id: nextId(),
          kind: 'turn',
          who: 'ai',
          html: `<b>${escapeHtml(name)}</b> 暂无结构化同辈情报 —— 这家是按赛道梯队补全的骨架公司，等有同学讨论会自动汇入。不编造它的门槛 / 待遇。`,
        });
      }
    }, 700);
  }

  // 「定制深挖」→ 定制回流对话主轴: AI 提议针对这家开一场模拟面试(实际开场 = Task 10).
  function skelCoach(company: string) {
    const name = company.trim();
    if (!name) return;
    setStarted(true);
    push({ id: nextId(), kind: 'turn', who: 'me', html: `想针对 ${escapeHtml(name)} 深挖` });
    push({
      id: nextId(),
      kind: 'turn',
      who: 'ai',
      html: `好，进入对 <b>${escapeHtml(name)}</b> 的定制：我会按它的门槛与考点反问你、对齐简历重点。要不要现在就开一场针对它的模拟面试？`,
    });
  }

  // ── 点结果卡 CTA → 才进入那个模块的视图 ──
  function openView(key: HubModule) {
    if (key === 'interview') {
      // 模拟面试全屏间 — 离开 Hub 进独立路由. 结束后由面试页自行处理回路.
      // TODO(next): interview 页加返回 /hub?session= 按钮
      router.push(`/interview/${sessionId}`);
      return;
    }
    // 简历优化 — 无感嵌入: 收进右侧画布槽(active='resume'), 保留左侧对话 + 思考流,
    // 不再 router.push 甩去 /hub-score 全屏页(那页左边空白、回不去)。打分已在跑技能
    // 时缓存, 面板优先复用缓存不重打 LLM。深链 /hub-score 仍保留作兜底入口。
    setActive(key as HubSlot);
  }

  // ── 发送 ──
  function onSend(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setStarted(true);
    lastUserText.current = trimmed; // feed 技能用它当 recommend-chat 的 message

    if (armed) {
      // 有激活的模块 → 这句话就是「激发交付物」
      const key = armed;
      setArmed(null);
      push({ id: nextId(), kind: 'turn', who: 'me', html: trimmed });
      runSkill(key);
      return;
    }

    // 没激活 → NL 路由
    push({ id: nextId(), kind: 'turn', who: 'me', html: trimmed });

    // 关键词命中模块 → 直接跑该技能
    let target: HubModule | null = null;
    if (/梯队|骨架|档次|全景/.test(trimmed)) target = 'skeleton';
    else if (/档案|我的资料|画像|记得/.test(trimmed)) target = 'profile';
    else if (/简历|改写|打分|优化/.test(trimmed)) target = 'resume';
    else if (/面试|模拟/.test(trimmed)) target = 'interview';
    else if (/推荐|岗位|职位|机会|看看|来点|多来|有什么/.test(trimmed)) target = 'feed';

    if (target) {
      runSkill(target);
      return;
    }

    // 都不命中 → 当作 feed 微调: 打 recommend-chat, 落意图 trace + AI 回复 + (命中时)记忆,
    // 同步刷新 feed / working query. 形态对齐推荐工作台 handleSend.
    void refineFeed(trimmed);
  }

  // feed 微调(非命中关键词的自由发言)→ 真后端 recommend-chat.
  async function refineFeed(text: string) {
    setThinking(true);
    try {
      const resp = await postRecommendChat(sessionId, text);
      push({ id: nextId(), kind: 'turn', who: 'ai', html: escapeHtml(resp.reply) });
      push({ id: nextId(), kind: 'trace', trace: resp.trace });
      if (resp.remembered) {
        push({
          id: nextId(),
          kind: 'memory',
          text: `记忆 → L3 preference · 后台落库（${resp.remembered.dimension}=${resp.remembered.value}）`,
        });
      }
      if (resp.feed !== null) setFeed(resp.feed);
      if (resp.working_query) setWorkingQuery(resp.working_query);
    } catch {
      push({
        id: nextId(),
        kind: 'turn',
        who: 'ai',
        html: '没太听懂，换个说法？比如「推荐岗位」「看看券商资管的梯队」「给简历打个分」。',
      });
    } finally {
      setThinking(false);
    }
  }

  // ── 新对话 = 在当前简历下另起一行(旧对话存好原样保留, 绝不覆盖)──
  function onNew() {
    flushRef.current(); // 当前对话的未落笔先存掉, 它会留在侧栏历史里
    setStarted(false);
    setActive('none');
    setArmed(null);
    setMsgs([]);
    setThinking(false);
    setFeed([]);
    setDeepening(null);
    setHighlightCompany(null);
    busy.current = false;
    completed.current = new Set();
    respById.current = new Map();
    pendingComplete.current = new Map();
    lastUserText.current = '';
    // 清当前对话指针 → 下一句话 create 新对话行(修单槽时代「新对话再聊就覆盖旧对话」)
    activeConvIdRef.current = null;
    setActiveConvId(null);
    pendingJson.current = null;
    lastSavedConv.current = '';
  }

  // 侧边栏高亮 = 激活态 或 已打开的画布槽
  const sidebarActive: HubModule | null = armed ?? (active === 'none' ? null : (active as HubModule));

  return (
    <div
      data-theme="hub"
      className="hf"
      data-session-id={sessionId}
      style={{ height: '100vh', display: 'flex', overflow: 'hidden', background: 'var(--parchment)' }}
    >
      {/* Left: 可折叠侧边栏 */}
      <HubSidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        active={sidebarActive}
        onNav={armModule}
        onNew={onNew}
        onUploadNew={() => router.push('/upload')}
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={(id) => {
          flushRef.current(); // 切简历前把当前对话存好(remount 会掐掉一切前端态)
          router.push(`/hub?session=${id}`);
        }}
        conversations={convs}
        activeConversationId={activeConvId}
        onSelectConversation={selectConversation}
        userName={userName}
      />

      {/* Center: 对话主轴(复用推荐工作台 chat 组件 → 挂 data-theme="recommend" 让其 CSS 命中) */}
      <div
        data-theme="recommend"
        style={{
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          flex: 1,
          background: 'var(--parchment)',
        }}
      >
        {!started ? (
          // 落地态: 问候+卡片中上部, 对话框沉底(HubLanding 内部满高分布)
          <div
            style={{
              flex: 1,
              overflow: 'auto',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '0 40px',
            }}
          >
            <HubLanding selected={armed} onPick={armModule} onSend={onSend} userName={userName} />
          </div>
        ) : (
          <>
            {/* 消息流 */}
            <div
              ref={bodyRef}
              style={{
                flex: 1,
                overflow: 'auto',
                padding: '18px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {msgs.map((m) => {
                switch (m.kind) {
                  case 'turn':
                    return (
                      <Turn key={m.id} who={m.who}>
                        <span dangerouslySetInnerHTML={{ __html: m.html }} />
                      </Turn>
                    );
                  case 'skillrun':
                    return (
                      <DeepThinkCard
                        key={m.id}
                        module={m.module as 'feed' | 'skeleton' | 'resume' | 'interview'}
                        understandOverride={m.understandOverride}
                        outputOverride={m.outputOverride}
                        settled={m.settled}
                        // 回放态不重触发结果卡(历史里已有那张); 双保险, 卡内 fired 也挡
                        onComplete={m.settled ? () => {} : () => onSkillComplete(m.id, m.module)}
                      />
                    );
                  case 'result':
                    return (
                      <ResultCard
                        key={m.id}
                        data={m.data}
                        opened={active === m.module}
                        onOpen={() => openView(m.module)}
                      />
                    );
                  case 'trace':
                    return <TraceCard key={m.id} trace={m.trace} />;
                  case 'memory':
                    return <MemoryToast key={m.id} text={m.text} />;
                  case 'intel':
                    return (
                      <Turn key={m.id} who="ai">
                        <span dangerouslySetInnerHTML={{ __html: m.text }} />
                      </Turn>
                    );
                  default:
                    return null;
                }
              })}
            </div>

            {/* dock: 激活引导 + SkillBar + Composer */}
            <div
              style={{
                flex: 'none',
                padding: '12px 16px 16px',
                borderTop: '1px solid var(--border-warm)',
                background: 'var(--parchment)',
                display: 'flex',
                flexDirection: 'column',
                gap: 11,
              }}
            >
              {armed && ARM_HINT[armed] && (
                <div
                  className="hf-slide"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '7px 12px',
                    borderRadius: 11,
                    background: 'var(--terracotta-wash)',
                    boxShadow: '0 0 0 1px #eccfb6',
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: 999,
                      background: 'var(--terracotta)',
                      flex: 'none',
                    }}
                  />
                  <span style={{ font: '500 12px var(--font-sans)', color: 'var(--terracotta-strong)' }}>
                    已激活「{ARM_HINT[armed].label}」· {ARM_HINT[armed].tip}
                  </span>
                </div>
              )}
              <SkillBar active={armed} onPick={armModule} />
              <Composer
                chips={QUICK_CHIPS}
                placeholder={
                  armed
                    ? '说一句就开始 —— 直接打你的话…'
                    : '说人话换方向、锁某家、或排除什么…'
                }
                onSend={onSend}
              />
            </div>
          </>
        )}
      </div>

      {/* Right: 会变形的画布槽 — 点结果卡 CTA 才出(active!=='none'); 关闭 → 全宽对话. */}
      <CanvasSlot
        active={active}
        sessionId={sessionId}
        feedProps={{
          sessionId,
          workingQuery,
          feed,
          setFeed,
          setWorkingQuery,
          onHighlightCompany,
          onIntel: skelIntel,
        }}
        highlightCompany={highlightCompany}
        onOpenIntel={skelIntel}
        onOpenCoach={skelCoach}
        onClose={() => setActive('none')}
      />
    </div>
  );
}
