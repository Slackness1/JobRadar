// hub/hub-app.jsx — Hub 外壳 orchestrator: sidebar + chat 主轴 + 会变形的画布槽 + Hub 落地态
/* global React, ReactDOM, window */
const { useState: useHA, useRef: useHARef, useEffect: useHAEffect, useMemo: useHAMemo } = React;
const { Turn, ThinkingCard, TraceCard, MemoryToast, IntelCard, Composer, Avatar, Spinner } = window.NLChat;
const { DeepThinkCard } = window.DeepThink;
const { FeedPane } = window.NLFeed;
const { HubSidebar, SkeletonView, ProfileView, ResumeView } = window;
const ND = window.NLData;
const ICO = window.I;

// 铁律：每个模块 = 对话里的一次技能执行。
//   AI 应一声 → 路径节点(4字一步) + 思考时间线 → 落结果卡 → 学生主动点开才进视图。
//   差异只在终点视图形态：feed/skeleton = 侧面板；resume = 全编辑页；interview = 全屏间。
const SKILL_META = {
  feed: {
    say: '好，我按你确认的赛道把<b>职位推荐</b>跑一遍。',
    nodes: ['锁定赛道', '检索岗位', '三维打分', '排出推荐'],
    result: () => ({ title: '岗位匹配已就绪', body: '按 <b>投研 · 券商资管</b> 评估 40 个在招、匹配 39 个，已排出第一版 Top。', cta: '查看岗位' }),
  },
  skeleton: {
    say: '好，我把<b>梯队骨架</b>拉出来分一下档。',
    nodes: ['拉取公司', '梯队分档', '背景定档', '铺出全景'],
    result: () => ({ title: '梯队全景已铺好', body: '二级买方 · 基本面 共 <b>18</b> 家 GT 公司，按 头部 / 主力 / 腰部 分了档，匹配档已高亮。', cta: '查看全景' }),
  },
  resume: {
    say: '好，我给你的<b>简历</b>做一次诚实打分 + 缺口定位。',
    nodes: ['解析简历', '诚实打分', '定位缺口', '给出建议'],
    result: () => ({ title: '简历打分完成', body: '现状 <b>72</b> · 潜力 80–85，3 段经历有可补的缺口，已定位到逐段入口。', cta: '查看打分报告' }),
  },
  interview: {
    say: '好，我按你的目标赛道备一场<b>模拟面试</b>。',
    nodes: ['调取记忆', '匹配考官', '备好题库', '进入面试间'],
    result: () => ({ title: '面试间准备好了', body: '按 <b>投研 · 券商资管</b> 配了考官与题库，记忆延续同一会话；进入后全屏，结束自动回 Hub。', cta: '进入面试' }),
  },
};
// 个人档案不是“跑技能”——是你自己的档案，点开直接看（确认/纠正闭环）
const PROFILE_SAY = '帮你打开<b>个人档案</b> —— 确认信息在上，AI 推断待确认在下，确认/否掉一眼可点。';
// 激活某模块后，composer 上方的引导：点了模块只是"激活"，说一句话才"激发交付物"
const ARM_HINT = {
  feed:      { label: '职位推荐', tip: '说一句就开始 —— 例如「给我推荐一下岗位」', eg: '给我推荐一下岗位' },
  skeleton:  { label: '梯队骨架', tip: '说一句就开始 —— 例如「看看券商资管的梯队」', eg: '看看券商资管的梯队' },
  resume:    { label: '简历优化', tip: '说一句就开始 —— 例如「帮我的简历打个分」', eg: '帮我的简历打个分' },
  interview: { label: '模拟面试', tip: '说一句就开始 —— 例如「按券商资管面我一场」', eg: '按券商资管面我一场' },
};

