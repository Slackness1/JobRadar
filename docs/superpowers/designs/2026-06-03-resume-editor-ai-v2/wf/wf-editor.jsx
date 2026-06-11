// wf-editor.jsx — Part 1 简历编辑页:三栏框架 + 左栏三个 tab 展开
/* global React, WF, WLine, WLines, WTag, WBtn, WChip, WTabs, WCard, WNote, WDot */

// ---- shared bits -------------------------------------------------------

function ColHead({ children }) {
  return <div style={{ font: `600 12.5px/1 ${WF.sans}`, color: WF.ink, marginBottom: 12 }}>{children}</div>;
}

// A4 resume skeleton used in the center preview
function A4Resume({ scale = 1 }) {
  return (
    <div style={{ background: '#fff', width: 360, padding: '26px 30px', boxSizing: 'border-box',
      boxShadow: '0 0 0 1px #e8e6dc, 0 12px 34px rgba(0,0,0,.08)', borderRadius: 3 }}>
      {/* name header */}
      <div style={{ borderBottom: `2px solid ${WF.ink}`, paddingBottom: 10, marginBottom: 12 }}>
        <div style={{ font: `600 19px/1 ${WF.sans}`, color: WF.ink, marginBottom: 8 }}>陈一帆</div>
        <div style={{ display: 'flex', gap: 14 }}>
          <WLine w={70} h={5} mb={0} /><WLine w={86} h={5} mb={0} /><WLine w={54} h={5} mb={0} />
        </div>
      </div>
      {['教育经历', '实习经历', '项目经历', '掌握技能'].map((s, i) => (
        <div key={i} style={{ marginBottom: 14 }}>
          <div style={{ font: `600 11px/1 ${WF.sans}`, color: WF.ink2, letterSpacing: '0.04em', marginBottom: 8 }}>{s}</div>
          <WLines rows={i === 3 ? 2 : 3} last={i === 1 ? '78%' : '60%'} h={5} gap={6} c={WF.line} />
        </div>
      ))}
    </div>
  );
}

// ---- ① full 3-column editor frame --------------------------------------

