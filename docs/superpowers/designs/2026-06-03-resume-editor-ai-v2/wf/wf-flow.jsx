// wf-flow.jsx — Part 2 ② 深度优化(反问取证) + ③ 自由 chat + 串联流
/* global React, WF, WLine, WLines, WTag, WBtn, WChip, WTabs, WCard, WNote, WDot, WMeter */

// chat bubble
function Bubble({ ai, children, w = '86%' }) {
  return (
    <div style={{ display: 'flex', justifyContent: ai ? 'flex-start' : 'flex-end', marginBottom: 11 }}>
      <div style={{ maxWidth: w, font: `400 12px/1.6 ${WF.sans}`,
        background: ai ? WF.fill : WF.dark, color: ai ? WF.ink2 : '#fff',
        border: ai ? `1px solid ${WF.line}` : 'none',
        borderRadius: ai ? '4px 13px 13px 13px' : '13px 4px 13px 13px', padding: '10px 12px' }}>
        {children}
      </div>
    </div>
  );
}

function Composer({ chips, active, placeholder }) {
  return (
    <div style={{ padding: 13, borderTop: `1px solid ${WF.line}`, background: WF.paper }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 9 }}>
        {chips.map((c, i) => <WChip key={i} active={i === active}>{c}</WChip>)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, border: `1px solid ${WF.line2}`, borderRadius: 12, padding: '10px 12px', background: WF.fill }}>
        <span style={{ font: `400 12px ${WF.sans}`, color: WF.faint, flex: 1 }}>{placeholder}</span>
        <span style={{ width: 26, height: 26, borderRadius: 8, background: WF.dark, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>↑</span>
      </div>
    </div>
  );
}

// ---- ② 深度优化 (反问取证) ---------------------------------------------

function DeepOptimizePanel() {
  return (
    <div style={{ width: 408, height: 760, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 16, font: WF.sans, color: WF.ink, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '13px 16px', borderBottom: `1px solid ${WF.line}`, display: 'flex', alignItems: 'center', gap: 9 }}>
        <WDot s={26} label="AI" />
        <div style={{ font: `600 13px ${WF.sans}` }}>深度优化</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <WChip>打分</WChip><WChip active>深度优化</WChip><WChip>自由问</WChip>
        </div>
      </div>

      {/* locked target bar */}
      <div style={{ padding: '11px 16px', borderBottom: `1px solid ${WF.line}`, background: WF.fill, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ font: `500 10px ${WF.sans}`, color: WF.faint, letterSpacing: '0.08em' }}>锁定经历</span>
        <span style={{ font: `600 11.5px ${WF.sans}`, color: WF.ink, background: WF.paper, border: `1px solid ${WF.line2}`, borderRadius: 999, padding: '4px 10px' }}>九坤投资 · 量化研究实习</span>
        <span style={{ font: `500 11.5px ${WF.sans}`, color: WF.ink2, border: `1px dashed ${WF.line2}`, borderRadius: 999, padding: '4px 10px' }}>目标：量化私募·研究 ✎</span>
      </div>

      {/* conversation */}
      <div style={{ flex: 1, padding: '14px 16px', overflow: 'hidden' }}>
        <Bubble ai>第一句先对齐：这段经历是要往 <b>量化私募 · 研究</b> 改吗？还是更偏 IB / 投研其它方向？</Bubble>
        <Bubble>对，量化私募研究方向。</Bubble>
        <Bubble ai>好。打分里这段 <b>STAR 缺 Result</b>：你“协助搭建因子回测框架”，最后这个框架真实跑出了什么结果？比如覆盖多少因子、回测了哪段区间、有没有指标变化？</Bubble>
        {/* evidence captured */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
          <div style={{ maxWidth: '86%', background: WF.dark, color: '#fff', borderRadius: '13px 4px 13px 13px', padding: '10px 12px', font: `400 12px/1.6 ${WF.sans}` }}>
            框架最后覆盖约 40 个量价因子，回测了 2021–2023，把单因子筛选从手动跑变成一键批量。
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <span style={{ font: `500 9.5px ${WF.sans}`, color: WF.meta, background: WF.metaBg, border: `1px solid ${WF.meta}33`, borderRadius: 999, padding: '2px 8px' }}>✓ 已写入事实账本 · 3-anchor</span>
        </div>
        <Bubble ai>再追一句可防守性：面试官如果问“你说一键批量，你具体写了哪部分？” 你怎么答？</Bubble>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: WF.faint, font: `400 11px ${WF.sans}`, paddingLeft: 4 }}>
          <span style={{ font: `13px ${WF.mono}` }}>✶</span> 代理思考中 · 等你的真实细节…
        </div>
      </div>

      {/* rewrite result preview */}
      <div style={{ borderTop: `1px solid ${WF.line}`, padding: '12px 16px', background: WF.fill }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
          <WTag style={{ marginBottom: 0 }}>定制改写 · 待你确认后写回简历</WTag>
          <span style={{ marginLeft: 'auto', font: `500 9.5px ${WF.sans}`, color: WF.muted, border: `1px solid ${WF.line2}`, borderRadius: 999, padding: '2px 7px' }}>编数字红线 ✓</span>
          <span style={{ font: `500 9.5px ${WF.sans}`, color: WF.muted, border: `1px solid ${WF.line2}`, borderRadius: 999, padding: '2px 7px' }}>证据门 ✓</span>
        </div>
        <WCard pad={11} style={{ borderRadius: 11 }}>
          <div style={{ font: `400 11.5px/1.6 ${WF.sans}`, color: WF.ink2 }}>
            搭建覆盖 <b>40+ 量价因子</b>的回测框架（<b>2021–2023</b>），将单因子筛选由手动改为一键批量，显著缩短迭代周期。
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <WBtn sm solid style={{ fontSize: 11 }}>写回简历</WBtn>
            <WBtn sm style={{ fontSize: 11 }}>再改一版</WBtn>
          </div>
        </WCard>
      </div>

      <Composer chips={['深度搜索', '职位推荐', '简历优化', '职场体验']} active={2} placeholder="回答 AI 的反问，或继续追问…" />
    </div>
  );
}

