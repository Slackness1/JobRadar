// wf-scoring.jsx — Part 2 ① 简历打分(报告式,不改简历)— priority screen
/* global React, WF, WLine, WLines, WTag, WBtn, WChip, WTabs, WCard, WNote, WDot, WMeter, WRadar */

// 6+2 维度命名（这一版）
const DIMS6 = [
  ['逻辑清晰', 78], ['STAR 应用', 58], ['内容可读', 84],
  ['内容完整', 70], ['专业表达', 80], ['成果量化', 52],
];
const DIMS2 = [['赛道匹配度', 64], ['面试可防守性', 55]];

const RADAR = [
  { k: '逻辑', v: 78 }, { k: 'STAR', v: 58 }, { k: '可读', v: 84 }, { k: '完整', v: 70 },
  { k: '表达', v: 80 }, { k: '量化', v: 52 }, { k: '匹配度', v: 64, fin: true }, { k: '可防守', v: 55, fin: true },
];

const GAPS = [
  { t: '九坤投资 · 量化研究实习', tags: ['STAR 缺 Result', '可防守性低'], d: '“协助搭建因子回测框架”——缺最终结果，且“协助”角色面试易被追问。' },
  { t: '校园量化策略项目', tags: ['成果无量化锚点'], d: '通篇无数字锚点：回测区间 / 收益 / 频次都缺，量化维拉低总分。' },
  { t: '个人介绍', tags: ['赛道匹配度低'], d: '偏通用自我介绍，未对齐“量化私募·研究”目标赛道的关键词。' },
];

function ScoringPanel() {
  return (
    <div style={{ width: 408, background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 16, font: WF.sans, color: WF.ink, overflow: 'hidden' }}>
      {/* header: capability chips */}
      <div style={{ padding: '13px 16px', borderBottom: `1px solid ${WF.line}`, display: 'flex', alignItems: 'center', gap: 9 }}>
        <WDot s={26} label="AI" />
        <div style={{ font: `600 13px ${WF.sans}` }}>简历打分</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <WChip active>打分</WChip><WChip>深度优化</WChip><WChip>自由问</WChip>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        {/* target subcat switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 13 }}>
          <WTag style={{ marginBottom: 0 }}>目标赛道</WTag>
          <span style={{ font: `600 12px ${WF.sans}`, color: WF.ink, border: `1px solid ${WF.line2}`, borderRadius: 999, padding: '5px 11px', display: 'inline-flex', alignItems: 'center', gap: 6 }}>量化私募 · 研究 <span style={{ color: WF.faint }}>▾</span></span>
          <span style={{ font: `500 11px ${WF.sans}`, color: WF.muted, marginLeft: 'auto' }}>切换重打分</span>
        </div>

        {/* total score */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, padding: '4px 2px 14px' }}>
          <div>
            <div style={{ font: `600 46px/0.9 ${WF.mono}`, color: WF.ink }}>72</div>
            <div style={{ font: `500 11px ${WF.sans}`, color: WF.muted, marginTop: 4 }}>现状分 · 诚实反映当前</div>
          </div>
          <div style={{ flex: 1, borderLeft: `1px solid ${WF.line}`, paddingLeft: 14, alignSelf: 'stretch', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ font: `600 13px ${WF.mono}`, color: WF.ink2 }}>潜力区间 80–85</div>
            <div style={{ font: `400 10.5px/1.45 ${WF.sans}`, color: WF.faint, marginTop: 4 }}>把下列缺口经反问取证补齐后可达 · 不编造，仅引导</div>
          </div>
        </div>

        {/* radar */}
        <div style={{ border: `1px solid ${WF.line}`, borderRadius: 13, padding: '8px 8px 4px', marginBottom: 14, display: 'flex', justifyContent: 'center' }}>
          <WRadar size={232} data={RADAR} />
        </div>

        {/* dimension bars */}
        <WTag style={{ marginBottom: 9 }}>6 表层维</WTag>
        <div style={{ marginBottom: 6 }}>
          {DIMS6.map(([l, s], i) => <WMeter key={i} label={l} score={s} />)}
        </div>
        <WTag style={{ margin: '4px 0 9px' }}>2 金融独有维</WTag>
        <div style={{ marginBottom: 14 }}>
          {DIMS2.map(([l, s], i) => (
            <WMeter key={i} label={l} score={s}
              note={i === 0 ? '这段经历对目标 subcat 的对口程度' : '这句话面试官追问会不会崩'} />
          ))}
        </div>

        {/* per-section gaps */}
        <WTag style={{ marginBottom: 9 }}>逐段缺口 · 深度优化入口</WTag>
        {GAPS.map((g, i) => (
          <div key={i} style={{ border: `1px solid ${WF.line}`, borderRadius: 12, padding: 12, marginBottom: 9 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8, flexWrap: 'wrap' }}>
              <span style={{ font: `600 12px ${WF.sans}`, color: WF.ink }}>{g.t}</span>
              {g.tags.map((t, j) => (
                <span key={j} style={{ font: `500 10px ${WF.sans}`, color: WF.ink2, background: WF.fill2, border: `1px solid ${WF.line2}`, borderRadius: 999, padding: '2px 8px', whiteSpace: 'nowrap' }}>{t}</span>
              ))}
            </div>
            <div style={{ font: `400 11px/1.55 ${WF.sans}`, color: WF.muted, marginBottom: 10 }}>{g.d}</div>
            <WBtn sm solid style={{ fontSize: 11 }}>去深度优化这段 →</WBtn>
          </div>
        ))}

        <div style={{ font: `400 10.5px/1.5 ${WF.sans}`, color: WF.faint, textAlign: 'center', marginTop: 6, padding: '0 8px' }}>只诊断、不改写。提分只能通过深度优化的反问取证补齐真实细节。</div>
      </div>
    </div>
  );
}

Object.assign(window, { ScoringPanel });
