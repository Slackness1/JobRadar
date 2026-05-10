/* global React, Box, Pill, Line, Para, ImgBox, Note, BrandDot, Wordmark, ToolLine, Btn, Spin */

// ============================================================
// TOP-5 RESULTS + AGENT TRACE — 3 directions
// ============================================================

const JOBS = [
  ['【应届补招】AI 工程师-应用方向', '蚂蚁科技集团股份有限公司 · 上海', 96],
  ['AI 应用研发工程师', '阿里巴巴 · 未知', 92],
  ['【应届补招】智能体与大模型应用工程', '蚂蚁集团 · 北京/上海/杭州/成都', 92],
  ['【转正实习】智能体与大模型应用工程', '蚂蚁集团 · 北京/上海/杭州/广州/深圳/重庆/成都', 92],
  ['大模型应用全栈开发实习生-巨量星图', '北京抖音信息服务有限公司 · 上海', 91],
];

// 01 — Existing structure, cleaner: trace on top, card list below
const Results_A = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '36px 64px', position:'relative' }}>
    <Wordmark />
    <div style={{ height: 16 }}/>
    <Box className="filled-soft" style={{ padding: 10, marginBottom: 14, borderColor:'#c7e5cf', background:'#edf7ef' }}>
      <span className="sk-hw" style={{ fontSize: 15 }}>推荐与反馈生成中，完成后会自动刷新到结果区。</span>
    </Box>

    <Box style={{ padding: 16, borderRadius: 18, marginBottom: 18 }}>
      <div className="sk-hw-b" style={{ fontSize: 15, marginBottom: 10 }}>AI 推理中</div>
      <ToolLine icon="📄" label="阅读岗位详情 — 读取 5 个岗位完整 JD" done />
      <ToolLine icon="📄" label="阅读岗位详情 — 金融科技 / 数据类岗位" done />
      <div style={{ display:'flex', alignItems:'center', gap: 8, fontSize: 14, color:'var(--soft)', marginTop: 4 }}>
        <Spin ch="✳" /> <span className="sk-hw" style={{ fontSize: 16 }}>正在推理...</span>
      </div>
    </Box>

    <div style={{ display:'flex', alignItems:'baseline', justifyContent:'space-between', marginBottom: 10 }}>
      <div className="sk-serif" style={{ fontSize: 22 }}>真实岗位推荐 <span style={{ fontWeight: 700 }}>Top 5</span></div>
      <Pill>规则排序</Pill>
    </div>

    {JOBS.map(([title, sub, score], i) => (
      <Box key={i} style={{ padding: 14, marginBottom: 8, borderRadius: 14 }}>
        <div style={{ display:'flex', alignItems:'flex-start', gap: 8 }}>
          <span className="sk-sans" style={{ fontWeight: 700, fontSize: 14 }}>{i+1}.</span>
          <div style={{ flex: 1 }}>
            <div className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
            <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>{sub}</div>
            <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', marginTop: 2 }}>Base {score} · Enhanced {score} · To-T1 主流平台</div>
            <div style={{ display:'flex', gap: 6, marginTop: 6 }}>
              <Pill className="amber">To-T1 主流平台</Pill>
              <Pill className="amber">情报增强内测中</Pill>
            </div>
          </div>
          <span className="sk-serif" style={{ color:'var(--accent)', fontSize: 16 }}>{score} ↗</span>
        </div>
      </Box>
    ))}
    <Note style={{ top: 80, right: 40 }} side="r">当前形态 — 清理版</Note>
  </div>
);

