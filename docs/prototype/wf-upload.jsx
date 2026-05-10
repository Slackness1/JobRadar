/* global React, Box, Pill, Line, Para, ImgBox, Note, BrandDot, Wordmark, ToolLine, Input, Btn, Spin */

// ============================================================
// UPLOAD + PARSING FLOW — 3 directions
// ============================================================

// 01 — Classic paper upload card, before & after split
const Upload_A = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '28px 40px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 20 }}>
      <Wordmark />
      <div className="sk-hw" style={{ color:'var(--soft)' }}>第 1 步 · 上传简历</div>
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 28 }}>
      {/* Before: big drop zone */}
      <div>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 10 }}>上传前</div>
        <Box className="dashed" style={{ height: 360, borderRadius: 28, padding: 24, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap: 10, borderWidth: 1.6 }}>
          <div style={{ width: 64, height: 64, borderRadius: '50%', background:'var(--accent-soft)', display:'flex', alignItems:'center', justifyContent:'center', color:'var(--accent)', fontSize: 28 }}>↑</div>
          <div className="sk-serif" style={{ fontSize: 24 }}>把 PDF 简历拖进来</div>
          <div className="sk-hw" style={{ color:'var(--soft)', fontSize: 15 }}>也支持 .docx · 最大 10 MB</div>
          <Btn label="或从本地选择文件" variant="line" h={36} />
        </Box>
        <div style={{ height: 14 }}/>
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>支持：PDF · DOCX · 扫描件 OCR（内测）</div>
      </div>

      {/* After: parsing in progress with agent trace */}
      <div>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 10 }}>解析中（~8 秒）</div>
        <Box style={{ padding: 18, borderRadius: 22 }}>
          <div style={{ display:'flex', alignItems:'center', gap: 10, marginBottom: 14 }}>
            <BrandDot size={22} />
            <span className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>周传博_简历.pdf</span>
            <Pill className="amber" style={{ marginLeft:'auto' }}>1.4 MB</Pill>
          </div>
          {/* progress bar */}
          <Box className="thin" style={{ height: 6, borderRadius: 99, padding: 0, background:'#efede4', borderWidth: 1 }}>
            <div style={{ width: '62%', height: '100%', background:'var(--accent)', borderRadius: 99 }}/>
          </Box>
          <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)', textAlign:'right', marginTop: 4 }}>62% · 正在提取结构化字段</div>

          <div style={{ height: 18 }}/>
          <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 6 }}>AI 推理中</div>
          <div style={{ display:'flex', flexDirection:'column', gap: 8 }}>
            <ToolLine icon="📄" label="读取 PDF 文本层" done />
            <ToolLine icon="🔍" label="识别教育经历 · 工作经历" done />
            <ToolLine icon="🏢" label="匹配公司库 · 补齐元数据" />
            <div style={{ display:'flex', alignItems:'center', gap: 8, fontSize: 14, color:'var(--soft)' }}>
              <Spin ch="✳" /> <span className="sk-hw" style={{ fontSize: 17 }}>正在推理...</span>
            </div>
          </div>
        </Box>

        <div style={{ height: 14 }}/>
        <Box className="filled-soft" style={{ padding: '10px 14px' }}>
          <span className="sk-hw" style={{ fontSize: 15 }}>💡 简历解析结果会自动填入下一步的偏好编辑器</span>
        </Box>
      </div>
    </div>

    <Note style={{ top: 90, right: 60 }} side="r">双栏：用户一眼看到"上传 → 结果"</Note>
  </div>
);

