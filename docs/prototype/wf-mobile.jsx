/* global React, Box, Pill, Line, Para, ImgBox, Note, BrandDot, Wordmark, ToolLine, Btn, Spin */

// ============================================================
// MOBILE COMPANION — 3 directions (375 × 780 iPhone-ish)
// ============================================================

const Phone = ({ children, label }) => (
  <div style={{ width: 375, height: 780, background:'var(--paper)', border:'2px solid var(--ink)', borderRadius: 36, padding: '10px 0', position:'relative', overflow:'hidden', boxShadow:'0 20px 40px rgba(0,0,0,0.08)' }}>
    {/* notch */}
    <div style={{ position:'absolute', top: 6, left:'50%', transform:'translateX(-50%)', width: 120, height: 22, background:'var(--ink)', borderRadius: 99 }}/>
    <div style={{ padding:'28px 16px 0', height:'100%', overflow:'hidden' }}>{children}</div>
    {label && <div className="sk-caption" style={{ position:'absolute', bottom:-28, left: 0, right: 0, textAlign:'center' }}>{label}</div>}
  </div>
);

// 01 — Feed-style: one card at a time, swipe up for next; minimal trace
const Mobile_A = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '28px 40px', position:'relative', display:'flex', gap: 40, justifyContent:'center', alignItems:'center' }}>
    <Phone label="1. 发现流">
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 14 }}>
        <Wordmark size={14} />
        <span style={{ fontSize: 18 }}>≡</span>
      </div>
      <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>今日推送 · 3 / 5</div>
      <Box style={{ padding: 16, marginTop: 10, borderRadius: 18 }}>
        <div style={{ display:'flex', alignItems:'center', gap: 6, marginBottom: 6 }}>
          <Pill className="amber">To-T1</Pill>
          <span className="sk-serif" style={{ color:'var(--accent)', marginLeft:'auto', fontSize: 22 }}>96</span>
        </div>
        <div className="sk-sans" style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>【应届补招】AI 工程师-应用方向</div>
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)', marginBottom: 10 }}>蚂蚁科技集团 · 上海</div>
        <Para rows={3} widths={['100%','92%','70%']} />
        <div style={{ height: 12 }}/>
        <Box className="filled-soft" style={{ padding: 8, borderRadius: 8 }}>
          <span className="sk-hw" style={{ fontSize: 13 }}>🏢 情报增强：团队规模 ~120，最近发过 3 个类似岗位</span>
        </Box>
        <div style={{ display:'flex', gap: 8, marginTop: 12 }}>
          <Btn label="跳过" variant="line" h={34} w="50%" />
          <Btn label="投递" variant="accent" h={34} w="50%" />
        </div>
      </Box>
      <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', textAlign:'center', marginTop: 18 }}>↑ 上滑看下一条</div>
    </Phone>

    <Phone label="2. 详情抽屉">
      <div style={{ display:'flex', alignItems:'center', marginBottom: 10 }}>
        <span style={{ fontSize: 18, color:'var(--soft)' }}>←</span>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14, marginLeft: 8 }}>岗位详情</span>
        <span style={{ marginLeft:'auto', fontSize: 16 }}>☆</span>
      </div>
      <div className="sk-serif" style={{ fontSize: 20, marginBottom: 4 }}>AI 工程师-应用方向</div>
      <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', marginBottom: 10 }}>蚂蚁科技集团 · 上海 · 月薪 25-45k</div>
      <div style={{ display:'flex', gap: 6, marginBottom: 10 }}>
        <Pill className="amber">To-T1</Pill>
        <Pill className="amber">情报增强</Pill>
      </div>
      <Box style={{ padding: 10, marginBottom: 8 }}>
        <div className="sk-hw-b" style={{ fontSize: 13 }}>为什么给你 96 分</div>
        <Para rows={3} widths={['100%','94%','60%']} />
      </Box>
      <Box style={{ padding: 10 }}>
        <div className="sk-hw-b" style={{ fontSize: 13 }}>职位描述</div>
        <Para rows={6} widths={['100%','96%','88%','92%','70%','40%']} />
      </Box>
      <div style={{ position:'absolute', bottom: 20, left: 16, right: 16, display:'flex', gap: 8 }}>
        <Btn label="保存" variant="line" w="40%" h={40} />
        <Btn label="立即投递 →" variant="accent" w="60%" h={40} />
      </div>
    </Phone>
    <Note style={{ top: 24, left: '50%', transform:'translateX(-50%) rotate(-1.5deg)' }}>类 Tinder 式发现流：一屏一岗位</Note>
  </div>
);

