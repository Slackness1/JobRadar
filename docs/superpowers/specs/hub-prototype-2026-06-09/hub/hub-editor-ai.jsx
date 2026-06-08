// hub/hub-editor-ai.jsx — 简历编辑器右栏 · AI 简历助手 v2
//   三能力共存：① 简历打分（报告式，不改简历）  ② 深度优化（反问取证 → 定制改写 → 写回）  ③ 自由问
/* global React, window */
const { useState: useEA, useEffect: useEAEffect, useRef: useEARef } = React;
const EICO = window.I;

// ---- 打分数据 ----------------------------------------------------------
const TARGET_TRACK = '量化私募 · 研究';
const ED_RADAR = [
  { k: '逻辑', v: 78 }, { k: 'STAR', v: 58 }, { k: '可读', v: 84 }, { k: '完整', v: 70 },
  { k: '表达', v: 80 }, { k: '量化', v: 52 }, { k: '匹配度', v: 64, fin: true }, { k: '佐证', v: 55, fin: true },
];
const ED_GAPS = [
  { id: 'intern', label: '九坤投资 · 量化研究实习', tags: ['STAR 缺 Result', '佐证不足'],
    ask: '这段我想把成果补成**经得起追问**的版本（佐证充分）。先确认两个事实：① 你搭的回测框架大概覆盖多少因子、什么频率？② 改成批量之后，单因子筛选从多久缩短到多久？',
    rewrite: ['搭建覆盖 40+ 量价因子的日频回测框架（2021–2023 全样本），将单因子筛选由手动改为一键批量，迭代周期由约 2 天缩短至 4 小时',
              '独立完成 12 个候选因子的有效性检验，其中 3 个进入组合因子池'] },
  { id: 'project', label: '校园量化策略研究', tags: ['成果无量化锚点'],
    ask: '这段缺一个能讲清楚的成果锚点。问你：策略在样本外大概跑出什么结果？比如年化、夏普或最大回撤，任意一个真实数字即可。',
    rewrite: ['基于公开行情构建动量 + 反转复合策略，样本外年化 11.4%、夏普 1.3、最大回撤控制在 8% 以内',
              '撰写 12 页策略研究报告，完成收益归因与回撤复盘'] },
  { id: 'intro', label: '个人介绍', tags: ['赛道匹配度低'],
    ask: '你的目标是量化私募 · 研究，但个人介绍偏泛。问你一句：最想让面试官记住你的一个硬能力是什么？',
    rewrite: ['面向量化研究方向：扎实的因子工程与回测工程能力，能独立从数据清洗走到策略归因'] },
];

// ---- ① 简历打分报告 ----------------------------------------------------
function ScoreReport({ onOptimize, activeId }) {
  const Radar = window.HubRadar;
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 16, background: 'var(--parchment)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span className="hf-overline" style={{ fontSize: 9.5 }}>目标赛道</span>
        <span className="hf-pill terra" style={{ height: 26 }}>量化私募 · 研究 ▾</span>
        <span style={{ marginLeft: 'auto', font: '500 11px var(--font-sans)', color: 'var(--stone)' }}>切换重打分</span>
      </div>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 16 }}>
        <div style={{ flex: 'none', textAlign: 'center' }}>
          <div style={{ font: '500 46px/0.9 var(--font-mono)', color: 'var(--ink)' }}>72</div>
          <div style={{ font: '500 11px var(--font-sans)', color: 'var(--olive)', marginTop: 4 }}>现状分</div>
          <div className="hf-pill" style={{ height: 24, marginTop: 9, fontFamily: 'var(--font-mono)' }}>潜力 80–85</div>
        </div>
        <div style={{ flex: 1, background: 'var(--ivory)', borderRadius: 14, boxShadow: 'var(--sh-ring)', display: 'flex', justifyContent: 'center', padding: 8 }}>
          <Radar size={172} data={ED_RADAR} />
        </div>
      </div>
      <div style={{ font: '400 11px/1.55 var(--font-sans)', color: 'var(--muted)', marginBottom: 13 }}>
        雷达 8 维 = 6 表层维 + 2 金融独有维（加粗 <b style={{ color: 'var(--terracotta-strong)' }}>匹配度 / 佐证充分度</b>）。<b style={{ color: 'var(--ink-soft)' }}>佐证</b> = 声明是否经得起追问，按目标 subcat 校准。
      </div>
      <div className="hf-overline" style={{ marginBottom: 10 }}>逐段缺口 · 深度优化入口</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        {ED_GAPS.map((g) => {
          const on = activeId === g.id;
          return (
            <div key={g.id} style={{ borderRadius: 13, padding: '12px 13px', background: 'var(--ivory)', boxShadow: on ? '0 0 0 1px var(--terracotta), 0 6px 18px rgba(201,100,66,0.08)' : 'var(--sh-ring)' }}>
              <div style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>{g.label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
                {g.tags.map((t, j) => <span key={j} className="hf-pill" style={{ height: 22, fontSize: 10.5, whiteSpace: 'nowrap' }}>{t}</span>)}
              </div>
              <button className={on ? 'hf-btn primary sm' : 'hf-btn sand sm'} style={{ height: 30 }} onClick={() => onOptimize(g)}>
                {on ? '正在深度优化 · 看对话 →' : '去深度优化这段 →'}
              </button>
            </div>
          );
        })}
      </div>
      <div style={{ font: '400 10.5px/1.5 var(--font-sans)', color: 'var(--stone)', textAlign: 'center', marginTop: 12 }}>只诊断、不改写 · 提分靠深度优化反问取证</div>
    </div>
  );
}