function EditorFrame() {
  return (
    <div style={{ width: 1180, height: 740, background: WF.fill, display: 'flex', flexDirection: 'column',
      font: WF.sans, color: WF.ink }}>
      {/* app top bar */}
      <div style={{ height: 48, flex: 'none', background: WF.paper, borderBottom: `1px solid ${WF.line}`,
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 12 }}>
        <span style={{ font: `700 15px ${WF.sans}`, letterSpacing: '-0.02em' }}>JobRadar</span>
        <span style={{ color: WF.ghost }}>/</span>
        <span style={{ font: `500 13px ${WF.sans}`, color: WF.muted }}>简历编辑器</span>
        <span style={{ marginLeft: 'auto' }} />
        <WBtn ghost sm>主工作台</WBtn>
        <WDot s={26} label="陈" />
      </div>

      {/* 3 columns */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '300px 1fr 380px', minHeight: 0 }}>
        {/* LEFT */}
        <div style={{ borderRight: `1px solid ${WF.line}`, background: WF.paper, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <WTabs items={['简历模版', '简历编辑', '页面布局']} active={1} />
          <div style={{ overflow: 'hidden' }}>
            <WTag style={{ marginBottom: 8 }}>就地编辑 · 分模块</WTag>
            {['基本信息', '个人介绍', '教育经历', '实习经历', '项目经历', '掌握技能'].map((m, i) => (
              <div key={i} style={{ border: `1px solid ${i === 3 ? WF.line2 : WF.line}`, borderRadius: 10, padding: 10, marginBottom: 8,
                background: i === 3 ? WF.fill : WF.paper }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: i === 3 ? 8 : 0 }}>
                  <span style={{ font: `600 12px ${WF.sans}`, color: WF.ink }}>{m}</span>
                  {i === 3 && <span style={{ font: `500 10px ${WF.sans}`, color: WF.muted, marginLeft: 'auto' }}>展开编辑 ▾</span>}
                </div>
                {i === 3 && <WLines rows={2} last="70%" h={6} c={WF.line} />}
              </div>
            ))}
            <div style={{ border: `1px dashed ${WF.line2}`, borderRadius: 10, padding: '9px 10px', font: `500 12px ${WF.sans}`, color: WF.muted, textAlign: 'center' }}>+ 自定义模块（证书 / 社团 / 作品…）</div>
          </div>
        </div>

        {/* CENTER */}
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ height: 44, flex: 'none', display: 'flex', alignItems: 'center', gap: 10, padding: '0 16px', borderBottom: `1px solid ${WF.line}`, background: WF.fill }}>
            <span style={{ font: `600 11px ${WF.mono}`, color: WF.ink2, border: `1px solid ${WF.line2}`, borderRadius: 999, padding: '3px 9px', background: WF.paper }}>1 页</span>
            <span style={{ font: `500 12px ${WF.sans}`, color: WF.muted }}>WYSIWYG 预览 · 所见即所导出</span>
            <span style={{ marginLeft: 'auto' }} />
            <WBtn sm>保存</WBtn>
            <WBtn sm solid>下载 PDF</WBtn>
          </div>
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', justifyContent: 'center', paddingTop: 26, background: WF.fill }}>
            <A4Resume />
          </div>
        </div>

        {/* RIGHT */}
        <div style={{ borderLeft: `1px solid ${WF.line}`, background: WF.paper, display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 16px', borderBottom: `1px solid ${WF.line}`, display: 'flex', alignItems: 'center', gap: 9 }}>
            <WDot s={26} label="AI" />
            <div>
              <div style={{ font: `600 13px ${WF.sans}` }}>AI 简历助手 v2</div>
              <div style={{ font: `400 10.5px ${WF.sans}`, color: WF.faint }}>诚实打分 · 反问取证</div>
            </div>
          </div>
          <div style={{ padding: '12px 16px', display: 'flex', gap: 7, borderBottom: `1px solid ${WF.line}` }}>
            <WChip active>简历打分</WChip><WChip>深度优化</WChip><WChip>自由问</WChip>
          </div>
          <div style={{ flex: 1, padding: 16, overflow: 'hidden' }}>
            <WCard pad={13} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ font: `600 30px ${WF.mono}`, color: WF.ink }}>72</span>
                <span style={{ font: `500 12px ${WF.sans}`, color: WF.muted }}>现状分</span>
                <span style={{ marginLeft: 'auto', font: `600 12px ${WF.mono}`, color: WF.ink2, border: `1px dashed ${WF.line2}`, borderRadius: 999, padding: '3px 9px' }}>潜力 80–85</span>
              </div>
              <div style={{ font: `400 10.5px ${WF.sans}`, color: WF.faint, marginTop: 6 }}>目标赛道：量化私募 · 研究 ▾</div>
            </WCard>
            <WTag style={{ marginBottom: 8 }}>逐段缺口</WTag>
            {['九坤实习：STAR 缺 Result', '校园项目：成果无量化锚点'].map((g, i) => (
              <div key={i} style={{ border: `1px solid ${WF.line}`, borderRadius: 11, padding: 11, marginBottom: 8 }}>
                <div style={{ font: `500 12px ${WF.sans}`, color: WF.ink2, marginBottom: 7 }}>{g}</div>
                <WBtn sm style={{ fontSize: 11 }}>去深度优化这段 →</WBtn>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---- ② left tab: 简历模版 (detail) --------------------------------------

function LeftTabTemplate() {
  const tpls = ['经典单栏', '蓝色双栏侧边', '深色页眉横幅', '墨绿弧形页眉', '浅青色块高亮'];
  return (
    <div style={{ width: 300, height: 560, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 14, padding: 16, font: WF.sans, boxSizing: 'border-box' }}>
      <WTabs items={['简历模版', '简历编辑', '页面布局']} active={0} style={{ marginBottom: 14 }} />
      <WTag style={{ marginBottom: 10 }}>5 个模板 · 点选即换皮</WTag>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {tpls.map((t, i) => (
          <div key={i} style={{ border: `1.5px solid ${i === 0 ? WF.dark : WF.line2}`, borderRadius: 9, padding: 7, background: i === 0 ? WF.fill : WF.paper }}>
            <div style={{ height: 92, borderRadius: 4, background: '#fff', border: `1px solid ${WF.line}`, padding: 6, marginBottom: 6, overflow: 'hidden' }}>
              {/* mini template skeleton */}
              {i === 1
                ? <div style={{ display: 'flex', gap: 4, height: '100%' }}><div style={{ width: '34%', background: WF.line2, borderRadius: 2 }} /><div style={{ flex: 1 }}><WLine w="80%" h={4} c={WF.line2} mb={4} /><WLines rows={4} last="60%" h={3} gap={4} c={WF.line} /></div></div>
                : i === 2
                  ? <div style={{ height: '100%' }}><div style={{ height: 16, background: WF.ink2, borderRadius: 2, marginBottom: 5 }} /><WLines rows={5} last="55%" h={3} gap={4} c={WF.line} /></div>
                  : i === 3
                    ? <div style={{ height: '100%' }}><div style={{ height: 18, background: WF.line2, borderRadius: '0 0 16px 16px', marginBottom: 5 }} /><WLines rows={5} last="50%" h={3} gap={4} c={WF.line} /></div>
                    : i === 4
                      ? <div style={{ height: '100%' }}><div style={{ height: 8, width: '52%', background: WF.line2, borderRadius: 2, marginBottom: 5 }} /><WLines rows={5} last="58%" h={3} gap={4} c={WF.line} /></div>
                      : <div style={{ height: '100%' }}><WLine w="44%" h={6} c={WF.ink2} mb={5} /><div style={{ height: 1, background: WF.line2, margin: '2px 0 5px' }} /><WLines rows={5} last="60%" h={3} gap={4} c={WF.line} /></div>}
            </div>
            <div style={{ font: `${i === 0 ? 600 : 500} 11px ${WF.sans}`, color: i === 0 ? WF.ink : WF.muted, textAlign: 'center' }}>{t}</div>
          </div>
        ))}
        <div style={{ borderRadius: 9, border: `1px dashed ${WF.line2}`, display: 'flex', alignItems: 'center', justifyContent: 'center', font: `500 11px ${WF.sans}`, color: WF.faint }}>全无照片 · 金融极简</div>
      </div>
    </div>
  );
}

// ---- ③ left tab: 简历编辑 (detail, with 引用此段) -----------------------

function LeftTabEdit() {
  return (
    <div style={{ width: 300, height: 560, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 14, padding: 16, font: WF.sans, boxSizing: 'border-box' }}>
      <WTabs items={['简历模版', '简历编辑', '页面布局']} active={1} style={{ marginBottom: 14 }} />
      <div style={{ border: `1px solid ${WF.line2}`, borderRadius: 11, padding: 12, marginBottom: 10, background: WF.fill }}>
        <div style={{ font: `600 12px ${WF.sans}`, color: WF.ink, marginBottom: 9 }}>实习经历 · 就地编辑</div>
        <div style={{ font: `500 11px ${WF.sans}`, color: WF.ink2, marginBottom: 4 }}>九坤投资 · 量化研究实习</div>
        <WLine w="86%" h={6} c={WF.line2} mb={9} />
        {/* bullets each with 引用此段 */}
        {['协助搭建因子回测框架，处理…', '负责日频数据清洗与对齐…'].map((b, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 0', borderTop: `1px solid ${WF.line}` }}>
            <span style={{ color: WF.faint, lineHeight: '14px', fontSize: 12 }}>•</span>
            <div style={{ flex: 1 }}>
              <div style={{ font: `400 11px/1.5 ${WF.sans}`, color: WF.ink2 }}>{b}</div>
            </div>
            <span style={{ font: `500 10px ${WF.sans}`, color: WF.muted, border: `1px solid ${WF.line2}`, borderRadius: 6, padding: '2px 6px', whiteSpace: 'nowrap', flex: 'none' }}>引用此段</span>
          </div>
        ))}
      </div>
      {['基本信息', '个人介绍', '教育经历', '项目经历', '掌握技能'].map((m, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', border: `1px solid ${WF.line}`, borderRadius: 9, padding: '9px 11px', marginBottom: 7 }}>
          <span style={{ font: `500 12px ${WF.sans}`, color: WF.ink2 }}>{m}</span>
          <span style={{ marginLeft: 'auto', color: WF.faint, fontSize: 12 }}>▾</span>
        </div>
      ))}
      <div style={{ border: `1px dashed ${WF.line2}`, borderRadius: 9, padding: '9px 10px', font: `500 12px ${WF.sans}`, color: WF.muted, textAlign: 'center', marginTop: 3 }}>+ 自定义模块</div>
    </div>
  );
}

// ---- ④ left tab: 页面布局 (detail) -------------------------------------

function LeftTabLayout() {
  const sliders = [['字号', 0.5], ['行高', 0.62], ['页边距', 0.4], ['模块间距', 0.55]];
  const mods = ['基本信息', '个人介绍', '教育经历', '实习经历', '项目经历', '掌握技能'];
  return (
    <div style={{ width: 300, height: 560, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 14, padding: 16, font: WF.sans, boxSizing: 'border-box' }}>
      <WTabs items={['简历模版', '简历编辑', '页面布局']} active={2} style={{ marginBottom: 14 }} />
      {/* overflow alert */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', background: WF.fill2, border: `1px solid ${WF.line2}`, borderRadius: 10, padding: 10, marginBottom: 13 }}>
        <span style={{ font: `600 12px ${WF.mono}`, color: WF.ink2, border: `1px solid ${WF.line2}`, borderRadius: 6, padding: '1px 6px', background: WF.paper }}>2 页</span>
        <div style={{ font: `400 11px/1.5 ${WF.sans}`, color: WF.muted }}>当前超过 1 页 · 仅提醒，不自动缩排</div>
      </div>
      <WTag style={{ marginBottom: 9 }}>排版滑块</WTag>
      {sliders.map(([l, v], i) => (
        <div key={i} style={{ marginBottom: 12 }}>
          <div style={{ font: `500 11.5px ${WF.sans}`, color: WF.ink2, marginBottom: 6 }}>{l}</div>
          <div style={{ position: 'relative', height: 4, background: WF.fill2, borderRadius: 999 }}>
            <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${v * 100}%`, background: WF.line2, borderRadius: 999 }} />
            <div style={{ position: 'absolute', left: `calc(${v * 100}% - 7px)`, top: -5, width: 14, height: 14, borderRadius: 999, background: WF.paper, border: `1.5px solid ${WF.dark}` }} />
          </div>
        </div>
      ))}
      <WTag style={{ margin: '4px 0 9px' }}>模块显示 / 隐藏</WTag>
      {mods.map((m, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '6px 0' }}>
          <span style={{ width: 15, height: 15, borderRadius: 4, border: `1.5px solid ${i === 1 ? WF.line2 : WF.dark}`, background: i === 1 ? WF.paper : WF.dark, color: '#fff', font: '700 10px sans-serif', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{i === 1 ? '' : '✓'}</span>
          <span style={{ font: `500 12px ${WF.sans}`, color: i === 1 ? WF.faint : WF.ink2 }}>{m}</span>
          {i === 1 && <span style={{ marginLeft: 'auto', font: `400 10px ${WF.sans}`, color: WF.faint }}>已隐藏</span>}
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { EditorFrame, LeftTabTemplate, LeftTabEdit, LeftTabLayout });
