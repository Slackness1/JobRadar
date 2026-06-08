/* global React, HFPill, I, useS */
// ============================================================
// Recommendation rail — PLATFORM tab rebuilt as 梯队骨架 (tier skeleton)
//   · companies grouped by head / mid / floor tier of the track
//   · GT skeleton companies show even with NO live matching jobs
//   · match-band tier highlighted; multiple cards expand at once
// ============================================================

// ---- Company library (GT skeleton + live-job overlay) -------
// hasLive=true  → live matching jobs this season (job list on expand)
// hasLive=false → skeleton-only (intel + past hiring window on expand)
window.RC_COMPANIES = [
  // ===== 第二梯队 · 主力 (match band) — live jobs =====
  {
    id: 'cs', ch: '信', name: '中信建投', pri: 'A', score: 81, match: '强匹配',
    industry: '券商投行', hasLive: true, nLive: 2, nInsights: 9, hot: true,
    intro: '近 30 天新开 2 个对口工位 · 偏好覆盖经验',
    miniJobs: [
      { id: 'cs-1', tag: '校', title: '研究部 · 食品饮料分析师', industry: '消费', score: 86, narrative: '你的易方达 8 篇报告框架可直接复用,一面常考过往报告细节' },
      { id: 'cs-2', tag: '校', title: '投行部 · 金融组通道', industry: 'IB', score: 76, narrative: '丐版投行四百问 + A股流水抽凭,你 CFA 一级覆盖 70%' },
    ],
    intel: {
      compensation: 'Base 26k · 总包约 40 万 · 签字费 5w',
      requirements: ['末流 985+', 'QS<100 留学', 'GPA 3.6+', '抗压', '主动'],
      prospects: '一面给 30 分钟讲一只你跟过的股票,体验很 buy-side',
      questions: [
        '介绍一只你跟过的股票及其逻辑',
        'DCF 假设有哪些容易踩坑',
        '硬科技 vs 消费,估值方法本质区别',
        '递延所得税怎么计量',
      ],
      quotes: [
        { text: '中信 IB 面试还是蛮套路的, 丐版投行四百问 + A股特色流水抽凭 + 高频会计问题 + 基础 behavior question', author: '2024 应届 · 复旦经院', hearts: 230 },
        { text: 'tech 部分跟 CFA 一级核心考点太像了, 递延所得税真的难爆了', author: 'anon · 上海交大 SAIF', hearts: 87 },
        { text: '一面给 30 分钟讲一只你跟过的股票,然后疯狂质疑你的假设,体验很 buy-side', author: '某 2023 实习生', hearts: 64 },
      ],
    },
  },
  {
    id: 'efd', ch: '易', name: '易方达基金', pri: 'A', score: 78, match: '强匹配',
    industry: '公募', hasLive: true, nLive: 1, nInsights: 5, hot: false,
    intro: '你已在这里实习过,有内部 referral 通道',
    miniJobs: [
      { id: 'efd-1', tag: '校', title: '量化研究员 · 公募方向', industry: '资管', score: 82, narrative: '消费组同事推内推 → 走绿色通道' },
    ],
    intel: {
      compensation: 'Base 22k · 总包约 35 万',
      requirements: ['985 / QS<50', 'GPA 3.5+', '研究框架完整'],
      prospects: '对实习生当正式员工用,文化非常 buy-side',
      questions: ['你的食品饮料覆盖框架是怎样的?', '24Q1 白酒为什么背离?'],
      quotes: [
        { text: '易方达消费组对实习生当正式员工用,文化非常 buy-side,适合想做长期研究的人', author: 'ex-实习生 · 23 届', hearts: 142 },
      ],
    },
  },
  {
    id: 'cm', ch: '招', name: '招商基金', pri: 'B', score: 68, match: '可迁移',
    industry: '公募', hasLive: true, nLive: 3, nInsights: 3, hot: false,
    intro: '入行门槛友好,GPA 3.6+ 你已达标',
    miniJobs: [
      { id: 'cm-1', tag: '校', title: '研究发展部 · 消费研究员', industry: '资管', score: 71, narrative: '门槛友好,适合作为主力梯队的稳妥一投' },
    ],
    intel: {
      compensation: 'Base 19k · 总包约 30 万',
      requirements: ['985 / QS<80', 'GPA 3.5+'],
      prospects: '组里 mentor 带得细,适合补研究方法论',
      questions: ['说一个你最近看好的消费标的'],
      quotes: [
        { text: '招商基金研究岗节奏没那么卷,leader 愿意带新人搭框架', author: '2024 实习 · 武大', hearts: 53 },
      ],
    },
  },

  // ===== 第一梯队 · 头部 (stretch band) — skeleton-only, no live =====
  {
    id: 'cicc', ch: '中', name: '中金公司', pri: 'B', score: 84, match: '可迁移',
    industry: '券商研究', hasLive: false, nLive: 0, nInsights: 24, hot: false,
    window: '通常 9–11 月秋招 · 上次开放 2025-10',
    intro: '硬科技研究头部 · 本季未开对口岗,看情报与往年窗口',
    miniJobs: [],
    intel: {
      compensation: null, // 数据现实:24 条 UGC 几乎无人谈薪酬数字 → 诚实留白
      compEmptyNote: '24 条情报集中在门槛 / 前景,无人谈具体薪酬',
      requirements: ['985 / 海外 Top20', 'GPA 3.7+', '至少 2 段 buy-side 实习'],
      prospects: '研究部一面就拉投委会纪要让你 critique,假设疯狂被质疑,挺锻炼人',
      questions: [
        '硬科技和消费在估值方法上有什么本质区别?',
        'DCF 假设有哪些容易踩坑',
        '你最自豪的一篇深度报告',
      ],
      quotes: [
        { text: '中金研究部一面就直接拉投委会的纪要让你 critique,假设疯狂被质疑,挺锻炼人的', author: '某 2024 入职 · 北大光华', hearts: 198 },
        { text: '面经里几乎没人聊到 base,大家都在卷留用和项目质量', author: 'anon · 清华五道口', hearts: 71 },
      ],
    },
  },
  {
    id: 'citic', ch: '中', name: '中信证券', pri: 'A', score: 82, match: '可迁移',
    industry: '券商研究', hasLive: false, nLive: 0, nInsights: 19, hot: false,
    window: '通常 8–10 月秋招 · 上次开放 2025-09',
    intro: '券业一哥 · 研究所体量最大,本季对口岗未开',
    miniJobs: [],
    intel: {
      compensation: 'Base 25k · 总包约 38 万',
      requirements: ['985 / QS<50', 'GPA 3.6+', 'CPA / CFA 加分'],
      prospects: '研究所平台大,出报告署名机会多,但新人轮岗压力大',
      questions: ['讲一个你跟踪过的行业景气拐点', '怎么判断卖方报告的水分'],
      quotes: [
        { text: '中信研究所平台是真的大,但新人前两年基本是给首席打杂,熬过去署名就多了', author: '2023 入职 · 复旦', hearts: 124 },
      ],
    },
  },
  {
    id: 'gs', ch: '高', name: '高盛 GBM', pri: 'A', score: 79, match: '有差距',
    industry: '外资行', hasLive: false, nLive: 0, nInsights: 2, hot: false,
    window: '通常 7–9 月暑期转正 · 暑期实习为主通道',
    intro: '外资研究天花板 · 暑期实习转正为主,本季无校招对口岗',
    miniJobs: [],
    intel: {
      compensation: null,
      compEmptyNote: '仅 2 条情报,均为流程讨论,未涉及薪酬',
      requirements: ['QS<30 / 海外 Top10', '全英面试', '暑期实习经历'],
      prospects: '门槛高,流程长,bar raiser 环节会反复 challenge 逻辑',
      questions: ['Walk me through a stock pitch in English'],
      quotes: [
        { text: 'GS 的 superday 全英,bar raiser 那轮会把你的 pitch 拆到底', author: 'anon · LSE', hearts: 44 },
      ],
    },
  },

  // ===== 第三梯队 · 腰部 (floor band) — mix =====
  {
    id: 'gtja', ch: '国', name: '国泰君安', pri: 'B', score: 66, match: '可迁移',
    industry: '券商', hasLive: false, nLive: 0, nInsights: 6, hot: false,
    window: '通常 9–11 月秋招 · 上次开放 2025-10',
    intro: '稳健腰部 · 本季对口岗未开,门槛较友好',
    miniJobs: [],
    intel: {
      compensation: 'Base 18k · 总包约 26 万',
      requirements: ['985 / QS<100', 'GPA 3.4+'],
      prospects: '体量大、节奏稳,适合保底,晋升靠资历',
      questions: ['为什么选券商研究而不是买方'],
      quotes: [
        { text: '国君研究所对学历卡得没头部那么死,GPA 够、有实习就能进面', author: '2024 实习 · 上财', hearts: 38 },
      ],
    },
  },
  {
    id: 'ht', ch: '华', name: '华泰证券', pri: 'C', score: 62, match: '有差距',
    industry: '券商', hasLive: false, nLive: 0, nInsights: 0, hot: false,
    window: '通常 9–10 月秋招 · 上次开放 2025-09',
    intro: '研究部更看重海外 PhD 背景 · 本季无对口岗、暂无同辈情报',
    miniJobs: [],
    intel: null,
  },
  {
    id: 'zaic', ch: '再', name: '中再资产', pri: 'C', score: 58, match: '有差距',
    industry: '保险资管', hasLive: false, nLive: 0, nInsights: 0, hot: false,
    window: '招聘窗口不定期 · 多走内推',
    intro: '保险资管腰部 · 骨架补全,暂无在招岗与情报',
    miniJobs: [],
    intel: null,
  },
];

