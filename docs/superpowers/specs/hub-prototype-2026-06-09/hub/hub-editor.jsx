// hub/hub-editor.jsx — 简历编辑器 · 全屏接管（从「简历优化」点「展开编辑器」进入）
//   独立页观感：顶栏 + 三栏（左 模板/编辑/布局 · 中 WYSIWYG · 右 AI 简历助手 v2）
/* global React, window */
const { useState: useED, useMemo: useEDMemo } = React;
const DICO = window.I;

const expandInIcon = (s = 13) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 9L4 4m0 0v5m0-5h5M15 15l5 5m0 0v-5m0 5h-5" />
  </svg>
);

// ===== 简历数据模型 ===================================================
const INITIAL_RESUME = {
  name: '陈一帆',
  contact: ['上海 · 可立即到岗', '178-0000-0000', 'chenyf@fudan.edu.cn'],
  sections: [
    { id: 'intro', title: '个人介绍', bullets: ['金融硕士在读，关注量化研究方向，熟悉数据处理与回测流程，学习能力强。'] },
    { id: 'edu', title: '教育经历', head: '复旦大学 · 金融学 硕士', meta: '2024.09 – 2027.06 · 上海',
      bullets: ['GPA 3.8 / 4.0 · 专业前 10%', '核心课程：随机过程、资产定价、计量经济学、机器学习'] },
    { id: 'intern', title: '实习经历', head: '九坤投资 · 量化研究实习', meta: '2024.06 – 2024.09 · 北京',
      bullets: ['协助搭建多因子回测框架，参与日频数据清洗与对齐', '负责单因子有效性检验，整理因子库文档'] },
    { id: 'project', title: '项目经历', head: '校园量化策略研究', meta: '2023.10 – 2024.03',
      bullets: ['基于公开行情构建动量与反转策略，完成样本外回测', '撰写策略研究报告，复盘归因与回撤控制'] },
    { id: 'skill', title: '掌握技能',
      bullets: ['Python（pandas / numpy / backtrader）· SQL · Git', '英语 CET-6 · 可英文工作'] },
  ],
};