// ---- ③ 自由 chat -------------------------------------------------------

function FreeChatPanel() {
  return (
    <div style={{ width: 408, height: 560, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 16, font: WF.sans, color: WF.ink, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '13px 16px', borderBottom: `1px solid ${WF.line}`, display: 'flex', alignItems: 'center', gap: 9 }}>
        <WDot s={26} label="AI" />
        <div style={{ font: `600 13px ${WF.sans}` }}>自由问</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <WChip>打分</WChip><WChip>深度优化</WChip><WChip active>自由问</WChip>
        </div>
      </div>
      <div style={{ flex: 1, padding: '14px 16px', overflow: 'hidden' }}>
        <Bubble>我适合投量化私募还是券商投研?</Bubble>
        <Bubble ai>从你简历看，量化背景（因子回测、Python）更贴量化私募；券商投研更看行业研究深度。要我按这两条赛道分别打分对比吗?</Bubble>
        <Bubble>这段实习还能怎么写得更像主导?</Bubble>
        <Bubble ai>能。但“主导”得有事实支撑——直接去 <b>深度优化</b> 把你真实负责的部分问出来，我不会凭空把“协助”改成“主导”。</Bubble>
      </div>
      <Composer chips={['深度搜索', '职位推荐', '简历优化', '职场体验']} active={-1} placeholder="随便问：这段怎么写 / 我适合哪个赛道…" />
    </div>
  );
}

// ---- 串联流 (overview strip) -------------------------------------------

function FlowStrip() {
  const steps = [
    ['进入「简历优化」', '自动带出目标 subcat（可改）'],
    ['① 打分', '整份雷达 + 逐段缺口（诚实分，不改简历）'],
    ['点某段缺口', '「去深度优化」'],
    ['② 深度优化', '确认 subcat → 流式反问取证 → 定制改写'],
    ['写回 profile', '中栏预览实时刷新 → 可重新打分看提升'],
  ];
  return (
    <div style={{ width: 1180, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 16, padding: 22, font: WF.sans, color: WF.ink }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <span style={{ font: `600 14px ${WF.sans}` }}>三能力串联流</span>
        <span style={{ font: `400 12px ${WF.sans}`, color: WF.muted }}>打分 → 深度优化 串联，自由 chat 随时可走</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>
        {steps.map((s, i) => (
          <React.Fragment key={i}>
            <div style={{ flex: 1, border: `1px solid ${i % 2 ? WF.line2 : WF.line}`, borderRadius: 12, padding: '13px 14px', background: i % 2 ? WF.fill : WF.paper }}>
              <div style={{ font: `600 10px ${WF.mono}`, color: WF.faint, marginBottom: 7 }}>{String(i + 1).padStart(2, '0')}</div>
              <div style={{ font: `600 12.5px ${WF.sans}`, color: WF.ink, marginBottom: 5 }}>{s[0]}</div>
              <div style={{ font: `400 11px/1.5 ${WF.sans}`, color: WF.muted }}>{s[1]}</div>
            </div>
            {i < steps.length - 1 && <div style={{ alignSelf: 'center', color: WF.ghost, font: '600 18px sans-serif', padding: '0 6px' }}>→</div>}
          </React.Fragment>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 16, font: `500 11.5px ${WF.sans}`, color: WF.meta, background: WF.metaBg, border: `1px dashed ${WF.meta}`, borderRadius: 10, padding: '9px 12px' }}>
        <span style={{ fontWeight: 700 }}>核心契约</span> 打分老实反映现状，绝不靠 AI 补内容刷分；提分只能靠深度优化把学生真实细节反问出来再改。
      </div>
    </div>
  );
}

Object.assign(window, { DeepOptimizePanel, FreeChatPanel, FlowStrip });