// 02 — Inbox + trace terminal at the bottom (Claude-code vibe)
const Mobile_B = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, padding: '28px 40px', position:'relative', display:'flex', gap: 40, justifyContent:'center', alignItems:'center' }}>
    <Phone label="1. 今日推荐">
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 14 }}>
        <div>
          <div className="sk-serif" style={{ fontSize: 22 }}>早 周传博</div>
          <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>今天有 5 个新岗位适合你</div>
        </div>
        <BrandDot size={32}/>
      </div>
      {[96,92,92,92,91].map((s,i) => (
        <Box key={i} style={{ padding: 10, marginBottom: 6, display:'flex', alignItems:'center', gap: 8 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background:'var(--accent-soft)', display:'flex', alignItems:'center', justifyContent:'center' }}>
            <span className="sk-serif" style={{ color:'var(--accent)', fontSize: 14 }}>{s}</span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sk-sans" style={{ fontWeight: 600, fontSize: 12, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
              {['AI 工程师-应用','AI 应用研发','智能体大模型','转正实习智能体','大模型全栈实习'][i]}
            </div>
            <div className="sk-hw" style={{ fontSize: 11, color:'var(--soft)' }}>{['蚂蚁·上海','阿里','蚂蚁·多城','蚂蚁·多城','抖音·上海'][i]}</div>
          </div>
          <span className="sk-hw" style={{ color:'var(--soft)' }}>›</span>
        </Box>
      ))}
      {/* bottom tab bar */}
      <div style={{ position:'absolute', bottom: 0, left: 0, right: 0, height: 60, borderTop:'1px solid var(--hair)', display:'flex', background:'var(--paper)' }}>
        {['🏠 推荐','🔍 搜索','💬 助手','👤 我'].map((t,i) => (
          <div key={i} style={{ flex: 1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', fontSize: 12, color: i===0?'var(--accent)':'var(--soft)' }}>
            <span className="sk-hw">{t}</span>
          </div>
        ))}
      </div>
    </Phone>

    <Phone label="2. AI 助手 (终端感)">
      <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 10 }}>
        <BrandDot size={24}/>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>AI 简历助手</span>
        <Pill className="amber" style={{ marginLeft:'auto' }}>快增强</Pill>
      </div>
      <Box className="filled-dark" style={{ padding: 12, borderRadius: 12, marginBottom: 10 }}>
        <div className="sk-mono" style={{ color:'#d0cec4', fontSize: 12, lineHeight: 1.9 }}>
          <div><span style={{ color:'var(--accent)' }}>✓</span> 🔍 search_candidates</div>
          <div><span style={{ color:'var(--accent)' }}>✓</span> 📄 inspect_jobs · 5</div>
          <div><span style={{ color:'#f5f4ed' }}>✢</span> 🏢 get_company_intel</div>
          <div style={{ color:'#87867f' }}>  &nbsp; pending · finalize</div>
        </div>
      </Box>
      <Box className="filled-soft" style={{ padding: 10, marginBottom: 8 }}>
        <span className="sk-hw" style={{ fontSize: 13 }}>你问："蚂蚁和字节哪个更适合我？"</span>
      </Box>
      <Box style={{ padding: 10 }}>
        <Para rows={4} widths={['100%','92%','86%','60%']} />
      </Box>
      <div style={{ position:'absolute', bottom: 64, left: 16, right: 16 }}>
        <Box style={{ background:'var(--hair)', padding: '8px 12px', display:'flex', alignItems:'center', gap: 8 }}>
          <span className="sk-hw" style={{ color:'var(--soft)', flex: 1, fontSize: 13 }}>问我任何事…</span>
          <div style={{ width: 24, height: 24, borderRadius:'50%', background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 12 }}>↑</div>
        </Box>
      </div>
    </Phone>
    <Note style={{ top: 24, left: '50%', transform:'translateX(-50%) rotate(1.5deg)' }} side="r">移动端也保留"终端感" — 这是产品人设</Note>
  </div>
);

