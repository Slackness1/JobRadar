/* global React, Box, Pill, Line, Para, ImgBox, Note, BrandDot, Wordmark, Btn, Spin */

// ============================================================
// JOBRADAR CORE — scraper dashboard / filter / admin — 3 directions
// ============================================================

// 01 — Table-first admin (engineering/ops view)
const Core_A = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, display:'flex', position:'relative' }}>
    {/* left nav */}
    <div style={{ width: 210, background:'var(--hair)', padding: 16, borderRight:'1px solid var(--hair)' }}>
      <Wordmark />
      <div style={{ height: 14 }}/>
      <div className="sk-hw" style={{ fontSize: 12, letterSpacing:'.1em', color:'var(--soft)', marginBottom: 6 }}>控制台</div>
      {['📡 站点节点','🗂 岗位库','⚙︎ 过滤规则','🔖 标签','📈 抓取日志','🧑 用户','🔐 权限'].map((x,i) => (
        <div key={x} style={{ padding:'6px 10px', borderRadius: 6, background: i===1?'var(--paper)':'transparent', marginBottom: 2 }}>
          <span className="sk-hw" style={{ fontSize: 14, color: i===1?'var(--ink)':'var(--soft)' }}>{x}</span>
        </div>
      ))}
      <div style={{ height: 14 }}/>
      <Box className="thin" style={{ padding: 10 }}>
        <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>今日抓取</div>
        <div className="sk-serif" style={{ fontSize: 20, color:'var(--accent)' }}>12,834</div>
        <div className="sk-hw" style={{ fontSize: 11, color:'var(--soft)' }}>42 节点 · 3 失败</div>
      </Box>
    </div>

    {/* main */}
    <div style={{ flex: 1, padding: 20 }}>
      <div style={{ display:'flex', alignItems:'baseline', gap: 10, marginBottom: 14 }}>
        <div className="sk-serif" style={{ fontSize: 26 }}>岗位库</div>
        <span className="sk-hw" style={{ color:'var(--soft)' }}>· 284,502 条</span>
        <div style={{ marginLeft:'auto', display:'flex', gap: 8 }}>
          <Btn label="+ 新增节点" variant="line" h={30}/>
          <Btn label="导出 CSV" variant="line" h={30}/>
          <Btn label="重跑失败" variant="accent" h={30}/>
        </div>
      </div>

      {/* filter bar */}
      <div style={{ display:'flex', gap: 8, marginBottom: 12, flexWrap:'wrap' }}>
        <Box className="thin" style={{ padding:'6px 10px', display:'flex', alignItems:'center', gap: 6 }}>
          <span className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>🔍 关键词</span>
          <span className="sk-hw" style={{ fontSize: 13 }}>AI</span>
        </Box>
        <Pill className="active">互联网</Pill>
        <Pill>券商</Pill>
        <Pill>央国企</Pill>
        <Pill>银行</Pill>
        <Pill className="soft">+ 标签</Pill>
        <div style={{ flex: 1 }}/>
        <Pill className="soft">最近 7 天</Pill>
        <Pill className="soft">去重后</Pill>
      </div>

      {/* table */}
      <Box style={{ padding: 0, overflow:'hidden' }}>
        <div style={{ display:'grid', gridTemplateColumns:'60px 2fr 1.3fr 1fr 90px 120px 80px 40px', padding:'10px 14px', borderBottom:'1px solid var(--hair)', background:'#faf9f0', fontSize: 12, color:'var(--soft)', fontFamily:"'Inter', sans-serif", fontWeight: 600 }}>
          {['ID','岗位名','公司','城市','梯队','更新','状态',''].map(h => <div key={h}>{h}</div>)}
        </div>
        {[
          ['1042','AI 工程师-应用方向','蚂蚁科技','上海','T1','3m ago','active'],
          ['1041','AI 应用研发工程师','阿里巴巴','—','T1','12m','active'],
          ['1040','智能体与大模型应用工程','蚂蚁集团','北京/上海','T1','23m','active'],
          ['1039','转正实习 智能体','蚂蚁集团','多城','T1','41m','active'],
          ['1038','大模型应用全栈实习','字节跳动','上海','T1','1h','active'],
          ['1037','量化分析师 (MMT)','中金公司','北京','T1','2h','dup?'],
          ['1036','风控数据分析','招商银行','深圳','T2','3h','active'],
          ['1035','产品经理-商业化','拼多多','上海','T1','5h','stale'],
          ['1034','【央国企】数据工程','中电科技','成都','T3','6h','active'],
          ['1033','投研实习生','中信建投','北京','T1','8h','active'],
        ].map((r,i) => (
          <div key={i} style={{ display:'grid', gridTemplateColumns:'60px 2fr 1.3fr 1fr 90px 120px 80px 40px', padding:'10px 14px', borderBottom:'1px dashed var(--hair)', fontSize: 13, alignItems:'center' }}>
            <span className="sk-mono" style={{ color:'var(--soft)' }}>#{r[0]}</span>
            <span className="sk-sans" style={{ fontWeight: 600 }}>{r[1]}</span>
            <span className="sk-sans">{r[2]}</span>
            <span className="sk-hw" style={{ color:'var(--soft)' }}>{r[3]}</span>
            <Pill className={r[4]==='T1'?'active':r[4]==='T2'?'amber':'soft'} style={{ fontSize: 11 }}>{r[4]}</Pill>
            <span className="sk-hw" style={{ color:'var(--soft)' }}>{r[5]}</span>
            <span className="sk-hw" style={{ color: r[6]==='active'?'#2f7a3a':r[6]==='dup?'?'#a16207':'var(--soft)', fontSize: 12 }}>● {r[6]}</span>
            <span style={{ color:'var(--soft)' }}>⋯</span>
          </div>
        ))}
      </Box>

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginTop: 10 }}>
        <span className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>显示 1–10 共 284,502</span>
        <div style={{ display:'flex', gap: 6 }}>
          <Pill>‹</Pill><Pill className="active">1</Pill><Pill>2</Pill><Pill>3</Pill><Pill>›</Pill>
        </div>
      </div>
    </div>

    <Note style={{ top: 20, right: 40 }} side="r">工程/运营向 — 密度优先</Note>
  </div>
);