// ---- Tier skeleton, keyed by track (GT coverage) -----------
// role: 'match' (你匹配这档) · 'stretch' (踮脚可冲) · 'floor' (稳·保底)
window.RC_PLATFORM_TIERS = {
  l2_buyside: {
    subCat: '二级买方 · 基本面',
    hasSkeleton: true,
    tiers: [
      { tier: 1, label: '第一梯队', band: '头部', role: 'stretch', companies: ['cicc', 'citic', 'gs'] },
      { tier: 2, label: '第二梯队', band: '主力', role: 'match',   companies: ['cs', 'efd', 'cm'] },
      { tier: 3, label: '第三梯队', band: '腰部', role: 'floor',   companies: ['gtja', 'ht', 'zaic'] },
    ],
  },
  // …all other tracks have no GT skeleton yet → flat live-only fallback
};

const getCompany = (id) => window.RC_COMPANIES.find(c => c.id === id);

const ROLE_META = {
  match:   { tag: '你匹配这档', mark: '✦', fg: 'var(--terracotta-strong)', bg: 'var(--terracotta-wash)', bd: '#eccfb6', node: 'var(--terracotta)', nodeFg: '#fff' },
  stretch: { tag: '踮脚可冲',   mark: '↑', fg: 'var(--amber-fg)',          bg: 'var(--amber-bg)',         bd: '#ecdfa4', node: 'var(--amber-bg)', nodeFg: 'var(--amber-fg)' },
  floor:   { tag: '稳 · 保底',  mark: '◆', fg: 'var(--stone)',             bg: 'var(--warm-sand)',        bd: 'var(--ring-warm)', node: 'var(--warm-sand)', nodeFg: 'var(--stone)' },
};

