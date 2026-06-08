// nlrec-app.jsx — shell + sidebar + topbar + lock modal + state orchestration
/* global React, ReactDOM, window */
const { useState, useEffect, useRef, useMemo } = React;
const { Turn, ThinkingCard, TraceCard, MemoryToast, IntelCard, Composer, Avatar } = window.NLChat;
const { FeedPane } = window.NLFeed;
const D = window.NLData;

// ---- TopBar -------------------------------------------------------------
function TopBar() {
  return (
    <div style={{ height: 54, flex: 'none', background: 'var(--ivory)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', padding: '0 20px', gap: 12 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
        <span style={{ width: 24, height: 24, borderRadius: 7, background: 'var(--deep-dark)', position: 'relative', flex: 'none' }}>
          <span style={{ position: 'absolute', width: 8, height: 8, borderRadius: 999, background: 'var(--terracotta)', top: 8, left: 8, boxShadow: '0 0 0 3px rgba(201,100,66,0.22)' }} />
        </span>
        <span style={{ font: '500 17px var(--font-serif)', letterSpacing: '-0.01em', color: 'var(--ink)' }}>JobRadar</span>
      </span>
      <span style={{ color: 'var(--warm-silver)' }}>/</span>
      <span style={{ font: '500 14px var(--font-sans)', color: 'var(--muted)' }}>推荐工作台</span>
      <span className="hf-pill" style={{ height: 26 }}>NL 推荐 agent</span>
      <span style={{ marginLeft: 'auto' }} />
      <button className="hf-btn ghost sm">简历编辑器</button>
      <div style={{ width: 30, height: 30, borderRadius: 999, background: 'var(--warm-sand)', color: 'var(--charcoal)', display: 'grid', placeItems: 'center', font: '600 13px var(--font-sans)', boxShadow: '0 0 0 1px var(--ring-warm)' }}>陈</div>
    </div>
  );
}

// ---- Sidebar ------------------------------------------------------------
function Sidebar() {
  const sessions = [['量化私募 · 研究方向', '刚刚'], ['券商资管 · 固收', '昨天'], ['央国企 · 战略', '3 天前']];
  return (
    <div style={{ borderRight: '1px solid var(--border)', background: 'var(--library-rail)', padding: 16, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      <button className="hf-btn primary sm" style={{ width: '100%', height: 38 }}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
        新会话
      </button>
      <div className="hf-overline" style={{ marginTop: 4, padding: '0 2px' }}>会话</div>
      {sessions.map(([s, t], i) => (
        <div key={i} style={{ borderRadius: 12, padding: '10px 12px', cursor: 'pointer',
          background: i === 0 ? 'var(--ivory)' : 'transparent',
          boxShadow: i === 0 ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px transparent' }}>
          <div style={{ font: `${i === 0 ? 600 : 500} 13px var(--font-sans)`, color: i === 0 ? 'var(--ink)' : 'var(--ink-soft)' }}>{s}</div>
          <div style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)', marginTop: 3 }}>{t}</div>
        </div>
      ))}
      <div style={{ marginTop: 'auto', borderRadius: 12, padding: '10px 12px', boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed' }}>
        <div style={{ font: '500 11.5px var(--font-sans)', color: 'var(--muted)', marginBottom: 4 }}>简历改写入口</div>
        <div style={{ font: '400 10.5px/1.5 var(--font-sans)', color: 'var(--stone)' }}>已隐藏 · 组件不删（只加不删）→ 子项④ 物理拆分</div>
      </div>
    </div>
  );
}

// ---- Lock modal ---------------------------------------------------------
function LockModal({ wq, onCancel, onConfirm }) {
  const writes = [...wq.add, ...(wq.only ? [wq.only] : [])];
  return (
    <div style={{ position: 'absolute', inset: 0, background: 'rgba(20,20,19,0.55)', display: 'grid', placeItems: 'center', zIndex: 40, padding: 24 }}>
      <div className="hf-slide" style={{ width: 420, maxWidth: '100%', background: 'var(--ivory)', borderRadius: 18, padding: 22, boxShadow: 'var(--sh-paper)' }}>
        <div style={{ font: '500 22px var(--font-serif)', color: 'var(--ink)', marginBottom: 8, letterSpacing: '-0.02em' }}>锁定为主方向？</div>
        <div style={{ font: '400 13px/1.65 var(--font-sans)', color: 'var(--muted)', marginBottom: 16 }}>
          把当前工作查询提交成 <b style={{ color: 'var(--ink-soft)' }}>confirmed 赛道</b>。这是 WorkingQuery 唯一会「落」成 confirmed 的入口——显式、你主动。
        </div>
        <div style={{ borderRadius: 13, padding: 14, background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border)', marginBottom: 16 }}>
          <div className="hf-overline" style={{ marginBottom: 9 }}>将写入 confirmed</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            {writes.length ? writes.map((w) => (
              <span key={w} className="hf-pill terra" style={{ height: 28, font: '600 12.5px var(--font-sans)' }}>{w}</span>
            )) : <span style={{ font: '400 12px var(--font-sans)', color: 'var(--stone)' }}>当前工作查询（投研 · 券商资管）</span>}
            <span style={{ font: '400 11.5px var(--font-mono)', color: 'var(--stone)', alignSelf: 'center' }}>→ preferred_tracks</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, marginBottom: 18 }}>
          <svg width="15" height="15" viewBox="0 0 14 14" style={{ marginTop: 1, flex: 'none' }}><path d="M2 7 L6 11 L12 3" fill="none" stroke="var(--muted)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--muted)' }}>梯队骨架（子项②）据此重塑 · 走现有 <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>PUT /preferences</span> 通道</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="hf-btn ghost" style={{ flex: 1 }} onClick={onCancel}>再想想</button>
          <button className="hf-btn primary" style={{ flex: 1.4 }} onClick={onConfirm}>锁定为主方向</button>
        </div>
      </div>
    </div>
  );
}

// ---- App ----------------------------------------------------------------
function App() {
  const [msgs, setMsgs] = useState([
    { t: 'turn', who: 'ai', html: '先按你的确认赛道（<b>投研 · 券商资管</b>）+ 平时偏好给了第一版 Top 列表。想换方向、锁某家、或排除什么，直接说。' },
  ]);
  const [thinking, setThinking] = useState(false);
  const [wq, setWq] = useState({ seed: ['投研', '券商资管'], add: [], exclude: [], sort: 'match', only: null, companies: [] });
  const [deepened, setDeepened] = useState(new Set());
  const [deepening, setDeepening] = useState(null);
  const [used, setUsed] = useState(new Set());
  const [lockOpen, setLockOpen] = useState(false);
  const [locked, setLocked] = useState(false);
  const busy = useRef(false);
  const bodyRef = useRef(null);

  const feed = useMemo(() => D.rankFeed(wq), [wq]);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, thinking]);

  const push = (m) => setMsgs((cur) => [...cur, m]);

  function runStep(step, userText) {
    if (busy.current) return;
    busy.current = true;
    push({ t: 'turn', who: 'me', html: userText || step.user });
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      push({ t: 'trace', trace: step.trace });
      push({ t: 'turn', who: 'ai', html: step.reply });
      setWq((prev) => step.apply(prev));
      if (step.memory) setTimeout(() => push({ t: 'memory', text: step.memory }), 280);
      if (step.intel) setTimeout(() => push({ t: 'intel', id: step.intel }), 200);
      setUsed((u) => new Set(u).add(step.key));
      busy.current = false;
    }, 1150);
  }

  function fallback(userText) {
    if (busy.current) return;
    busy.current = true;
    push({ t: 'turn', who: 'me', html: userText });
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      push({ t: 'turn', who: 'ai', html: '没太听懂，换个说法？比如「多来点固收」「排除国企」「只看头部券商资管」或「讲讲某家」。feed 没动。' });
      busy.current = false;
    }, 900);
  }

  function onSend(text) {
    const step = D.SCRIPT.find((s) => !used.has(s.key) && s.match(text));
    if (step) runStep(step, text);
    else fallback(text);
  }

  function onDeepen(job) {
    if (deepening || deepened.has(job.id)) return;
    setDeepening(job.id);
    setTimeout(() => {
      setDeepened((s) => new Set(s).add(job.id));
      setDeepening(null);
    }, 1500);
  }

  function onIntel(job) {
    if (busy.current) return;
    if (job.intel) {
      const step = D.SCRIPT.find((s) => s.key === 'intel');
      busy.current = true;
      push({ t: 'turn', who: 'me', html: `讲讲${job.co}` });
      setThinking(true);
      setTimeout(() => {
        setThinking(false);
        push({ t: 'trace', trace: step.trace });
        push({ t: 'turn', who: 'ai', html: `${job.co}的情报卡给你拉出来了 →` });
        push({ t: 'intel', id: job.intel });
        setUsed((u) => new Set(u).add('intel'));
        busy.current = false;
      }, 1000);
    } else {
      busy.current = true;
      push({ t: 'turn', who: 'me', html: `讲讲${job.co}` });
      setThinking(true);
      setTimeout(() => {
        setThinking(false);
        push({ t: 'turn', who: 'ai', html: `${job.co}暂无结构化情报。按公开信息：该方向有在招、梯队中上；要更细可点「深挖」补 4-anchor 理由。` });
        busy.current = false;
      }, 900);
    }
  }

  function confirmLock() {
    setLocked(true);
    setLockOpen(false);
    push({ t: 'turn', who: 'ai', html: '已锁定为主方向 ✓ 当前工作查询写入 confirmed 赛道，梯队骨架（子项②）会据此重塑。' });
    setTimeout(() => push({ t: 'memory', text: 'L2 → PUT /preferences · confirmed 赛道已更新' }), 260);
  }

  const chips = D.SCRIPT.filter((s) => !used.has(s.key)).map((s) => ({ key: s.key, label: s.label, run: s }));

  return (
    <div className="hf" style={{ height: '100vh', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <TopBar />
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '208px minmax(340px,1fr) minmax(372px,440px)', minHeight: 0 }}>
        <Sidebar />

        {/* CENTER — NL 推荐对话 */}
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--parchment)', borderRight: '1px solid var(--border)' }}>
          <div style={{ padding: '13px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 11, background: 'var(--ivory)' }}>
            <Avatar size={32} />
            <div style={{ flex: 1 }}>
              <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>推荐 agent</div>
              <div style={{ font: '400 11.5px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>说人话换方向 · 秒级重排，不动确认赛道</div>
            </div>
            <span className="hf-pill" style={{ height: 28, whiteSpace: 'nowrap' }}><span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--emerald)' }} />快路 · 规则排</span>
          </div>

          <div ref={bodyRef} style={{ flex: 1, overflow: 'auto', padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {msgs.map((m, i) => {
              if (m.t === 'turn') return <Turn key={i} who={m.who}><span dangerouslySetInnerHTML={{ __html: m.html }} /></Turn>;
              if (m.t === 'trace') return <TraceCard key={i} trace={m.trace} />;
              if (m.t === 'memory') return <MemoryToast key={i} text={m.text} />;
              if (m.t === 'intel') return <IntelCard key={i} id={m.id} />;
              return null;
            })}
            {thinking && <ThinkingCard />}
          </div>

          <Composer chips={chips} placeholder="只看头部券商资管 / 讲讲中信资管 / 就按这个锁定…"
            onChip={(c) => runStep(c.run)} onSend={onSend} />
        </div>

        {/* RIGHT — feed */}
        <FeedPane feed={feed} wq={wq} deepened={deepened} deepening={deepening}
          onDeepen={onDeepen} onIntel={onIntel} locked={locked}
          onLock={() => setLockOpen(true)}
          onRemoveAdd={(s) => setWq((p) => ({ ...p, add: p.add.filter((x) => x !== s) }))}
          onClearOnly={() => setWq((p) => ({ ...p, only: null }))} />
      </div>

      {lockOpen && <LockModal wq={wq} onCancel={() => setLockOpen(false)} onConfirm={confirmLock} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