// 02 — Node map: YAML site-nodes visualized as a graph, status chips
const Core_B = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '28px 40px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 18 }}>
      <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
        <Wordmark />
        <span className="sk-hw" style={{ color:'var(--soft)' }}>· 站点节点视图</span>
      </div>
      <div style={{ display:'flex', gap: 8 }}>
        <Pill className="active">运行中 38</Pill>
        <Pill className="amber">报警 2</Pill>
        <Pill className="soft">停用 4</Pill>
        <Btn label="+ 新增站点" variant="accent" h={30}/>
      </div>
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1fr 360px', gap: 20 }}>
      {/* graph area */}
      <Box style={{ padding: 22, borderRadius: 16, height: 640, position:'relative', overflow:'hidden', background:'#fbfaf5' }}>
        {/* center hub */}
        <div style={{ position:'absolute', left:'50%', top:'50%', transform:'translate(-50%,-50%)', width: 120, height: 120, borderRadius: 16, background:'var(--ink)', color:'#fff', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center' }}>
          <BrandDot size={28}/>
          <div className="sk-sans" style={{ fontWeight: 700, fontSize: 14, marginTop: 8 }}>JobRadar</div>
          <div className="sk-hw" style={{ fontSize: 12, color:'#b0aea5' }}>scraper core</div>
        </div>

        {/* categories circle */}
        {[
          { label:'互联网', count: 18, x: 120, y: 100 },
          { label:'券商',   count: 8,  x: 420, y: 80 },
          { label:'央国企', count: 6,  x: 680, y: 160 },
          { label:'银行',   count: 10, x: 740, y: 380 },
          { label:'外企',   count: 4,  x: 560, y: 540 },
          { label:'初创',   count: 12, x: 200, y: 520 },
        ].map(c => (
          <div key={c.label} style={{ position:'absolute', left: c.x, top: c.y, width: 140 }}>
            <Box className="thin" style={{ padding: 10 }}>
              <div className="sk-hw-b" style={{ fontSize: 14 }}>{c.label}</div>
              <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>{c.count} 个节点</div>
              <div style={{ display:'flex', gap: 3, marginTop: 6 }}>
                {Array.from({length: c.count}).map((_, i) => (
                  <div key={i} style={{ width: 6, height: 6, borderRadius:'50%', background: i === 0 && c.label==='券商' ? '#b53333' : 'var(--accent)' }}/>
                ))}
              </div>
            </Box>
          </div>
        ))}

        {/* lines from hub to nodes */}
        <svg style={{ position:'absolute', inset: 0, width:'100%', height:'100%', pointerEvents:'none' }}>
          {[
            [190, 120, 380, 340],
            [490, 100, 420, 330],
            [750, 180, 460, 330],
            [810, 400, 460, 360],
            [630, 560, 430, 380],
            [270, 540, 390, 380],
          ].map(([x1,y1,x2,y2], i) => (
            <path key={i} d={`M ${x1} ${y1} Q ${(x1+x2)/2} ${(y1+y2)/2 + 20} ${x2} ${y2}`} stroke="var(--hair)" strokeWidth="1.2" fill="none"/>
          ))}
        </svg>

        {/* legend */}
        <div style={{ position:'absolute', bottom: 14, left: 14, display:'flex', gap: 12, fontSize: 12 }}>
          <span className="sk-hw" style={{ color:'var(--soft)' }}><span className="sk-dot"/> 运行</span>
          <span className="sk-hw" style={{ color:'var(--soft)' }}><span style={{ display:'inline-block', width:10, height:10, borderRadius:99, background:'#b53333' }}/> 失败</span>
        </div>
      </Box>

      {/* sidebar: clicked node detail */}
      <div>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 10 }}>节点详情 · 中金公司</div>
        <Box style={{ padding: 16, borderRadius: 14, marginBottom: 10 }}>
          <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
            <span className="sk-dot" style={{ background:'#b53333' }}/>
            <span className="sk-sans" style={{ fontWeight: 700, fontSize: 14 }}>cicc.com/campus</span>
            <Pill className="amber" style={{ marginLeft:'auto' }}>失败 3 次</Pill>
          </div>
          <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', marginTop: 6 }}>券商 · T1 · YAML 节点 id = <span className="sk-mono">cicc_campus</span></div>
          <div style={{ height: 10 }}/>
          <div className="sk-mono" style={{ fontSize: 11, background:'#f0eee6', padding: 8, borderRadius: 6, color:'var(--ink)', lineHeight: 1.8 }}>
            parser: html-list-v2<br/>
            selector: .job-item<br/>
            retries: 3 · last_error: timeout
          </div>
        </Box>
        <div className="sk-hw-b" style={{ fontSize: 13, marginBottom: 6 }}>最近 24h</div>
        <Box style={{ padding: 10 }}>
          <div style={{ display:'flex', alignItems:'end', gap: 2, height: 40 }}>
            {[12,14,10,18,16,0,0,0,18,22,14,12].map((h,i) => (
              <div key={i} style={{ flex:1, height: Math.max(4,h), background: h===0?'#b53333':'var(--accent)', borderRadius: 1.5 }}/>
            ))}
          </div>
          <div className="sk-hw" style={{ fontSize: 11, color:'var(--soft)', marginTop: 4 }}>0 点开始连续 3 次失败</div>
        </Box>
        <div style={{ height: 10 }}/>
        <Btn label="重跑这个节点" variant="accent" h={34} w="100%" />
      </div>
    </div>
    <Note style={{ bottom: 20, right: 40 }} side="r">把 YAML 站点节点可视化 —<br/>对投资人讲"我们有 42 个数据源"</Note>
  </div>
);