// ============================================================
// 跑技能卡 (路径节点 + 思考时间线) — DeepHire 式"对话内跑技能"
//   4 字一步逐步亮起：当前步转 spinner，已完成 ✓，未到的灰。跑完回调落结果卡。
// ============================================================
function SkillRunCard({ nodes, onComplete }) {
  const [step, setStep] = useHA(0);          // 当前正在跑的下标；=== nodes.length 表示全部完成
  const fired = useHARef(false);
  useHAEffect(() => {
    const per = 720;
    const timers = nodes.map((_, i) => setTimeout(() => setStep(i + 1), per * (i + 1)));
    const end = setTimeout(() => { if (!fired.current) { fired.current = true; onComplete && onComplete(); } }, per * nodes.length + 380);
    return () => { timers.forEach(clearTimeout); clearTimeout(end); };
  }, []);
  const running = step < nodes.length;
  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
      <Avatar />
      <div style={{ position: 'relative', flex: 1, maxWidth: '82%', borderRadius: 15, borderTopLeftRadius: 5, background: 'var(--ivory)', boxShadow: '0 0 0 1px var(--border)', overflow: 'hidden', padding: '12px 15px' }}>
        {running && <div className="ds-border-beam" />}
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {running ? <Spinner /> : <span style={{ color: 'var(--emerald)', font: '600 14px var(--font-mono)', minWidth: '1ch', textAlign: 'center' }}>✓</span>}
            <span style={{ font: '600 11px var(--font-sans)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--stone)' }}>{running ? '正在跑技能' : '技能完成'}</span>
            <span className="hf-mono-sm" style={{ marginLeft: 'auto', color: 'var(--stone)', fontSize: 11 }}>{Math.min(step, nodes.length)} / {nodes.length} 步</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {nodes.map((n, i) => {
              const done = i < step, active = i === step && running;
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '5px 0' }}>
                  <span style={{ width: 16, flex: 'none', display: 'inline-flex', justifyContent: 'center' }}>
                    {done ? <span style={{ color: 'var(--emerald)', font: '600 13px var(--font-mono)' }}>✓</span>
                          : active ? <Spinner />
                          : <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--border-strong)' }} />}
                  </span>
                  <span style={{ font: `${active ? 600 : 500} 13px var(--font-sans)`, color: done ? 'var(--ink-soft)' : active ? 'var(--ink)' : 'var(--stone)', opacity: done || active ? 1 : 0.55 }}>{n}</span>
                  {i < nodes.length - 1 && <span style={{ flex: 1, height: 1, background: done ? 'var(--terracotta-wash)' : 'transparent' }} />}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// 结果卡 — 技能跑完落在对话里的"产出"。点 CTA 才进入那个模块的视图（永不瞬移）。
function ResultCard({ data, opened, onOpen }) {
  return (
    <div className="hf-slide" style={{ marginLeft: 37, marginTop: 2, background: 'var(--ivory)', borderRadius: 16, padding: '14px 16px', boxShadow: 'var(--sh-ring)', maxWidth: 462 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
        <span style={{ color: 'var(--emerald)', display: 'inline-flex' }}>{ICO.check(15)}</span>
        <span style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>{data.title}</span>
      </div>
      <div style={{ font: '400 12.5px/1.6 var(--font-sans)', color: 'var(--ink-soft)', marginBottom: 12 }} dangerouslySetInnerHTML={{ __html: data.body }} />
      <button className={opened ? 'hf-btn sand sm' : 'hf-btn primary sm'} onClick={onOpen} style={{ width: '100%', gap: 6 }}>
        {opened ? '已打开 · 再看一次' : data.cta} {ICO.arrowRight(14)}
      </button>
    </div>
  );
}

// skill chips above the composer (壳内切视图)
function SkillBar({ active, onPick }) {
  const chips = [
    { key: 'feed',     label: '职位推荐', icon: ICO.radar(13) },
    { key: 'skeleton', label: '梯队骨架', icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg> },
    { key: 'resume',   label: '简历优化', icon: ICO.file(13) },
  ];
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {chips.map((c) => {
        const on = active === c.key;
        return (
          <button key={c.key} onClick={() => !c.disabled && onPick(c.key)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 32, padding: '0 13px', borderRadius: 999, cursor: c.disabled ? 'default' : 'pointer',
              font: `${on ? 600 : 500} 12.5px var(--font-sans)`,
              background: on ? 'var(--terracotta)' : c.disabled ? 'transparent' : 'var(--ivory)',
              color: on ? 'var(--ivory)' : c.disabled ? 'var(--warm-silver)' : 'var(--ink-soft)',
              boxShadow: on ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)' }}>
            {c.icon}{c.label}{c.disabled && <span style={{ fontSize: 9.5, marginLeft: 1 }}>· 占位</span>}
          </button>
        );
      })}
    </div>
  );
}

// ============================================================
// Chat axis (对话主轴) — reuses NLChat turns/thinking/trace/intel
// ============================================================
function ChatAxis({ msgs, thinking, bodyRef, active, armed, onPick, chips, onChip, onSend, centered, greeting, onSkillComplete, onOpenView }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1, background: 'var(--parchment)' }}>
      {centered ? (
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 40px' }}>
          {greeting}
        </div>
      ) : (
        <div ref={bodyRef} className="hub-thread-in" style={{ flex: 1, overflow: 'auto', padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {msgs.map((m, i) => {
            if (m.t === 'turn') return <Turn key={i} who={m.who}><span dangerouslySetInnerHTML={{ __html: m.html }} /></Turn>;
            if (m.t === 'skillrun') return <DeepThinkCard key={i} module={m.module} nodes={m.nodes} onComplete={() => onSkillComplete(m.module)} />;
            if (m.t === 'result') return <ResultCard key={i} data={m.data} opened={active === m.module} onOpen={() => onOpenView(m.module)} />;
            if (m.t === 'trace') return <TraceCard key={i} trace={m.trace} />;
            if (m.t === 'memory') return <MemoryToast key={i} text={m.text} />;
            if (m.t === 'intel') return <IntelCard key={i} id={m.id} />;
            return null;
          })}
          {thinking && <ThinkingCard />}
        </div>
      )}

      {/* composer + skill bar — hidden in landing (greeting carries its own input) */}
      {!centered && (
      <div className="hub-dock" style={{ flex: 'none', padding: '12px 16px 16px', borderTop: '1px solid var(--border)', background: 'var(--parchment)', display: 'flex', flexDirection: 'column', gap: 11 }}>
        {armed && ARM_HINT[armed] && (
          <div className="hf-slide" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', borderRadius: 11, background: 'var(--terracotta-wash)', boxShadow: '0 0 0 1px #eccfb6' }}>
            <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--terracotta)', flex: 'none' }} />
            <span style={{ font: '500 12px var(--font-sans)', color: 'var(--terracotta-strong)' }}>已激活「{ARM_HINT[armed].label}」· {ARM_HINT[armed].tip}</span>
          </div>
        )}
        <SkillBar active={armed || active} onPick={onPick} />
        <ComposerInput onSend={onSend} hints={chips.map((c) => c.label)} armedEg={armed && ARM_HINT[armed] ? ARM_HINT[armed].eg : null} />
      </div>
      )}
    </div>
  );
}

// rotating typewriter hint used as the composer placeholder — cycles through suggestions,
// types a phrase out, holds, deletes, advances. Pauses while the user is typing/focused.
function useTypewriterHint(hints, paused) {
  const [text, setText] = useHA('');
  const st = useHARef({ i: 0, sub: 0, dir: 1 });
  useHAEffect(() => {
    if (paused || !hints || hints.length === 0) return;
    let timer;
    const tick = () => {
      const s = st.current;
      const full = hints[s.i % hints.length] || '';
      if (s.dir === 1) {
        s.sub += 1;
        setText(full.slice(0, s.sub));
        if (s.sub >= full.length) { s.dir = 0; timer = setTimeout(tick, 1500); return; }
        timer = setTimeout(tick, 58 + Math.random() * 46);
      } else {
        s.sub -= 1;
        setText(full.slice(0, s.sub));
        if (s.sub <= 0) { s.dir = 1; s.i += 1; timer = setTimeout(tick, 320); return; }
        timer = setTimeout(tick, 26);
      }
    };
    timer = setTimeout(tick, 460);
    return () => clearTimeout(timer);
  }, [paused, hints && hints.join('|')]);
  return text;
}

function ComposerInput({ onSend, hints, armedEg }) {
  const [val, setVal] = useHA('');
  const [focused, setFocused] = useHA(false);
  const typed = useTypewriterHint(hints, focused || val.length > 0 || !!armedEg);
  const send = () => { const v = val.trim(); if (!v) return; onSend(v); setVal(''); };
  // 激活了模块 → 直接给出该模块的示例话术；否则走打字机提示
  const ph = armedEg
    ? '例如：' + armedEg
    : hints && hints.length > 0
      ? (typed ? typed + '\u2009▍' : '\u2009▍')
      : '说人话换方向、锁某家、或排除什么…';
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', background: 'var(--library-rail)', borderRadius: 16, padding: '8px 8px 8px 14px', boxShadow: '0 0 0 1px var(--border)' }}>
      <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        placeholder={ph} className="hub-composer-input" style={{ flex: 1, background: 'transparent', border: 0, outline: 0, font: '400 14px var(--font-sans)', color: 'var(--ink)' }} />
      <button onClick={send} className="hf-btn primary" style={{ width: 36, height: 36, padding: 0, borderRadius: 999 }} title="发送">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </button>
    </div>
  );
}

