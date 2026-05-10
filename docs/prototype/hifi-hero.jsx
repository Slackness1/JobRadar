/* global React, HFLogo, HFBtn, HFPill, HFTicker, I, useCountUp */

const HF_FEATURED = [
  { company: '阿里巴巴', title: '后端开发工程师', location: '杭州', track: '互联网' },
  { company: '腾讯', title: '产品经理', location: '深圳', track: '互联网' },
  { company: '字节跳动', title: '算法工程师', location: '北京', track: '互联网' },
  { company: '中金公司', title: '研究助理', location: '上海', track: '券商' },
  { company: '中信证券', title: '投行项目助理', location: '北京', track: '券商' },
  { company: '华泰证券', title: '量化分析岗', location: '上海', track: '券商' },
  { company: '国家电网', title: '信息技术岗', location: '南京', track: '央国企' },
  { company: '招商银行', title: '数据分析岗', location: '深圳', track: '银行' },
  { company: '工商银行', title: '金融科技岗', location: '北京', track: '银行' },
  { company: '建设银行', title: '数据治理岗', location: '北京', track: '银行' },
  { company: '蚂蚁集团', title: 'AI 应用研发', location: '杭州', track: '金融科技' },
];

const HF_TOP5_DEMO = [
  { rank: 1, title: '【应届补招】AI 工程师', company: '蚂蚁集团', tier: 'T1', base: 96, enhanced: 98 },
  { rank: 2, title: 'AI 应用研发工程师', company: '字节跳动', tier: 'T1', base: 94, enhanced: 95 },
  { rank: 3, title: '智能体 / 大模型应用', company: '腾讯金融', tier: 'T1', base: 92, enhanced: 93 },
  { rank: 4, title: '数据分析岗（春招）', company: '招商银行', tier: 'T2', base: 90, enhanced: 91 },
  { rank: 5, title: '大模型应用全栈', company: '华泰证券', tier: 'T2', base: 89, enhanced: 90 },
];