// 03 — Investor-flavored health dashboard
const Core_C = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, padding: '28px 48px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 16 }}>
      <Wordmark />
      <div style={{ display:'flex', gap: 8 }}>
        <Pill className="soft">今日</Pill>
        <Pill className="active">本周</Pill>
        <Pill className="soft">本月</Pill>
      </div>
    </div>
    <div className="sk-serif" style={{ fontSize: 32, marginBottom: 4 }}>产品健康面板</div>
    <div className="sk-hw" style={{ fontSize: 15, color:'var(--soft)', marginBottom: 18 }}>本周 · 4 月 17–23 · feature/big-wip-20260315</div>

    {/* KPI row */}
    <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap: 14, marginBottom: 18 }}>
      {[
        ['新增用户', '2,842', '+18%'],
        ['解析简历', '1,204', '+24%'],
        ['推荐命中率', '58%', '+6pp'],
        ['投递转化', '41%', '+3pp'],
      ].map(([k,v,d]) => (
        <Box key={k} style={{ padding: 16, borderRadius: 14 }}>
          <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>{k}</div>
          <div style={{ display:'flex', alignItems:'baseline', gap: 8 }}>
            <span className="sk-serif" style={{ fontSize: 34, color:'var(--ink)' }}>{v}</span>
            <span className="sk-hw" style={{ color:'#2f7a3a', fontSize: 13 }}>{d}</span>
          </div>
          {/* sparkline */}
          <svg viewBox="0 0 100 20" style={{ width:'100%', height: 24, marginTop: 4 }}>
            <polyline points="0,16 14,14 28,12 42,13 56,9 70,7 84,5 100,4" fill="none" stroke="var(--accent)" strokeWidth="1.4"/>
          </svg>
        </Box>
      ))}
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr', gap: 16 }}>
      {/* scraper activity */}
      <Box style={{ padding: 18, borderRadius: 16 }}>
        <div style={{ display:'flex', alignItems:'baseline', gap: 8, marginBottom: 10 }}>
          <div className="sk-hw-b" style={{ fontSize: 15 }}>抓取活动 · 7 日</div>
          <span className="sk-hw" style={{ color:'var(--soft)', fontSize: 13 }}>42 节点 · 互联网 / 券商 / 央国企 / 银行</span>
          <span className="sk-hw" style={{ marginLeft:'auto', color:'var(--soft)', fontSize: 13 }}>峰值 14.2k/天</span>
        </div>
        {/* stacked bars */}
        <div style={{ display:'flex', alignItems:'flex-end', gap: 10, height: 180 }}>
          {[
            [60, 30, 20, 10],
            [70, 38, 22, 12],
            [55, 28, 18, 8],
            [80, 40, 28, 14],
            [90, 42, 26, 16],
            [72, 36, 24, 12],
            [96, 46, 30, 18],
          ].map((col, i) => {
            const total = col.reduce((a,b)=>a+b, 0);
            return (
              <div key={i} style={{ flex: 1, display:'flex', flexDirection:'column-reverse', height:'100%' }}>
                <div style={{ height: (col[0]/120)*100+'%', background:'var(--accent)' }}/>
                <div style={{ height: (col[1]/120)*100+'%', background:'#e8b09b' }}/>
                <div style={{ height: (col[2]/120)*100+'%', background:'#d9d6cc' }}/>
                <div style={{ height: (col[3]/120)*100+'%', background:'#f0eee6' }}/>
                <div className="sk-hw" style={{ fontSize: 11, color:'var(--soft)', textAlign:'center', paddingTop: 4 }}>D{i+1}</div>
              </div>
            );
          })}
        </div>
        <div style={{ display:'flex', gap: 14, marginTop: 10, fontSize: 12 }}>
          <span className="sk-hw"><span style={{ display:'inline-block', width:10, height:10, background:'var(--accent)', borderRadius:2, marginRight: 4 }}/>互联网</span>
          <span className="sk-hw"><span style={{ display:'inline-block', width:10, height:10, background:'#e8b09b', borderRadius:2, marginRight: 4 }}/>券商</span>
          <span className="sk-hw"><span style={{ display:'inline-block', width:10, height:10, background:'#d9d6cc', borderRadius:2, marginRight: 4 }}/>央国企</span>
          <span className="sk-hw"><span style={{ display:'inline-block', width:10, height:10, background:'#f0eee6', borderRadius:2, marginRight: 4, border:'1px solid var(--hair)' }}/>银行</span>
        </div>
      </Box>

      {/* funnel */}
      <Box style={{ padding: 18, borderRadius: 16 }}>
        <div className="sk-hw-b" style={{ fontSize: 15, marginBottom: 14 }}>漏斗 · 本周</div>
        {[
          ['访问落地页', '12,402', 1.0],
          ['上传简历', '1,842', 0.70],
          ['收到 Top 5', '1,798', 0.68],
          ['打开 JD', '1,104', 0.42],
          ['投递', '458', 0.18],
        ].map(([label, v, w], i) => (
          <div key={label} style={{ marginBottom: 10 }}>
            <div style={{ display:'flex', justifyContent:'space-between' }}>
              <span className="sk-sans" style={{ fontSize: 13 }}>{label}</span>
              <span className="sk-mono" style={{ fontSize: 12, color:'var(--soft)' }}>{v}</span>
            </div>
            <div style={{ height: 10, background:'var(--hair)', borderRadius: 4, marginTop: 4 }}>
              <div style={{ width: `${w*100}%`, height:'100%', background:'var(--accent)', opacity: 0.4 + w*0.6, borderRadius: 4 }}/>
            </div>
          </div>
        ))}
      </Box>
    </div>

    <Note style={{ top: 90, right: 48 }} side="r">给投资人看的一屏 —<br/>数据 + 漏斗 + 趋势</Note>
  </div>
);

Object.assign(window, { Core_A, Core_B, Core_C });
