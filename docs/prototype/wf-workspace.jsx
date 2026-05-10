/* global React, Box, Pill, Line, Para, ImgBox, Note, BrandDot, Wordmark, ToolLine, Input, Btn, Spin */

// ============================================================
// 3-PANE WORKSPACE — 3 directions
// ============================================================

// Shared sidebar bit
const Sidebar = ({ w = 220 }) => (
  <div style={{ width: w, background:'var(--hair)', borderRight:'1px solid var(--hair)', padding: 14, display:'flex', flexDirection:'column', gap: 10 }}>
    <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
      <div style={{ width:22, height:22, borderRadius:6, background:'var(--ink)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 12 }}>N</div>
      <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>简历鸭</span>
      <span className="sk-hw" style={{ color:'var(--soft)', marginLeft:'auto', fontSize: 13 }}>›</span>
    </div>
    <Box className="filled-accent" style={{ padding:'6px 10px', textAlign:'center' }}>
      <span className="sk-hw-b" style={{ fontSize: 14, color:'#fff' }}>+ 新建会话</span>
    </Box>
    <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)', marginTop: 4 }}>我的简历</div>
    {[0,1,2,3].map(i => (
      <Box key={i} className={i===0?'filled-soft':'thin'} style={{ padding:'8px 10px' }}>
        <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>周传博 简历</div>
        <div className="sk-hw" style={{ color:'var(--soft)', fontSize: 12 }}>{i===0 ? '今天更新' : `${i+1} 天前`}</div>
      </Box>
    ))}
    <div style={{ flex: 1 }}/>
    <div className="sk-hw" style={{ color:'var(--soft)', fontSize: 13 }}>⌂ 返回首页</div>
  </div>
);

// 01 — Close to current: sidebar + chat-centered middle + preview right
const Workspace_A = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, display:'flex', position:'relative' }}>
    <Sidebar />
    <div style={{ flex: 1, display:'flex', flexDirection:'column', borderRight:'1px solid var(--hair)' }}>
      <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--hair)', display:'flex', alignItems:'center', gap: 10 }}>
        <BrandDot size={24} />
        <div>
          <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>AI 简历助手</div>
          <div className="sk-hw" style={{ color:'var(--soft)', fontSize: 12 }}>AI 简历助手</div>
        </div>
        <span style={{ marginLeft:'auto', color:'var(--accent)' }}>✓</span>
      </div>
      <div style={{ flex: 1, padding: 16, overflow:'hidden' }}>
        <Box className="filled-soft" style={{ padding: 12, borderRadius: 14, marginBottom: 14 }}>
          <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)', marginBottom: 4 }}>暂无分析结果。如需重新分析，请在下方修改目标岗位后点击"保存并重新分析"。</div>
        </Box>
        <Box style={{ padding: 12, borderRadius: 14, marginBottom: 14, borderColor:'#c7e5cf', background:'#edf7ef' }}>
          <div className="sk-hw" style={{ fontSize: 14 }}>AI 已生成结构化摘要，你可以先有问有答，或者继续编辑简历模块。</div>
        </Box>

        {/* prefs block collapsed */}
        <Box style={{ padding: 14, borderRadius: 16, marginBottom: 14 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom: 6 }}>
            <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
              <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>修改目标岗位</span>
              <Pill className="soft">已填写</Pill>
            </div>
            <span className="sk-hw" style={{ color:'var(--soft)' }}>▾</span>
          </div>
          <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>数据科学家 · 上海 · 互联网</div>
        </Box>
      </div>
      {/* composer */}
      <div style={{ padding: 14, borderTop:'1px solid var(--hair)' }}>
        <Box style={{ background:'var(--hair)', padding:'10px 12px', display:'flex', alignItems:'center', gap: 10 }}>
          <span className="sk-hw" style={{ color:'var(--soft)', flex: 1 }}>问我如何优化这份简历...</span>
          <div style={{ width: 28, height: 28, borderRadius:'50%', background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center' }}>↑</div>
        </Box>
      </div>
    </div>

    {/* Preview right */}
    <div style={{ width: 440, display:'flex', flexDirection:'column' }}>
      <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--hair)', display:'flex', alignItems:'center', gap: 8 }}>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>预览所见</span>
        <div style={{ marginLeft:'auto', display:'flex', gap: 6 }}>
          <Pill className="soft">页边距</Pill>
          <Pill className="soft">模块边距</Pill>
          <Pill className="soft">行间距</Pill>
          <Pill className="soft">字体大小</Pill>
        </div>
        <Btn label="保存" variant="accent" h={26} style={{ padding:'0 10px' }} />
      </div>
      <div style={{ flex: 1, padding: 20, background:'#f5f4ed' }}>
        <Box style={{ padding: 16, borderRadius: 10, height:'100%' }}>
          <div className="sk-serif" style={{ fontSize: 26, textAlign:'center' }}>周传博</div>
          <div className="sk-hw" style={{ textAlign:'center', color:'var(--soft)', fontSize: 14, marginBottom: 12 }}>数据科学家</div>
          <div style={{ borderTop:'1px solid var(--hair)', paddingTop: 10 }}>
            <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13, color:'var(--accent)', marginBottom: 6 }}>教育背景</div>
            <Para rows={3} />
            <div style={{ height: 12 }}/>
            <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13, color:'var(--accent)', marginBottom: 6 }}>工作经历</div>
            <Para rows={4} widths={['100%','92%','85%','40%']} />
          </div>
        </Box>
      </div>
    </div>
    <Note style={{ top: 12, left: 240 }}>现有布局：窄侧栏 / 聊天流 / 简历预览</Note>
  </div>
);

