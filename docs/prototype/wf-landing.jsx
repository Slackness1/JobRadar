/* global React, Box, Pill, Line, Para, ImgBox, Note, Caption, BrandDot, Wordmark, ToolLine, Input, Btn, Spin */

// ============================================================
// LANDING / LOGIN — 3 directions
// ============================================================

// 01 — Classic centered hero, left headline + right paper card (close to current)
const Landing_A = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '32px 48px', position:'relative' }}>
    {/* top nav */}
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 48 }}>
      <Wordmark />
      <div style={{ display:'flex', gap: 12 }}>
        <span className="sk-hw" style={{ fontSize: 16, color:'var(--soft)' }}>产品</span>
        <span className="sk-hw" style={{ fontSize: 16, color:'var(--soft)' }}>关于</span>
        <Btn label="登录" variant="line" />
        <Btn label="开始使用" variant="accent" />
      </div>
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1.18fr 1fr', gap: 48, alignItems:'start' }}>
      <div>
        <Pill className="amber" style={{ marginBottom: 18 }}>情报增强内测中</Pill>
        <div className="sk-serif" style={{ fontSize: 64, lineHeight: 0.98, letterSpacing: '-0.04em', marginBottom: 20 }}>
          更快发现<br/>
          真正值得<span className="sk-squiggle">投递</span>的岗位
        </div>
        <div className="sk-hw" style={{ fontSize: 18, color:'var(--soft)', maxWidth: 480, marginBottom: 28 }}>
          面向高校就业与职业发展场景，聚合互联网、券商、央国企、银行等重点平台岗位
        </div>
        <div style={{ display:'flex', gap: 12, marginBottom: 36 }}>
          <Btn label="上传简历 →" variant="accent" h={40} />
          <Btn label="看示例推荐" variant="line" h={40} />
        </div>

        {/* ticker */}
        <Box className="thin" style={{ padding: '10px 14px', display:'flex', gap: 28, overflow:'hidden' }}>
          <span className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>实时更新 ·</span>
          <span className="sk-hw" style={{ fontSize: 14 }}>蚂蚁 AI 工程师</span>
          <span className="sk-hw" style={{ fontSize: 14 }}>字节 大模型</span>
          <span className="sk-hw" style={{ fontSize: 14 }}>腾讯金融 AI</span>
          <span className="sk-hw" style={{ fontSize: 14 }}>招商银行 数据</span>
        </Box>
      </div>

      {/* Right — paper card preview */}
      <Box style={{ padding: 16, borderRadius: 22 }}>
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)', marginBottom: 8 }}>示例推荐</div>
        <div className="sk-serif" style={{ fontSize: 18, marginBottom: 10 }}>真实岗位推荐 Top 5</div>
        {[0,1,2,3,4].map(i => (
          <Box key={i} className="thin" style={{ padding: 10, marginBottom: 8, display:'flex', alignItems:'center', gap: 10 }}>
            <span className="sk-hw-b" style={{ fontSize: 16 }}>{i+1}.</span>
            <div style={{ flex: 1 }}>
              <Line w="70%" />
              <div style={{ height: 4 }}/>
              <Line w="45%" className="dark" />
            </div>
            <span className="sk-serif" style={{ color:'var(--accent)' }}>{96 - i}</span>
          </Box>
        ))}
      </Box>
    </div>

    <Note style={{ top: 120, right: 40 }} side="r">标配预览：直接把产品截图放这里，少说多看</Note>
  </div>
);