// ============================================================
// Small bits
// ============================================================

const HFLogoBubble = ({ ch, tone = 'A', size = 36 }) => {
  const conf = {
    A: { bg: 'var(--terracotta-wash)', fg: 'var(--terracotta)', border: '#eccfb6' },
    B: { bg: 'var(--amber-bg)', fg: 'var(--amber-fg)', border: '#ecdfa4' },
    C: { bg: 'var(--warm-sand)', fg: 'var(--stone)', border: 'var(--ring-warm)' },
  }[tone] || { bg: 'var(--warm-sand)', fg: 'var(--stone)', border: 'var(--ring-warm)' };
  return (
    <span style={{
      width: size, height: size, borderRadius: '50%',
      background: conf.bg, color: conf.fg,
      fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: size * 0.5,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: `0 0 0 1px ${conf.border}`,
      flexShrink: 0,
    }}>{ch}</span>
  );
};

const HFPri = ({ p }) => {
  const tone = { A: 'var(--terracotta)', B: 'var(--amber-fg)', C: 'var(--stone)' }[p];
  return (
    <span style={{
      width: 18, height: 18, borderRadius: 4, border: `1.5px solid ${tone}`,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 700, fontSize: 10.5, color: tone, lineHeight: 1, fontFamily: 'var(--font-sans)',
    }}>{p}</span>
  );
};