// 02 — Preview-led: resume is the hero (2/3), chat is a docked right panel
const Workspace_B = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, display:'flex', position:'relative' }}>
    <Sidebar w={200} />
    {/* Preview big */}
    <div style={{ flex: 1.6, padding: 24, background:'#f5f4ed', borderRight:'1px solid var(--hair)' }}>
      <div style={{ display:'flex', alignItems:'center', gap: 10, marginBottom: 12 }}>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>周传博 简历 · 数据科学家</span>
        <Pill className="amber">分析中</Pill>
        <div style={{ marginLeft:'auto', display:'flex', gap: 6 }}>
          <Pill>撤销</Pill>
          <Pill>对比原版</Pill>
          <Btn label="导出 PDF" variant="accent" h={26} style={{ padding:'0 10px' }} />
        </div>
      </div>
      <Box style={{ padding: 28, borderRadius: 12, height: 720 }}>
        <div className="sk-serif" style={{ fontSize: 36, textAlign:'center' }}>周传博</div>
        <div className="sk-hw" style={{ textAlign:'center', color:'var(--soft)', fontSize: 16, marginBottom: 18 }}>数据科学家 · 上海</div>
        {/* highlighted edit in-place */}
        <div style={{ padding: 10, background:'#fff6ea', borderLeft:'3px solid var(--accent)', borderRadius: 4, marginBottom: 16 }}>
          <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13, color:'var(--accent)', marginBottom: 4 }}>AI 建议修改</div>
          <Para rows={2} widths={['100%','60%']} />
        </div>
        <div className="sk-sans" style={{ fontWeight: 600, fontSize: 14, color:'var(--accent)', marginBottom: 6 }}>工作经历</div>
        <Para rows={5} widths={['100%','92%','85%','88%','50%']} />
        <div style={{ height: 14 }}/>
        <div className="sk-sans" style={{ fontWeight: 600, fontSize: 14, color:'var(--accent)', marginBottom: 6 }}>项目经历</div>
        <Para rows={4} widths={['100%','88%','70%','44%']} />
      </Box>
    </div>
    {/* right: chat docked */}
    <div style={{ width: 360, display:'flex', flexDirection:'column' }}>
      <div style={{ padding:'10px 14px', borderBottom:'1px solid var(--hair)', display:'flex', alignItems:'center', gap: 8 }}>
        <BrandDot size={22}/>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>AI 简历助手</span>
        <span style={{ marginLeft:'auto', color:'var(--soft)', fontSize: 12 }}>×</span>
      </div>
      <div style={{ flex: 1, padding: 14, overflow:'hidden' }}>
        <Box className="filled-soft" style={{ padding: 10, marginBottom: 8 }}>
          <div className="sk-hw" style={{ fontSize: 14 }}>把"工作经历"里第 1 条的量化指标再强一点</div>
        </Box>
        <Box style={{ padding: 10, marginBottom: 8 }}>
          <div className="sk-hw" style={{ fontSize: 14, marginBottom: 6 }}>我给了 3 种改写：</div>
          <div style={{ display:'flex', flexDirection:'column', gap: 6 }}>
            <Box className="thin" style={{ padding: 8 }}><Line w="92%"/><div style={{height:3}}/><Line w="60%"/></Box>
            <Box className="thin" style={{ padding: 8 }}><Line w="88%"/><div style={{height:3}}/><Line w="72%"/></Box>
            <Box className="thin accent" style={{ padding: 8 }}><Line w="90%" className="accent"/><div style={{height:3}}/><Line w="55%"/></Box>
          </div>
          <div style={{ display:'flex', gap: 6, marginTop: 8 }}>
            <Btn label="应用第 3 条" variant="accent" h={26}/>
            <Btn label="再来一批" variant="line" h={26}/>
          </div>
        </Box>
      </div>
      <div style={{ padding: 12, borderTop:'1px solid var(--hair)' }}>
        <Box style={{ background:'var(--hair)', padding:'8px 12px', display:'flex', alignItems:'center', gap: 8 }}>
          <span className="sk-hw" style={{ color:'var(--soft)', flex: 1, fontSize: 14 }}>问我...</span>
          <div style={{ width: 22, height: 22, borderRadius:'50%', background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 13 }}>↑</div>
        </Box>
      </div>
    </div>
    <Note style={{ top: 40, right: 140 }} side="r">预览为主角 — 简历本身就是 UI</Note>
  </div>
);

