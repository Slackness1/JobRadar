// hub/hub-views.jsx — hi-fi Hub shell: collapsible sidebar + morphing slot views (skeleton / profile / resume placeholder) + landing
/* global React, window */
const { useState: useHV } = React;
const HI = window.I;

// inline icons not in the shared set
const micIcon = (s = 18) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </svg>
);
const layersIcon = (s = 18) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5" />
  </svg>
);
const composeIcon = (s = 18) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 20h16" /><path d="M14.5 4.5l4 4L8 19l-5 1 1-5 10.5-10.5z" />
  </svg>
);
const expandIcon = (s = 13) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
  </svg>
);

// =========================================================================
// SIDEBAR — 导航 + 简历切换器 + 历史(会话) + 底部身份常驻 (collapsible)
// =========================================================================
const NAV = [
  { key: 'feed',      label: '职位推荐', icon: HI.radar },
  { key: 'skeleton',  label: '梯队骨架', icon: layersIcon },
  { key: 'resume',    label: '简历优化', icon: HI.file },
  { key: 'interview', label: '模拟面试', icon: micIcon, jump: true },
  { key: 'profile',   label: '个人档案', icon: HI.user },
];

function SideNavItem({ item, active, collapsed, onClick }) {
  const [hov, setHov] = useHV(false);
  const base = active ? 'var(--ink)' : item.disabled ? 'var(--warm-silver)' : 'var(--ink-soft)';
  return (
    <button
      onClick={() => !item.disabled && onClick(item)}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      title={collapsed ? item.label : undefined}
      style={{
        position: 'relative', width: '100%', display: 'flex', alignItems: 'center',
        gap: 11, padding: collapsed ? '10px 0' : '9px 11px', justifyContent: collapsed ? 'center' : 'flex-start',
        borderRadius: 10, cursor: item.disabled ? 'default' : 'pointer',
        background: active ? 'var(--terracotta-wash)' : hov && !item.disabled ? 'var(--library-rail)' : 'transparent',
        boxShadow: active ? '0 0 0 1px #eccfb6' : 'none',
        color: base, transition: 'background .14s',
      }}
    >
      {active && !collapsed && <span style={{ position: 'absolute', left: -1, top: 8, bottom: 8, width: 2.5, borderRadius: 2, background: 'var(--terracotta)' }} />}
      <span style={{ color: active ? 'var(--terracotta-strong)' : base, display: 'inline-flex', flex: 'none' }}>{item.icon(collapsed ? 19 : 17)}</span>
      {!collapsed && <>
        <span style={{ font: `${active ? 600 : 500} 13.5px var(--font-sans)`, flex: 1, textAlign: 'left' }}>{item.label}</span>
        {item.jump && <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>{expandIcon(13)}</span>}
        {item.disabled && <span style={{ font: '500 9.5px var(--font-sans)', color: 'var(--warm-silver)', boxShadow: '0 0 0 1px var(--border-warm)', borderRadius: 999, padding: '1px 7px' }}>占位</span>}
      </>}
    </button>
  );
}

const SESSIONS = [
  ['券商资管 · 固收方向', '刚刚'],
  ['量化私募 · 研究岗', '昨天'],
  ['央国企 · 战略', '3 天前'],
];