// 02 — Full-screen dark parsing screen (the "signature dark surface" per the guide)
const Upload_B = () => (
  <div style={{ width: 1280, height: 820, background:'var(--ink)', color:'#f5f4ed', position:'relative', padding: '60px 80px', overflow:'hidden' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 60 }}>
      <div style={{ display:'inline-flex', alignItems:'center', gap: 8 }}>
        <BrandDot size={24} />
        <span className="sk-sans" style={{ fontWeight: 700, color:'#f5f4ed' }}>JobRadar</span>
      </div>
      <span className="sk-hw" style={{ color:'#87867f' }}>esc 取消</span>
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1fr 520px', gap: 80, alignItems:'center' }}>
      <div>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.15em', textTransform:'uppercase', color:'#b0aea5', marginBottom: 14 }}>AI THINKING · 6.4s</div>
        <div className="sk-serif" style={{ fontSize: 58, lineHeight: 1.0, letterSpacing:'-0.04em', marginBottom: 24, color:'#f5f4ed' }}>
          正在读你的<br/>简历。<span style={{ color:'var(--accent)' }}>一分钟。</span>
        </div>
        <div className="sk-hw" style={{ fontSize: 16, color:'#b0aea5', marginBottom: 36, maxWidth: 420 }}>
          把平台梯队、岗位画像和不确定点一起讲清楚
        </div>

        {/* terminal-style trace */}
        <div className="sk-mono" style={{ fontSize: 14, color:'#d0cec4', lineHeight: 1.9 }}>
          <div><span style={{ color:'var(--accent)' }}>✓</span> read_pdf &nbsp;→ 3 页 / 1.4MB</div>
          <div><span style={{ color:'var(--accent)' }}>✓</span> extract_sections &nbsp;→ 教育 · 工作 · 项目 · 技能</div>
          <div><span style={{ color:'var(--accent)' }}>✓</span> match_companies &nbsp;→ 12 / 14 命中</div>
          <div><span style={{ color:'#f5f4ed' }}>✢</span> infer_preferences &nbsp;<span style={{ color:'#87867f' }}>金融科技 / 数据分析</span></div>
          <div style={{ color:'#87867f' }}>&nbsp;&nbsp; pending · normalize_skills</div>
        </div>
      </div>

      {/* Right — miniature emerging resume */}
      <Box style={{ background:'#1c1c1a', borderColor:'#30302e', padding: 20, borderRadius: 18 }}>
        <div className="sk-serif" style={{ color:'#f5f4ed', fontSize: 22, marginBottom: 4 }}>周传博</div>
        <div className="sk-hw" style={{ color:'#87867f', fontSize: 14, marginBottom: 14 }}>数据科学家</div>
        <div style={{ borderTop:'1px solid #30302e', paddingTop: 12, marginBottom: 10 }}>
          <div className="sk-hw" style={{ color:'#b0aea5', fontSize: 13, marginBottom: 4 }}>教育背景</div>
          <Line w="80%" className="dark" />
          <div style={{ height: 4 }}/>
          <Line w="60%" className="dark" />
        </div>
        <div style={{ marginBottom: 10 }}>
          <div className="sk-hw" style={{ color:'#b0aea5', fontSize: 13, marginBottom: 4 }}>工作经历</div>
          <Line w="100%" className="dark" />
          <div style={{ height: 4 }}/>
          <Line w="72%" className="dark" />
        </div>
        <div style={{ marginBottom: 10, opacity: 0.4 }}>
          <div className="sk-hw" style={{ color:'#87867f', fontSize: 13, marginBottom: 4 }}>项目经历</div>
          <Line w="90%" />
          <div style={{ height: 4 }}/>
          <Line w="40%" />
        </div>
      </Box>
    </div>

    <Note style={{ bottom: 32, left: 80 }}>终端美学 + 真实进度 = "这产品懂技术"</Note>
  </div>
);

