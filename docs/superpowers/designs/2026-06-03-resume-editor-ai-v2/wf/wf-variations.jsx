// wf-variations.jsx — 右栏三能力组织方案对比:A 顶部 Tab / B 流式串联 / C composer chip 驱动
/* global React, WF, WLine, WLines, WTag, WBtn, WChip, WTabs, WCard, WNote, WDot, WMeter */

const VW = 340, VH = 600;

function VShell({ children }) {
  return (
    <div style={{ width: VW, height: VH, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 16, font: WF.sans, color: WF.ink, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {children}
    </div>
  );
}
function VHead() {
  return (
    <div style={{ padding: '11px 14px', borderBottom: `1px solid ${WF.line}`, display: 'flex', alignItems: 'center', gap: 8, flex: 'none' }}>
      <WDot s={24} label="AI" />
      <div style={{ font: `600 12.5px ${WF.sans}` }}>AI 简历助手 v2</div>
    </div>
  );
}
function MiniMeter({ l, v }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ font: `500 11px ${WF.sans}`, color: WF.ink2 }}>{l}</span>
        <span style={{ font: `600 11px ${WF.mono}`, color: WF.ink }}>{v}</span>
      </div>
      <div style={{ height: 5, borderRadius: 999, background: WF.fill2 }}><div style={{ width: v + '%', height: '100%', background: WF.muted, borderRadius: 999 }} /></div>
    </div>
  );
}