// ===== WYSIWYG A4 =====================================================
function A4Doc({ resume, lit }) {
  return (
    <div style={{ background: '#fff', width: 480, padding: '40px 46px', boxSizing: 'border-box', borderRadius: 4,
      boxShadow: '0 0 0 1px var(--border-warm), 0 16px 44px rgba(0,0,0,0.10)' }}>
      <div style={{ borderBottom: '2px solid var(--ink)', paddingBottom: 14, marginBottom: 18 }}>
        <div style={{ font: '600 26px/1 var(--font-sans)', color: 'var(--ink)', marginBottom: 10, letterSpacing: '-0.01em' }}>{resume.name}</div>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', font: '400 11px var(--font-sans)', color: 'var(--olive)' }}>
          {resume.contact.map((c, i) => <span key={i} style={{ whiteSpace: 'nowrap' }}>{c}</span>)}
        </div>
      </div>
      {resume.sections.map((s) => {
        const on = lit === s.id;
        return (
          <div key={s.id} style={{ marginBottom: 20, background: on ? 'var(--terracotta-wash)' : 'transparent', borderRadius: on ? 8 : 0,
            margin: on ? '0 -12px 20px' : '0 0 20px', padding: on ? '11px 12px' : 0, boxShadow: on ? '0 0 0 1.5px var(--terracotta)' : 'none', transition: 'box-shadow .2s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
              <span style={{ font: '600 12px/1 var(--font-sans)', color: 'var(--ink-soft)', letterSpacing: '0.06em' }}>{s.title}</span>
              <span style={{ flex: 1, height: 1, background: 'var(--border-warm)' }} />
              {on && <span style={{ font: '600 9px var(--font-sans)', color: '#fff', background: 'var(--terracotta)', borderRadius: 999, padding: '2px 8px' }}>AI 刚写回</span>}
            </div>
            {s.head && (
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                <span style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', whiteSpace: 'nowrap' }}>{s.head}</span>
                <span style={{ font: '400 10.5px var(--font-mono)', color: 'var(--stone)', whiteSpace: 'nowrap', flex: 'none' }}>{s.meta}</span>
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {s.bullets.map((b, i) => (
                <div key={i} style={{ display: 'flex', gap: 7, font: '400 11.5px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}>
                  {s.head && <span style={{ color: 'var(--stone)', flex: 'none' }}>•</span>}<span>{b}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ===== LEFT 三个 tab ==================================================
const MODULES = ['基本信息', '个人介绍', '教育经历', '实习经历', '项目经历', '掌握技能'];

function LeftTemplate() {
  const tpls = [['素白单栏', 0], ['蓝栏双侧', 1], ['深首横幅', 2], ['墨绿弧顶', 3], ['浅青色块', 4]];
  const [sel, setSel] = useED(0);
  const mini = (i) => {
    if (i === 1) return <div style={{ display: 'flex', gap: 4, height: '100%' }}><div style={{ width: '34%', background: 'var(--ring-warm)', borderRadius: 2 }} /><div style={{ flex: 1 }}>{[88, 70, 80, 64, 76].map((w, k) => <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />)}</div></div>;
    if (i === 2) return <div style={{ height: '100%' }}><div style={{ height: 16, background: 'var(--ink-soft)', borderRadius: 2, marginBottom: 6 }} />{[100, 84, 92, 60].map((w, k) => <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />)}</div>;
    if (i === 3) return <div style={{ height: '100%' }}><div style={{ height: 18, background: 'var(--ring-warm)', borderRadius: '0 0 16px 16px', marginBottom: 6 }} />{[100, 84, 92, 56].map((w, k) => <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />)}</div>;
    if (i === 4) return <div style={{ height: '100%' }}><div style={{ height: 8, width: '52%', background: 'var(--terracotta-wash)', borderRadius: 2, marginBottom: 6, boxShadow: '0 0 0 1px #eccfb6' }} />{[100, 84, 92, 58].map((w, k) => <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />)}</div>;
    return <div style={{ height: '100%' }}><div style={{ width: '44%', height: 6, background: 'var(--ink-soft)', borderRadius: 2, marginBottom: 4 }} /><div style={{ height: 1, background: 'var(--ring-warm)', margin: '3px 0 6px' }} />{[100, 84, 92, 60].map((w, k) => <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />)}</div>;
  };
  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 0' }}>
      <span className="hf-pill" style={{ height: 24, marginBottom: 12 }}>5 个模板 · 默认素白单栏（纯净无色）</span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
        {tpls.map(([t, i]) => (
          <button key={i} onClick={() => setSel(i)} style={{ textAlign: 'left', borderRadius: 10, padding: 7, cursor: 'pointer',
            background: sel === i ? 'var(--terracotta-wash)' : 'var(--ivory)', boxShadow: sel === i ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1px var(--border-warm)' }}>
            <div style={{ height: 86, borderRadius: 5, background: '#fff', boxShadow: '0 0 0 1px var(--border-warm)', padding: 7, marginBottom: 7, overflow: 'hidden' }}>{mini(i)}</div>
            <div style={{ font: `${sel === i ? 600 : 500} 11px var(--font-sans)`, color: sel === i ? 'var(--terracotta-strong)' : 'var(--olive)', textAlign: 'center' }}>{t}</div>
          </button>
        ))}
        <div style={{ borderRadius: 10, boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed', display: 'grid', placeItems: 'center', font: '500 10.5px/1.4 var(--font-sans)', color: 'var(--stone)', textAlign: 'center', padding: 6 }}>全无照片 · 金融极简</div>
      </div>
    </div>
  );
}

function LeftEdit({ resume, onQuote }) {
  const intern = resume.sections.find((s) => s.id === 'intern');
  const [open, setOpen] = useED('intern');
  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 0' }}>
      <span className="hf-pill" style={{ height: 24, marginBottom: 10, whiteSpace: 'nowrap' }}>就地编辑 · 分模块</span>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* 展开的 实习经历 */}
        <div style={{ borderRadius: 12, background: 'var(--ivory)', boxShadow: '0 0 0 1px var(--terracotta-ring)', padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
            <span style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', whiteSpace: 'nowrap' }}>实习经历 · 就地编辑</span>
            <span style={{ marginLeft: 'auto', color: 'var(--stone)', display: 'inline-flex' }}>{DICO.chevron(13)}</span>
          </div>
          <div style={{ font: '600 11.5px var(--font-sans)', color: 'var(--ink-soft)', marginBottom: 8 }}>{intern.head}</div>
          {intern.bullets.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border-cream)' }}>
              <span style={{ color: 'var(--warm-silver)', fontSize: 12, lineHeight: '16px' }}>•</span>
              <div style={{ flex: 1, font: '400 11px/1.55 var(--font-sans)', color: 'var(--ink-soft)' }}>{b}</div>
              <button onClick={() => onQuote('intern')} style={{ flex: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, font: '500 10px var(--font-sans)', color: 'var(--terracotta-strong)', background: 'var(--terracotta-wash)', boxShadow: '0 0 0 1px #eccfb6', borderRadius: 7, padding: '3px 7px', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                {DICO.quote(11)} 引用此段
              </button>
            </div>
          ))}
        </div>
        {/* 其余模块折叠条 */}
        {MODULES.filter((m) => m !== '实习经历').map((m, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', borderRadius: 10, background: 'var(--ivory)', boxShadow: '0 0 0 1px var(--border-warm)', padding: '10px 12px', cursor: 'pointer' }}>
            <span style={{ font: '500 12px var(--font-sans)', color: 'var(--ink-soft)' }}>{m}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--warm-silver)', display: 'inline-flex' }}>{DICO.chevron(13)}</span>
          </div>
        ))}
        <div style={{ borderRadius: 10, boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed', padding: '10px', font: '500 12px var(--font-sans)', color: 'var(--stone)', textAlign: 'center' }}>+ 自定义模块（证书 / 社团 / 作品…）</div>
      </div>
    </div>
  );
}

function LeftLayout({ overflow }) {
  const sliders = [['字号', 0.5], ['行高', 0.62], ['页边距', 0.4], ['模块间距', 0.55]];
  const [hidden, setHidden] = useED(() => new Set(['个人介绍']));
  const toggle = (m) => setHidden((s) => { const n = new Set(s); n.has(m) ? n.delete(m) : n.add(m); return n; });
  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 0' }}>
      {overflow && (
        <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start', background: 'var(--amber-bg)', boxShadow: '0 0 0 1px #ecdfa4', borderRadius: 11, padding: 11, marginBottom: 14 }}>
          <span style={{ font: '600 11px var(--font-mono)', color: 'var(--amber-fg)', boxShadow: '0 0 0 1px #ecdfa4', borderRadius: 6, padding: '2px 7px', background: 'var(--ivory)', flex: 'none' }}>2 页</span>
          <div style={{ font: '400 11px/1.5 var(--font-sans)', color: 'var(--amber-fg)' }}>当前超过 1 页 · 仅提醒，不自动缩排。下调字号或页边距，或隐藏次要模块。</div>
        </div>
      )}
      <span className="hf-pill" style={{ height: 24, marginBottom: 12 }}>排版滑块</span>
      <div style={{ marginTop: 12 }}>
        {sliders.map(([l, v], i) => (
          <div key={i} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', font: '500 11.5px var(--font-sans)', color: 'var(--ink-soft)', marginBottom: 7 }}><span>{l}</span></div>
            <div style={{ position: 'relative', height: 4, background: 'var(--library-rail)', borderRadius: 999, boxShadow: '0 0 0 1px var(--border-warm)' }}>
              <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${v * 100}%`, background: 'var(--terracotta)', borderRadius: 999 }} />
              <div style={{ position: 'absolute', left: `calc(${v * 100}% - 7px)`, top: -5, width: 14, height: 14, borderRadius: 999, background: '#fff', boxShadow: '0 0 0 1.5px var(--terracotta), 0 1px 3px rgba(0,0,0,0.15)' }} />
            </div>
          </div>
        ))}
      </div>
      <span className="hf-pill" style={{ height: 24, margin: '6px 0 10px' }}>模块显示 / 隐藏</span>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 3 }}>
        {MODULES.map((m, i) => {
          const off = hidden.has(m);
          return (
            <button key={i} onClick={() => toggle(m)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 6px', borderRadius: 8, cursor: 'pointer', background: 'transparent', textAlign: 'left' }}>
              <span style={{ width: 16, height: 16, flex: 'none', borderRadius: 5, display: 'grid', placeItems: 'center', color: '#fff',
                background: off ? 'var(--ivory)' : 'var(--terracotta)', boxShadow: off ? '0 0 0 1.5px var(--border-strong)' : '0 0 0 1px var(--terracotta)' }}>{!off && DICO.check(11)}</span>
              <span style={{ font: '500 12px var(--font-sans)', color: off ? 'var(--stone)' : 'var(--ink-soft)' }}>{m}</span>
              {off && <span style={{ marginLeft: 'auto', font: '400 10px var(--font-sans)', color: 'var(--stone)' }}>已隐藏</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ===== ResumeEditor 全屏壳 ===========================================
function ResumeEditor({ onClose }) {
  const [leftTab, setLeftTab] = useED('edit');
  const [resume, setResume] = useED(INITIAL_RESUME);
  const [lit, setLit] = useED(null);
  // 右栏 AI 受控态
  const [aiTab, setAiTab] = useED('score');
  const [seed, setSeed] = useED(null);
  const [activeGap, setActiveGap] = useED(null);

  const GAPS = window.ED_GAPS || [];

  function optimize(gap) {
    setActiveGap(gap.id);
    setSeed({ gap, nonce: Date.now() });
    setAiTab('deep');
  }
  function quote(sectionId) {
    const gap = GAPS.find((g) => g.id === sectionId);
    if (gap) optimize(gap);
  }
  function writeBack(sectionId, newBullets) {
    setResume((r) => ({ ...r, sections: r.sections.map((s) => s.id === sectionId ? { ...s, bullets: newBullets } : s) }));
    setLit(sectionId);
  }

  const L_TABS = [['tpl', '模板'], ['edit', '简历编辑'], ['layout', '布局']];
  return (
    <div className="hf hub-editor-in" style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'var(--parchment)', display: 'flex', flexDirection: 'column' }}>
      {/* 顶栏 */}
      <div style={{ height: 52, flex: 'none', background: 'var(--ivory)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', padding: '0 18px', gap: 12 }}>
        <window.HFLogo size="sm" />
        <span style={{ color: 'var(--warm-silver)' }}>/</span>
        <span style={{ font: '500 13px var(--font-sans)', color: 'var(--ink-soft)' }}>简历编辑器</span>
        <span className="hf-pill" style={{ height: 24, marginLeft: 2 }}>中文主版</span>
        <button onClick={onClose} className="hf-btn ghost sm" style={{ marginLeft: 'auto', gap: 6 }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M15 6l-6 6 6 6" /></svg>
          返回主工作台
        </button>
        <div style={{ width: 30, height: 30, borderRadius: 999, background: 'var(--terracotta)', color: '#fff', display: 'grid', placeItems: 'center', font: '600 13px var(--font-sans)' }}>陈</div>
      </div>

      {/* 三栏 */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '296px minmax(0,1fr) 396px', minHeight: 0 }}>
        {/* LEFT */}
        <div style={{ borderRight: '1px solid var(--border)', background: 'var(--ivory)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ padding: '12px 14px 0', flex: 'none' }}>
            <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 11, boxShadow: '0 0 0 1px var(--border-warm)' }}>
              {L_TABS.map(([k, t]) => (
                <button key={k} onClick={() => setLeftTab(k)} style={{ flex: 1, textAlign: 'center', cursor: 'pointer', font: `${leftTab === k ? 600 : 500} 12px var(--font-sans)`, padding: '6px 0', borderRadius: 8, color: leftTab === k ? 'var(--ink)' : 'var(--olive)', background: leftTab === k ? 'var(--ivory)' : 'transparent', boxShadow: leftTab === k ? '0 0 0 1px var(--border-strong)' : 'none' }}>{t}</button>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, minHeight: 0, padding: '12px 14px' }}>
            {leftTab === 'tpl' && <LeftTemplate />}
            {leftTab === 'edit' && <LeftEdit resume={resume} onQuote={quote} />}
            {leftTab === 'layout' && <LeftLayout overflow />}
          </div>
        </div>

        {/* CENTER — WYSIWYG */}
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--parchment)' }}>
          <div style={{ height: 46, flex: 'none', display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', borderBottom: '1px solid var(--border)', background: 'var(--ivory)' }}>
            <span className="hf-pill" style={{ height: 26, fontFamily: 'var(--font-mono)' }}>1 页</span>
            <span style={{ font: '500 12px var(--font-sans)', color: 'var(--olive)' }}>WYSIWYG · 所见即所导出</span>
            <span style={{ marginLeft: 'auto' }} />
            <button className="hf-btn ghost sm" style={{ gap: 6 }}>{DICO.save(13)} 保存</button>
            <button className="hf-btn dark sm" style={{ gap: 6 }}>{DICO.download(13)} 下载 PDF</button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '28px 0', display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
            <A4Doc resume={resume} lit={lit} />
          </div>
        </div>

        {/* RIGHT — AI 简历助手 v2 */}
        <window.EditorAIPanel resume={resume} onWriteBack={writeBack}
          tab={aiTab} setTab={setAiTab} seed={seed} activeGap={activeGap} onOptimize={optimize} />
      </div>
    </div>
  );
}

Object.assign(window, { ResumeEditor });