function HubSidebar({ collapsed, onToggle, active, onNav, onNew }) {
  if (collapsed) {
    return (
      <div style={{ width: 64, flex: 'none', borderRight: '1px solid var(--border)', background: 'var(--ivory)',
        display: 'flex', flexDirection: 'column', padding: '14px 10px', gap: 6 }}>
        <button onClick={onToggle} title="展开侧边栏" style={{ width: 30, height: 30, margin: '0 auto 6px', borderRadius: 9, background: 'var(--deep-dark)', position: 'relative', cursor: 'pointer' }}>
          <span style={{ position: 'absolute', width: 8, height: 8, borderRadius: 999, background: 'var(--terracotta)', top: 11, left: 11, boxShadow: '0 0 0 3px rgba(201,100,66,0.22)' }} />
        </button>
        <button onClick={onNew} title="新对话" style={{ width: 40, height: 40, margin: '0 auto 4px', borderRadius: 10, background: 'var(--terracotta-wash)', color: 'var(--terracotta-strong)', display: 'grid', placeItems: 'center', cursor: 'pointer', boxShadow: '0 0 0 1px #eccfb6' }}>{HI.plus(16)}</button>
        {NAV.map((n) => <SideNavItem key={n.key} item={n} active={active === n.key} collapsed onClick={onNav} />)}
        <div style={{ marginTop: 'auto', display: 'grid', placeItems: 'center', paddingTop: 8 }}>
          <div style={{ width: 30, height: 30, borderRadius: 999, background: 'var(--terracotta)', color: '#fff', display: 'grid', placeItems: 'center', font: '600 13px var(--font-sans)' }}>陈</div>
        </div>
      </div>
    );
  }
  return (
    <div style={{ width: 252, flex: 'none', borderRight: '1px solid var(--border)', background: 'var(--ivory)',
      display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* brand + collapse */}
      <div style={{ padding: '14px 14px 8px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <window.HFLogo size="sm" />
        <button onClick={onToggle} title="收起侧边栏" style={{ marginLeft: 'auto', width: 28, height: 28, borderRadius: 8, display: 'grid', placeItems: 'center', color: 'var(--stone)', cursor: 'pointer', boxShadow: '0 0 0 1px var(--border-warm)' }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M15 6l-6 6 6 6" /></svg>
        </button>
      </div>
      {/* new chat — 与选中 tab 统一的浅土红样式 */}
      <div style={{ padding: '6px 12px 4px' }}>
        <button onClick={onNew} style={{ position: 'relative', width: '100%', height: 40, display: 'flex', alignItems: 'center',
          justifyContent: 'flex-start', gap: 10, paddingLeft: 13, borderRadius: 10, cursor: 'pointer',
          background: 'var(--terracotta-wash)', boxShadow: '0 0 0 1px #eccfb6', color: 'var(--ink)' }}>
          <span style={{ position: 'absolute', left: -1, top: 8, bottom: 8, width: 2.5, borderRadius: 2, background: 'var(--terracotta)' }} />
          <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex', flex: 'none' }}>{composeIcon(16)}</span>
          <span style={{ font: '600 13.5px var(--font-sans)' }}>新对话</span>
        </button>
      </div>
      {/* nav */}
      <div style={{ padding: '6px 10px 4px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV.map((n) => <SideNavItem key={n.key} item={n} active={active === n.key} onClick={onNav} />)}
      </div>
      <div className="hf-hr" style={{ margin: '8px 14px' }} />
      {/* resume switcher — 只在 >1 份简历时显形 (会话嵌简历下) */}
      <div style={{ padding: '0 12px 8px' }}>
        <button style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 11px', borderRadius: 10, cursor: 'pointer', background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border-warm)' }}>
          <span style={{ color: 'var(--stone)', display: 'inline-flex', flex: 'none' }}>{HI.file(15)}</span>
          <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
            <div style={{ font: '600 12px var(--font-sans)', color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>简历 · 中文主版</div>
            <div style={{ font: '400 10px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>当前画像 · 切换简历(2)</div>
          </div>
          <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>{HI.chevron(13)}</span>
        </button>
      </div>
      {/* history = 当前简历名下的会话列表 */}
      <div style={{ padding: '0 16px 6px', display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>{HI.history(12)}</span>
        <span className="hf-overline" style={{ fontSize: 9.5 }}>历史记录 · 此简历下的会话</span>
      </div>
      <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 2, overflow: 'auto', minHeight: 0 }}>
        {SESSIONS.map(([s, t], i) => (
          <div key={i} style={{ padding: '8px 11px', borderRadius: 10, cursor: 'pointer',
            background: i === 0 ? 'var(--library-rail)' : 'transparent',
            boxShadow: i === 0 ? '0 0 0 1px var(--border-warm)' : 'none' }}>
            <div style={{ font: `${i === 0 ? 600 : 500} 12.5px var(--font-sans)`, color: i === 0 ? 'var(--ink)' : 'var(--ink-soft)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s}</div>
            <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)', marginTop: 2 }}>{t}</div>
          </div>
        ))}
      </div>
      {/* identity persistent (底部头像 = 完整档案入口) */}
      <button onClick={() => onNav({ key: 'profile' })} style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', padding: '11px 13px',
        display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', background: 'transparent', textAlign: 'left' }}>
        <div style={{ width: 32, height: 32, borderRadius: 999, background: 'var(--terracotta)', color: '#fff', display: 'grid', placeItems: 'center', font: '600 13px var(--font-sans)', flex: 'none' }}>陈</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 13px var(--font-sans)', color: 'var(--ink)' }}>陈思远</div>
          <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)' }}>它记得你 · 点开看档案</div>
        </div>
        <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>{HI.arrowRight(13)}</span>
      </button>
    </div>
  );
}

// =========================================================================
// SLOT CHROME — shared header for skeleton / profile / resume views
// =========================================================================
// shared close affordance — 关掉侧面板回到全宽对话
function SlotCloseBtn({ onClose }) {
  return (
    <button onClick={onClose} title="关掉 · 回到全宽对话" style={{ width: 28, height: 28, flex: 'none', borderRadius: 8, display: 'grid', placeItems: 'center', color: 'var(--stone)', cursor: 'pointer', boxShadow: '0 0 0 1px var(--border-warm)' }}>{HI.close(14)}</button>
  );
}

function SlotHead({ icon, title, sub, right }) {
  return (
    <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', background: 'var(--ivory)', display: 'flex', alignItems: 'center', gap: 11, flex: 'none' }}>
      {icon && <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex' }}>{icon}</span>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>{title}</div>
        {sub && <div style={{ font: '400 11.5px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>{sub}</div>}
      </div>
      {right}
    </div>
  );
}

// =========================================================================
// 梯队骨架 · 档次全景 (view B)
//   接入工作台左栏 rail (hifi-ws-rail.jsx)：阶梯脊柱 + 三梯队 + 双态公司卡
//   （在招岗列表 / 骨架公司情报 + 往年窗口）。情报 / 定制按钮回流到对话主轴。
// =========================================================================
function SkeletonView({ onIntel, onCoach, onClose }) {
  const [expandedIds, setExpandedIds] = useHV(() => new Set(['cs']));
  const [activeJobId, setActiveJobId] = useHV(null);
  const HFTierGroup = window.HFTierGroup;
  const skel = (window.RC_PLATFORM_TIERS || {}).l2_buyside;

  const toggle = (id) => setExpandedIds((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const jobClick = (jid) => setActiveJobId((p) => (p === jid ? null : jid));
  const intel = (id) => { if (onIntel) onIntel(id); else { setExpandedIds((p) => new Set(p).add(id)); } };
  const coach = (id) => { if (onCoach) onCoach(id); else { setExpandedIds((p) => new Set(p).add(id)); } };

  if (!skel || !HFTierGroup) {
    return <SlotHead icon={layersIcon(18)} title="梯队骨架" sub="骨架数据加载中…" />;
  }
  return (
    <>
      <SlotHead icon={layersIcon(18)} title="梯队骨架 · 档次全景" sub="二级买方 · 基本面 · 头 / 主力 / 腰部"
        right={<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span className="hf-pill terra" style={{ height: 28 }}>{skel.subCat}</span>{onClose && <SlotCloseBtn onClose={onClose} />}</div>} />
      <div style={{ flex: 1, overflow: 'auto', padding: '14px 14px 18px', background: 'var(--library-rail)' }}>
        {/* intro */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '9px 11px', marginBottom: 12,
          background: 'var(--ivory)', borderRadius: 10, boxShadow: '0 0 0 1px var(--border-warm)' }}>
          <span style={{ color: 'var(--terracotta)', display: 'inline-flex', flexShrink: 0, marginTop: 1 }}>{HI.radar(15)}</span>
          <div style={{ fontSize: 11.5, color: 'var(--olive)', lineHeight: 1.5 }}>
            <b style={{ color: 'var(--ink)' }}>{skel.subCat}</b> 平台格局 · 按梯队展示。
            <span style={{ color: 'var(--terracotta)' }}> 在招</span> 与 <span style={{ color: 'var(--stone)' }}>暂无对口岗</span> 的头部公司都在，匹配档已高亮。
          </div>
        </div>
        {skel.tiers.map((t, i) => (
          <HFTierGroup key={t.tier} tier={t} expandedIds={expandedIds} activeJobId={activeJobId}
            onToggle={toggle} onIntel={intel} onCoach={coach} onJobClick={jobClick}
            isFirst={i === 0} isLast={i === skel.tiers.length - 1} />
        ))}
        <div style={{ textAlign: 'center', padding: 8, fontSize: 11.5, color: 'var(--stone)' }}>骨架来自 GT 公司库 · 在招标记每日刷新</div>
      </div>
    </>
  );
}

// =========================================================================
// 个人档案 · B 确认/纠正闭环 (view)
// =========================================================================
const CONFIRMED = [
  ['目标赛道', '二级买方 · 基本面 · 公募/私募'],
  ['目标城市', '上海 · 北京'],
  ['求职阶段', '2026 校招 · 毕业 2026.06'],
  ['投递类型', '全职'],
];
const INFERRED = [
  { claim: '偏向固定收益方向', from: '近 5 轮对话多次主动加「固收」', conf: '高' },
  { claim: '行业回避：国企', from: '原话「我一直不考虑国企」', conf: '高' },
  { claim: '更看重平台梯队 > 薪资', from: '锁定方向时优先选头部券商资管', conf: '中' },
];

function InferredCard({ item, onConfirm, onReject, state }) {
  if (state === 'confirmed') {
    return (
      <div className="hf-slide" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', borderRadius: 13, background: 'var(--emerald-soft)', boxShadow: '0 0 0 1px #c7d9c2' }}>
        <span style={{ color: 'var(--emerald)', display: 'inline-flex' }}>{HI.check(15)}</span>
        <span style={{ font: '500 13px var(--font-sans)', color: 'var(--ink-soft)', flex: 1 }}>{item.claim}</span>
        <span className="hf-pill emerald" style={{ height: 24 }}>已升为确认信息</span>
      </div>
    );
  }
  if (state === 'rejected') {
    return (
      <div className="hf-slide" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', borderRadius: 13, background: 'transparent', boxShadow: '0 0 0 1px var(--border-warm)', opacity: 0.7 }}>
        <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>{HI.close(14)}</span>
        <span style={{ font: '500 13px var(--font-sans)', color: 'var(--stone)', textDecoration: 'line-through', flex: 1 }}>{item.claim}</span>
        <span style={{ font: '500 11px var(--font-sans)', color: 'var(--stone)' }}>已否掉 · 不再喂画像</span>
      </div>
    );
  }
  return (
    <div style={{ padding: '13px 15px', borderRadius: 14, background: 'var(--ivory)', boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)', flex: 1 }}>{item.claim}</span>
        <span className="hf-pill amber" style={{ height: 24, flexShrink: 0, whiteSpace: 'nowrap' }}>AI 推断 · 待确认</span>
      </div>
      <div style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--muted)', marginBottom: 11 }}>
        依据：{item.from} <span style={{ color: 'var(--stone)', fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>· 置信 {item.conf}</span>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="hf-btn primary sm" style={{ flex: 1 }} onClick={onConfirm}>确认 · 升为确认信息</button>
        <button className="hf-btn ghost sm" onClick={onReject}>否掉</button>
      </div>
    </div>
  );
}

function ProfileView({ onClose }) {
  const [states, setStates] = useHV({});
  const set = (i, v) => setStates((s) => ({ ...s, [i]: v }));
  return (
    <>
      <SlotHead icon={HI.user(18)} title="个人档案" sub="确认信息 + AI 推断待确认 · B 闭环"
        right={<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><button className="hf-btn ghost sm">编辑</button>{onClose && <SlotCloseBtn onClose={onClose} />}</div>} />
      <div style={{ flex: 1, overflow: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 18 }}>
        {/* layer 1 — 确认信息 (权威) */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 11 }}>
            <span className="hf-overline">确认信息</span>
            <span style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)' }}>· 你拍板的 · 喂推荐 + 骨架</span>
          </div>
          <div style={{ background: 'var(--ivory)', borderRadius: 16, padding: '6px 16px', boxShadow: 'var(--sh-ring)' }}>
            {CONFIRMED.map(([k, v], i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 12, padding: '11px 0', borderBottom: i < CONFIRMED.length - 1 ? '1px solid var(--border-cream)' : 'none' }}>
                <span style={{ flex: 'none', width: 64, font: '500 12px var(--font-sans)', color: 'var(--stone)' }}>{k}</span>
                <span style={{ font: '500 13.5px var(--font-sans)', color: 'var(--ink)', flex: 1, lineHeight: 1.5 }}>{v}</span>
                <span style={{ color: 'var(--warm-silver)', display: 'inline-flex', cursor: 'pointer' }}>{HI.edit(14)}</span>
              </div>
            ))}
          </div>
        </div>
        {/* layer 2 — AI 推断待确认 */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 11 }}>
            <span className="hf-overline" style={{ color: 'var(--amber-fg)' }}>AI 推断 · 待确认</span>
            <span style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)' }}>· 从对话推断 · 确认后才喂画像</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {INFERRED.map((it, i) => (
              <InferredCard key={i} item={it} state={states[i]}
                onConfirm={() => set(i, 'confirmed')} onReject={() => set(i, 'rejected')} />
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// =========================================================================
// 简历优化 · 占位 (接口位 · 本期前端等 HiFi)
// =========================================================================
function ResumePlaceholderView() {
  return (
    <>
      <SlotHead icon={HI.file(18)} title="简历优化" sub="接口位 · 本期前端等 HiFi · 灰置占位" />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 28, textAlign: 'center' }}>
        <span style={{ width: 58, height: 58, borderRadius: 16, display: 'grid', placeItems: 'center', color: 'var(--warm-silver)', boxShadow: '0 0 0 1.5px var(--border-strong)', borderStyle: 'dashed' }}>{HI.file(26)}</span>
        <div>
          <div style={{ font: '600 14px var(--font-sans)', color: 'var(--olive)' }}>简历优化在另一分支</div>
          <div style={{ font: '400 12px/1.6 var(--font-sans)', color: 'var(--stone)', marginTop: 7, maxWidth: 260 }}>本期只留侧边栏占位 + 画布槽接口位。日后它的视图（打分 / 深度优化）直接塞进同一个槽，不动外壳。</div>
        </div>
        <span className="hf-pill amber" style={{ height: 28 }}>等 HiFi · 可见不可用</span>
      </div>
    </>
  );
}

// =========================================================================
// 简历优化 · 接进画布槽 (打分报告 + WYSIWYG 预览 + 写回) — 不再是占位
// =========================================================================
const R_RADAR = [
  { k: '逻辑', v: 78 }, { k: 'STAR', v: 58 }, { k: '可读', v: 84 }, { k: '完整', v: 70 },
  { k: '表达', v: 80 }, { k: '量化', v: 52 }, { k: '匹配度', v: 64, fin: true }, { k: '佐证', v: 55, fin: true },
];
const R_GAPS = [
  { t: '九坤投资 · 量化研究实习', tags: ['STAR 缺 Result', '佐证不足'], active: true },
  { t: '校园量化策略项目', tags: ['成果无量化锚点'] },
  { t: '个人介绍', tags: ['赛道匹配度低'] },
];

function HubRadar({ size = 180, data, max = 100 }) {
  const cx = size / 2, cy = size / 2, R = size * 0.38, n = data.length;
  const ang = (i) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const pt = (i, r) => [cx + Math.cos(ang(i)) * r, cy + Math.sin(ang(i)) * r];
  const poly = (r) => data.map((_, i) => pt(i, R * r).join(',')).join(' ');
  const valPoly = data.map((d, i) => pt(i, R * (d.v / max)).join(',')).join(' ');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
      {[0.25, 0.5, 0.75, 1].map((r, i) => <polygon key={i} points={poly(r)} fill="none" stroke={i === 3 ? 'var(--border-strong)' : 'var(--border-warm)'} strokeWidth="1" />)}
      {data.map((_, i) => { const [x, y] = pt(i, R); return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--border-warm)" strokeWidth="1" />; })}
      <polygon points={valPoly} fill="var(--terracotta)" fillOpacity="0.13" stroke="var(--terracotta)" strokeWidth="1.6" strokeLinejoin="round" />
      {data.map((d, i) => { const [x, y] = pt(i, R * (d.v / max)); return <circle key={i} cx={x} cy={y} r="2.6" fill="var(--terracotta-strong)" />; })}
      {data.map((d, i) => {
        const [x, y] = pt(i, R + 15);
        const anchor = Math.abs(x - cx) < 6 ? 'middle' : x > cx ? 'start' : 'end';
        return <text key={i} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" style={{ font: `${d.fin ? 700 : 500} 9.5px var(--font-sans)`, fill: d.fin ? 'var(--terracotta-strong)' : 'var(--olive)' }}>{d.k}</text>;
      })}
    </svg>
  );
}

// WYSIWYG A4 preview with "AI 刚写回" highlight on 实习经历
function ResumeA4({ highlight }) {
  const secs = ['教育经历', '实习经历', '项目经历', '掌握技能'];
  const grayLine = (w, mb = 6) => <div style={{ width: w, height: 4.5, background: 'var(--border-warm)', borderRadius: 3, marginBottom: mb }} />;
  return (
    <div style={{ background: '#fff', width: 322, padding: '24px 28px', boxSizing: 'border-box', borderRadius: 4, margin: '0 auto', boxShadow: '0 0 0 1px var(--border-warm), 0 12px 32px rgba(0,0,0,0.09)' }}>
      <div style={{ borderBottom: '2px solid var(--ink)', paddingBottom: 10, marginBottom: 12 }}>
        <div style={{ font: '600 18px/1 var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>陈一帆</div>
        <div style={{ display: 'flex', gap: 12 }}>{grayLine(58, 0)}{grayLine(72, 0)}{grayLine(46, 0)}</div>
      </div>
      {secs.map((s, i) => {
        const lit = highlight && i === 1;
        return (
          <div key={i} style={{ marginBottom: 14, background: lit ? 'var(--terracotta-wash)' : 'transparent', borderRadius: lit ? 7 : 0,
            margin: lit ? '0 -10px 14px' : '0 0 14px', padding: lit ? '8px 10px' : 0, boxShadow: lit ? '0 0 0 1.5px var(--terracotta)' : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span style={{ font: '600 11px/1 var(--font-sans)', color: 'var(--ink-soft)', letterSpacing: '0.04em' }}>{s}</span>
              {lit && <span style={{ font: '600 9px var(--font-sans)', color: '#fff', background: 'var(--terracotta)', borderRadius: 999, padding: '2px 8px', marginLeft: 'auto' }}>AI 刚写回</span>}
            </div>
            {lit
              ? <div style={{ font: '400 10px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}>搭建覆盖 <b>40+ 量价因子</b>的回测框架（<b>2021–2023</b>），将单因子筛选由手动改为一键批量，显著缩短迭代周期。</div>
              : [...Array(i === 3 ? 2 : 3)].map((_, j, a) => grayLine(j === a.length - 1 ? (i === 2 ? '74%' : '56%') : '100%', 5))}
          </div>
        );
      })}
    </div>
  );
}

function ResumeView({ onExpand, onClose }) {
  const [view, setView] = useHV('score');
  return (
    <>
      {/* chrome: title + 展开编辑器 + segmented */}
      <div style={{ padding: '13px 16px 0', background: 'var(--ivory)', borderBottom: '1px solid var(--border)', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex' }}>{HI.file(18)}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>简历优化</div>
            <div style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>诚实打分 + 深度优化 · 写回实时刷新</div>
          </div>
          <button className="hf-btn ghost sm" style={{ gap: 6 }} onClick={onExpand}>{expandIcon(13)} 展开编辑器</button>
          {onClose && <SlotCloseBtn onClose={onClose} />}
        </div>
        <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 11, boxShadow: '0 0 0 1px var(--border-warm)', margin: '12px 0 13px' }}>
          {[['score', '打分报告'], ['preview', '简历预览']].map(([k, t]) => (
            <button key={k} onClick={() => setView(k)} style={{ flex: 1, textAlign: 'center', cursor: 'pointer', font: `${view === k ? 600 : 500} 12.5px var(--font-sans)`, padding: '7px 0', borderRadius: 8, color: view === k ? 'var(--ink)' : 'var(--olive)', background: view === k ? 'var(--ivory)' : 'transparent', boxShadow: view === k ? '0 0 0 1px var(--border-strong), 0 1px 2px rgba(0,0,0,0.04)' : 'none' }}>{t}</button>
          ))}
        </div>
      </div>

      {view === 'score' ? (
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
              <HubRadar size={172} data={R_RADAR} />
            </div>
          </div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>逐段缺口 · 深度优化入口</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {R_GAPS.map((g, i) => (
              <div key={i} style={{ borderRadius: 13, padding: '12px 13px', background: 'var(--ivory)', boxShadow: g.active ? '0 0 0 1px var(--terracotta), 0 6px 18px rgba(201,100,66,0.08)' : 'var(--sh-ring)' }}>
                <div style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>{g.t}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
                  {g.tags.map((t, j) => <span key={j} className="hf-pill" style={{ height: 22, fontSize: 10.5, whiteSpace: 'nowrap' }}>{t}</span>)}
                </div>
                <button className={g.active ? 'hf-btn primary sm' : 'hf-btn sand sm'} style={{ height: 30 }}>{g.active ? '正在深度优化 · 看对话 ←' : '去深度优化这段 →'}</button>
              </div>
            ))}
          </div>
          <div style={{ font: '400 10.5px/1.5 var(--font-sans)', color: 'var(--stone)', textAlign: 'center', marginTop: 12 }}>只诊断、不改写 · 提分靠深度优化反问取证</div>
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--parchment)' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--ivory)', display: 'flex', alignItems: 'center', gap: 7, flex: 'none' }}>
            <span className="hf-pill" style={{ height: 26, fontFamily: 'var(--font-mono)' }}>1 页</span>
            <span className="hf-pill" style={{ height: 26 }}>模板 · 经典单栏 ▾</span>
            <span className="hf-pill" style={{ height: 26 }}>布局 ▾</span>
            <button className="hf-btn dark sm" style={{ marginLeft: 'auto', height: 28 }}>下载 PDF</button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '18px 0', display: 'flex', justifyContent: 'center' }}>
            <ResumeA4 highlight />
          </div>
        </div>
      )}
    </>
  );
}

Object.assign(window, { HubSidebar, SkeletonView, ProfileView, ResumeView, ResumePlaceholderView, SlotHead, HubNav: NAV, HubRadar });