const HFMatch = ({ kind }) => {
  const map = {
    '强匹配': { bg: 'var(--emerald-soft)', fg: 'var(--emerald)', bd: '#c7d9c2' },
    '可迁移': { bg: 'var(--amber-bg)', fg: 'var(--amber-fg)', bd: '#ecdfa4' },
    '有差距': { bg: '#f6e2d8', fg: '#a04a2a', bd: '#dec0ad' },
  };
  const t = map[kind] || map['可迁移'];
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 999,
      background: t.bg, color: t.fg,
      boxShadow: `0 0 0 1px ${t.bd}`,
      fontSize: 11, fontWeight: 600, lineHeight: 1.4,
    }}>{kind}</span>
  );
};

// live / no-live status badge
const HFLiveBadge = ({ c }) => c.hasLive ? (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 5,
    padding: '2px 9px', borderRadius: 999,
    background: 'var(--terracotta)', color: '#fff',
    fontSize: 11, fontWeight: 600, lineHeight: 1.4,
    boxShadow: '0 0 0 3px rgba(201,100,66,0.10)',
  }}>
    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff' }}/>
    在招 {c.nLive} 岗
  </span>
) : (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 5,
    padding: '2px 9px', borderRadius: 999,
    background: 'var(--ivory)', color: 'var(--stone)',
    fontSize: 11, fontWeight: 500, lineHeight: 1.4,
    boxShadow: '0 0 0 1px var(--border-warm)',
  }}>
    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ring-deep)' }}/>
    本季暂无对口岗
  </span>
);

const HFInsightBadge = ({ n, hot = false, onClick }) => (
  <button
    onClick={onClick}
    style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 999,
      background: hot ? 'linear-gradient(135deg, #fff5ed, #fde2cf)' : 'var(--ivory)',
      color: hot ? 'var(--terracotta-strong)' : 'var(--ink-soft)',
      boxShadow: hot ? '0 0 0 1px var(--terracotta), 0 0 0 4px rgba(201,100,66,0.08)' : '0 0 0 1px var(--border-warm)',
      fontSize: 11.5, fontWeight: 600, cursor: 'pointer',
    }}
  >
    {hot && <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--terracotta)', boxShadow: '0 0 0 2px rgba(201,100,66,0.18)' }}/>}
    <span>情报</span>
    <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>×{n}</span>
  </button>
);

// ============================================================
// 3-dim intel mini (for skeleton / no-live cards)
//   门槛 → 待遇 → 前景, empty dims honestly sink to bottom
// ============================================================
const HFIntelMini = ({ c }) => {
  const intel = c.intel;
  if (!intel) {
    return (
      <div style={{ padding: '10px 12px', background: 'var(--warm-sand)', borderRadius: 10, fontSize: 12, color: 'var(--stone)', lineHeight: 1.55 }}>
        暂无同辈情报 — 这家是按赛道梯队补全的骨架公司,等到有同学讨论会自动汇入。
      </div>
    );
  }
  const compEmpty = !intel.compensation;
  const Row = ({ icon, label, children, empty }) => (
    <div style={{
      display: 'flex', gap: 10, padding: '9px 11px', borderRadius: 10,
      background: empty ? 'transparent' : 'var(--ivory)',
      boxShadow: empty ? 'none' : '0 0 0 1px var(--border-warm)',
      marginBottom: 7, alignItems: 'flex-start',
      border: empty ? '1px dashed var(--ring-warm)' : 'none',
    }}>
      <span style={{ flexShrink: 0, width: 38, fontSize: 11, fontWeight: 700, color: empty ? 'var(--stone)' : 'var(--terracotta)', paddingTop: 1, fontFamily: 'var(--font-sans)' }}>{label}</span>
      <div style={{ flex: 1, minWidth: 0, fontSize: 12.5, lineHeight: 1.55, color: empty ? 'var(--stone)' : 'var(--ink)' }}>{children}</div>
    </div>
  );
  return (
    <div>
      {/* 门槛 */}
      <Row label="门槛">
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {intel.requirements.map(r => (
            <span key={r} style={{ padding: '2px 8px', borderRadius: 999, background: 'var(--warm-sand)', fontSize: 11.5, color: 'var(--ink-soft)' }}>{r}</span>
          ))}
        </div>
      </Row>
      {/* 前景 */}
      {intel.prospects && (
        <Row label="前景">
          <span style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', color: 'var(--ink)' }}>“{intel.prospects}”</span>
        </Row>
      )}
      {/* 待遇 — honest empty copy sinks last */}
      {compEmpty ? (
        <Row label="待遇" empty>
          同龄人讨论中暂未提及
          <span style={{ display: 'block', marginTop: 2, fontSize: 11, color: 'var(--warm-silver)' }}>
            {intel.compEmptyNote || `${c.nInsights} 条情报集中在门槛 / 前景`} · 不编造数字
          </span>
        </Row>
      ) : (
        <Row label="待遇">{intel.compensation}</Row>
      )}
    </div>
  );
};