// 02 — Two-column: trace pinned left, jobs scroll right, with inline reasoning per card
const Results_B = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, padding: '32px 48px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 18 }}>
      <Wordmark />
      <div style={{ display:'flex', gap: 8 }}>
        <Pill>规则排序</Pill>
        <Pill className="soft">匹配度排序</Pill>
        <Pill className="soft">薪资排序</Pill>
      </div>
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'340px 1fr', gap: 24 }}>
      {/* trace pinned */}
      <div>
        <Box className="filled-dark" style={{ padding: 16, borderRadius: 16, position:'relative', overflow:'hidden' }}>
          <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'#b0aea5', marginBottom: 10 }}>AI THINKING · 14.2s</div>
          <div className="sk-mono" style={{ color:'#d0cec4', fontSize: 13, lineHeight: 2 }}>
            <div><span style={{ color:'var(--accent)' }}>✓</span> 🔍 search_candidates · 284</div>
            <div><span style={{ color:'var(--accent)' }}>✓</span> 📄 inspect_jobs · 12</div>
            <div><span style={{ color:'var(--accent)' }}>✓</span> 🏢 get_company_intel · 9</div>
            <div><span style={{ color:'var(--accent)' }}>✓</span> 🌐 search_web · 4</div>
            <div><span style={{ color:'#f5f4ed' }}>✢</span> ✅ finalize</div>
            <div style={{ color:'#87867f', paddingLeft: 14, fontSize: 12 }}>weighing 3 top cands…</div>
          </div>
        </Box>
        <div style={{ height: 12 }}/>
        <Box style={{ padding: 12 }}>
          <div className="sk-hw-b" style={{ fontSize: 14, marginBottom: 4 }}>分数构成</div>
          <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', lineHeight: 1.5 }}>
            Base = 技能匹配 · 地域<br/>
            Enhanced = + 公司情报 + JD 原文
          </div>
        </Box>
      </div>

      {/* jobs column */}
      <div style={{ display:'flex', flexDirection:'column', gap: 10 }}>
        {JOBS.map(([title, sub, score], i) => (
          <Box key={i} style={{ padding: 14, borderRadius: 14 }}>
            <div style={{ display:'flex', alignItems:'flex-start', gap: 10 }}>
              <div style={{ width: 40, textAlign:'center' }}>
                <div className="sk-serif" style={{ fontSize: 24, color:'var(--accent)' }}>{score}</div>
                <div className="sk-hw" style={{ fontSize: 10, color:'var(--soft)', marginTop:-4 }}>Base / Enhanced</div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display:'flex', alignItems:'center', gap: 6 }}>
                  <span className="sk-sans" style={{ fontWeight: 700, fontSize: 14 }}>{i+1}. {title}</span>
                </div>
                <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>{sub}</div>
                {/* inline reasoning bubble */}
                <Box className="filled-soft" style={{ padding: 8, marginTop: 6, borderRadius: 10 }}>
                  <span className="sk-hw" style={{ fontSize: 13 }}>
                    <b>为什么 {score}：</b>
                    {['技能全覆盖 (PyTorch/LLM) + 上海优先 + 蚂蚁 T1',
                      '行业契合但 JD 未写具体业务线，Enhanced 补 -4',
                      '技术栈对齐 · 多城市可选',
                      '补招窗口小 · 需快投',
                      '实习转正 · 岗位画像接近'][i]}
                  </span>
                </Box>
                <div style={{ display:'flex', gap: 6, marginTop: 6 }}>
                  <Pill className="amber">To-T1 主流平台</Pill>
                  <Btn label="投递" variant="accent" h={22} style={{ padding:'0 10px' }}/>
                  <Btn label="打开 JD" variant="line" h={22} style={{ padding:'0 10px' }}/>
                </div>
              </div>
            </div>
          </Box>
        ))}
      </div>
    </div>

    <Note style={{ bottom: 30, left: 48 }}>每张卡都带"为什么这个分"的一句话解释</Note>
  </div>
);

