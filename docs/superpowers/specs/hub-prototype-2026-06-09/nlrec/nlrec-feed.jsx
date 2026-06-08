// nlrec-feed.jsx — 流动 feed 右栏: WorkingQuery readout + job cards + deepen
/* global React, window */
const { useState } = React;

// L1 working-query chip
function QueryChip({ kind, children, onX }) {
  if (kind === 'seed') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, height: 26, padding: '0 11px', borderRadius: 999,
        font: '600 12px var(--font-sans)', background: 'var(--dark-surface)', color: 'var(--ivory)' }}>
        {children}
      </span>
    );
  }
  if (kind === 'excl') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, height: 26, padding: '0 11px', borderRadius: 999,
        font: '500 12px var(--font-sans)', background: 'transparent', color: 'var(--muted)', boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed' }}>
        <span style={{ opacity: 0.7, fontSize: 11 }}>✕</span>{children}
      </span>
    );
  }
  // add (terracotta wash, removable)
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, height: 26, padding: '0 6px 0 11px', borderRadius: 999,
      font: '600 12px var(--font-sans)', background: 'var(--terracotta-wash)', color: 'var(--terracotta-strong)', boxShadow: '0 0 0 1px #eccfb6' }}>
      {children}
      {onX && <button onClick={onX} title="移除" style={{ width: 16, height: 16, borderRadius: 999, display: 'grid', placeItems: 'center', color: 'var(--terracotta-strong)', opacity: 0.6, fontSize: 13, lineHeight: 1 }}>×</button>}
    </span>
  );
}

// 卡面只留学生看得懂的：匹配 / 深度匹配（黑话 Base/Enhanced/规则三维分/used_ai 收进 ? 或不显示）
function ScorePill({ kind, label, value }) {
  if (kind === 'base') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 8,
        font: '600 12px var(--font-mono)', background: 'var(--warm-sand)', color: 'var(--charcoal)', boxShadow: '0 0 0 1px var(--ring-warm)' }}>
        <span style={{ font: '600 10px var(--font-sans)', letterSpacing: '0.01em', opacity: 0.7 }}>匹配</span>{value}
      </span>
    );
  }
  if (kind === 'enh') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 8,
        font: '600 12px var(--font-mono)', background: 'var(--terracotta)', color: 'var(--ivory)', boxShadow: '0 0 0 1px var(--terracotta)' }}>
        <span style={{ font: '600 10px var(--font-sans)', letterSpacing: '0.01em', opacity: 0.85 }}>深度匹配</span>{value}
      </span>
    );
  }
  // 未深挖：留白显示 — ，不暴露英文 Enhanced
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 8,
      font: '500 12px var(--font-mono)', color: 'var(--stone)', background: 'transparent', boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed' }}>
      <span style={{ font: '600 10px var(--font-sans)', letterSpacing: '0.01em', opacity: 0.8 }}>深度匹配</span>—
    </span>
  );
}