// ============================================================
// Company card — dual mode (live job list / skeleton intel)
// ============================================================
const HFCompanyCard = ({ c, expanded, onToggle, onIntel, onCoach, onJobClick, activeJobId, dim }) => (
  <div
    className="hf-card lift"
    style={{
      marginBottom: 9, padding: 13,
      transition: 'box-shadow 0.2s',
      boxShadow: expanded ? '0 0 0 1.5px var(--terracotta), 0 14px 32px rgba(201,100,66,0.10)' : 'var(--sh-ring)',
      cursor: expanded ? 'default' : 'pointer',
      opacity: dim && !expanded ? 0.82 : 1,
      background: c.hasLive ? 'var(--ivory)' : 'var(--parchment)',
    }}
    onClick={() => !expanded && onToggle(c.id)}
  >
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
      <HFLogoBubble ch={c.ch} tone={c.pri} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontSize: 14.5, fontWeight: 600, color: 'var(--ink)' }}>{c.name}</span>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
            <HFPri p={c.pri} />
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--terracotta)', fontFamily: 'var(--font-mono)' }}>{c.score}</span>
            <span style={{ color: 'var(--stone)', transition: 'transform 0.2s', transform: expanded ? 'rotate(180deg)' : 'rotate(0)' }}>
              {I.chevron(12)}
            </span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 7, flexWrap: 'wrap' }}>
          <HFLiveBadge c={c} />
          <HFMatch kind={c.match} />
          <span style={{ fontSize: 11.5, color: 'var(--stone)' }}>{c.industry}</span>
          {c.nInsights > 0 && (
            <span style={{ marginLeft: 'auto' }}>
              <HFInsightBadge n={c.nInsights} hot={c.hot} onClick={(e) => { e.stopPropagation(); onIntel(c.id); }} />
            </span>
          )}
        </div>
        {!expanded && (
          <div style={{ marginTop: 8, fontSize: 12.5, color: 'var(--olive)', lineHeight: 1.5 }}>
            <span style={{ color: c.hasLive ? 'var(--terracotta)' : 'var(--stone)' }}>{c.hasLive ? '✦' : '◇'}</span> {c.intro}
          </div>
        )}
      </div>
    </div>

    {expanded && (c.hasLive ? (
      // ---------- LIVE: job list ----------
      <div style={{ marginTop: 13, paddingTop: 13, borderTop: '1px dashed var(--border-warm)' }}>
        <div style={{
          padding: 12, marginBottom: 11,
          background: 'var(--terracotta-wash)', borderRadius: 12, border: '1px solid #eccfb6',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ color: 'var(--terracotta)', fontSize: 14 }}>✦</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--terracotta-strong)', letterSpacing: '0.04em' }}>为你定制</span>
            <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--olive)' }}>{c.intel?.quotes.length || 0} 条情报支撑</span>
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.65, color: 'var(--ink)' }}>
            {c.intro}。{c.miniJobs.length > 0 && (<>top 推荐 <b>{c.miniJobs[0].title.split('·')[0].trim()}</b> — {c.miniJobs[0].narrative}。</>)}
          </div>
        </div>

        {c.miniJobs.map(j => (
          <div
            key={j.id}
            onClick={(e) => { e.stopPropagation(); onJobClick && onJobClick(j.id); }}
            style={{
              padding: '10px 12px', marginBottom: 6,
              background: activeJobId === j.id ? '#fff' : 'transparent',
              borderRadius: 10,
              boxShadow: activeJobId === j.id ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
              cursor: 'pointer', transition: 'box-shadow 0.15s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{
                padding: '2px 6px', borderRadius: 4,
                background: j.tag === '实' ? 'var(--amber-bg)' : 'var(--terracotta-wash)',
                color: j.tag === '实' ? 'var(--amber-fg)' : 'var(--terracotta)',
                fontSize: 10, fontWeight: 700,
              }}>{j.tag}</span>
              <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>{j.title}</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--terracotta)', fontFamily: 'var(--font-mono)' }}>{j.score}</span>
            </div>
            <div style={{ paddingLeft: 32, marginTop: 4, display: 'flex', gap: 6 }}>
              <span style={{ color: 'var(--terracotta)', fontSize: 12 }}>✦</span>
              <span style={{ fontSize: 12, color: 'var(--olive)', lineHeight: 1.5, flex: 1 }}>{j.narrative}</span>
            </div>
          </div>
        ))}

        {c.intel && (
          <button
            onClick={(e) => { e.stopPropagation(); onIntel(c.id); }}
            style={{
              width: '100%', padding: '10px 12px', marginTop: 6,
              background: '#faf4ed', border: '1px dashed var(--terracotta)', borderRadius: 10,
              display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', textAlign: 'left',
            }}
          >
            <span style={{ color: 'var(--terracotta)', display: 'inline-flex' }}>{I.book(16)}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700 }}>同辈情报 · {c.intel.quotes.length} 段原话 / {c.nInsights} 条洞察</div>
              <div style={{ fontSize: 11.5, color: 'var(--olive)', marginTop: 2, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                {c.intel.compensation || '待遇待补'} · {c.intel.questions.length} 道真题
              </div>
            </div>
            <span style={{ color: 'var(--terracotta)' }}>{I.arrowRight(14)}</span>
          </button>
        )}

        <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
          <button className="hf-btn primary sm" onClick={(e) => { e.stopPropagation(); onCoach(c.id); }}
            style={{ flex: 1, display: 'inline-flex', gap: 6, alignItems: 'center', justifyContent: 'center' }}>
            {I.target(13)} 针对这家定制
          </button>
          <button className="hf-btn ghost sm" onClick={(e) => e.stopPropagation()}>查看岗位</button>
          <button className="hf-btn ghost sm" onClick={(e) => e.stopPropagation()} style={{ padding: '0 8px', color: 'var(--stone)' }} title="不感兴趣">✗</button>
        </div>
      </div>
    ) : (
      // ---------- SKELETON: intel + past hiring window ----------
      <div style={{ marginTop: 13, paddingTop: 13, borderTop: '1px dashed var(--border-warm)' }}>
        <div style={{
          display: 'flex', gap: 9, alignItems: 'flex-start',
          padding: '10px 12px', marginBottom: 11,
          background: 'var(--warm-sand)', borderRadius: 10,
        }}>
          <span style={{ color: 'var(--stone)', display: 'inline-flex', flexShrink: 0, marginTop: 1 }}>{I.history(15)}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink-soft)' }}>本季未开对口岗 · 往年招聘窗口</div>
            <div style={{ fontSize: 12, color: 'var(--olive)', marginTop: 2, lineHeight: 1.5 }}>{c.window}</div>
          </div>
        </div>

        <HFIntelMini c={c} />

        <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
          {c.intel ? (
            <button className="hf-btn primary sm" onClick={(e) => { e.stopPropagation(); onIntel(c.id); }}
              style={{ flex: 1, display: 'inline-flex', gap: 6, alignItems: 'center', justifyContent: 'center' }}>
              {I.book(13)} 看 {c.nInsights} 条同辈情报
            </button>
          ) : (
            <div style={{ flex: 1 }}/>
          )}
          <button className="hf-btn ghost sm" onClick={(e) => e.stopPropagation()}
            style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }} title="开岗提醒">
            {I.bell(13)} 开岗提醒我
          </button>
        </div>
      </div>
    ))}
  </div>
);