// 03 — Card stack + investor-vibe dashboard
const Mobile_C = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '28px 40px', position:'relative', display:'flex', gap: 40, justifyContent:'center', alignItems:'center' }}>
    <Phone label="1. 仪表盘">
      <div className="sk-serif" style={{ fontSize: 24, marginBottom: 2 }}>你的求职进度</div>
      <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', marginBottom: 16 }}>本周 · 4 月 17–23</div>

      {/* Big metric */}
      <Box className="filled-accent" style={{ padding: 16, borderRadius: 16, marginBottom: 12, color:'#fff' }}>
        <div className="sk-hw" style={{ fontSize: 13, opacity: 0.8 }}>已投递</div>
        <div className="sk-serif" style={{ fontSize: 48, lineHeight: 1, margin:'4px 0' }}>12</div>
        <div className="sk-hw" style={{ fontSize: 13, opacity: 0.8 }}>+3 本周 · 命中率 58%</div>
      </Box>

      <div style={{ display:'flex', gap: 8, marginBottom: 12 }}>
        <Box style={{ padding: 10, flex: 1, borderRadius: 12 }}>
          <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>待处理</div>
          <div className="sk-serif" style={{ fontSize: 26 }}>7</div>
        </Box>
        <Box style={{ padding: 10, flex: 1, borderRadius: 12 }}>
          <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>面试中</div>
          <div className="sk-serif" style={{ fontSize: 26 }}>3</div>
        </Box>
        <Box style={{ padding: 10, flex: 1, borderRadius: 12 }}>
          <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>Offer</div>
          <div className="sk-serif" style={{ fontSize: 26, color:'var(--accent)' }}>1</div>
        </Box>
      </div>

      <div className="sk-hw-b" style={{ fontSize: 14, marginBottom: 8 }}>最近动态</div>
      {['蚂蚁 · 进入二面','字节 · 简历通过','字节 · 已投递'].map((t,i) => (
        <div key={i} style={{ display:'flex', alignItems:'center', gap: 10, marginBottom: 8 }}>
          <div style={{ width: 6, height: 6, borderRadius:'50%', background: i===0?'var(--accent)':'var(--hair)' }}/>
          <span className="sk-hw" style={{ fontSize: 13 }}>{t}</span>
          <span className="sk-hw" style={{ marginLeft:'auto', fontSize: 12, color:'var(--soft)' }}>{i+1}h</span>
        </div>
      ))}
    </Phone>

    <Phone label="2. 投递追踪">
      <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 18 }}>←</span>
        <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>蚂蚁 · AI 工程师</span>
        <span style={{ marginLeft:'auto', fontSize: 16 }}>⋯</span>
      </div>
      {/* progress pipeline */}
      <div style={{ display:'flex', alignItems:'center', gap: 4, marginBottom: 14 }}>
        {['投递','简历','一面','二面','Offer'].map((s, i) => {
          const active = i <= 3;
          return (
            <div key={s} style={{ flex: 1, textAlign:'center' }}>
              <div style={{ height: 4, background: active ? 'var(--accent)' : 'var(--hair)', borderRadius: 2 }}/>
              <div className="sk-hw" style={{ fontSize: 11, color: active ? 'var(--accent)' : 'var(--soft)', marginTop: 4 }}>{s}</div>
            </div>
          );
        })}
      </div>

      <Box className="filled-soft" style={{ padding: 10, marginBottom: 10 }}>
        <div className="sk-hw-b" style={{ fontSize: 13 }}>下一步：二面 · 明天 14:00</div>
        <div className="sk-hw" style={{ fontSize: 12, color:'var(--soft)' }}>面试官：李某 · 数据算法 LD</div>
      </Box>

      <div className="sk-hw-b" style={{ fontSize: 13, marginBottom: 6 }}>AI 准备包 (自动生成)</div>
      {['📌 高频考点：LLM 应用落地经验','📝 模拟题：3 道技术 + 2 道项目','🏢 公司情报：最近两次 OKR'].map(x => (
        <Box key={x} style={{ padding: 10, marginBottom: 6, display:'flex', alignItems:'center' }}>
          <span className="sk-hw" style={{ fontSize: 13, flex: 1 }}>{x}</span>
          <span className="sk-hw" style={{ color:'var(--soft)' }}>›</span>
        </Box>
      ))}
      <div style={{ position:'absolute', bottom: 20, left: 16, right: 16 }}>
        <Btn label="打开面试准备包 →" variant="accent" h={40} w="100%" />
      </div>
    </Phone>
    <Note style={{ bottom: 50, left: '50%', transform:'translateX(-50%) rotate(-1deg)' }}>面向投资人演示：指标 + 追踪 + AI 辅助</Note>
  </div>
);

Object.assign(window, { Mobile_A, Mobile_B, Mobile_C });
