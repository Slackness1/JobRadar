'use client';

import { useEffect, useRef, useState } from 'react';
import type { JSX, ReactNode } from 'react';
import { Sparkles, ArrowUp, Check, Target } from 'lucide-react';
import {
  deepOptimizeStart,
  planTurn,
  deepOptimizeWriteBack,
  postChatMessage,
  type DeepOptimizeStartIn,
  type PlanStateOut,
  type PlanItemWire,
} from '../../../../api';

// ── 富文本:**加粗** → <b> ──────────────────────────────────────────────
function richHtml(s: string): { __html: string } {
  return { __html: (s || '').replace(/\*\*(.+?)\*\*/g, '<b style="color:var(--ink)">$1</b>') };
}

// ── AI 头像圆点(气泡 / thinking 共用)──────────────────────────────────
function AiAvatar(): JSX.Element {
  return (
    <span
      style={{
        width: 26,
        height: 26,
        flex: 'none',
        borderRadius: 999,
        display: 'grid',
        placeItems: 'center',
        color: '#faf9f5',
        background:
          'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)',
      }}
    >
      <Sparkles size={13} />
    </span>
  );
}

// ── 气泡 ─────────────────────────────────────────────────────────────────
function Bubble({ who, children }: { who: 'me' | 'ai'; children: ReactNode }): JSX.Element {
  const me = who === 'me';
  return (
    <div
      className="hf-slide"
      style={{
        display: 'flex',
        gap: 9,
        flexDirection: me ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
      }}
    >
      {!me && <AiAvatar />}
      <div
        style={{
          maxWidth: '84%',
          font: '400 12.5px/1.62 var(--font-sans)',
          color: me ? 'var(--ivory)' : 'var(--ink-soft)',
          background: me ? 'var(--terracotta)' : 'var(--ivory)',
          boxShadow: me ? 'none' : 'var(--sh-ring)',
          borderRadius: me ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
          padding: '9px 12px',
        }}
      >
        {children}
      </div>
    </div>
  );
}