// ---- 富文本：**加粗** ----
function rich(s) { return { __html: (s || '').replace(/\*\*(.+?)\*\*/g, '<b style="color:var(--ink)">$1</b>') }; }

// ---- 气泡 ----
function Bubble({ who, children }) {
  const me = who === 'me';
  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, flexDirection: me ? 'row-reverse' : 'row', alignItems: 'flex-start' }}>
      {!me && <span style={{ width: 26, height: 26, flex: 'none', borderRadius: 999, display: 'grid', placeItems: 'center', color: '#faf9f5',
        background: 'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)' }}>{EICO.sparkle(13)}</span>}
      <div style={{ maxWidth: '84%', font: '400 12.5px/1.62 var(--font-sans)', color: me ? 'var(--ivory)' : 'var(--ink-soft)',
        background: me ? 'var(--terracotta)' : 'var(--ivory)', boxShadow: me ? 'none' : 'var(--sh-ring)',
        borderRadius: me ? '14px 14px 4px 14px' : '14px 14px 14px 4px', padding: '9px 12px' }}>
        {children}
      </div>
    </div>
  );
}

function ThinkingDots() {
  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
      <span style={{ width: 26, height: 26, flex: 'none', borderRadius: 999, display: 'grid', placeItems: 'center', color: '#faf9f5',
        background: 'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)' }}>{EICO.sparkle(13)}</span>
      <div style={{ display: 'flex', gap: 4, padding: '11px 13px', background: 'var(--ivory)', borderRadius: 14, boxShadow: 'var(--sh-ring)' }}>
        {[0, 1, 2].map((i) => <span key={i} className="hf-pulse" style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--warm-silver)', animationDelay: `${i * 0.18}s` }} />)}
      </div>
    </div>
  );
}

// ---- 改写卡 ----
function RewriteCard({ rw, done, onWriteBack }) {
  return (
    <div className="hf-slide" style={{ marginLeft: 35, background: 'var(--ivory)', borderRadius: 14, boxShadow: '0 0 0 1px var(--terracotta-ring)', padding: 13 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
        <span className="hf-pill terra" style={{ height: 22, fontSize: 10.5 }}>定制改写 · {rw.label}</span>
        <span style={{ marginLeft: 'auto', font: '400 9.5px var(--font-mono)', color: 'var(--stone)' }}>证据门 · 不编数字</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rw.newBullets.map((b, i) => (
          <div key={i} style={{ display: 'flex', gap: 7, font: '400 12px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}>
            <span style={{ color: 'var(--terracotta)', flex: 'none' }}>•</span><span>{b}</span>
          </div>
        ))}
      </div>
      {done ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 11, font: '500 11.5px var(--font-sans)', color: 'var(--emerald)' }}>
          {EICO.check(13)} 已写回 · 中栏预览已刷新
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, marginTop: 11 }}>
          <button className="hf-btn primary sm" style={{ flex: 1 }} onClick={onWriteBack}>确认写回 · 刷新预览</button>
          <button className="hf-btn ghost sm">再改改</button>
        </div>
      )}
    </div>
  );
}