// 03 — Three-step horizontal flow (stepper) with resume morphing across stages
const Upload_C = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, padding: '40px 56px', position:'relative' }}>
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 28 }}>
      <Wordmark />
      <Btn label="保存草稿" variant="line" />
    </div>

    {/* Stepper */}
    <div style={{ display:'flex', alignItems:'center', gap: 0, marginBottom: 28 }}>
      {['上传','解析','确认偏好'].map((s, i) => {
        const active = i <= 1;
        return (
          <React.Fragment key={s}>
            <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius:'50%',
                border: `1.6px solid ${active ? 'var(--accent)' : 'var(--hair)'}`,
                background: active ? 'var(--accent)' : 'transparent',
                color: active ? '#fff' : 'var(--soft)',
                display:'flex', alignItems:'center', justifyContent:'center',
                fontFamily:"'Caveat', cursive", fontWeight: 700, fontSize: 16,
              }}>{i + 1}</div>
              <span className="sk-serif" style={{ fontSize: 20, color: active ? 'var(--ink)' : 'var(--soft)' }}>{s}</span>
            </div>
            {i < 2 && <div style={{ flex: 1, height: 1.4, background:'var(--hair)', margin:'0 20px', position:'relative' }}>
              {i === 0 && <div style={{ position:'absolute', inset:0, background:'var(--accent)', transformOrigin:'left', transform:'scaleX(1)' }}/>}
            </div>}
          </React.Fragment>
        );
      })}
    </div>

    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap: 20 }}>
      {/* Step 1 — done */}
      <Box style={{ padding: 18, borderRadius: 20, opacity: 0.55 }}>
        <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 10 }}>
          <span style={{ color:'var(--accent)' }}>✓</span>
          <span className="sk-hw-b" style={{ fontSize: 17 }}>上传</span>
        </div>
        <Box className="filled-soft" style={{ padding: 12, display:'flex', alignItems:'center', gap: 10 }}>
          <div style={{ width: 36, height: 44, background:'#fff', border:'1px solid var(--hair)', borderRadius: 4 }}/>
          <div>
            <div className="sk-sans" style={{ fontWeight: 600, fontSize: 13 }}>周传博_简历.pdf</div>
            <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>1.4 MB · 3 页</div>
          </div>
        </Box>
      </Box>

      {/* Step 2 — active */}
      <Box className="accent" style={{ padding: 18, borderRadius: 20, boxShadow:'0 0 0 1px var(--accent-soft), 0 10px 30px rgba(201,100,66,0.08)' }}>
        <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 10 }}>
          <Spin ch="✻" accent />
          <span className="sk-hw-b" style={{ fontSize: 17 }}>解析中</span>
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap: 8 }}>
          <ToolLine icon="📄" label="读取 PDF 文本" done />
          <ToolLine icon="🔍" label="识别结构字段" done />
          <ToolLine icon="🏢" label="补齐公司信息" />
          <ToolLine icon="✅" label="生成偏好草稿" />
        </div>
        <div style={{ height: 12 }}/>
        <Box className="thin" style={{ padding: 10, background:'#fff' }}>
          <div className="sk-mono" style={{ fontSize: 12, color:'var(--soft)' }}>inferring目标方向...</div>
          <div className="sk-mono" style={{ fontSize: 12 }}>→ 数据分析 · 金融科技</div>
        </Box>
      </Box>

      {/* Step 3 — upcoming */}
      <Box style={{ padding: 18, borderRadius: 20, opacity: 0.45 }}>
        <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 10 }}>
          <span style={{ color:'var(--soft)' }}>·</span>
          <span className="sk-hw-b" style={{ fontSize: 17 }}>确认偏好</span>
        </div>
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)', marginBottom: 8 }}>我们会预填：</div>
        <div style={{ display:'flex', flexWrap:'wrap', gap: 6 }}>
          <Pill className="soft">金融科技</Pill>
          <Pill className="soft">数据分析师</Pill>
          <Pill className="soft">上海</Pill>
          <Pill className="soft">互联网</Pill>
        </div>
        <div style={{ height: 12 }}/>
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>下一步你可以补充或改动</div>
      </Box>
    </div>

    <div style={{ height: 28 }}/>
    <Box style={{ padding: 16, borderRadius: 16, display:'flex', alignItems:'center', gap: 12 }}>
      <span style={{ fontSize: 18 }}>💡</span>
      <div>
        <div className="sk-sans" style={{ fontWeight: 600, fontSize: 14 }}>为什么要三步？</div>
        <div className="sk-hw" style={{ fontSize: 15, color:'var(--soft)' }}>
          第一步我们读你的简历 · 第二步 AI 起草目标岗位 · 第三步你确认 — 每步都能撤回
        </div>
      </div>
    </Box>

    <Note style={{ top: 180, right: 60 }} side="r">进度条是"信任锚"<br/>用户看到 AI 做了什么</Note>
  </div>
);

Object.assign(window, { Upload_A, Upload_B, Upload_C });