// 03 — Agent-first: collapsed rail + big agent trace theater + small preview
const Workspace_C = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, display:'flex', position:'relative' }}>
    {/* thin icon rail */}
    <div style={{ width: 56, background:'var(--hair)', padding:'14px 0', display:'flex', flexDirection:'column', alignItems:'center', gap: 12 }}>
      <BrandDot size={28}/>
      <div style={{ height: 16 }}/>
      {['📝','🔍','⚙︎','?'].map((ic, i) => (
        <div key={i} style={{ width: 32, height: 32, borderRadius: 8, background: i===0?'#fff':'transparent', border: i===0?'1px solid var(--hair)':'none', display:'flex', alignItems:'center', justifyContent:'center' }}>{ic}</div>
      ))}
    </div>

    {/* middle: agent theater */}
    <div style={{ flex: 1.2, padding: 20, borderRight:'1px solid var(--hair)', display:'flex', flexDirection:'column' }}>
      <div style={{ display:'flex', alignItems:'center', gap: 10, marginBottom: 14 }}>
        <div className="sk-hw-b" style={{ fontSize: 18 }}>代理思考中</div>
        <Pill className="amber">快增强</Pill>
        <span className="sk-hw" style={{ color:'var(--soft)', fontSize: 13, marginLeft:'auto' }}>12.4s · 3 agents</span>
      </div>
      {/* Animated lanes */}
      {[
        { n: 1, label: '召回岗位中', icon:'✢', desc:'扫 互联网/券商 共 284 个相关职位' },
        { n: 2, label: '生成检索词', icon:'✳', desc:'从你的简历抽出 12 个关键词并加权' },
        { n: 3, label: '提取页面正文', icon:'✶', desc:'按 JD 原文判断 must-have / nice-to-have' },
      ].map((a, i) => (
        <Box key={i} className="thin" style={{ padding: 12, marginBottom: 10, display:'flex', gap: 12 }}>
          <Spin ch={a.icon} accent={i===0} />
          <div style={{ flex: 1 }}>
            <div style={{ display:'flex', alignItems:'baseline', gap: 10 }}>
              <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>Agent {a.n}</span>
              <span className="sk-hw" style={{ color:'var(--soft)' }}>·</span>
              <span className="sk-hw-b" style={{ fontSize: 15 }}>{a.label}</span>
            </div>
            <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>{a.desc}</div>
          </div>
          <span className="sk-mono" style={{ fontSize: 11, color:'var(--soft)' }}>{i===0?'4.1s':i===1?'—':'—'}</span>
        </Box>
      ))}

      <div style={{ marginTop: 10 }}>
        <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', marginBottom: 8 }}>已完成步骤</div>
        <Box style={{ padding: 10, marginBottom: 6 }}>
          <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
            <span style={{ color:'var(--accent)' }}>✓</span>
            <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>阅读岗位详情</span>
            <span className="sk-hw" style={{ color:'var(--soft)', marginLeft: 'auto', fontSize: 12 }}>读取 5 个岗位完整 JD</span>
          </div>
        </Box>
        <Box style={{ padding: 10 }}>
          <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
            <span style={{ color:'var(--accent)' }}>✓</span>
            <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>阅读岗位详情</span>
            <span className="sk-hw" style={{ color:'var(--soft)', marginLeft: 'auto', fontSize: 12 }}>金融科技 / 数据类岗位</span>
          </div>
        </Box>
      </div>
    </div>

    {/* right: small preview + results */}
    <div style={{ width: 440, display:'flex', flexDirection:'column' }}>
      <div style={{ padding: 14, borderBottom:'1px solid var(--hair)', display:'flex', gap: 8, alignItems:'center' }}>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>真实岗位推荐 Top 5</span>
        <Pill className="soft" style={{ marginLeft:'auto' }}>规则排序</Pill>
      </div>
      <div style={{ flex: 1, padding: 14, display:'flex', flexDirection:'column', gap: 8 }}>
        {[96,92,92,92,91].map((s, i) => (
          <Box key={i} className="thin" style={{ padding: 10 }}>
            <div style={{ display:'flex', alignItems:'baseline', gap: 6 }}>
              <span className="sk-sans" style={{ fontWeight: 700, fontSize: 13 }}>{i+1}.</span>
              <span className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>
                {['【应届补招】AI 工程师','AI 应用研发工程师','智能体大模型应用','【转正实习】智能体','大模型应用全栈'][i]}
              </span>
              <span className="sk-serif" style={{ marginLeft:'auto', color:'var(--accent)', fontSize: 15 }}>{s} ↗</span>
            </div>
            <div className="sk-hw" style={{ color:'var(--soft)', fontSize: 12, marginTop: 2 }}>Base {s} · Enhanced {s} · To-T1 主流平台</div>
          </Box>
        ))}
      </div>
    </div>

    <Note style={{ top: 100, left: 90 }}>把 "AI 思考" 当作中心剧场<br/>左栏折叠，简历临时退到侧位</Note>
  </div>
);

Object.assign(window, { Workspace_A, Workspace_B, Workspace_C });