// ---- ②③ 对话型（深度优化 / 自由问共用底座）----------------------------
function ChatThread({ mode, seed, onWriteBack, onUsedGap }) {
  const [msgs, setMsgs] = useEA([]);
  const [thinking, setThinking] = useEA(false);
  const [val, setVal] = useEA('');
  const [stage, setStage] = useEA('idle'); // idle | asked | rewritten
  const [focusLabel, setFocusLabel] = useEA(null); // 深度优化：当前聚焦的那一段
  const cur = useEARef(null);
  const bodyRef = useEARef(null);
  const busy = useEARef(false);

  useEAEffect(() => { const el = bodyRef.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, thinking]);

  // 深度优化：外部点「去深度优化这段」→ seed 改变 → 锁定该段 + AI 先抛反问
  useEAEffect(() => {
    if (mode !== 'deep' || !seed) return;
    cur.current = seed.gap;
    setFocusLabel(seed.gap.label);
    setStage('asked');
    setMsgs([{ who: 'me', html: `帮我改「${seed.gap.label}」这段` }]);
    setThinking(true);
    const t = setTimeout(() => { setThinking(false); setMsgs((m) => [...m, { who: 'ai', html: seed.gap.ask }]); }, 900);
    return () => clearTimeout(t);
  }, [seed && seed.nonce]);

  function send() {
    const v = val.trim(); if (!v || busy.current) return;
    busy.current = true;
    setMsgs((m) => [...m, { who: 'me', html: v }]); setVal('');
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      if (mode === 'deep' && stage === 'asked' && cur.current) {
        const g = cur.current;
        setMsgs((m) => [...m, { who: 'ai', html: '够了。基于你给的**真实事实**，我把这段改成 STAR 完整、且每个数字面试都能讲清来源的版本：' },
          { rewrite: { id: g.id, label: g.label, newBullets: g.rewrite } }]);
        setStage('rewritten');
      } else {
        setMsgs((m) => [...m, { who: 'ai', html: mode === 'free'
          ? '可以。说说你的具体顾虑，我按你目标赛道（量化私募 · 研究）的标准给判断 —— 但不替你编没发生过的经历。'
          : '记下了，这条作为事实写进记忆账本。还要继续补这段，还是去打分看其它缺口？' }]);
      }
      busy.current = false;
    }, 1000);
  }

  function writeBack(idx, rw) {
    onWriteBack(rw.id, rw.newBullets);
    if (onUsedGap) onUsedGap(rw.id);
    setMsgs((m) => m.map((x, i) => i === idx ? { ...x, done: true } : x));
    setTimeout(() => setMsgs((m) => [...m, { who: 'ai', html: `已写回到「${rw.label}」✓ 中栏预览实时刷新，这段的缺口标记会消掉。` }]), 360);
  }

  const empty = msgs.length === 0 && !thinking;
  const hints = mode === 'deep'
    ? ['先去左边「打分」点一段缺口', '或直接说要改哪一段']
    : ['这段写法面试会被问什么？', '量化私募更看重哪些经历？', '帮我看下整体结构'];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--parchment)' }}>
      {/* 深度优化契约：一次只聚焦一段 + 锁定目标赛道(subcat) */}
      {mode === 'deep' && focusLabel && (
        <div style={{ flex: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', borderBottom: '1px solid var(--border)', background: 'var(--terracotta-wash)' }}>
          <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex', flex: 'none' }}>{EICO.target(14)}</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ font: '600 12px var(--font-sans)', color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>聚焦：{focusLabel}</div>
            <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--terracotta-strong)', marginTop: 1 }}>锁定赛道 · {TARGET_TRACK} · 一次只改这一段</div>
          </div>
        </div>
      )}
      <div ref={bodyRef} style={{ flex: 1, overflow: 'auto', padding: '14px 14px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        {empty && (
          <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 250 }}>
            <div style={{ font: '500 13px var(--font-sans)', color: 'var(--olive)', marginBottom: 6 }}>
              {mode === 'deep' ? '反问取证 · 改写有据可依' : '自由问 · 随便聊'}
            </div>
            <div style={{ font: '400 11.5px/1.6 var(--font-sans)', color: 'var(--stone)' }}>
              {mode === 'deep'
                ? '从打分缺口进来，AI 会先反问你真实事实，再做定制改写 —— 不编没问出来的东西。'
                : '问写法、问赛道标准、对齐目标 —— 三能力随时可切。'}
            </div>
          </div>
        )}
        {msgs.map((m, i) => {
          if (m.rewrite) return <RewriteCard key={i} rw={m.rewrite} done={m.done} onWriteBack={() => writeBack(i, m.rewrite)} />;
          return <Bubble key={i} who={m.who}><span dangerouslySetInnerHTML={rich(m.html)} /></Bubble>;
        })}
        {thinking && <ThinkingDots />}
      </div>
      <div style={{ flex: 'none', padding: '10px 14px 14px', borderTop: '1px solid var(--border)', background: 'var(--parchment)' }}>
        {empty && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 9 }}>
            {hints.map((h, i) => (
              <button key={i} onClick={() => setVal(h)} className="hf-pill" style={{ height: 26, cursor: 'pointer' }}>{h}</button>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 9, alignItems: 'center', background: 'var(--library-rail)', borderRadius: 14, padding: '7px 7px 7px 13px', boxShadow: '0 0 0 1px var(--border)' }}>
          <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder={mode === 'deep' ? '把真实情况说给它（数字越具体越好）…' : '问点什么…'}
            style={{ flex: 1, background: 'transparent', border: 0, outline: 0, font: '400 13px var(--font-sans)', color: 'var(--ink)' }} />
          <button onClick={send} className="hf-btn primary" style={{ width: 32, height: 32, padding: 0, borderRadius: 999 }}>{EICO.arrowUp(15)}</button>
        </div>
      </div>
    </div>
  );
}