// ------------------------------------------------------------------
// HERO — interactive landing
// ------------------------------------------------------------------
const HFHero = () => {
  const companies = useCountUp(3486, 1600);
  const jobs = useCountUp(12834, 1800);
  const daily = useCountUp(1087, 1400);

  return (
    <div className="hf hf-parchment-grid" style={{ width: 1280, height: 820, position: 'relative', overflow: 'hidden' }}>
      <HFTopNav />

      {/* ticker */}
      <div style={{ padding: '0 56px', marginBottom: 28 }}>
        <div className="hf-card" style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 16, background: 'var(--ivory)' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, paddingRight: 16, borderRight: '1px solid var(--border-cream)', flexShrink: 0 }}>
            <span className="hf-radar-dot" />
            <span className="hf-overline" style={{ color: 'var(--terracotta)' }}>LIVE · 重点岗位速览</span>
          </div>
          <HFTicker items={HF_FEATURED} />
        </div>
      </div>

      <div style={{ padding: '0 56px', display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: 56, alignItems: 'start' }}>
        {/* LEFT */}
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderRadius: 999, background: 'var(--terracotta-wash)', marginBottom: 26 }}>
            <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--terracotta)' }} />
            <span style={{ fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--terracotta-strong)', fontWeight: 600 }}>情报增强 · 内测 v0.9</span>
          </div>

          <h1 className="hf-hero" style={{ margin: 0 }}>
            更快发现<br/>
            真正值得<span style={{ color: 'var(--terracotta)', fontStyle: 'italic', fontWeight: 500 }}>投递</span><br/>
            的岗位。
          </h1>
          <p className="hf-body-lg" style={{ maxWidth: 520, marginTop: 22 }}>
            面向高校就业与职业发展场景，聚合互联网、券商、央国企、银行等重点平台岗位。<span style={{ color: 'var(--ink-soft)' }}>覆盖、筛选、更新时效</span>——一次看清。
          </p>

          <div style={{ display: 'flex', gap: 12, marginTop: 32 }}>
            <HFBtn variant="primary" size="lg" iconRight={I.arrowRight(16)}>上传简历</HFBtn>
            <HFBtn variant="ghost" size="lg" icon={I.book(14)}>看示例推荐</HFBtn>
          </div>

          {/* Metric row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, auto)', gap: 40, marginTop: 48, borderTop: '1px solid var(--border-cream)', paddingTop: 24 }}>
            <div>
              <div className="hf-serif" style={{ fontSize: 36, color: 'var(--ink)', letterSpacing: '-0.02em' }}>{companies.toLocaleString()}<span style={{ color: 'var(--stone)', fontSize: 18, marginLeft: 4 }}>+</span></div>
              <div className="hf-cap">重点覆盖公司</div>
            </div>
            <div>
              <div className="hf-serif" style={{ fontSize: 36, color: 'var(--ink)', letterSpacing: '-0.02em' }}>{jobs.toLocaleString()}</div>
              <div className="hf-cap">今日新岗位</div>
            </div>
            <div>
              <div className="hf-serif" style={{ fontSize: 36, color: 'var(--terracotta)', letterSpacing: '-0.02em' }}>{daily}</div>
              <div className="hf-cap">日均更新次数</div>
            </div>
          </div>
        </div>

        {/* RIGHT — product preview card */}
        <div style={{ position: 'relative', paddingTop: 6 }}>
          <div className="hf-card paper" style={{ padding: 0, borderRadius: 20, overflow: 'hidden' }}>
            {/* Fake browser bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 14px', background: 'var(--library-rail)', borderBottom: '1px solid var(--border-cream)' }}>
              <span style={{ width: 10, height: 10, borderRadius: 5, background: '#e68786' }}/>
              <span style={{ width: 10, height: 10, borderRadius: 5, background: '#ebc17a' }}/>
              <span style={{ width: 10, height: 10, borderRadius: 5, background: '#a6c79d' }}/>
              <div style={{ margin: '0 auto', fontSize: 11, color: 'var(--stone)' }} className="hf-mono">jobradar.app / recommendations</div>
            </div>

            {/* Content */}
            <div style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 12 }}>
                <div className="hf-serif" style={{ fontSize: 20 }}>真实岗位推荐 · Top 5</div>
                <span className="hf-pill emerald" style={{ marginLeft: 'auto' }}>
                  <span className="hf-spin" style={{ width: 10, height: 10, borderWidth: 1.5 }} />已完成分析
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {HF_TOP5_DEMO.map((j, i) => (
                  <div key={i} className="hf-slide" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 12, background: 'var(--parchment)', boxShadow: '0 0 0 1px var(--border-cream)', animationDelay: `${0.1 + i * 0.08}s` }}>
                    <span className="hf-serif" style={{ fontSize: 18, color: 'var(--stone)', width: 22 }}>{String(j.rank).padStart(2, '0')}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.title}</div>
                      <div className="hf-cap" style={{ marginTop: 2 }}>{j.company} · {j.tier} · Base {j.base}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className="hf-mono-sm" style={{ color: 'var(--stone)' }}>→</span>
                      <span className="hf-serif" style={{ fontSize: 22, color: 'var(--terracotta)' }}>{j.enhanced}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 14, padding: '10px 12px', borderRadius: 10, background: 'var(--terracotta-wash)' }}>
                <span style={{ color: 'var(--terracotta)' }}>{I.sparkle(14)}</span>
                <span className="hf-body-sm" style={{ color: 'var(--terracotta-strong)' }}>AI 代理刚刚读完前 5 个岗位的完整 JD — <b>查看增强解释</b></span>
              </div>
            </div>
          </div>

          {/* floating pill */}
          <div style={{ position: 'absolute', top: -14, right: 12, padding: '8px 12px', background: 'var(--deep-dark)', color: 'var(--ivory)', borderRadius: 999, display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12, boxShadow: '0 12px 30px rgba(0,0,0,0.22)' }}>
            <span className="hf-spin cool" style={{ width: 10, height: 10, borderWidth: 1.5 }}/>
            <span className="hf-mono" style={{ fontSize: 11.5 }}>agent · 12.4s · 3 tools</span>
          </div>
        </div>
      </div>

      {/* Bottom coverage strip */}
      <div style={{ position: 'absolute', left: 56, right: 56, bottom: 28, display: 'flex', alignItems: 'center', gap: 18 }}>
        <span className="hf-overline">覆盖梯队</span>
        {['互联网 T1','券商','央国企','银行','金融科技','制造','新能源','高校选调'].map((t, i) => (
          <span key={i} style={{ fontSize: 13, color: i < 3 ? 'var(--ink)' : 'var(--stone)', fontWeight: i < 3 ? 500 : 400 }}>{t}</span>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--stone)' }} className="hf-mono">更新于 04-24 · 14:32</span>
      </div>
    </div>
  );
};

Object.assign(window, { HFHero, HF_FEATURED, HF_TOP5_DEMO });
