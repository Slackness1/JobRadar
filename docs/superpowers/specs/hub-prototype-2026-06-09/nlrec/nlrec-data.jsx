// nlrec-data.jsx — job dataset, deterministic ranker, scripted NL turns, intel + anchors
/* global window */

// ---- job universe (流动 feed source) -----------------------------------
// cats drive matching; soe = 国企; pay/freshDays drive alt sorts.
const JOBS = [
  { id: 'citic-fi',  name: '固定收益研究 · 实习', co: '中信证券资管', loc: '上海', cats: ['投研','固收','券商资管','头部券商资管'], soe: false, base: 94, pay: 96, freshDays: 2, intel: 'citic' },
  { id: 'htam-cr',   name: '信用研究助理',        co: '华泰资管',     loc: '上海', cats: ['投研','固收','券商资管','头部券商资管'], soe: false, base: 91, pay: 90, freshDays: 0 },
  { id: 'gf-quant',  name: '固收量化研究',        co: '广发资管',     loc: '深圳', cats: ['投研','固收','量化','券商资管'],         soe: false, base: 88, pay: 88, freshDays: 4 },
  { id: 'gj-macro',  name: '宏观固收研究',        co: '国君资管',     loc: '上海', cats: ['投研','固收','宏观','券商资管','头部券商资管'], soe: false, base: 86, pay: 92, freshDays: 5 },
  { id: 'cicc-eq',   name: '权益研究 · 消费组',   co: '中金公司',     loc: '北京', cats: ['投研','权益','券商','头部券商资管'],     soe: false, base: 84, pay: 94, freshDays: 3 },
  { id: 'cms-fi',    name: '固收交易支持',        co: '招商资管',     loc: '深圳', cats: ['投研','固收','券商资管'],               soe: false, base: 82, pay: 84, freshDays: 2 },
  { id: 'xz-cb',     name: '可转债研究实习',      co: '兴证资管',     loc: '上海', cats: ['投研','固收','券商资管'],               soe: false, base: 83, pay: 80, freshDays: 1 },
  { id: 'fx-esg',    name: 'ESG 固收研究',        co: '某外资资管',   loc: '上海', cats: ['投研','固收','外资'],                   soe: false, base: 81, pay: 86, freshDays: 6 },
  { id: 'pa-fof',    name: 'FOF 配置研究',        co: '平安资管',     loc: '上海', cats: ['投研','资管'],                         soe: false, base: 80, pay: 82, freshDays: 4 },
  { id: 'pf-quant',  name: '量化策略研究实习',    co: '某量化私募',   loc: '上海', cats: ['投研','量化'],                         soe: false, base: 85, pay: 98, freshDays: 1 },
  { id: 'soe-strat', name: '战略研究岗',          co: '某央企投资',   loc: '北京', cats: ['投研','战略'],                         soe: true,  base: 79, pay: 70, freshDays: 6 },
  { id: 'soe-plat',  name: '国企战投研究',        co: '某省国资平台', loc: '杭州', cats: ['投研','战略'],                         soe: true,  base: 76, pay: 66, freshDays: 9 },
];

const HEAD_BROKER = '头部券商资管';

function matchScore(job, wq) {
  let s = job.base;
  const wants = [...(wq.seed || []), ...(wq.add || [])];
  s += job.cats.filter((c) => wants.includes(c)).length * 2;
  if ((wq.companies || []).some((c) => job.co.includes(c))) s += 6;
  return s;
}

// search_candidates(): deterministic recall + rank. used_ai = false.
function rankFeed(wq) {
  let list = JOBS.slice();
  if (wq.only) list = list.filter((j) => j.cats.includes(wq.only));
  if ((wq.exclude || []).length) {
    list = list.filter((j) => !wq.exclude.some((ex) => (ex === '国企' ? j.soe : j.cats.includes(ex))));
  }
  let scored = list.map((j) => ({ ...j, score: matchScore(j, wq) }));
  if (wq.sort === 'fresh') scored.sort((a, b) => a.freshDays - b.freshDays || b.score - a.score);
  else if (wq.sort === 'pay') scored.sort((a, b) => b.pay - a.pay || b.score - a.score);
  else scored.sort((a, b) => b.score - a.score || a.freshDays - b.freshDays);
  return scored;
}

const freshText = (d) => (d === 0 ? '今天' : d === 1 ? '昨天' : d + ' 天前');

