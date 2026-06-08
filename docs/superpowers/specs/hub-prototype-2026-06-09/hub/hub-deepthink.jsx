// hub/hub-deepthink.jsx — embeddable "深度思考" card for the 统一对话 Hub.
// Replaces the old border-beam SkillRunCard. Runs live on real timers:
//   我的理解 (确认赛道 + 记忆, 先说清我懂你要什么)  →  思考过程 (4 阶段连接线轨迹,
//   每步可展开 input/output)  →  自动折叠,点开可看  →  onComplete 落结果卡.
// No border-beam. One thinking indicator at a time. Monochrome Lucide icons.
/* global React, window */
const { useState: useDT, useEffect: useDTEffect, useRef: useDTRef } = React;
const DTAvatar = window.NLChat.Avatar;
const DTSpinner = window.NLChat.Spinner;

// one-time shimmer style (calm breathe, kept legible — no background-clip)
if (typeof document !== 'undefined' && !document.getElementById('dt-style')) {
  const s = document.createElement('style');
  s.id = 'dt-style';
  s.textContent = '@keyframes dt-breathe{0%,100%{opacity:.58}50%{opacity:1}}.dt-shimmer{animation:dt-breathe 1.7s ease-in-out infinite}';
  document.head.appendChild(s);
}

// ── Lucide line icons (monochrome) ───────────────────────────────
const DT_ICONS = {
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  search: '<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.2-4.2"/>',
  searchcheck: '<path d="m8 11 2 2 4-4"/><circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.2-4.2"/>',
  barchart: '<path d="M3 3v18h18"/><path d="M8 17v-4"/><path d="M13 17V8"/><path d="M18 17v-7"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  listchecks: '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  filetext: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v5h5"/><path d="M9 13h6M9 17h6"/>',
  pencil: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  layers: '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
  building: '<rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M9 8h.01M15 8h.01M9 12h.01M15 12h.01M9 16h6"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  usercheck: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/>',
  door: '<path d="M13 4h3a2 2 0 0 1 2 2v14"/><path d="M2 20h20"/><path d="M14 12v.01"/><path d="M10 4H6a2 2 0 0 0-2 2v14h8V6a2 2 0 0 0-2-2Z"/>',
};
function DTIcon({ name, size = 15, color = 'currentColor', stroke = 1.6 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none' }} dangerouslySetInnerHTML={{ __html: DT_ICONS[name] || '' }} />;
}
function DTCheck({ size = 18, on }) {
  return (
    <span style={{ width: size, height: size, borderRadius: 999, flex: 'none', display: 'inline-grid', placeItems: 'center', background: on ? 'var(--emerald-soft)' : 'transparent', boxShadow: on ? '0 0 0 1px #c1ddc0' : '0 0 0 1.5px var(--ring-warm)', transition: 'background .25s ease-out, box-shadow .25s ease-out' }}>
      {on && <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24" fill="none" stroke="var(--emerald)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>}
    </span>
  );
}
const DTChevron = ({ open, size = 12 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="var(--stone)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transition: 'transform .2s ease-out', transform: open ? 'rotate(180deg)' : 'none', flex: 'none' }}><path d="m6 9 6 6 6-6" /></svg>
);
function DTEnter({ children, style }) {
  const [on, setOn] = useDT(false);
  useDTEffect(() => { setOn(true); }, []);
  return <div style={{ ...style, transform: on ? 'none' : 'translateY(7px)', transition: 'transform .4s ease-out' }}>{children}</div>;
}

// ── per-module config (understanding + node io) ──────────────────
const DEEP_META = {
  feed: {
    understand: {
      headline: '投研 / 券商资管方向的真实在招岗位,不是泛泛的金融岗。',
      tracks: ['投研', '券商资管'],
      memory: ['看重平台梯队', '可接受 base 985', '记忆 ×3'],
      reasoning: '结合你确认过的赛道和偏好:更看重平台梯队而不是起薪。我会先锁定范围,再检索在招、做三维打分,最后排出最值得投的几个。',
    },
    nodes: [
      { icon: 'target', title: '锁定赛道', tool: 'lock_track', input: { track: ['投研', '券商资管'], base: '≥ 985' }, output: '锁定 2 条赛道 · 命中记忆 3 项', chips: ['投研', '券商资管', '命中记忆 ×3'] },
      { icon: 'search', title: '检索岗位', tool: 'search_candidates', input: { tracks: ['投研', '券商资管'], degree: '硕士' }, output: '召回 40 → 去重 39', chips: ['券商研究 ×14', '资管 ×16', '公募 ×9'] },
      { icon: 'barchart', title: '三维打分', tool: 'score_jobs', input: { dims: ['硬匹配', '情报增强', '赛道契合'], n: 39 }, output: '39 个岗位三维评分完成', chips: ['硬匹配', '情报增强', '赛道契合'] },
      { icon: 'listchecks', title: '排出推荐', tool: 'finalize', input: { topN: 'Top', guard: 'substring 反幻觉' }, output: '第一版 Top 已就绪', chips: ['Base 96 · Enhanced 96'] },
    ],
  },
  skeleton: {
    understand: {
      headline: '把券商资管这条赛道的公司,按梯队分档铺成全景。',
      tracks: ['二级买方', '基本面'],
      memory: ['关注头部 / 主力', '匹配档高亮'],
      reasoning: '我会先把这条赛道的相关公司拉全,再按规模与口碑分档,结合你的背景定位你落在哪一档,最后铺成可对照的全景。',
    },
    nodes: [
      { icon: 'building', title: '拉取公司', tool: 'pull_companies', input: { track: '二级买方 · 基本面' }, output: '拉到 18 家 GT 公司', chips: ['18 家公司'] },
      { icon: 'layers', title: '梯队分档', tool: 'tier_split', input: { by: ['规模', '口碑', '在招'] }, output: '分出 头部 / 主力 / 腰部', chips: ['头部', '主力', '腰部'] },
      { icon: 'target', title: '背景定档', tool: 'place_profile', input: { profile: '陈思远 · 投研' }, output: '定位到「主力」档', chips: ['你 → 主力档'] },
      { icon: 'grid', title: '铺出全景', tool: 'finalize', input: { layout: '梯队全景' }, output: '全景已铺好 · 匹配档高亮', chips: ['匹配档高亮'] },
    ],
  },
  resume: {
    understand: {
      headline: '对这份简历做一次诚实打分 + 缺口定位,不是粉饰。',
      tracks: ['投研', '券商资管'],
      memory: ['只诚实评估', '逐段可补', '中文主版'],
      reasoning: '我会先解析简历结构,按目标赛道做诚实打分,再逐段定位缺口在哪,最后给出能落地补的建议 —— 数字与经历都基于你原文,不灌水。',
    },
    nodes: [
      { icon: 'filetext', title: '解析简历', tool: 'parse_resume', input: { sections: ['基本', '经历 ×6', '技能'] }, output: '6 段经历已结构化', chips: ['6 段经历'] },
      { icon: 'gauge', title: '诚实打分', tool: 'score_resume', input: { against: '投研 JD 画像' }, output: '现状 72 · 潜力 80–85', chips: ['现状 72', '潜力 80–85'] },
      { icon: 'searchcheck', title: '定位缺口', tool: 'find_gaps', input: { scan: ['硬门槛', '量化结果', '关键词'] }, output: '定位到 3 段可补缺口', chips: ['缺量化', '关键词不足', '弱动词'] },
      { icon: 'listchecks', title: '给出建议', tool: 'finalize', input: { perGap: '逐段入口' }, output: '3 段建议 · 已挂逐段入口', chips: ['逐段入口'] },
    ],
  },
  interview: {
    understand: {
      headline: '按你的目标赛道,备一场对路的模拟面试。',
      tracks: ['投研', '券商资管'],
      memory: ['延续同一会话', '记忆延用'],
      reasoning: '我会调取你这条会话里的记忆与画像,匹配对路的考官风格,按赛道门槛与真题备好题库,然后进入全屏面试间。',
    },
    nodes: [
      { icon: 'clock', title: '调取记忆', tool: 'load_memory', input: { from: '本会话' }, output: '画像与偏好已载入', chips: ['记忆延用'] },
      { icon: 'usercheck', title: '匹配考官', tool: 'match_examiner', input: { track: '券商资管' }, output: '匹配到买方研究考官', chips: ['买方研究风格'] },
      { icon: 'listchecks', title: '备好题库', tool: 'build_bank', input: { by: ['门槛', '真题'] }, output: '题库已就绪', chips: ['门槛题', '真题'] },
      { icon: 'door', title: '进入面试间', tool: 'finalize', input: { mode: '全屏' }, output: '面试间准备好了', chips: ['全屏 · 结束回 Hub'] },
    ],
  },
};

// ── tool input/output body ───────────────────────────────────────
function DTToolBody({ node, status }) {
  const done = status === 'done';
  return (
    <div style={{ marginTop: 9, borderRadius: 12, background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border-cream)', overflow: 'hidden' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-cream)' }}>
        <div style={{ font: '600 9.5px var(--font-sans)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--stone)', marginBottom: 5 }}>Input</div>
        <code style={{ font: '500 11.5px/1.7 var(--font-mono)', color: 'var(--ink-soft)', display: 'block', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {Object.entries(node.input).map(([k, v]) => (
            <span key={k}><span style={{ color: 'var(--terracotta-strong)' }}>{k}</span>: {Array.isArray(v) ? `[${v.join(', ')}]` : String(v)}{'\n'}</span>
          ))}
        </code>
      </div>
      <div style={{ padding: '8px 12px' }}>
        <div style={{ font: '600 9.5px var(--font-sans)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--stone)', marginBottom: 5 }}>Output</div>
        {done
          ? <div style={{ font: '500 12px var(--font-mono)', color: 'var(--ink)' }}>{node.output}</div>
          : <div style={{ display: 'flex', alignItems: 'center', gap: 7, font: '500 12px var(--font-mono)', color: 'var(--stone)' }}><DTSpinner color="var(--coral)" /> 执行中…</div>}
      </div>
    </div>
  );
}

// ── one chain-of-thought step ────────────────────────────────────
function DTStep({ node, status, last }) {
  const [userOpen, setUserOpen] = useDT(null);
  const open = userOpen !== null ? userOpen : status === 'running';
  return (
    <DTEnter style={{ display: 'flex', gap: 12, position: 'relative' }}>
      {!last && <div style={{ position: 'absolute', left: 14, top: 30, bottom: -6, width: 2, background: status === 'done' ? 'var(--terracotta)' : 'var(--warm-sand)', transition: 'background .3s ease-out' }} />}
      <div style={{ flex: 'none', width: 29, height: 29, borderRadius: 999, display: 'grid', placeItems: 'center', background: 'var(--ivory)', boxShadow: status === 'done' ? '0 0 0 1.5px #c1ddc0' : status === 'running' ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1.5px var(--ring-warm)', zIndex: 1, transition: 'box-shadow .3s ease-out' }}>
        {status === 'done' ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--emerald)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
          : status === 'running' ? <DTSpinner /> : <DTIcon name={node.icon} size={14} color="var(--stone)" />}
      </div>
      <div style={{ flex: 1, paddingBottom: 16, minWidth: 0 }}>
        <button onClick={() => setUserOpen(!open)} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', background: 'none', border: 0, cursor: 'pointer', padding: 0 }}>
          <DTIcon name={node.icon} size={15} color="var(--ink-soft)" />
          <span style={{ font: '500 13.5px var(--font-sans)', color: status === 'pending' ? 'var(--stone)' : 'var(--ink)' }}>{node.title}</span>
          <span style={{ font: '500 10px var(--font-mono)', color: 'var(--stone)', background: 'var(--library-rail)', padding: '1px 6px', borderRadius: 999 }}>{node.tool}</span>
          {status === 'running' && <span style={{ font: '400 11px var(--font-sans)', color: 'var(--coral)', whiteSpace: 'nowrap' }}>运行中…</span>}
          <span style={{ marginLeft: 'auto', opacity: status === 'pending' ? 0.4 : 1 }}><DTChevron open={open} /></span>
        </button>
        {open && <DTToolBody node={node} status={status} />}
        {status === 'done' && (
          <DTEnter style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 9 }}>
            {node.chips.map((c) => <span key={c} className="hf-pill" style={{ height: 24, fontSize: 11.5 }}>{c}</span>)}
          </DTEnter>
        )}
      </div>
    </DTEnter>
  );
}

// ── the embeddable deep-think card ───────────────────────────────
function DeepThinkCard({ module, nodes: fallbackNodes, onComplete }) {
  const cfg = DEEP_META[module] || {
    understand: { headline: '按你说的把这件事想清楚。', tracks: [], memory: [], reasoning: '先理解你的目标,再分步推进。' },
    nodes: (fallbackNodes || ['理解', '检索', '评估', '产出']).map((t) => ({ icon: 'listchecks', title: t, tool: 'step', input: { step: t }, output: '完成', chips: [] })),
  };
  const u = cfg.understand;
  const [phase, setPhase] = useDT('understand');   // understand | think | done
  const [step, setStep] = useDT(0);                 // active node index while thinking
  const [chars, setChars] = useDT(0);               // reasoning typewriter
  const [thinkOpen, setThinkOpen] = useDT(null);
  const fired = useDTRef(false);

  // understanding → think
  useDTEffect(() => {
    const t = setTimeout(() => setPhase('think'), 1600);
    return () => clearTimeout(t);
  }, []);
  // reasoning typewriter during understanding
  useDTEffect(() => {
    if (phase !== 'understand') { setChars(u.reasoning.length); return; }
    let i = 0; const id = setInterval(() => { i += 2; setChars(i); if (i >= u.reasoning.length) clearInterval(id); }, 22);
    return () => clearInterval(id);
  }, [phase]);
  // run the nodes
  useDTEffect(() => {
    if (phase !== 'think') return;
    const per = 760;
    const timers = cfg.nodes.map((_, i) => setTimeout(() => setStep(i + 1), per * (i + 1)));
    const end = setTimeout(() => {
      setPhase('done');
      if (!fired.current) { fired.current = true; onComplete && onComplete(); }
    }, per * cfg.nodes.length + 320);
    return () => { timers.forEach(clearTimeout); clearTimeout(end); };
  }, [phase]);

  const understanding = phase === 'understand';
  const running = phase !== 'done';
  const thinkOpenEff = thinkOpen !== null ? thinkOpen : running;  // auto-collapse on done
  const doneCount = phase === 'done' ? cfg.nodes.length : step;
  const nodeStatus = (i) => (i < step ? 'done' : (i === step && phase === 'think') ? 'running' : 'pending');

  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
      <DTAvatar />
      <div style={{ flex: 1, minWidth: 0, maxWidth: 540, background: 'var(--ivory)', borderRadius: 16, borderTopLeftRadius: 5, boxShadow: '0 0 0 1px var(--border)', overflow: 'hidden' }}>
        {/* 我的理解 */}
        <div style={{ padding: '13px 15px', borderBottom: phase !== 'understand' ? '1px solid var(--border-cream)' : 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 7 }}>
            {understanding ? <DTSpinner /> : <DTCheck size={16} on />}
            <span style={{ font: '600 11px var(--font-sans)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--terracotta-strong)' }}>我的理解</span>
          </div>
          <p style={{ font: '400 13.5px/1.6 var(--font-sans)', color: 'var(--ink)', margin: 0 }}>
            我理解你要的是 —— <b style={{ fontWeight: 600 }}>{u.headline}</b>
          </p>
          {(u.tracks.length > 0 || u.memory.length > 0) && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 9, alignItems: 'center' }}>
              {u.tracks.map((c) => <span key={c} className="hf-pill terra" style={{ height: 24, fontSize: 11.5 }}>{c}</span>)}
              {u.memory.length > 0 && <span style={{ width: 1, height: 16, background: 'var(--border-warm)', margin: '0 2px' }} />}
              {u.memory.map((c) => (
                <span key={c} className="hf-pill" style={{ height: 24, fontSize: 11, color: 'var(--muted)' }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--stone)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8v4l3 2" /><circle cx="12" cy="12" r="9" /></svg>{c}
                </span>
              ))}
            </div>
          )}
          <p className={understanding ? 'dt-shimmer' : ''} style={{ font: '400 12.5px/1.7 var(--font-sans)', color: 'var(--muted)', whiteSpace: 'pre-wrap', margin: '11px 0 0', borderLeft: '2px solid var(--warm-sand)', paddingLeft: 12 }}>
            {u.reasoning.slice(0, chars)}{understanding && <span className="hf-caret" style={{ height: '0.9em' }} />}
          </p>
        </div>

        {/* 思考过程 — auto-collapses when done; click to reopen */}
        {phase !== 'understand' && (
          <div style={{ padding: '13px 15px' }}>
            <button onClick={() => setThinkOpen(!thinkOpenEff)} style={{ display: 'flex', alignItems: 'center', gap: 9, width: '100%', textAlign: 'left', background: 'none', border: 0, cursor: 'pointer', padding: 0 }}>
              {phase === 'done' ? <DTCheck size={15} on /> : !thinkOpenEff ? <DTSpinner /> : <span style={{ width: 13, flex: 'none' }} />}
              <span style={{ font: '600 11px var(--font-sans)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--stone)' }}>思考过程</span>
              <span style={{ font: '400 11px var(--font-mono)', color: 'var(--stone)' }}>{doneCount}/{cfg.nodes.length}{phase === 'done' ? ' · 已完成' : ''}</span>
              <span style={{ marginLeft: 'auto' }}><DTChevron open={thinkOpenEff} /></span>
            </button>
            {thinkOpenEff && (
              <div style={{ paddingTop: 15 }}>
                {cfg.nodes.map((n, i) => <DTStep key={i} node={n} status={nodeStatus(i)} last={i === cfg.nodes.length - 1} />)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

window.DeepThink = { DeepThinkCard };