// 02 — Login-focused split; half parchment / half dark; big count-up metric
const Landing_B = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, display:'grid', gridTemplateColumns:'1fr 1fr', position:'relative' }}>
    <div style={{ padding: '48px 56px', display:'flex', flexDirection:'column', justifyContent:'space-between' }}>
      <Wordmark />
      <div>
        <Pill style={{ marginBottom: 16 }}>面向应届 · 实习 · 转正</Pill>
        <div className="sk-serif" style={{ fontSize: 56, lineHeight: 1.02, letterSpacing: '-0.04em', marginBottom: 18 }}>
          登录 JobRadar<br/>
          <span style={{ color:'var(--soft)' }}>继续你的求职。</span>
        </div>
        <div className="sk-hw" style={{ fontSize: 18, color:'var(--soft)', maxWidth: 400, marginBottom: 28 }}>
          先给第一版推荐，再对重点岗位做 10–20 秒快增强
        </div>
        <div style={{ display:'flex', alignItems:'baseline', gap: 12, marginBottom: 24 }}>
          <span className="sk-serif" style={{ fontSize: 72, letterSpacing:'-0.04em', color:'var(--accent)' }}>12,834</span>
          <span className="sk-hw" style={{ fontSize: 18, color:'var(--soft)' }}>今日新岗位</span>
        </div>
        <div style={{ display:'flex', gap: 16, flexWrap:'wrap' }}>
          <div><span className="sk-serif" style={{ fontSize: 28 }}>420+</span><div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>公司</div></div>
          <div><span className="sk-serif" style={{ fontSize: 28 }}>4</span><div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>平台梯队</div></div>
          <div><span className="sk-serif" style={{ fontSize: 28 }}>96</span><div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>最高 Base 分</div></div>
        </div>
      </div>
      <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>© 2026 JobRadar · feature/big-wip</div>
    </div>

    {/* Right dark panel: login */}
    <div style={{ background:'var(--ink)', color:'#f5f4ed', padding:'72px 56px', display:'flex', flexDirection:'column', justifyContent:'center' }}>
      <div className="sk-serif" style={{ fontSize: 34, marginBottom: 20 }}>登录 / 注册</div>
      <div className="sk-hw" style={{ fontSize: 14, color:'#b0aea5', marginBottom: 6 }}>邮箱</div>
      <Box style={{ background:'transparent', borderColor:'#30302e', padding:'8px 12px', marginBottom: 16 }}>
        <span className="sk-hw" style={{ color:'#8a8a86' }}>you@school.edu.cn</span>
      </Box>
      <div className="sk-hw" style={{ fontSize: 14, color:'#b0aea5', marginBottom: 6 }}>验证码</div>
      <div style={{ display:'flex', gap: 8, marginBottom: 24 }}>
        <Box style={{ flex: 1, background:'transparent', borderColor:'#30302e', padding:'8px 12px' }}>
          <span className="sk-hw" style={{ color:'#8a8a86' }}>6 位</span>
        </Box>
        <Box style={{ background:'transparent', borderColor:'#30302e', padding:'8px 12px' }}>
          <span className="sk-hw" style={{ color:'#b0aea5' }}>获取验证码</span>
        </Box>
      </div>
      <Btn label="登录 →" variant="accent" h={44} />
      <div style={{ height: 20 }}/>
      <div className="sk-hw" style={{ fontSize: 13, color:'#87867f' }}>登录即同意《用户协议》《隐私政策》</div>

      <div style={{ height: 48 }}/>
      <Box className="dashed" style={{ background:'transparent', borderColor:'#30302e', padding: 14 }}>
        <div className="sk-hw" style={{ color:'#b0aea5', fontSize: 13, marginBottom: 6 }}>还没登录？直接试一下</div>
        <div className="sk-serif" style={{ color:'#f5f4ed', fontSize: 18 }}>拖入一份 PDF 简历 →</div>
      </Box>
    </div>

    <Note style={{ top: 40, right: 40 }} side="r">大数字 = 实时性证明<br/>(count-up 动画 1.2s)</Note>
  </div>
);

// 03 — Editorial magazine cover: serif dominates, numbered sections
const Landing_C = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '36px 56px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', borderBottom: '1px solid var(--hair)', paddingBottom: 12, marginBottom: 28 }}>
      <Wordmark />
      <span className="sk-hw" style={{ color:'var(--soft)' }}>第 04 期 · 2026 春招</span>
      <Btn label="登录" variant="line" />
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1fr 1.4fr 0.9fr', gap: 28 }}>
      <div>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'0.15em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 8 }}>01 · 产品</div>
        <div className="sk-serif" style={{ fontSize: 22, marginBottom: 12 }}>多源岗位聚合 + 简历评分 + ReAct 代理</div>
        <Para rows={4} widths={['100%','96%','90%','60%']} />
        <div style={{ height: 24 }}/>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'0.15em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 8 }}>02 · 覆盖</div>
        <Para rows={3} widths={['100%','88%','54%']} />
      </div>

      <div>
        <div className="sk-serif" style={{ fontSize: 92, lineHeight: 0.92, letterSpacing:'-0.05em', marginBottom: 12 }}>
          更快<br/>发现值得<br/><span style={{ color:'var(--accent)' }}>投递</span>的岗位。
        </div>
        <div style={{ display:'flex', gap: 10, marginTop: 24 }}>
          <Btn label="上传简历 →" variant="accent" h={42} />
          <Btn label="看示例推荐" variant="line" h={42} />
        </div>
      </div>

      <div>
        <ImgBox style={{ height: 280, marginBottom: 16 }} label="产品截图 · 真实 UI" />
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)', marginBottom: 8 }}>当前分类</div>
        <div style={{ display:'flex', flexWrap:'wrap', gap: 6 }}>
          <Pill className="active">互联网</Pill>
          <Pill>券商</Pill>
          <Pill>央国企</Pill>
          <Pill>银行</Pill>
          <Pill>金融科技</Pill>
        </div>
        <div style={{ height: 18 }}/>
        <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>"面向高校就业与职业发展场景"</div>
      </div>
    </div>

    <Note style={{ bottom: 24, left: 48 }}>像 NYT Magazine 那种栏位感 — 敢用大号 serif</Note>
  </div>
);

Object.assign(window, { Landing_A, Landing_B, Landing_C });