// ============================================================
// Canvas slot (会变形的画布槽)
// ============================================================
function CanvasSlot({ active, feedProps, onExpandEditor, skelProps, onClose }) {
  if (active === 'none') return null;
  const W = active === 'feed' ? 448 : active === 'skeleton' ? 436 : active === 'resume' ? 500 : 460;
  return (
    <div style={{ width: W, flex: 'none', minWidth: 0, display: 'flex', flexDirection: 'column' }} className="hf-slide">
      {active === 'feed' && <FeedPane {...feedProps} onClose={onClose} />}
      {active === 'skeleton' && <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, borderLeft: '1px solid var(--border)', background: 'var(--parchment)' }}><SkeletonView {...skelProps} onClose={onClose} /></div>}
      {active === 'profile' && <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, borderLeft: '1px solid var(--border)', background: 'var(--parchment)' }}><ProfileView onClose={onClose} /></div>}
      {active === 'resume' && <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, borderLeft: '1px solid var(--border)', background: 'var(--parchment)' }}><ResumeView onExpand={onExpandEditor} onClose={onClose} /></div>}
    </div>
  );
}

// empty slot rail (Hub 落地态)
function EmptySlotRail() {
  return (
    <div style={{ width: 64, flex: 'none', borderLeft: '1px dashed var(--border-strong)', background: 'var(--parchment)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ writingMode: 'vertical-rl', font: '500 10.5px var(--font-sans)', letterSpacing: '0.14em', color: 'var(--warm-silver)', textTransform: 'uppercase' }}>画布槽 · 空</span>
    </div>
  );
}

// ============================================================
// Landing greeting (对话居中)
// ============================================================
function LandingGreeting({ selected, onPick, onSend }) {
  const hintFor = { feed: '已激活「职位推荐」· 说一句就给你排第一版岗位', skeleton: '已激活「梯队骨架」· 说一句就铺开档次全景', resume: '已激活「简历优化」· 说一句就开始打分诊断' };
  return (
    <div style={{ width: '100%', maxWidth: 580 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ font: '500 28px/1.3 var(--font-serif)', color: 'var(--ink)', letterSpacing: '-0.02em' }}>晚上好，陈思远。今天想看哪个方向？</div>
      </div>
      <div style={{ marginTop: 22 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: 'var(--library-rail)', borderRadius: 16, padding: '10px 10px 10px 16px', boxShadow: selected ? '0 0 0 1px var(--terracotta-ring)' : '0 0 0 1px var(--border)', transition: 'box-shadow .2s' }}>
          <LandingInput onSend={onSend} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12, minHeight: 32 }}>
          <SkillBar active={selected || 'none'} onPick={onPick} />
          {selected && hintFor[selected] && <span style={{ font: '400 11.5px var(--font-sans)', color: 'var(--terracotta-strong)', whiteSpace: 'nowrap' }}>{hintFor[selected]}</span>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 18 }}>
        {[['feed', ICO.radar(16), '职位推荐', '按确认赛道给第一版 Top，再快增强'],
          ['resume', ICO.file(16), '简历优化', '诚实打分 + 反问取证，写回实时刷新']].map(([k, ic, t, d, dis]) => {
          const on = selected === k;
          return (
          <button key={k} onClick={() => !dis && onPick(k)} style={{ flex: 1, textAlign: 'left', borderRadius: 14, padding: '14px 15px', cursor: dis ? 'default' : 'pointer',
            background: dis ? 'transparent' : on ? 'var(--terracotta-wash)' : 'var(--ivory)', boxShadow: dis ? '0 0 0 1px var(--border-warm)' : on ? '0 0 0 1.5px var(--terracotta)' : 'var(--sh-ring)', opacity: dis ? 0.72 : 1, transition: 'box-shadow .15s, background .15s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ color: dis ? 'var(--warm-silver)' : 'var(--terracotta-strong)', display: 'inline-flex' }}>{ic}</span>
              <span style={{ font: '600 13.5px var(--font-sans)', color: dis ? 'var(--olive)' : 'var(--ink)' }}>{t}</span>
              {dis ? <span style={{ marginLeft: 'auto', font: '500 9.5px var(--font-sans)', color: 'var(--warm-silver)', boxShadow: '0 0 0 1px var(--border-warm)', borderRadius: 999, padding: '1px 7px' }}>占位</span>
                   : on ? <span style={{ marginLeft: 'auto', font: '600 9.5px var(--font-sans)', color: '#fff', background: 'var(--terracotta)', borderRadius: 999, padding: '2px 8px' }}>已激活</span>
                   : <span style={{ marginLeft: 'auto', color: 'var(--stone)', display: 'inline-flex' }}>{ICO.arrowRight(14)}</span>}
            </div>
            <div style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--stone)' }}>{d}</div>
          </button>
          );
        })}
      </div>
    </div>
  );
}
function LandingInput({ onSend }) {
  const [val, setVal] = useHA('');
  const [focused, setFocused] = useHA(false);
  const HINTS = ['多来点固收', '看看券商资管的梯队', '一直不考虑国企', '只看头部，按薪资排', '讲讲中信资管', '帮我看下个人档案'];
  const typed = useTypewriterHint(HINTS, focused || val.length > 0);
  const send = () => { const v = val.trim(); if (!v) return; onSend(v); setVal(''); };
  const ph = '例如：' + (typed ? typed + '\u2009▍' : '\u2009▍');
  return (
    <>
      <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        placeholder={ph} className="hub-composer-input"
        style={{ flex: 1, background: 'transparent', border: 0, outline: 0, font: '400 14.5px var(--font-sans)', color: 'var(--ink)' }} />
      <button onClick={send} className="hf-btn primary" style={{ width: 38, height: 38, padding: 0, borderRadius: 999 }}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
      </button>
    </>
  );
}