// ---- 右栏壳：头部 + 三能力切换 (受控：tab/seed/activeGap 提升到 ResumeEditor) ----
function EditorAIPanel({ resume, onWriteBack, tab, setTab, seed, activeGap, onOptimize }) {
  const TABS = [['score', '简历打分'], ['deep', '深度优化'], ['free', '自由问']];
  return (
    <div style={{ borderLeft: '1px solid var(--border)', background: 'var(--ivory)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ padding: '13px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, flex: 'none' }}>
        <span style={{ width: 28, height: 28, flex: 'none', borderRadius: 999, display: 'grid', placeItems: 'center', color: '#faf9f5',
          background: 'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)', boxShadow: '0 4px 12px rgba(201,100,66,0.26)' }}>{EICO.sparkle(15)}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>AI 简历助手 v2</div>
          <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)' }}>诚实打分 · 反问取证 · 写回即刷新</div>
        </div>
      </div>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 6, flex: 'none' }}>
        {TABS.map(([k, t]) => {
          const on = tab === k;
          return (
            <button key={k} onClick={() => setTab(k)} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, height: 30, padding: '0 12px', borderRadius: 999, cursor: 'pointer',
              font: `${on ? 600 : 500} 12px var(--font-sans)`,
              background: on ? 'var(--terracotta)' : 'var(--ivory)', color: on ? 'var(--ivory)' : 'var(--ink-soft)',
              boxShadow: on ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)' }}>
              {t}{k === 'deep' && activeGap && !on && <span style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--terracotta)' }} />}
            </button>
          );
        })}
      </div>
      {tab === 'score' && <ScoreReport onOptimize={onOptimize} activeId={activeGap} />}
      {tab === 'deep' && <ChatThread mode="deep" seed={seed} onWriteBack={onWriteBack} />}
      {tab === 'free' && <ChatThread mode="free" />}
    </div>
  );
}

Object.assign(window, { EditorAIPanel, ED_GAPS });