// ============================================================
// Tier group — header (ladder node + name + role) + cards
// ============================================================
const HFTierGroup = ({ tier, expandedIds, onToggle, onIntel, onCoach, onJobClick, activeJobId, isFirst, isLast }) => {
  const meta = ROLE_META[tier.role];
  const isMatch = tier.role === 'match';
  const companies = tier.companies.map(getCompany).filter(Boolean);
  const liveCount = companies.filter(c => c.hasLive).length;

  return (
    <div style={{ position: 'relative', paddingLeft: 26, marginBottom: 14 }}>
      {/* ladder spine */}
      <span style={{
        position: 'absolute', left: 11, top: isFirst ? 16 : 0, bottom: isLast ? 'auto' : 0,
        height: isLast ? 18 : 'auto', width: 2, background: 'var(--border-warm)',
      }}/>
      {/* tier node */}
      <span style={{
        position: 'absolute', left: 3, top: 6, zIndex: 1,
        width: 18, height: 18, borderRadius: '50%',
        background: meta.node, color: meta.nodeFg,
        boxShadow: `0 0 0 3px var(--library-rail), 0 0 0 4px ${isMatch ? 'var(--terracotta)' : meta.bd}`,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10.5, fontWeight: 700, fontFamily: 'var(--font-mono)',
      }}>{tier.tier}</span>

      {/* header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9,
        padding: isMatch ? '6px 10px' : '4px 0',
        borderRadius: 10,
        background: isMatch ? 'var(--terracotta-wash)' : 'transparent',
        boxShadow: isMatch ? '0 0 0 1px #eccfb6' : 'none',
      }}>
        <span style={{ fontFamily: 'var(--font-serif)', fontSize: 16, fontWeight: 600, color: 'var(--ink)' }}>{tier.label}</span>
        <span style={{ fontSize: 12, color: 'var(--olive)' }}>{tier.band}</span>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '2px 9px', borderRadius: 999,
          background: isMatch ? 'var(--terracotta)' : meta.bg,
          color: isMatch ? '#fff' : meta.fg,
          boxShadow: isMatch ? 'none' : `0 0 0 1px ${meta.bd}`,
          fontSize: 11, fontWeight: 600,
        }}>
          <span style={{ fontSize: 10 }}>{meta.mark}</span> {meta.tag}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--stone)', fontFamily: 'var(--font-mono)' }}>
          {companies.length} 家{liveCount > 0 && <span style={{ color: 'var(--terracotta)' }}> · {liveCount} 在招</span>}
        </span>
      </div>

      {/* cards */}
      {companies.map(c => (
        <HFCompanyCard
          key={c.id}
          c={c}
          expanded={expandedIds.has(c.id)}
          activeJobId={activeJobId}
          dim={tier.role === 'floor'}
          onToggle={onToggle}
          onIntel={onIntel}
          onCoach={onCoach}
          onJobClick={onJobClick}
        />
      ))}
    </div>
  );
};

