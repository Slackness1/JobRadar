/* global React, Box, Pill, Line, Para, ImgBox, Note, BrandDot, Wordmark, Input, Btn */

// ============================================================
// 修改目标岗位 PREFERENCES EDITOR — 3 directions
// ============================================================

const CATS = ['金融科技','咨询','数据分析','产品运营','后端开发','投研'];
const ROLES = ['数据分析师','后端工程师','产品经理','咨询顾问','投研实习生'];
const CITIES = ['上海','北京','深圳','杭州','广州','远程'];
const COMPS = ['互联网','金融机构','咨询公司','外企','初创公司','国央企'];

// 01 — Pill grid (current pattern, cleaned up) inside a collapsible card
const Prefs_A = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '40px 80px', position:'relative' }}>
    <Wordmark />
    <div style={{ height: 20 }}/>
    <div className="sk-serif" style={{ fontSize: 32, marginBottom: 6 }}>修改目标岗位</div>
    <div className="sk-hw" style={{ fontSize: 16, color:'var(--soft)', marginBottom: 20 }}>告诉我你心里想的方向，越具体越准。留空也可以，我会自动推断。</div>

    <Box style={{ padding: 22, borderRadius: 20, maxWidth: 860 }}>
      <div style={{ display:'flex', alignItems:'center', gap: 8, marginBottom: 18 }}>
        <span className="sk-sans" style={{ fontWeight: 600 }}>已展开 · 修改后 AI 会重新打分</span>
        <Pill className="soft">已填写</Pill>
        <Btn label="✎ 修改目标岗位" variant="line" h={28} style={{ marginLeft:'auto', padding:'0 10px' }}/>
      </div>

      {[
        ['目标行业', CATS, [0,5]],
        ['岗位方向', ROLES, [0,1]],
        ['意向城市', CITIES, [0,3]],
        ['公司类型', COMPS, [0,4]],
      ].map(([label, opts, selected]) => (
        <div key={label} style={{ marginBottom: 14 }}>
          <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)', marginBottom: 6 }}>{label}</div>
          <div style={{ display:'flex', flexWrap:'wrap', gap: 6 }}>
            {opts.map((o, i) => (
              <Pill key={o} className={selected.includes(i) ? 'active' : ''}>{o}</Pill>
            ))}
          </div>
        </div>
      ))}

      <div style={{ height: 12 }}/>
      <div style={{ display:'flex', gap: 8, justifyContent:'flex-end' }}>
        <Btn label="暂且保留" variant="line" h={32} />
        <Btn label="✓ 保存" variant="line" h={32} />
        <Btn label="保存并重新分析" variant="accent" h={32} />
      </div>
    </Box>

    <Note style={{ top: 140, right: 60 }} side="r">清晰的选项分组 + 颜色状态</Note>
  </div>
);