// 03 — Map-like radar view (unconventional): jobs as dots on a 2D map (fit × reach)
const Results_C = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, padding: '32px 48px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 16 }}>
      <Wordmark />
      <div className="sk-hw" style={{ color:'var(--soft)' }}>岗位雷达视图 · 实验</div>
    </div>
    <div className="sk-serif" style={{ fontSize: 28, marginBottom: 4 }}>284 个候选里，你的 Top 5 长这样</div>
    <div className="sk-hw" style={{ fontSize: 15, color:'var(--soft)', marginBottom: 16 }}>横轴：技能契合 · 纵轴：公司梯队 · 圆圈大小：岗位热度</div>

    <div style={{ display:'grid', gridTemplateColumns:'1.3fr 1fr', gap: 24 }}>
      {/* Radar / scatter */}
      <Box style={{ padding: 24, borderRadius: 18, height: 560, position:'relative', background:'#fbfaf5' }}>
        {/* axes */}
        <div style={{ position:'absolute', left: 24, top: 24, bottom: 24, width: 1, background:'var(--hair)' }}/>
        <div style={{ position:'absolute', left: 24, right: 24, bottom: 24, height: 1, background:'var(--hair)' }}/>
        <div style={{ position:'absolute', left: 10, top: 20, fontSize: 12, color:'var(--soft)' }} className="sk-hw">T1</div>
        <div style={{ position:'absolute', left: 10, bottom: 40, fontSize: 12, color:'var(--soft)' }} className="sk-hw">T3</div>
        <div style={{ position:'absolute', right: 30, bottom: 8, fontSize: 12, color:'var(--soft)' }} className="sk-hw">契合 ↑</div>

        {/* grid lines */}
        {[0.25,0.5,0.75].map(v => (
          <React.Fragment key={v}>
            <div style={{ position:'absolute', left: `${24 + (100-48)*v/100 * 5}px`, top: 24, bottom: 24, width: 1, background:'var(--hair)', opacity: 0.5 }}/>
          </React.Fragment>
        ))}

        {/* 200 gray dots (candidates) */}
        {Array.from({length: 40}).map((_, i) => {
          const x = 30 + Math.random() * 380; const y = 30 + Math.random() * 450;
          const s = 4 + Math.random() * 6;
          return <div key={i} style={{ position:'absolute', left: x, top: y, width: s, height: s, borderRadius:'50%', background:'#d1cfc5' }}/>;
        })}

        {/* top 5 dots */}
        {[
          { x: 380, y: 60,  r: 22, n: 1, score: 96 },
          { x: 340, y: 110, r: 18, n: 2, score: 92 },
          { x: 300, y: 160, r: 20, n: 3, score: 92 },
          { x: 280, y: 210, r: 18, n: 4, score: 92 },
          { x: 320, y: 260, r: 16, n: 5, score: 91 },
        ].map(d => (
          <div key={d.n} style={{ position:'absolute', left: d.x, top: d.y }}>
            <div style={{ width: d.r*2, height: d.r*2, borderRadius:'50%', background:'var(--accent)', opacity: 0.25 }}/>
            <div style={{ position:'absolute', top: d.r-10, left: d.r-10, width: 20, height: 20, borderRadius:'50%', background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:"'Caveat'", fontWeight:700, fontSize: 12 }}>{d.n}</div>
            <div style={{ position:'absolute', top: d.r*2, left: d.r+6, fontSize: 12, fontFamily:"'Caveat'", color:'var(--accent)', fontWeight: 700 }}>{d.score}</div>
          </div>
        ))}

        {/* your radius — "sweet spot" */}
        <div style={{ position:'absolute', left: 310, top: 110, width: 180, height: 180, borderRadius:'50%', border: '1.4px dashed var(--accent)', opacity: 0.6 }}/>
        <div style={{ position:'absolute', left: 310, top: 95, color:'var(--accent)', fontSize: 13, fontFamily:"'Caveat'" }} className="sk-hw-b">你的甜蜜区</div>
      </Box>

      {/* ranked mini-list */}
      <div>
        <div className="sk-hw-b" style={{ fontSize: 16, marginBottom: 8 }}>Top 5 · 点击跳到地图</div>
        <div style={{ display:'flex', flexDirection:'column', gap: 8 }}>
          {JOBS.map(([title,sub,score], i) => (
            <Box key={i} className={i===0?'accent':''} style={{ padding: 10, display:'flex', alignItems:'center', gap: 10 }}>
              <div style={{ width: 22, height: 22, borderRadius:'50%', background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:"'Caveat'", fontWeight:700, fontSize: 12 }}>{i+1}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{title}</div>
                <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>{sub.split('·')[0]}</div>
              </div>
              <div className="sk-serif" style={{ color:'var(--accent)' }}>{score}</div>
            </Box>
          ))}
        </div>
        <div style={{ height: 14 }}/>
        <Box className="filled-soft" style={{ padding: 12 }}>
          <div className="sk-hw" style={{ fontSize: 14 }}>💡 你的候选里还有 <b>9 个</b> 在"次甜蜜区"— 切到下一批看看？</div>
          <div style={{ height: 8 }}/>
          <Btn label="看第二批 →" variant="line" h={28} />
        </Box>
      </div>
    </div>
    <Note style={{ bottom: 30, right: 48 }} side="r">"地图"隐喻 — 让 284 个候选变得可视<br/>可能过于 geek — 留作可选视图</Note>
  </div>
);

Object.assign(window, { Results_A, Results_B, Results_C });