// ============================================================
// Rail header (tabs + filters)
// ============================================================
const HFRailHeader = ({ activeTab, onTab }) => {
  const tabs = [
    { id: 'platform', label: '平台', count: 9 },
    { id: 'campus', label: '校招', count: 12 },
    { id: 'intern', label: '实习', count: 8 },
  ];
  return (
    <>
      <div style={{ padding: '12px 18px 0' }}>
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-warm)' }}>
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => onTab(t.id)}
              style={{
                padding: '8px 14px',
                borderBottom: activeTab === t.id ? '2px solid var(--terracotta)' : '2px solid transparent',
                marginBottom: -1, cursor: 'pointer', background: 'transparent',
                color: activeTab === t.id ? 'var(--ink)' : 'var(--stone)',
                fontSize: 13, fontWeight: activeTab === t.id ? 600 : 500,
                display: 'inline-flex', alignItems: 'center', gap: 6, transition: 'color 0.15s',
              }}
            >
              {t.label}
              <span style={{
                padding: '0 6px', borderRadius: 999, fontSize: 10.5,
                background: activeTab === t.id ? 'var(--terracotta)' : 'var(--warm-sand)',
                color: activeTab === t.id ? '#fff' : 'var(--stone)',
              }}>{t.count}</span>
            </button>
          ))}
          <div style={{ flex: 1 }}/>
          <button style={{ alignSelf: 'center', color: 'var(--stone)', cursor: 'pointer', padding: 4 }} title="重新推荐">{I.radar(16)}</button>
        </div>
      </div>
      <div style={{ padding: '10px 18px 8px', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <span className="hf-pill">行业 ▾</span>
        <span className="hf-pill terra">仅看在招</span>
        <span className="hf-pill">有情报</span>
        <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--stone)', fontFamily: 'var(--font-mono)' }}>按梯队</span>
      </div>
    </>
  );
};