function JobCard({ job, rank, deep, deepening, onDeepen, onIntel }) {
  const D = window.NLData;
  const anchors = deep ? D.anchorsFor(job) : null;
  return (
    <div className="hf-slide" style={{ background: 'var(--ivory)', borderRadius: 14, padding: '13px 15px',
      boxShadow: deep ? '0 0 0 1px var(--terracotta-ring), 0 6px 20px rgba(201,100,66,0.08)' : 'var(--sh-ring)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 9 }}>
        <span style={{ font: '600 12px var(--font-mono)', color: 'var(--warm-silver)', minWidth: 20 }}>#{rank}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)', lineHeight: 1.3 }}>{job.name}</div>
          <div style={{ font: '400 12px var(--font-sans)', color: 'var(--muted)', marginTop: 3 }}>{job.co} · {job.loc}</div>
        </div>
        <span style={{ font: '500 11px var(--font-mono)', color: 'var(--stone)', whiteSpace: 'nowrap' }}>{D.freshText(job.freshDays)}</span>
      </div>

      <div style={{ display: 'flex', gap: 7, alignItems: 'center', flexWrap: 'wrap' }}>
        <ScorePill kind="base" value={job.base} />
        {deep ? <ScorePill kind="enh" value={D.enhancedFor(job)} /> : <ScorePill kind="pending" />}
        {deep && <span className="hf-pill terra" style={{ height: 24 }}>深度匹配 ✓</span>}
        {!deep && (
          <span title="便宜的快速匹配分 · 综合赛道匹配 / 新鲜度 / 平台梯队，先覆盖全部在招；点「深挖」再跑深度匹配"
            style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, borderRadius: 999, cursor: 'help', font: '600 11px var(--font-sans)', color: 'var(--stone)', boxShadow: '0 0 0 1px var(--border-strong)' }}>?</span>
        )}
      </div>

      {deep && (
        <div className="hf-slide" style={{ marginTop: 11, paddingTop: 11, borderTop: '1px dashed var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="hf-overline" style={{ color: 'var(--terracotta-strong)' }}>深度匹配 · 4 个理由</div>
          {anchors.map(([k, v], i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{ flex: 'none', minWidth: 58, textAlign: 'center', font: '600 10.5px var(--font-sans)', color: 'var(--charcoal)', background: 'var(--library-rail)', borderRadius: 6, padding: '4px 6px', boxShadow: '0 0 0 1px var(--border-warm)' }}>{k}</span>
              <div style={{ font: '400 12px var(--font-sans)', color: 'var(--ink-soft)', lineHeight: 1.55, flex: 1 }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button className="hf-btn ghost sm" style={{ flex: 1 }} onClick={() => onIntel(job)}>🏢 讲讲这家</button>
        {deep ? (
          <button className="hf-btn sand sm" style={{ flex: 1 }} disabled>已深挖 ✓</button>
        ) : deepening ? (
          <button className="hf-btn primary sm" style={{ flex: 1.3, opacity: 0.85 }} disabled>
            <span className="hf-spin" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.4)', borderTopWidth: 2 }} /> 深挖中…
          </button>
        ) : (
          <button className="hf-btn primary sm" style={{ flex: 1.3 }} onClick={() => onDeepen(job)}>深挖这个岗 →</button>
        )}
      </div>
    </div>
  );
}

function FeedPane({ feed, wq, deepened, deepening, onDeepen, onIntel, onLock, locked, onRemoveAdd, onClearOnly, onClose }) {
  return (
    <div style={{ borderLeft: '1px solid var(--border)', background: 'var(--parchment)', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      {/* header + working query */}
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', background: 'var(--ivory)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 11 }}>
          <span style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>岗位匹配</span>
          <span style={{ font: '400 12px var(--font-sans)', color: 'var(--stone)' }}>按你的 投研 · 券商资管 · {feed.length} 个在招</span>
          <span style={{ marginLeft: 'auto' }} />
          {locked
            ? <span className="hf-pill emerald" style={{ height: 30 }}>✓ 已锁定为主方向</span>
            : <button className="hf-btn ghost sm" onClick={onLock} style={{ boxShadow: '0 0 0 1px var(--terracotta-ring)', color: 'var(--terracotta-strong)' }}>锁定为主方向 →</button>}
          {onClose && <button onClick={onClose} title="关掉 · 回到全宽对话" style={{ width: 28, height: 28, flex: 'none', borderRadius: 8, display: 'grid', placeItems: 'center', color: 'var(--stone)', cursor: 'pointer', boxShadow: '0 0 0 1px var(--border-warm)' }}>{(window.I.close)(14)}</button>}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ font: '600 10px var(--font-sans)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--stone)', marginRight: 2 }}>当前方向</span>
          {wq.seed.map((s) => <QueryChip key={s} kind="seed">{s}</QueryChip>)}
          {wq.add.map((s) => <QueryChip key={s} kind="add" onX={() => onRemoveAdd(s)}>{s}</QueryChip>)}
          {wq.exclude.map((s) => <QueryChip key={s} kind="excl">{s}</QueryChip>)}
          {wq.only && (
            <span onClick={onClearOnly} title="点开放开" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5, height: 26, padding: '0 10px', borderRadius: 999, font: '600 12px var(--font-sans)', background: 'var(--deep-dark)', color: 'var(--ivory)' }}>
              仅看 {wq.only}<span style={{ opacity: 0.55, fontSize: 13 }}>×</span>
            </span>
          )}
          <span style={{ marginLeft: 'auto', font: '500 11px var(--font-mono)', color: 'var(--muted)' }}>
            排序：{wq.sort === 'pay' ? '薪资 ▾' : wq.sort === 'fresh' ? '新鲜度 ▾' : '匹配 ▾'}
          </span>
        </div>
      </div>

      {/* list */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 11 }}>
        {feed.map((job, i) => (
          <JobCard key={job.id} job={job} rank={i + 1} deep={deepened.has(job.id)} deepening={deepening === job.id}
            onDeepen={onDeepen} onIntel={onIntel} />
        ))}
        {feed.length === 0 && (
          <div style={{ textAlign: 'center', padding: '28px 16px', color: 'var(--muted)' }}>
            <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)', marginBottom: 6 }}>这方向库里暂无在招</div>
            <div style={{ font: '400 12.5px var(--font-sans)', lineHeight: 1.6 }}>要不要看相邻方向，或放宽地点？绝不静默空白。</div>
          </div>
        )}
      </div>
    </div>
  );
}

window.NLFeed = { FeedPane, JobCard, QueryChip };
