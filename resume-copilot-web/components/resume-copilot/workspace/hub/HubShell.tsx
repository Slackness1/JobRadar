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
  getScoreTaskStatus,
  getStudentKbIndex,
  getWorkingQuery,
  listHubConversations,
  listResumeCopilotSessions,
  postRecommendChat,
  putHubConversationDetail,
  startScoreTask,
  updateWorkingQuery,
} from '../../api';
import { cacheScoreReport } from './scoreCache';
import type { RecommendFeedItem, WorkingQuery } from '../../types';
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

// 对话主轴下方的快捷 chip —— 按产品要求移除(留空数组,Composer 不渲染 chip 区)
const QUICK_CHIPS: ComposerChip[] = [];

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

  const busy = useRef(false); // 防双触发(受控技能启动后即释放 — 长任务期间还能继续聊)
  const completed = useRef<Set<string>>(new Set()); // skillrun id → 已落结果卡(防重, 仅 interview 定时路径)
  // 学生最近一句话(armed fire 时拿来当 recommend-chat 的 message)
  const lastUserText = useRef<string>('');
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // ── 后台续跑机制(③): 技能运行登记簿 + 对话纪元 ────────────────────────────
  // 每条 skillrun 登记 {module, epoch, sessionId}; epoch 在每次切对话/新对话/换简历
  // 时自增。完成时 epoch 没变 → 还在原对话, 结果就地落卡; 变了 → 学生已切走,
  // 把进度定格 + 结果卡直接写回原对话的库行(切回去就能看到), 任务不白跑。
  interface RunRec {
    module: HubModule;
    epoch: number;
    sessionId: number;
    finished: boolean;
  }
  const runsRef = useRef<Map<string, RunRec>>(new Map());
  const convEpoch = useRef(0);
  // epoch → 该纪元对话的库行 id(写回用)。create 成功 / 水合 / 切换时登记。
  const epochConvId = useRef<Map<number, number>>(new Map());

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

  // 滚到底 — 仅当本来就贴近底部(长任务轮询会持续更新思考卡, 不能把正在
  // 往上翻历史的学生反复拽回底部)。
  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (nearBottom) el.scrollTop = el.scrollHeight;
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
    const epochAtFlush = convEpoch.current; // 同步捕获 — create 回来时可能已切走
    saveBusy.current = true;
    pendingJson.current = null;
    try {
      if (activeConvIdRef.current == null) {
        const r = await createHubConversation(sessionId, deriveConvTitle(messages), messages);
        activeConvIdRef.current = r.id;
        setActiveConvId(r.id);
        epochConvId.current.set(epochAtFlush, r.id); // 后台续跑写回要认得这行
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
          convEpoch.current += 1; // 新视图纪元(换简历进场也算切换)
          epochConvId.current.set(convEpoch.current, latest.id);
          setMsgs(arr);
          setStarted(true);
          adoptRunningSkillruns(arr); // 「跑到一半」的打分任务重新挂上轮询(③)
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
    // adoptRunningSkillruns 是稳定的组件内函数(只碰 ref + setState), 不入依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ── 对话变动 → 记快照 + 短防抖落库。skillrun(思考路径)也入库 —— 打上 settled 标,
  //   回放时渲染成定格完成态(修「思考过程不保存」: 路径本身是交付物的一部分)。
  //   水合完成前不落(convLoaded)、空对话不落、内容没变不重复落。防抖只为合并同一轮
  //   连续 push 的几条消息(400ms); 跳页/卸载由上面的 unmount flush 兜底, 不会再丢。
  useEffect(() => {
    if (!convLoaded.current) return;
    // 已完成(progress.done 或老定时卡)的 skillrun 落库时打 settled(回放定格);
    // 还在跑的(progress 未 done)原样入库 —— 它是「跑到一半」的真实状态,
    // 切回/刷新时据此重新挂上轮询续跑(③ 后台续跑的存档面)。
    const persistable = msgs.map((m) =>
      m.kind === 'skillrun' && !m.settled && (!m.progress || m.progress.done)
        ? { ...m, settled: true }
        : m,
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
  // 运行登记簿不清 —— 原对话还在跑的任务继续跑(③), 完成时写回它自己的对话行。
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
        convEpoch.current += 1; // 新纪元 — 旧对话的运行落到「后台」语义
        epochConvId.current.set(convEpoch.current, convId);
        setMsgs(arr);
        setStarted(arr.length > 0);
        setActive('none');
        setArmed(null);
        setThinking(false);
        busy.current = false;
        adoptRunningSkillruns(arr); // 切回来 — 还在跑的任务改绑当前视图, 实时续播
      })
      .catch(() => {
        /* 拉不到则留在当前对话 */
      });
  }

  // ── 技能运行的统一收口(真实进度 + 后台续跑)────────────────────────────────
  // 给某条 skillrun 打补丁(仅当它还在当前对话视图里; 切走了由 completeRun 写回库行)
  function patchSkillrun(run: RunRec, skillrunId: string, patch: Record<string, unknown>) {
    if (run.epoch !== convEpoch.current) return;
    setMsgs((cur) =>
      cur.map((m) =>
        m.id === skillrunId && m.kind === 'skillrun' ? ({ ...m, ...patch } as HubMessage) : m,
      ),
    );
  }

  // 失败时的诚实话术(不落假「完成」结果卡 — 修「明明失败了卡片还说完成」)
  const FAIL_SAY: Record<string, string> = {
    feed: '这次<b>职位推荐</b>没跑成(网络或服务波动)。再说一句「给我推荐一下岗位」就能重试。',
    skeleton: '这次<b>梯队骨架</b>没拉出来。再说一句「看看券商资管的梯队」就能重试。',
    resume:
      '这次<b>简历打分</b>没跑成(评审模型超时或服务波动)。再说一句「帮我的简历打个分」就能重试。',
  };

  // 在(可能已切走的)skillrun 所属对话里定格进度 + 落结果卡/失败说明。
  // epoch 没变 → 就地更新; 变了 → 直接写回那条对话的库行, 切回去就能看到(③)。
  async function completeRun(
    skillrunId: string,
    outcome:
      | {
          ok: true;
          ctx: ResultCtx;
          outputOverride?: Record<number, string>;
          understandOverride?: object;
          nodeOverride?: Record<number, { input?: Record<string, string | string[]>; chips?: string[] }>;
        }
      | { ok: false; failStep: number },
  ) {
    const run = runsRef.current.get(skillrunId);
    if (!run || run.finished) return;
    run.finished = true;
    busy.current = false;

    const finalPatch: Record<string, unknown> = outcome.ok
      ? {
          progress: { step: 4, done: true },
          ...(outcome.outputOverride ? { outputOverride: outcome.outputOverride } : {}),
          ...(outcome.understandOverride ? { understandOverride: outcome.understandOverride } : {}),
          ...(outcome.nodeOverride ? { nodeOverride: outcome.nodeOverride } : {}),
        }
      : { progress: { step: outcome.failStep, done: true, failed: true } };

    if (run.epoch === convEpoch.current) {
      // 还在原对话 — 就地定格 + 落卡
      patchSkillrun(run, skillrunId, finalPatch);
      if (outcome.ok) {
        push({ id: nextId(), kind: 'result', module: run.module, data: RESULT_FOR(run.module, outcome.ctx) });
      } else {
        push({ id: nextId(), kind: 'turn', who: 'ai', html: FAIL_SAY[run.module] ?? '这次没跑成,再试一次。' });
      }
      return;
    }

    // 已切走 — 写回原对话库行(后台续跑的交付面)
    const convId = epochConvId.current.get(run.epoch);
    if (convId == null) return; // 对话从未落库(demo 只读等) → 无处可写, 放弃
    try {
      const detail = await getHubConversationDetail(run.sessionId, convId);
      const arr = Array.isArray(detail.messages) ? (detail.messages as HubMessage[]) : [];
      const patched = arr.map((m) =>
        m.id === skillrunId && m.kind === 'skillrun'
          ? ({ ...m, ...finalPatch, settled: true } as HubMessage)
          : m,
      );
      const tail: HubMessage = outcome.ok
        ? { id: nextId(), kind: 'result', module: run.module, data: RESULT_FOR(run.module, outcome.ctx) }
        : { id: nextId(), kind: 'turn', who: 'ai', html: FAIL_SAY[run.module] ?? '这次没跑成,再试一次。' };
      await putHubConversationDetail(run.sessionId, convId, [...patched, tail]);
      if (run.sessionId === sessionId) refreshConvs();
    } catch {
      /* 写回失败(网络/只读)不阻断 — 任务结果仍在后端缓存, 重开还能拿到 */
    }
  }

  // 简历打分: 轮询后端任务真实阶段 → 思考卡节点(prepare=解析, llm=评审, parse=定位)。
  // 任务在服务端跑, 切对话/刷新都不中断; 这里只是「看表」。
  function pollScoreTask(skillrunId: string) {
    const STAGE_STEP: Record<string, number> = { prepare: 0, llm: 1, parse: 2 };
    let netFails = 0; // 连续网络失败计数 — 有界重试, 不无限转
    const tick = async () => {
      const run = runsRef.current.get(skillrunId);
      if (!run || run.finished) return;
      try {
        const st = await getScoreTaskStatus(run.sessionId);
        netFails = 0;
        if (st.status === 'running') {
          const step = STAGE_STEP[st.stage] ?? 0;
          const live: Record<number, string> = {};
          if (st.stage === 'llm' && st.elapsed_seconds != null && st.elapsed_seconds >= 10) {
            // 10s 粒度 — 既给「真的在跑」的体感, 又不至于每拍都触发落库
            live[1] = `评审模型工作中 · 已约 ${Math.floor(st.elapsed_seconds / 10) * 10}s`;
          }
          patchSkillrun(run, skillrunId, {
            progress: { step, done: false },
            ...(Object.keys(live).length ? { outputOverride: live } : {}),
          });
          window.setTimeout(() => void tick(), 2500);
          return;
        }
        if (st.status === 'done' && st.report) {
          const sc = st.report;
          cacheScoreReport(run.sessionId, sc);
          const gaps = (sc.section_gaps ?? []).length;
          const gapLabels = (sc.section_gaps ?? [])
            .map((g) => (g.label || '').trim())
            .filter(Boolean)
            .slice(0, 3);
          void completeRun(skillrunId, {
            ok: true,
            ctx: {
              resumeCurrent: sc.overall_current,
              resumePotLow: sc.overall_potential_low,
              resumePotHigh: sc.overall_potential_high,
              resumeGaps: gaps,
            },
            understandOverride: {
              tracks: sc.target_track ? [sc.target_track] : [],
              memory: memoryPills,
            },
            outputOverride: {
              0: '简历画像已就绪',
              1: `现状 ${sc.overall_current} · 潜力 ${sc.overall_potential_low}–${sc.overall_potential_high}`,
              2: gaps > 0 ? `定位到 ${gaps} 段可补缺口` : '未发现硬缺口',
              3: gaps > 0 ? `${gaps} 段建议 · 已挂逐段入口` : '建议已生成',
            },
            nodeOverride: {
              0: { chips: ['结构化完成'] },
              1: {
                input: { against: `${sc.target_track || '通用'} 画像` },
                chips: [
                  `现状 ${sc.overall_current}`,
                  `潜力 ${sc.overall_potential_low}–${sc.overall_potential_high}`,
                ],
              },
              2: { chips: gapLabels.length > 0 ? gapLabels : ['未发现硬缺口'] },
              3: { chips: gaps > 0 ? ['逐段入口已挂'] : ['无需逐段修补'] },
            },
          });
          return;
        }
        // failed / none(后端重启任务丢了) → 诚实失败
        void completeRun(skillrunId, { ok: false, failStep: 1 });
      } catch {
        // 单次轮询失败不算任务失败(网络抖动), 但连抖 6 次(~24s)就诚实失败
        netFails += 1;
        if (netFails >= 6) {
          void completeRun(skillrunId, { ok: false, failStep: 1 });
          return;
        }
        window.setTimeout(() => void tick(), 4000);
      }
    };
    void tick();
  }

  // 水合/切对话后: 把「跑到一半」的 skillrun 重新挂上(③ 切回续跑)。
  // - 登记簿里还有活的(同页切换) → 改绑到新纪元, 完成时就地落卡;
  // - 簿里没有但是 resume(任务在后端) → 重新挂轮询;
  // - 簿里没有的 feed/skeleton(请求随刷新丢了) → 诚实定格为未完成。
  function adoptRunningSkillruns(arr: HubMessage[]) {
    for (const m of arr) {
      if (m.kind !== 'skillrun' || !m.progress || m.progress.done) continue;
      const live = runsRef.current.get(m.id);
      if (live && !live.finished) {
        live.epoch = convEpoch.current;
        continue;
      }
      if (m.module === 'resume') {
        runsRef.current.set(m.id, {
          module: 'resume',
          epoch: convEpoch.current,
          sessionId,
          finished: false,
        });
        pollScoreTask(m.id);
      } else {
        // 请求已随页面生命周期丢失 — 定格为未完成, 不装成功
        setMsgs((cur) =>
          cur.map((x) =>
            x.id === m.id && x.kind === 'skillrun'
              ? { ...x, progress: { ...m.progress!, done: true, failed: true }, settled: true }
              : x,
          ),
        );
      }
    }
  }

  // ── 跑技能: 每个模块 = 对话里跑一次技能 → 落结果卡 → 点开才进视图 ──
  // feed/skeleton/resume 走「受控真实进度」: 思考卡节点跟着真实请求/后端任务走,
  // 结果出来之前卡不会说「完成」(修「思考完了很久才出结果, 体验割裂」)。
  function runSkill(key: HubModule) {
    if (busy.current) return;

    if (key === 'profile') {
      // 个人档案不是「跑技能」, 直接看(无思考卡、无结果卡)
      setStarted(true);
      push({ id: nextId(), kind: 'turn', who: 'ai', html: PROFILE_SAY });
      setActive('profile');
      return;
    }

    // 同一对话里同模块还在跑 → 不重复开(后端打分本身也会去重)
    for (const [, r] of runsRef.current) {
      if (!r.finished && r.module === key && r.epoch === convEpoch.current) {
        push({
          id: nextId(),
          kind: 'turn',
          who: 'ai',
          html: '这个还在跑 —— 上面的思考卡就是实时进度,跑完结果会落在这里。',
        });
        return;
      }
    }

    busy.current = true;
    setStarted(true);
    setActive('none'); // 收回全宽对话看它「想」—— 永不瞬移进面板
    push({ id: nextId(), kind: 'turn', who: 'ai', html: SAY[key] });
    const skillrunId = nextId();

    if (key === 'interview') {
      // 面试预备没有真实后端任务 — 保留定时思考卡, 跑完由 onSkillComplete 落卡
      push({ id: skillrunId, kind: 'skillrun', module: key });
      setTimeout(() => {
        busy.current = false;
      }, 8000);
      return;
    }

    // 受控模块: skillrun 自带 progress(真实进度), 登记进运行簿(③ 后台续跑)。
    // 「我的理解」与节点入参从启动起就用真实数据(当前工作查询的子赛道 + 真实记忆),
    // 不再露静态底座里写死的投研/券商资管话术(2026-06-12 反馈「我选的是互联网赛道」)。
    const seedTracks = (workingQuery?.seed_sub_cats ?? []).filter(Boolean);
    const trackText = seedTracks.length > 0 ? seedTracks.slice(0, 3).join(' · ') : '你确认的赛道';
    const understand0 = {
      tracks: seedTracks,
      memory: memoryPills,
      ...(key === 'feed'
        ? {
            headline: `${trackText} 方向的真实在招岗位,不是泛泛撒网。`,
            reasoning:
              '结合你确认的赛道和记忆,我会先锁定范围,再检索在招、做三维打分,最后排出最值得投的几个。',
          }
        : {}),
      ...(key === 'skeleton' ? { headline: `把 ${trackText} 的公司按梯队分档铺成全景。` } : {}),
    };
    const node0: Record<number, { input?: Record<string, string | string[]>; chips?: string[] }> =
      key === 'feed'
        ? {
            0: {
              input: { track: seedTracks.length ? seedTracks : '你确认的赛道' },
              chips: [...seedTracks.slice(0, 3), `命中记忆 ×${memoryPills.length}`],
            },
            1: { input: { tracks: seedTracks.length ? seedTracks : '你确认的赛道' } },
          }
        : key === 'skeleton'
          ? {
              0: { input: { track: trackText } },
              2: { input: { profile: userName || '你的画像' } },
            }
          : {
              0: { chips: ['结构化完成'] },
              1: { input: { against: '你确认的目标赛道画像' } },
            };
    const initialStep = key === 'feed' ? 1 : 0; // feed 的节点0「锁定赛道」即时完成
    push({
      id: skillrunId,
      kind: 'skillrun',
      module: key,
      progress: { step: initialStep, done: false },
      understandOverride: understand0,
      nodeOverride: node0,
    });
    const run: RunRec = { module: key, epoch: convEpoch.current, sessionId, finished: false };
    runsRef.current.set(skillrunId, run);
    // 启动即释放 busy — 长任务(打分 ~90s)期间学生还能继续聊/跑别的模块
    busy.current = false;

    // 职位推荐: 真后端 recommend-chat; 最后一个节点等真实结果回来才亮(不抢跑)。
    if (key === 'feed') {
      const text = lastUserText.current || '给我推荐一下岗位';
      const finishFeed = (feedItems: RecommendFeedItem[], wq: WorkingQuery | null) => {
        setFeed(feedItems);
        if (wq) setWorkingQuery(wq);
        const tracks = (wq?.seed_sub_cats ?? []).filter(Boolean);
        const tt = tracks.length > 0 ? tracks.slice(0, 3).join(' · ') : '你确认的赛道';
        // 检索节点的结果签用真实赛道分布(按命中赛道计数), 不再写死券商研究×14
        const counts = new Map<string, number>();
        for (const it of feedItems) {
          const label = (it.matched_track_label || '').trim();
          if (label) counts.set(label, (counts.get(label) ?? 0) + 1);
        }
        const topChips = [...counts.entries()]
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([k, v]) => `${k} ×${v}`);
        const n = feedItems.length;
        void completeRun(skillrunId, {
          ok: true,
          ctx: { tracks, feedLen: n },
          understandOverride: {
            tracks,
            memory: memoryPills,
            headline: `${tt} 方向的真实在招岗位,不是泛泛撒网。`,
            reasoning:
              '结合你确认的赛道和记忆,我会先锁定范围,再检索在招、做三维打分,最后排出最值得投的几个。',
          },
          outputOverride: {
            1: `召回 ${n} → 去重 ${n}`,
            2: n > 0 ? `${n} 个岗位三维评分完成` : '本版无可评分岗位',
            3: n > 0 ? '第一版 Top 已就绪' : '本版暂无匹配',
          },
          nodeOverride: {
            0: {
              input: { track: tracks.length ? tracks : '你确认的赛道' },
              chips: [...tracks.slice(0, 3), `命中记忆 ×${memoryPills.length}`],
            },
            1: {
              input: { tracks: tracks.length ? tracks : '你确认的赛道' },
              chips: topChips.length > 0 ? topChips : [`在招 ${n}`],
            },
            3: {
              input: { topN: `Top ${Math.min(n, 10)}`, guard: 'substring 反幻觉' },
              chips: n > 0 ? [`Top ${Math.min(n, 10)} 已排出`] : ['本版暂无匹配'],
            },
          },
        });
      };
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
          finishFeed(feedItems, wq);
        })
        .catch(async () => {
          // 对话接口被拒(典型: demo 只读会话 403) → 退到只读 reseed,
          // 仍按会话画像铺出在招岗; reseed 也失败才落「暂无匹配」.
          try {
            const r = await updateWorkingQuery(sessionId, { reseed: true });
            finishFeed(r.feed ?? [], r.working_query ?? workingQuery ?? null);
          } catch {
            finishFeed([], workingQuery ?? null);
          }
        });
      return;
    }

    // 梯队骨架: 拉真实 platform-skeleton(读缓存情报, 不打实时 LLM, 便宜)。
    if (key === 'skeleton') {
      getPlatformsByTier(sessionId)
        .then((sk) => {
          const count = (sk.tiers ?? []).reduce((n, t) => n + (t.companies?.length ?? 0), 0);
          const bands = (sk.tiers ?? []).map((t) => t.band).filter(Boolean);
          const sc = sk.sub_cat || '你确认的赛道';
          void completeRun(skillrunId, {
            ok: true,
            ctx: { subCat: sk.sub_cat || '', skeletonCount: count, skeletonBands: bands },
            understandOverride: {
              tracks: sk.sub_cat ? [sk.sub_cat] : [],
              memory: memoryPills,
              headline: `把 ${sc} 的公司按梯队分档铺成全景。`,
            },
            outputOverride: {
              0: `拉到 ${count} 家公司`,
              1: bands.length > 0 ? `分出 ${bands.join(' / ')}` : '本版暂无分档',
              // 个人定档不是这条便宜链路算的 — 不冒领, 指到骨架卡看真实对照
              2: '梯队全景铺开 · 个人定档看骨架卡',
            },
            nodeOverride: {
              0: { input: { track: sc }, chips: [`${count} 家公司`] },
              1: { chips: bands.length > 0 ? bands : ['本版暂无分档'] },
              2: {
                input: { profile: userName || '你的画像' },
                chips: bands.length > 0 ? [`按 ${bands.join(' / ')} 对照`] : [],
              },
            },
          });
        })
        .catch(() => void completeRun(skillrunId, { ok: false, failStep: 0 }));
      return;
    }

    // 简历优化(④⑤核心): 打分改后端任务 — start 立即返回, 任务在服务端跑
    // (切对话/跳页不中断), 思考卡轮询真实阶段; 失败诚实失败, 不落假「完成」。
    if (key === 'resume') {
      startScoreTask(sessionId, { force: true })
        .then(() => pollScoreTask(skillrunId))
        .catch(() => void completeRun(skillrunId, { ok: false, failStep: 0 }));
    }
  }

  // 技能跑完 → 落结果卡(仅 interview 定时路径; 受控模块由 completeRun 收口)。
  function onSkillComplete(skillrunId: string, key: HubModule) {
    busy.current = false;
    if (completed.current.has(skillrunId)) return;
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
  // 运行登记簿不清 — 旧对话还在跑的任务转入后台, 完成时写回它自己的对话行(③)。
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
    convEpoch.current += 1; // 新纪元(对话行 id 等第一笔 create 后由 flush 登记)
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
        onOpenEditor={() => {
          flushRef.current(); // 跳全屏编辑器前把当前对话存好
          router.push(`/resume-copilot/hub-score?session=${sessionId}&editor=1`);
        }}
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
                        nodeOverride={m.nodeOverride}
                        settled={m.settled}
                        // 受控模式: 节点状态由真实进度驱动, 结果卡由 completeRun 收口
                        progress={m.progress}
                        // 回放/受控都不经卡片触发结果卡; 仅 interview 定时路径用
                        onComplete={
                          m.settled || m.progress
                            ? () => {}
                            : () => onSkillComplete(m.id, m.module)
                        }
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