// ============================================================
// Rail
// ============================================================
const HFRail = ({ trackId, expandedIds, activeJobId, onToggle, onIntel, onCoach, onJobClick }) => {
  const [tab, setTab] = useS('platform');
  const skeleton = window.RC_PLATFORM_TIERS[trackId];
  const hasSkeleton = skeleton?.hasSkeleton && skeleton.tiers;

  return (
    <div style={{
      width: 388, background: 'var(--library-rail)',
      borderRight: '1px solid var(--border-warm)',
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <HFRailHeader activeTab={tab} onTab={setTab} />

      <div style={{ flex: 1, padding: '6px 14px 16px', overflowY: 'auto' }}>
        {hasSkeleton ? (
          <>
            {/* intro to the skeleton view */}
            <div style={{
              display: 'flex', gap: 8, alignItems: 'flex-start',
              padding: '9px 11px', marginBottom: 12,
              background: 'var(--ivory)', borderRadius: 10, boxShadow: '0 0 0 1px var(--border-warm)',
            }}>
              <span style={{ color: 'var(--terracotta)', display: 'inline-flex', flexShrink: 0, marginTop: 1 }}>{I.radar(15)}</span>
              <div style={{ fontSize: 11.5, color: 'var(--olive)', lineHeight: 1.5 }}>
                <b style={{ color: 'var(--ink)' }}>{skeleton.subCat}</b> 平台格局 · 按梯队展示。
                <span style={{ color: 'var(--terracotta)' }}> 在招</span> 与 <span style={{ color: 'var(--stone)' }}>暂无对口岗</span> 的头部公司都在,匹配档已高亮。
              </div>
            </div>

            {skeleton.tiers.map((t, i) => (
              <HFTierGroup
                key={t.tier}
                tier={t}
                expandedIds={expandedIds}
                activeJobId={activeJobId}
                onToggle={onToggle}
                onIntel={onIntel}
                onCoach={onCoach}
                onJobClick={onJobClick}
                isFirst={i === 0}
                isLast={i === skeleton.tiers.length - 1}
              />
            ))}

            <div style={{ textAlign: 'center', padding: 8, fontSize: 11.5, color: 'var(--stone)' }}>
              骨架来自 GT 公司库 · 在招标记每日刷新
            </div>
          </>
        ) : (
          // ---------- Fallback: no GT skeleton → flat live list ----------
          <>
            <div style={{
              display: 'flex', gap: 8, alignItems: 'flex-start',
              padding: '10px 12px', marginBottom: 12,
              background: 'var(--amber-bg)', borderRadius: 10, boxShadow: '0 0 0 1px #ecdfa4',
            }}>
              <span style={{ color: 'var(--amber-fg)', display: 'inline-flex', flexShrink: 0, marginTop: 1 }}>{I.clipboard(15)}</span>
              <div style={{ fontSize: 11.5, color: 'var(--amber-fg)', lineHeight: 1.5 }}>
                该赛道梯队数据整理中,先按在招平台展示。
              </div>
            </div>
            {window.RC_COMPANIES.filter(c => c.hasLive).map(c => (
              <HFCompanyCard
                key={c.id}
                c={c}
                expanded={expandedIds.has(c.id)}
                activeJobId={activeJobId}
                onToggle={onToggle}
                onIntel={onIntel}
                onCoach={onCoach}
                onJobClick={onJobClick}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
};

Object.assign(window, { HFRail, HFCompanyCard, HFTierGroup, HFIntelMini, HFLogoBubble, HFPri, HFMatch, HFLiveBadge, HFInsightBadge, getCompany });