// ---- company intel (get_company_intel) ---------------------------------
const INTEL = {
  citic: {
    co: '中信证券资管',
    line: '头部券商资管，固收团队规模居前；实习转正路径清晰，校招认可度高。',
    rows: [
      ['梯队', 'To-T1 主流平台 · 券商资管头部'],
      ['在招', '3 个相关岗位 · 含 1 个固收研究实习'],
      ['口碑', '研究体系成熟 · 带教密度高'],
    ],
    tags: ['To-T1 主流平台', '固收强', '转正路径清晰'],
  },
};

// ---- deepen result (慢路 · Pro 精排 · 4-anchor 理由) --------------------
function anchorsFor(job) {
  if (job.id === 'citic-fi') {
    return [
      ['赛道契合', '固收研究方向与你确认赛道高度对齐，毋需转向'],
      ['平台梯队', '头部券商资管 · 主流平台 To-T1，校招认可度高'],
      ['岗位画像', 'JD 重信用债与组合管理，匹配你的因子研究经验'],
      ['不确定点', '该岗偏卖方研究，需确认你对路演与外发报告的接受度'],
    ];
  }
  const top = job.cats[1] || job.cats[0];
  return [
    ['赛道契合', `${top}方向与你的工作查询匹配，落在确认赛道邻域`],
    ['平台梯队', job.cats.includes(HEAD_BROKER) ? '头部券商资管 · 主流平台' : `${job.co} · 平台梯队中上`],
    ['岗位画像', `JD 与${top}研究经验相关，技能可迁移`],
    ['不确定点', '岗位说明披露有限，建议深挖后再决定投递优先级'],
  ];
}
const enhancedFor = (job) => Math.min(98, job.base + 2 + (job.cats.includes(HEAD_BROKER) ? 2 : 0));

// ---- scripted NL turns --------------------------------------------------
// each: trigger keys, the parsed JSON contract, the working-query delta fn, agent reply
const SCRIPT = [
  {
    key: 'fi',
    label: '多来点固收',
    user: '多来点固收',
    match: (t) => /固收|固定收益/.test(t),
    trace: { intent: 'refine', query_delta: '+固收 · sort=match', remember: 'null', rememberNote: '（按匹配度软提权，不藏岗）' },
    apply: (wq) => ({ ...wq, add: [...new Set([...wq.add, '固收'])] }),
    reply: '已加上<b>固收</b>，按匹配度给你重排了。固收相关的提到前面，其余没藏。',
    fast: true,
  },
  {
    key: 'nosoe',
    label: '一直不考虑国企',
    user: '我一直不考虑国企',
    match: (t) => /国企|央国企|不考虑/.test(t),
    trace: { intent: 'refine', query_delta: 'exclude=国企', remember: '{ dimension: industry_avoid, value: 国企 }', rememberNote: '（“一直” → 稳定偏好，升 L3）' },
    apply: (wq) => ({ ...wq, exclude: [...new Set([...wq.exclude, '国企'])] }),
    reply: '好，已从这次结果里排除<b>国企</b>。这条像长期偏好，我顺手记下了，下次自动带上。',
    memory: '记忆 → L3 preference · 后台 BackgroundTask 落库',
    fast: true,
  },
  {
    key: 'headpay',
    label: '只看头部券商资管，按薪资排',
    user: '只看头部券商资管，按薪资排',
    match: (t) => /头部|只看|薪资|薪酬|工资/.test(t),
    trace: { intent: 'refine', query_delta: 'only=头部券商资管 · sort=pay', remember: 'null', rememberNote: '（“只看”是一次性过滤，不升 L3）' },
    apply: (wq) => ({ ...wq, only: HEAD_BROKER, sort: 'pay' }),
    reply: '收窄到<b>头部券商资管</b>，按薪资排了。「只看」是过滤，其余先收起来——想放开说一声。',
    fast: true,
  },
  {
    key: 'intel',
    label: '讲讲中信资管',
    user: '讲讲中信资管',
    match: (t) => /讲讲|中信|了解|介绍/.test(t),
    trace: { intent: 'intel', query_delta: 'company=中信证券资管', remember: 'null', rememberNote: '（不动 feed）' },
    apply: (wq) => wq,
    reply: '中信证券资管的情报卡给你拉出来了 →',
    intel: 'citic',
    fast: true,
  },
];

window.NLData = { JOBS, rankFeed, freshText, INTEL, anchorsFor, enhancedFor, SCRIPT, HEAD_BROKER };