// 02 — Conversational intake (chat-driven wizard)
const Prefs_B = () => (
  <div className="sk-paper" style={{ width: 1280, height: 820, padding: '40px 80px', position:'relative' }}>
    <Wordmark />
    <div style={{ height: 20 }}/>
    <div style={{ display:'grid', gridTemplateColumns:'1fr 360px', gap: 36 }}>
      <div>
        <div className="sk-serif" style={{ fontSize: 28, marginBottom: 16 }}>来，聊几句偏好</div>

        {/* chat blocks */}
        <div style={{ display:'flex', gap: 10, marginBottom: 12 }}>
          <BrandDot size={28}/>
          <Box style={{ padding: 12, borderRadius: 14, maxWidth: 560 }}>
            <div className="sk-hw" style={{ fontSize: 16 }}>我读完了你的简历，看起来你偏数据方向。主要城市想在哪？</div>
          </Box>
        </div>
        <div style={{ display:'flex', gap: 10, marginBottom: 12, justifyContent:'flex-end' }}>
          <Box className="filled-accent" style={{ padding: 10, borderRadius: 14 }}>
            <span className="sk-hw" style={{ fontSize: 16, color:'#fff' }}>上海优先，北京也可以</span>
          </Box>
        </div>
        <div style={{ display:'flex', gap: 10, marginBottom: 12 }}>
          <BrandDot size={28}/>
          <Box style={{ padding: 12, borderRadius: 14, maxWidth: 560 }}>
            <div className="sk-hw" style={{ fontSize: 16, marginBottom: 8 }}>公司类型倾向？（多选）</div>
            <div style={{ display:'flex', flexWrap:'wrap', gap: 6 }}>
              {COMPS.map((c, i) => <Pill key={c} className={[0,1].includes(i)?'active':''}>{c}</Pill>)}
            </div>
          </Box>
        </div>
        <div style={{ display:'flex', gap: 10, marginBottom: 12 }}>
          <BrandDot size={28}/>
          <Box style={{ padding: 12, borderRadius: 14, maxWidth: 560 }}>
            <div className="sk-hw" style={{ fontSize: 16, marginBottom: 8 }}>下面这些岗位我觉得值得给你推，你看是哪一类最吸引：</div>
            <div style={{ display:'flex', flexDirection:'column', gap: 6 }}>
              {['量化分析 · 券商研究所','数据科学 · 互联网大厂','机器学习工程师 · 金融科技'].map(x => (
                <Box key={x} className="thin" style={{ padding: 8, display:'flex', alignItems:'center', gap: 8 }}>
                  <span style={{ width:14, height:14, border:'1.4px solid var(--soft)', borderRadius: 3 }}/>
                  <span className="sk-hw" style={{ fontSize: 15 }}>{x}</span>
                </Box>
              ))}
            </div>
          </Box>
        </div>

        {/* composer */}
        <Box style={{ padding:'10px 12px', display:'flex', alignItems:'center', gap: 8, background:'var(--hair)' }}>
          <span className="sk-hw" style={{ color:'var(--soft)', flex: 1 }}>继续回答，或直接选上面...</span>
          <div style={{ width: 26, height: 26, borderRadius:'50%', background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 13 }}>↑</div>
        </Box>
      </div>

      {/* Right — live summary being built */}
      <div>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 10 }}>当前偏好草稿</div>
        <Box style={{ padding: 18, borderRadius: 18 }}>
          <div style={{ display:'flex', flexDirection:'column', gap: 14 }}>
            {[
              ['城市', '上海 · 北京'],
              ['行业', '金融科技 · 互联网'],
              ['公司类型', '互联网 / 金融机构'],
              ['岗位方向', '数据分析师 · ML 工程师'],
              ['未填', '薪资 / 工作强度 / 远程比例'],
            ].map(([k, v], i) => (
              <div key={k}>
                <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>{k}</div>
                <div className="sk-sans" style={{ fontSize: 14, color: i===4 ? 'var(--soft)' : 'var(--ink)' }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ height: 16 }}/>
          <Btn label="用这份偏好跑推荐 →" variant="accent" h={36} />
        </Box>
        <div style={{ height: 14 }}/>
        <div className="sk-hw" style={{ fontSize: 14, color:'var(--soft)' }}>你可以随时跳过，我会自己推断</div>
      </div>
    </div>

    <Note style={{ top: 60, right: 60 }} side="r">填表变对话：左聊，右侧实时汇总</Note>
  </div>
);

// 03 — Slider-driven: weighted priorities instead of binary selection
const Prefs_C = () => (
  <div className="sk-paper sk-grid" style={{ width: 1280, height: 820, padding: '40px 60px', position:'relative' }}>
    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom: 20 }}>
      <Wordmark />
      <div style={{ display:'flex', gap: 8 }}>
        <Btn label="重置默认" variant="line" />
        <Btn label="保存并重新分析" variant="accent" />
      </div>
    </div>
    <div className="sk-serif" style={{ fontSize: 32, marginBottom: 4 }}>打分权重</div>
    <div className="sk-hw" style={{ fontSize: 16, color:'var(--soft)', marginBottom: 20 }}>不用二选一 — 告诉我"多重要"，我在评分里按权重乘。</div>

    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 24 }}>
      <Box style={{ padding: 20, borderRadius: 18 }}>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 14 }}>基础维度</div>
        {[
          ['城市匹配 (上海)', 0.9],
          ['行业匹配 (金融科技)', 0.75],
          ['薪资上限', 0.4],
          ['公司规模 (T1)', 0.6],
          ['远程友好度', 0.25],
        ].map(([label, v]) => (
          <div key={label} style={{ marginBottom: 14 }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom: 6 }}>
              <span className="sk-sans" style={{ fontSize: 14 }}>{label}</span>
              <span className="sk-mono" style={{ fontSize: 12, color:'var(--soft)' }}>×{v.toFixed(2)}</span>
            </div>
            <div style={{ position:'relative', height: 8, background:'var(--hair)', borderRadius: 99 }}>
              <div style={{ width:`${v*100}%`, height:'100%', background:'var(--accent)', borderRadius: 99 }}/>
              <div style={{ position:'absolute', left:`calc(${v*100}% - 8px)`, top: -4, width: 16, height: 16, borderRadius:'50%', background:'#fff', border:'1.8px solid var(--accent)' }}/>
            </div>
          </div>
        ))}
      </Box>

      <Box style={{ padding: 20, borderRadius: 18 }}>
        <div className="sk-hw" style={{ fontSize: 13, letterSpacing:'.12em', textTransform:'uppercase', color:'var(--soft)', marginBottom: 14 }}>硬性过滤</div>
        {[
          ['只看 应届补招','on'],
          ['排除 外包公司','on'],
          ['必须有 SSP / 加班补贴','off'],
          ['含 投研 / 量化','on'],
          ['排除 销售类','off'],
        ].map(([label, state]) => (
          <div key={label} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 0', borderBottom:'1px dashed var(--hair)' }}>
            <span className="sk-sans" style={{ fontSize: 14 }}>{label}</span>
            <div style={{ width: 34, height: 20, borderRadius: 99, background: state==='on'?'var(--accent)':'var(--hair)', position:'relative' }}>
              <div style={{ position:'absolute', top: 2, left: state==='on'?16:2, width: 16, height: 16, borderRadius:'50%', background:'#fff' }}/>
            </div>
          </div>
        ))}
        <div style={{ height: 10 }}/>
        <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>过滤器会直接裁掉不符合的岗位，不影响打分</div>
      </Box>
    </div>

    {/* live preview score */}
    <div style={{ height: 16 }}/>
    <Box className="filled-soft" style={{ padding: 14, borderRadius: 14, display:'flex', alignItems:'center', gap: 16 }}>
      <div>
        <div className="sk-hw" style={{ fontSize: 13, color:'var(--soft)' }}>基于当前权重，预计推荐分布</div>
        <div className="sk-sans" style={{ fontSize: 14 }}>96 分段 3 个 · 90+ 段 14 个 · 80+ 段 62 个</div>
      </div>
      <div style={{ flex: 1 }}/>
      <div style={{ display:'flex', alignItems:'flex-end', gap: 3, height: 40 }}>
        {[6,14,22,36,44,40,28,16,10,6,4,2].map((h, i) => (
          <div key={i} style={{ width: 8, height: h, background: i>=10?'var(--accent)':'var(--hair)', borderRadius: 2 }}/>
        ))}
      </div>
    </Box>
    <Note style={{ top: 120, right: 80 }} side="r">权重式比二选一更准 —<br/>但需要更多教育</Note>
  </div>
);

Object.assign(window, { Prefs_A, Prefs_B, Prefs_C });