// ── 思考中三点 ─────────────────────────────────────────────────────────
function ThinkingDots(): JSX.Element {
  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
      <AiAvatar />
      <div
        style={{
          display: 'flex',
          gap: 4,
          padding: '11px 13px',
          background: 'var(--ivory)',
          borderRadius: 14,
          boxShadow: 'var(--sh-ring)',
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="hf-pulse"
            style={{
              width: 5,
              height: 5,
              borderRadius: 999,
              background: 'var(--warm-silver)',
              animationDelay: `${i * 0.18}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

// ── 改写卡 ─────────────────────────────────────────────────────────────
function RewriteCard({
  label,
  text,
  done,
  busy,
  onWriteBack,
}: {
  label: string;
  text: string;
  done: boolean;
  busy: boolean;
  onWriteBack: () => void;
}): JSX.Element {
  // draft.text 可能含多条 bullet(以换行分隔),逐行渲染。
  const bullets = text
    .split('\n')
    .map((b) => b.replace(/^[•\-\s]+/, '').trim())
    .filter(Boolean);
  return (
    <div
      className="hf-slide"
      style={{
        marginLeft: 35,
        background: 'var(--ivory)',
        borderRadius: 14,
        boxShadow: '0 0 0 1px var(--terracotta-ring)',
        padding: 13,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
        <span className="hf-pill terra" style={{ height: 22, fontSize: 10.5 }}>
          定制改写 · {label}
        </span>
        <span style={{ marginLeft: 'auto', font: '400 9.5px var(--font-mono)', color: 'var(--stone)' }}>
          证据门 · 不编数字
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {bullets.map((b, i) => (
          <div
            key={i}
            style={{ display: 'flex', gap: 7, font: '400 12px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}
          >
            <span style={{ color: 'var(--terracotta)', flex: 'none' }}>•</span>
            <span>{b}</span>
          </div>
        ))}
      </div>
      {done ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginTop: 11,
            font: '500 11.5px var(--font-sans)',
            color: 'var(--emerald)',
          }}
        >
          <Check size={13} /> 已写回 · 中栏预览已刷新
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, marginTop: 11 }}>
          <button className="hf-btn primary sm" style={{ flex: 1 }} disabled={busy} onClick={onWriteBack}>
            {busy ? '写回中…' : '确认写回 · 刷新预览'}
          </button>
        </div>
      )}
    </div>
  );
}

// ── 会话消息(本地视图模型,从 PlanStateOut 派生 / 自由问本地 echo)────────
type ChatMsg =
  | { kind: 'text'; who: 'me' | 'ai'; html: string }
  | { kind: 'rewrite'; label: string; text: string; done: boolean };

const TARGET_TRACK_FALLBACK = '目标赛道';

// 从 plan 取「当前 item」。
function currentItem(plan: PlanStateOut): PlanItemWire | undefined {
  return plan.items.find((i) => i.id === plan.current_item_id) ?? plan.items[0];
}
// 当前 item 最新一条 open_question 文本。
function latestQuestion(item: PlanItemWire | undefined): string {
  const qs = item?.open_questions ?? [];
  return qs.length ? qs[qs.length - 1].text : '';
}

export interface ChatThreadProps {
  sessionId: number;
  mode: 'deep' | 'free';
  /** 深度优化:从打分缺口播种的首问入参。null = 还没选段。 */
  seed?: DeepOptimizeStartIn | null;
  /** 写回成功 → 通知父组件把对应段映射成 A4 lit。 */
  onWriteBack?: (section: string) => void;
  /** 无真实 session 时渲染样例对话(离线目测)。 */
  mock?: boolean;
}

// mock 样例对话(深度优化:AI 反问 → 用户答 → 改写卡)。
const MOCK_DEEP: ChatMsg[] = [
  { kind: 'text', who: 'me', html: '帮我改「九坤投资 · 量化研究实习」这段' },
  {
    kind: 'text',
    who: 'ai',
    html:
      '这段我想把成果补成**经得起追问**的版本(佐证充分)。先确认两个事实:① 你搭的回测框架大概覆盖多少因子、什么频率?② 改成批量之后,单因子筛选从多久缩短到多久?',
  },
  { kind: 'text', who: 'me', html: '覆盖 40 多个量价因子,日频;批量之后从大概 2 天缩到 4 小时。' },
  {
    kind: 'text',
    who: 'ai',
    html:
      '够了。基于你给的**真实事实**,我把这段改成 STAR 完整、且每个数字面试都能讲清来源的版本:',
  },
  {
    kind: 'rewrite',
    label: '九坤投资 · 量化研究实习',
    text:
      '搭建覆盖 40+ 量价因子的日频回测框架(2021–2023 全样本),将单因子筛选由手动改为一键批量,迭代周期由约 2 天缩短至 4 小时\n独立完成 12 个候选因子的有效性检验,其中 3 个进入组合因子池',
    done: false,
  },
];

export function ChatThread({ sessionId, mode, seed = null, onWriteBack, mock = false }: ChatThreadProps): JSX.Element {
  const [msgs, setMsgs] = useState<ChatMsg[]>(mock && mode === 'deep' ? MOCK_DEEP : []);
  const [thinking, setThinking] = useState(false);
  const [val, setVal] = useState('');
  const [focusLabel, setFocusLabel] = useState<string | null>(mock && mode === 'deep' ? '九坤投资 · 量化研究实习' : null);
  const [targetTrack, setTargetTrack] = useState<string>(TARGET_TRACK_FALLBACK);
  const [writingBack, setWritingBack] = useState(false);

  const plan = useRef<PlanStateOut | null>(null);
  const seededNonce = useRef<DeepOptimizeStartIn | null>(null);
  const busy = useRef(false);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // 输入框随内容自动加高:先归零再贴合 scrollHeight,最多三行(再多内部滚动)。
  // tab 用 display:none 切换 — 隐藏时 scrollHeight=0,直接套用会把输入框塌成
  // 零高度(点不进去、占位字也没了),所以隐藏状态跳过。
  useEffect(() => {
    const ta = taRef.current;
    if (!ta || ta.offsetParent === null) return;
    ta.style.height = 'auto';
    const lh = 19.5; // 13px 字号 × 1.5 行高
    const max = Math.round(lh * 3);
    const h = Math.max(Math.round(lh), Math.min(ta.scrollHeight, max));
    ta.style.height = `${h}px`;
    ta.style.overflowY = ta.scrollHeight > max ? 'auto' : 'hidden';
  }, [val]);

  // 自动滚到底。
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, thinking]);

  // 深度优化:seed 变化 → 锁定该段 + 调 deepOptimizeStart → 渲染首问。
  useEffect(() => {
    if (mode !== 'deep' || !seed || mock) return;
    if (seededNonce.current === seed) return; // 同一 seed 不重复 start
    seededNonce.current = seed;
    let alive = true;

    setFocusLabel(seed.label);
    setTargetTrack(seed.target_track || TARGET_TRACK_FALLBACK);
    setMsgs([{ kind: 'text', who: 'me', html: `帮我改「${seed.label}」这段` }]);
    setThinking(true);

    deepOptimizeStart(sessionId, seed)
      .then((p) => {
        if (!alive) return;
        plan.current = p;
        applyPlanToMsgs(p, true);
      })
      .catch((e) => {
        if (!alive) return;
        setMsgs((m) => [
          ...m,
          { kind: 'text', who: 'ai', html: `启动深度优化失败:${e instanceof Error ? e.message : '未知错误'}` },
        ]);
      })
      .finally(() => {
        if (alive) setThinking(false);
      });

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed, mode, mock, sessionId]);

  // 把一份 plan 派生成要追加的 AI 消息:反问气泡 / 改写卡。
  // reset=true 时(首问)只追加 AI 内容(用户气泡已先放好)。
  function applyPlanToMsgs(p: PlanStateOut, _reset: boolean): void {
    void _reset;
    const item = currentItem(p);
    const q = latestQuestion(item);
    const additions: ChatMsg[] = [];

    if (item?.status === 'awaiting_review' && item.draft?.text) {
      // 改写草稿就绪:先一句过渡,再放改写卡。
      additions.push({
        kind: 'text',
        who: 'ai',
        html: '够了。基于你给的**真实事实**,我把这段改成 STAR 完整、且每个数字面试都能讲清来源的版本:',
      });
      additions.push({ kind: 'rewrite', label: item.title || focusLabel || '改写', text: item.draft.text, done: false });
    } else if (q) {
      additions.push({ kind: 'text', who: 'ai', html: q });
    } else {
      additions.push({ kind: 'text', who: 'ai', html: '记下了。还要继续补这段,还是去打分看其它缺口?' });
    }
    setMsgs((m) => [...m, ...additions]);
  }

  function send(): void {
    const v = val.trim();
    if (!v || busy.current) return;
    busy.current = true;
    setMsgs((m) => [...m, { kind: 'text', who: 'me', html: v }]);
    setVal('');

    // 自由问:走后端真实顾问对话(/chat,带改写审计与目标赛道上下文)。
    if (mode === 'free' && !mock) {
      setThinking(true);
      postChatMessage(sessionId, v)
        .then((reply) => {
          setMsgs((m) => [...m, { kind: 'text', who: 'ai', html: reply.content || '(空回复)' }]);
        })
        .catch((e) => {
          setMsgs((m) => [
            ...m,
            { kind: 'text', who: 'ai', html: `这条没答上来:${e instanceof Error ? e.message : '未知错误'}。可以换个问法再试。` },
          ]);
        })
        .finally(() => {
          setThinking(false);
          busy.current = false;
        });
      return;
    }
    if (mode === 'free') {
      // 离线目测(mock):不调后端,给一句示例回声。
      setThinking(true);
      setTimeout(() => {
        setThinking(false);
        setMsgs((m) => [...m, { kind: 'text', who: 'ai', html: '(示例会话不接真模型——上传真实简历后这里会按目标赛道标准回答。)' }]);
        busy.current = false;
      }, 700);
      return;
    }

    // mock 深度优化:本地补一条改写卡。
    if (mock) {
      setThinking(true);
      setTimeout(() => {
        setThinking(false);
        setMsgs((m) => [
          ...m,
          { kind: 'text', who: 'ai', html: '够了。基于你给的**真实事实**,我把这段改成 STAR 完整的版本:' },
          {
            kind: 'rewrite',
            label: focusLabel || '改写',
            text: '补充真实成果指标后的 STAR 完整改写示例(mock)。',
            done: false,
          },
        ]);
        busy.current = false;
      }, 800);
      return;
    }

    // 真实深度优化:planTurn → 派生下一条反问 / 改写卡。
    setThinking(true);
    planTurn(sessionId, v)
      .then((p) => {
        plan.current = p;
        applyPlanToMsgs(p, false);
      })
      .catch((e) => {
        setMsgs((m) => [
          ...m,
          { kind: 'text', who: 'ai', html: `出错了:${e instanceof Error ? e.message : '未知错误'}` },
        ]);
      })
      .finally(() => {
        setThinking(false);
        busy.current = false;
      });
  }

  function handleWriteBack(idx: number): void {
    if (writingBack) return;

    // mock:本地标完成 + 通知父组件高亮(用 seed.section 或默认 internships.0)。
    if (mock) {
      setMsgs((m) => m.map((x, i) => (i === idx && x.kind === 'rewrite' ? { ...x, done: true } : x)));
      onWriteBack?.(seed?.section || 'internships.0');
      setTimeout(
        () =>
          setMsgs((m) => [
            ...m,
            { kind: 'text', who: 'ai', html: `已写回到「${focusLabel}」✓ 中栏预览实时刷新,这段的缺口标记会消掉。` },
          ]),
        360,
      );
      return;
    }

    setWritingBack(true);
    deepOptimizeWriteBack(sessionId)
      .then((res) => {
        if (res.applied) {
          setMsgs((m) => m.map((x, i) => (i === idx && x.kind === 'rewrite' ? { ...x, done: true } : x)));
          onWriteBack?.(res.section);
          setTimeout(
            () =>
              setMsgs((m) => [
                ...m,
                { kind: 'text', who: 'ai', html: `已写回到「${focusLabel}」✓ 中栏预览实时刷新。` },
              ]),
            360,
          );
        } else {
          setMsgs((m) => [...m, { kind: 'text', who: 'ai', html: '写回未生效,请检查改写是否就绪。' }]);
        }
      })
      .catch((e) => {
        setMsgs((m) => [
          ...m,
          { kind: 'text', who: 'ai', html: `写回失败:${e instanceof Error ? e.message : '未知错误'}` },
        ]);
      })
      .finally(() => setWritingBack(false));
  }

  const empty = msgs.length === 0 && !thinking;
  const hints =
    mode === 'deep'
      ? ['先去左边「打分」点一段缺口', '或直接说要改哪一段']
      : ['这段写法面试会被问什么?', '量化私募更看重哪些经历?', '帮我看下整体结构'];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--parchment)' }}>
      {/* 深度优化契约:一次只聚焦一段 + 锁定目标赛道 */}
      {mode === 'deep' && focusLabel && (
        <div
          style={{
            flex: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 14px',
            borderBottom: '1px solid var(--border-warm)',
            background: 'var(--terracotta-wash)',
          }}
        >
          <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex', flex: 'none' }}>
            <Target size={14} />
          </span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                font: '600 12px var(--font-sans)',
                color: 'var(--ink)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              锁定段:{focusLabel}
            </div>
            <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--terracotta-strong)', marginTop: 1 }}>
              目标赛道 · {targetTrack} · 一次只改这一段
            </div>
          </div>
        </div>
      )}

      <div
        ref={bodyRef}
        style={{ flex: 1, overflow: 'auto', padding: '14px 14px', display: 'flex', flexDirection: 'column', gap: 11 }}
      >
        {empty && (
          <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 250 }}>
            <div style={{ font: '500 13px var(--font-sans)', color: 'var(--olive)', marginBottom: 6 }}>
              {mode === 'deep' ? '反问取证 · 改写有据可依' : '自由问 · 随便聊'}
            </div>
            <div style={{ font: '400 11.5px/1.6 var(--font-sans)', color: 'var(--stone)' }}>
              {mode === 'deep'
                ? '从打分缺口进来,AI 会先反问你真实事实,再做定制改写 —— 不编没问出来的东西。'
                : '围绕你的简历和目标赛道随便问:写法、面试考点、行业标准都行。只按事实回答,不替你编经历。'}
            </div>
          </div>
        )}
        {msgs.map((m, i) => {
          if (m.kind === 'rewrite') {
            return (
              <RewriteCard
                key={i}
                label={m.label}
                text={m.text}
                done={m.done}
                busy={writingBack}
                onWriteBack={() => handleWriteBack(i)}
              />
            );
          }
          return (
            <Bubble key={i} who={m.who}>
              <span dangerouslySetInnerHTML={richHtml(m.html)} />
            </Bubble>
          );
        })}
        {thinking && <ThinkingDots />}
      </div>

      <div
        style={{
          flex: 'none',
          padding: '10px 14px 14px',
          borderTop: '1px solid var(--border-warm)',
          background: 'var(--parchment)',
        }}
      >
        {empty && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 9 }}>
            {hints.map((h, i) => (
              <button key={i} onClick={() => setVal(h)} className="hf-pill" style={{ height: 26, cursor: 'pointer' }}>
                {h}
              </button>
            ))}
          </div>
        )}
        <div
          style={{
            display: 'flex',
            gap: 9,
            alignItems: 'flex-end',
            background: 'var(--library-rail)',
            borderRadius: 14,
            padding: '7px 7px 7px 13px',
            boxShadow: '0 0 0 1px var(--border-warm)',
          }}
        >
          <textarea
            ref={taRef}
            rows={1}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => {
              // Enter 发送;Shift+Enter 换行。
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={mode === 'deep' ? '把真实情况说给它(数字越具体越好)…' : '问点什么…'}
            style={{
              flex: 1,
              background: 'transparent',
              border: 0,
              outline: 0,
              resize: 'none',
              font: '400 13px var(--font-sans)',
              lineHeight: '19.5px',
              color: 'var(--ink)',
              maxHeight: 59,
              overflowY: 'hidden',
              padding: 0,
              margin: '6px 0',
            }}
          />
          <button
            onClick={send}
            className="hf-btn primary"
            style={{ width: 32, height: 32, padding: 0, borderRadius: 999 }}
            aria-label="发送"
          >
            <ArrowUp size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