// ============================================================
// HubApp
// ============================================================
function HubApp() {
  const [collapsed, setCollapsed] = useHA(false);
  const [active, setActive] = useHA('none');          // none | feed | skeleton | resume | profile —— 当前打开的面板
  const [armed, setArmed] = useHA(null);               // 被「激活」但还没说话触发的模块（点 chip/nav 只激活）
  const [started, setStarted] = useHA(false);          // left landing?
  const [msgs, setMsgs] = useHA([]);
  const [thinking, setThinking] = useHA(false);
  const [wq, setWq] = useHA({ seed: ['投研', '券商资管'], add: [], exclude: [], sort: 'match', only: null, companies: [] });
  const [deepened, setDeepened] = useHA(() => new Set());
  const [deepening, setDeepening] = useHA(null);
  const [used, setUsed] = useHA(() => new Set());
  const [locked, setLocked] = useHA(false);
  const [editorOpen, setEditorOpen] = useHA(false);
  const busy = useHARef(false);
  const bodyRef = useHARef(null);

  const feed = useHAMemo(() => ND.rankFeed(wq), [wq]);
  const landing = !started;

  useHAEffect(() => { const el = bodyRef.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, thinking]);

  const push = (m) => setMsgs((cur) => [...cur, m]);

  // ---- 统一进入：每个模块 = 对话里跑一次技能 → 落结果卡 → 点开才进视图 ----
  function runSkill(key) {
    if (busy.current) return;
    if (key === 'profile') {                 // 个人档案不是"跑技能"，是你自己的档案，直接看
      setStarted(true);
      push({ t: 'turn', who: 'ai', html: PROFILE_SAY });
      setActive('profile');
      return;
    }
    const meta = SKILL_META[key];
    if (!meta) return;
    busy.current = true;
    setStarted(true);
    setActive('none');                       // 收回全宽对话看它"想" —— 永不瞬移进面板
    push({ t: 'turn', who: 'ai', html: meta.say });
    push({ t: 'skillrun', module: key, nodes: meta.nodes });
    // busy is cleared in onSkillComplete when the deep-think card finishes;
    // this is just a safety fallback (card total ≈ 5s).
    setTimeout(() => { busy.current = false; }, 6800);
  }

  // 技能跑完 → 落结果卡（产出，不是落点）
  function onSkillComplete(key) {
    busy.current = false;
    const meta = SKILL_META[key];
    if (!meta) return;
    push({ t: 'result', module: key, data: meta.result(wq) });
  }

  // 点结果卡 CTA → 才进入那个模块的视图：feed/skeleton/resume = 侧面板 · interview = 全屏间
  //   简历：先进「打分报告」面板,其右上角「展开编辑器」才进全屏编辑页（不跳过打分这步）
  function openView(key) {
    if (key === 'interview') { window.location.href = encodeURI('Mock Interview · AI Interviewer.html'); return; }
    setActive(key);
  }
  function closeView() { setActive('none'); }     // 关掉 → 回到全宽对话

  // ---- 激活语义：点 chip / 侧边栏 / 落地卡 = 只「激活」模块（高亮 + 引导），说一句话才「激发交付物」 ----
  function armModule(key) {
    if (key === 'profile') { runSkill('profile'); return; }   // 档案不是交付物，点开直接看
    setArmed((cur) => (cur === key ? null : key));            // 再点一次取消激活
  }

  function onNav(item) { armModule(item.key); }     // 侧边栏 / chip / 落地卡 统一：先激活，再打字触发

  function onNew() { setStarted(false); setActive('none'); setArmed(null); setMsgs([]); setUsed(new Set()); setWq({ seed: ['投研', '券商资管'], add: [], exclude: [], sort: 'match', only: null, companies: [] }); }

  // ---- scripted NL turns (reused from nlrec) ----
  function runStep(step, userText) {
    if (busy.current) return;
    busy.current = true;
    setStarted(true);
    push({ t: 'turn', who: 'me', html: userText || step.user });
    // queries about feed/skeleton imply that module
    if (step.key === 'intel') { /* stays in chat */ }
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      push({ t: 'trace', trace: step.trace });
      push({ t: 'turn', who: 'ai', html: step.reply });
      setWq((prev) => step.apply(prev));
      if (step.memory) setTimeout(() => push({ t: 'memory', text: step.memory }), 280);
      if (step.intel) setTimeout(() => push({ t: 'intel', id: step.intel }), 200);
      setUsed((u) => new Set(u).add(step.key));
      // 不瞬移进面板：feed 开着 → 实时改右栏；没开 → 落一张结果卡让学生点开
      if (step.key !== 'intel' && active !== 'feed') {
        setTimeout(() => push({ t: 'result', module: 'feed', data: { title: '岗位匹配已更新', body: '按你刚说的调了筛选，岗位匹配重排好了。', cta: '查看岗位' } }), 380);
      }
      busy.current = false;
    }, 1100);
  }
  function fallback(text) {
    if (busy.current) return;
    // 模块意图 → 走统一的"对话内跑技能"路径；都不命中 → 轻提示
    let target;
    if (/梯队|骨架|档次|全景/.test(text)) target = 'skeleton';
    else if (/档案|我的资料|画像|记得/.test(text)) target = 'profile';
    else if (/简历|改写|打分|优化/.test(text)) target = 'resume';
    else if (/面试|模拟/.test(text)) target = 'interview';
    else if (/推荐|岗位|职位|机会|看看|来点|多来|有什么/.test(text)) target = 'feed';
    else target = null;

    push({ t: 'turn', who: 'me', html: text });
    if (target) { runSkill(target); return; }

    busy.current = true;
    setStarted(true);
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      push({ t: 'turn', who: 'ai', html: '没太听懂，换个说法？比如「推荐岗位」「看看券商资管的梯队」「给简历打个分」或「讲讲某家」。' });
      busy.current = false;
    }, 900);
  }
  function onSend(text) {
    // 有激活的模块 → 这句话就是「激发交付物」：落学生发言 + 跑该模块的技能
    if (armed) {
      const key = armed;
      setArmed(null);
      push({ t: 'turn', who: 'me', html: text });
      runSkill(key);
      return;
    }
    // 没激活：走脚本微调 或 NL 意图路由（也能直接打字触发模块，不强制先点 chip）
    const step = ND.SCRIPT.find((s) => !used.has(s.key) && s.match(text));
    if (step) runStep(step, text);
    else fallback(text);
  }
  function onDeepen(job) {
    if (deepening || deepened.has(job.id)) return;
    setDeepening(job.id);
    setTimeout(() => { setDeepened((s) => new Set(s).add(job.id)); setDeepening(null); }, 1400);
  }
  function onIntel(job) {
    if (busy.current) return;
    busy.current = true;
    push({ t: 'turn', who: 'me', html: `讲讲${job.co}` });
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      if (job.intel) {
        const step = ND.SCRIPT.find((s) => s.key === 'intel');
        push({ t: 'trace', trace: step.trace });
        push({ t: 'turn', who: 'ai', html: `${job.co}的情报卡给你拉出来了 →` });
        push({ t: 'intel', id: job.intel });
        setUsed((u) => new Set(u).add('intel'));
      } else {
        push({ t: 'turn', who: 'ai', html: `${job.co}暂无结构化情报。按公开信息：该方向有在招、梯队中上；要更细可点「深挖」补 4-anchor 理由。` });
      }
      busy.current = false;
    }, 1000);
  }
  // ---- 梯队骨架卡：情报 / 定制 回流到对话主轴 ----
  function skelIntel(id) {
    if (busy.current) return; busy.current = true;
    const c = window.getCompany(id) || {}; const it = c.intel;
    push({ t: 'turn', who: 'me', html: `讲讲${c.name}` });
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      if (it) {
        push({ t: 'trace', trace: ['检索同辈情报', '聚合门槛 / 前景 / 待遇', `命中 ${c.nInsights} 条`] });
        const comp = it.compensation || (it.compEmptyNote || '同龄人讨论中暂未提及·不编数字');
        push({ t: 'turn', who: 'ai', html: `<b>${c.name}</b>（${c.industry} · 匹配 ${c.score}）。门槛：${it.requirements.slice(0, 3).join(' / ')}；待遇：${comp}；前景「${it.prospects || '—'}」。共 ${c.nInsights} 条同辈情报、${(it.questions || []).length} 道真题。` });
      } else {
        push({ t: 'turn', who: 'ai', html: `<b>${c.name}</b> 暂无结构化同辈情报 —— 这家是按赛道梯队补全的骨架公司，等有同学讨论会自动汇入。` });
      }
      busy.current = false;
    }, 1000);
  }
  function skelCoach(id) {
    if (busy.current) return; busy.current = true;
    const c = window.getCompany(id) || {};
    push({ t: 'turn', who: 'me', html: `针对${c.name}定制深挖` });
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      push({ t: 'turn', who: 'ai', html: `好，进入对 <b>${c.name}</b> 的定制：我会按它的门槛与真题反问你、对齐简历重点。要不要现在开一场针对它的模拟面试？` });
      busy.current = false;
    }, 1000);
  }

  function confirmLock() {
    setLocked(true);
    push({ t: 'turn', who: 'ai', html: '已锁定为主方向 ✓ 当前工作查询写入 confirmed 赛道，梯队骨架会据此重塑。' });
    setTimeout(() => push({ t: 'memory', text: 'L3 → PUT /preferences · confirmed 赛道已更新' }), 260);
  }

  const chips = ND.SCRIPT.filter((s) => !used.has(s.key)).map((s) => ({ key: s.key, label: s.label, run: s }));
  const feedProps = { feed, wq, deepened, deepening, onDeepen, onIntel, locked, onLock: confirmLock,
    onRemoveAdd: (s) => setWq((p) => ({ ...p, add: p.add.filter((x) => x !== s) })),
    onClearOnly: () => setWq((p) => ({ ...p, only: null })) };

  return (
    <div className="hf" style={{ height: '100vh', display: 'flex', overflow: 'hidden', background: 'var(--parchment)' }}>
      <HubSidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} active={armed || (active === 'none' ? null : active)} onNav={onNav} onNew={onNew} />
      <ChatAxis
        msgs={msgs} thinking={thinking} bodyRef={bodyRef}
        active={active === 'none' ? null : active}
        armed={armed}
        onPick={armModule}
        chips={chips} onChip={(c) => runStep(c.run)} onSend={onSend}
        onSkillComplete={onSkillComplete} onOpenView={openView}
        centered={landing}
        greeting={<LandingGreeting selected={armed} onPick={armModule} onSend={onSend} />}
      />
      {landing ? <EmptySlotRail /> : <CanvasSlot active={active} feedProps={feedProps} onExpandEditor={() => setEditorOpen(true)} skelProps={{ onIntel: skelIntel, onCoach: skelCoach }} onClose={closeView} />}
      {editorOpen && <window.ResumeEditor onClose={() => setEditorOpen(false)} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<HubApp />);