// ---- A · 顶部 Tab 切换 (强分隔,一次一能力) ------------------------------
function VarTabs() {
  return (
    <VShell>
      <VHead />
      <div style={{ padding: '10px 14px', borderBottom: `1px solid ${WF.line}` }}>
        <WTabs items={['简历打分', '深度优化', '自由问']} active={0} style={{ width: '100%', display: 'flex' }} />
      </div>
      <div style={{ flex: 1, padding: 14, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 12 }}>
          <span style={{ font: `600 34px/0.9 ${WF.mono}` }}>72</span>
          <span style={{ font: `500 10.5px ${WF.sans}`, color: WF.muted, paddingBottom: 4 }}>现状分 · 潜力 80–85</span>
        </div>
        {[['逻辑清晰', 78], ['STAR 应用', 58], ['成果量化', 52], ['赛道匹配度', 64]].map((d, i) => <MiniMeter key={i} l={d[0]} v={d[1]} />)}
        <div style={{ marginTop: 4 }}>
          {['九坤实习：STAR 缺 Result', '校园项目：无量化锚点'].map((g, i) => (
            <div key={i} style={{ border: `1px solid ${WF.line}`, borderRadius: 10, padding: 9, marginBottom: 7, font: `500 11px ${WF.sans}`, color: WF.ink2, display: 'flex', alignItems: 'center' }}>
              {g}<span style={{ marginLeft: 'auto', color: WF.faint }}>→</span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ flex: 'none', padding: '9px 14px', borderTop: `1px dashed ${WF.line2}`, font: `500 10.5px/1.5 ${WF.sans}`, color: WF.meta, background: WF.metaBg }}>
        A · 顶部 Tab：三能力强分隔，一次专注一个。最清晰，但串联靠「去深度优化」按钮跳 tab。
      </div>
    </VShell>
  );
}

// ---- B · 流式串联 (单条 thread,打分→优化 顺着滚) -------------------------
function VarFlow() {
  return (
    <VShell>
      <VHead />
      <div style={{ flex: 1, padding: 14, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
          <span style={{ width: 18, height: 18, borderRadius: 999, background: WF.dark, color: '#fff', font: '700 9px sans-serif', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>1</span>
          <span style={{ font: `600 11px ${WF.sans}` }}>简历打分</span>
          <span style={{ font: `500 10px ${WF.mono}`, color: WF.muted, marginLeft: 'auto' }}>72 → 80–85</span>
        </div>
        <WCard pad={10} style={{ borderRadius: 11, marginBottom: 7 }}>
          {[['STAR 应用', 58], ['成果量化', 52]].map((d, i) => <MiniMeter key={i} l={d[0]} v={d[1]} />)}
          <div style={{ font: `500 11px ${WF.sans}`, color: WF.ink2, marginTop: 2 }}>九坤实习：STAR 缺 Result →</div>
        </WCard>
        {/* connector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 0 8px', paddingLeft: 8 }}>
          <div style={{ width: 1, height: 14, background: WF.line2 }} />
          <span style={{ font: `500 10px ${WF.sans}`, color: WF.faint }}>点缺口，顺势进入 ↓</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
          <span style={{ width: 18, height: 18, borderRadius: 999, background: WF.dark, color: '#fff', font: '700 9px sans-serif', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>2</span>
          <span style={{ font: `600 11px ${WF.sans}` }}>深度优化 · 反问取证</span>
        </div>
        <div style={{ background: WF.fill, border: `1px solid ${WF.line}`, borderRadius: '4px 11px 11px 11px', padding: '9px 11px', font: `400 11px/1.55 ${WF.sans}`, color: WF.ink2, marginBottom: 8 }}>
          这段往量化私募改吗？框架最后跑出了什么结果——覆盖多少因子、回测哪段区间？
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <div style={{ background: WF.dark, color: '#fff', borderRadius: '11px 4px 11px 11px', padding: '9px 11px', font: `400 11px/1.55 ${WF.sans}`, maxWidth: '84%' }}>40 个因子，回测 2021–2023…</div>
        </div>
      </div>
      <div style={{ flex: 'none', padding: '9px 14px', borderTop: `1px dashed ${WF.line2}`, font: `500 10.5px/1.5 ${WF.sans}`, color: WF.meta, background: WF.metaBg }}>
        B · 流式串联：打分与优化在同一条 thread，顺着滚下去最连贯。最贴「串联流」，但长。
      </div>
    </VShell>
  );
}

// ---- C · composer chip 驱动 (跟现有产品 chip 一致) -----------------------
function VarChip() {
  return (
    <VShell>
      <VHead />
      <div style={{ flex: 1, padding: 14, overflow: 'hidden' }}>
        <div style={{ background: WF.fill, border: `1px solid ${WF.line}`, borderRadius: '4px 11px 11px 11px', padding: '9px 11px', font: `400 11px/1.55 ${WF.sans}`, color: WF.ink2, marginBottom: 9 }}>
          已按「简历优化」模式打分：现状 <b>72</b>，潜力 80–85。最拖分的是 STAR 与成果量化。
        </div>
        <WCard pad={10} style={{ borderRadius: 11, marginBottom: 9 }}>
          {[['STAR 应用', 58], ['成果量化', 52]].map((d, i) => <MiniMeter key={i} l={d[0]} v={d[1]} />)}
        </WCard>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 9 }}>
          <div style={{ background: WF.dark, color: '#fff', borderRadius: '11px 4px 11px 11px', padding: '9px 11px', font: `400 11px ${WF.sans}` }}>优化九坤那段</div>
        </div>
        <div style={{ background: WF.fill, border: `1px solid ${WF.line}`, borderRadius: '4px 11px 11px 11px', padding: '9px 11px', font: `400 11px/1.55 ${WF.sans}`, color: WF.ink2 }}>
          好。先对齐目标：往量化私募·研究改吗？
        </div>
      </div>
      <div style={{ flex: 'none', padding: 12, borderTop: `1px solid ${WF.line}` }}>
        <div style={{ display: 'flex', gap: 5, marginBottom: 8, flexWrap: 'wrap' }}>
          <WChip>深度搜索</WChip><WChip>职位推荐</WChip><WChip active>简历优化</WChip><WChip>职场体验</WChip>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, border: `1px solid ${WF.line2}`, borderRadius: 11, padding: '9px 11px', background: WF.fill }}>
          <span style={{ font: `400 11px ${WF.sans}`, color: WF.faint, flex: 1 }}>选 chip 切能力，直接对话…</span>
          <span style={{ width: 24, height: 24, borderRadius: 7, background: WF.dark, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>↑</span>
        </div>
      </div>
      <div style={{ flex: 'none', padding: '9px 14px', borderTop: `1px dashed ${WF.line2}`, font: `500 10.5px/1.5 ${WF.sans}`, color: WF.meta, background: WF.metaBg }}>
        C · chip 驱动：跟现有 composer chips 一致，能力即 chip。最像现产品，但打分报告被压进对话气泡里。
      </div>
    </VShell>
  );
}

Object.assign(window, { VarTabs, VarFlow, VarChip });
