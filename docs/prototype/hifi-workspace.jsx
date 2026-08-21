/* global React, HFLogo, HFBtn, HFPill, I */
const { useState, useEffect, useRef } = React;

// ------------------------------------------------------------------
// THREE-PANE WORKSPACE — Resume Copilot
// Left: library rail · Middle: chat + prefs · Right: resume preview
// ------------------------------------------------------------------
const HFWorkspace = () => {
  const [target, setTarget] = useState({
    role: '数据分析师',
    industry: '金融科技',
    city: '上海',
    salary: '20k-35k',
  });
  const [chat, setChat] = useState([
    { role: 'user', text: '帮我把第一段工作经历的量化指标再强一点' },
    { role: 'agent', kind: 'rewrites' },
  ]);
  const [composing, setComposing] = useState('');
  const [thinking, setThinking] = useState(false);
  const [activeHistory, setActiveHistory] = useState(0);

  const send = () => {
    if (!composing.trim()) return;
    setChat([...chat, { role: 'user', text: composing }]);
    setComposing('');
    setThinking(true);
    setTimeout(() => {
      setChat(c => [...c, { role: 'agent', text: '已根据你的反馈给出 3 条改写，点击应用到简历。', kind: 'rewrites' }]);
      setThinking(false);
    }, 1600);
  };

  return (
    <div className="hf" style={{ width: 1280, height: 820, background: 'var(--parchment)', display: 'flex', overflow: 'hidden' }}>
      {/* ========== LEFT RAIL ========== */}
      <aside style={{ width: 240, background: 'var(--library-rail)', borderRight: '1px solid var(--border-warm)', display: 'flex', flexDirection: 'column', padding: 14, gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px' }}>
          <HFLogo size="sm"/>
          <span style={{ marginLeft: 'auto', color: 'var(--stone)' }}>{I.chevron(12)}</span>
        </div>

        <HFBtn variant="primary" size="sm" icon={I.plus(12)} style={{ width: '100%', justifyContent: 'center' }}>新建会话</HFBtn>

        <div style={{ position: 'relative' }}>
          <input placeholder="搜索历史会话…" style={{ width: '100%', height: 32, padding: '0 10px 0 28px', borderRadius: 8, background: 'var(--ivory)', boxShadow: '0 0 0 1px var(--border-warm)', border: 0, fontSize: 13 }}/>
          <span style={{ position: 'absolute', left: 9, top: 9, color: 'var(--stone)' }}>{I.search(12)}</span>
        </div>

        <div className="hf-overline" style={{ marginTop: 6, padding: '0 4px' }}>我的简历 · 3</div>
        {[
          { t: '林晨 · 数据分析', meta: '今天 · 分析中' },
          { t: '林晨 · AI 工程', meta: '2 天前' },
          { t: '林晨 · 券商研究', meta: '5 天前' },
        ].map((it, i) => (
          <div key={i} onClick={() => setActiveHistory(i)} style={{
            padding: '10px 12px', borderRadius: 10, cursor: 'pointer',
            background: activeHistory === i ? 'var(--ivory)' : 'transparent',
            boxShadow: activeHistory === i ? '0 0 0 1px var(--border-warm)' : 'none',
          }}>
            <div style={{ fontSize: 13, fontWeight: activeHistory === i ? 600 : 500, color: 'var(--ink)' }}>{it.t}</div>
            <div className="hf-cap" style={{ marginTop: 2 }}>{it.meta}</div>
          </div>
        ))}

        <div style={{ flex: 1 }}/>

        <div style={{ padding: '10px 12px', borderRadius: 10, background: 'var(--ivory)', boxShadow: 'var(--sh-ring)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 26, height: 26, borderRadius: 13, background: 'var(--terracotta-wash)', color: 'var(--terracotta)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>ZC</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500 }}>林晨</div>
              <div className="hf-cap">内测用户 · Pro</div>
            </div>
          </div>
        </div>
      </aside>

      {/* ========== MIDDLE (Chat + Prefs) ========== */}
      <section style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border-warm)', background: 'var(--ivory)' }}>
        <header style={{ height: 56, display: 'flex', alignItems: 'center', padding: '0 20px', gap: 12, borderBottom: '1px solid var(--border-cream)' }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--deep-dark)', position: 'relative' }}>
            <div style={{ position: 'absolute', top: 10, left: 10, width: 8, height: 8, borderRadius: 4, background: 'var(--terracotta)', boxShadow: '0 0 0 3px rgba(201,100,66,0.2)' }}/>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>AI 简历助手</div>
            <div className="hf-cap" style={{ marginTop: 1 }}>ReAct · 已连接岗位库 · {target.role} · {target.city}</div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <HFPill tone="emerald">{I.check(12)} 在线</HFPill>
            <HFBtn variant="ghost" size="sm" icon={I.bolt(12)}>快增强</HFBtn>
          </div>
        </header>

        {/* chat scroll */}
        <div style={{ flex: 1, overflow: 'hidden', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Prefs summary card — always top */}
          <div className="hf-card" style={{ padding: 16, borderRadius: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{ color: 'var(--terracotta)' }}>{I.radar(14)}</span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>当前目标</span>
              <HFPill tone="terra">已填写</HFPill>
              <HFBtn variant="link" size="sm" icon={I.edit(12)} style={{ marginLeft: 'auto' }}>修改</HFBtn>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <HFTargetChip label="岗位" value={target.role}/>
              <HFTargetChip label="行业" value={target.industry}/>
              <HFTargetChip label="城市" value={target.city}/>
              <HFTargetChip label="期望薪资" value={target.salary}/>
            </div>
            <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 8, background: 'var(--terracotta-wash)' }}>
              <span style={{ color: 'var(--terracotta)' }}>{I.sparkle(12)}</span>
              <span style={{ fontSize: 12.5, color: 'var(--terracotta-strong)' }}>改动后点击"保存并重新分析"——AI 将用新目标重跑 Top 5</span>
              <HFBtn variant="primary" size="sm" style={{ marginLeft: 'auto' }}>保存并重新分析</HFBtn>
            </div>
          </div>

          {/* Agent greeting */}
          <div className="hf-slide" style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--terracotta-wash)', color: 'var(--terracotta)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{I.sparkle(13)}</div>
            <div style={{ maxWidth: 520, padding: '10px 14px', borderRadius: 14, background: 'var(--library-rail)', fontSize: 14, color: 'var(--ink)', lineHeight: 1.55 }}>
              简历已解析完成。根据你"数据分析 · 金融科技"的目标，我读取了前 5 个高匹配岗位的 JD，发现<b>量化指标偏弱</b>与<b>因果推断关键词缺失</b>两个可提升点。需要我先改"工作经历"吗？
            </div>
          </div>

          {/* User message */}
          <div className="hf-slide" style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <div style={{ maxWidth: 460, padding: '10px 14px', borderRadius: 14, background: 'var(--terracotta)', color: '#fff', fontSize: 14, lineHeight: 1.5 }}>
              帮我把第一段工作经历的量化指标再强一点
            </div>
          </div>

          {/* Agent thinking or rewrites */}
          {thinking ? (
            <div className="hf-slide" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--terracotta-wash)', color: 'var(--terracotta)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{I.sparkle(13)}</div>
              <div style={{ padding: '10px 14px', borderRadius: 14, background: 'var(--library-rail)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="hf-spin cool"/>
                <span className="hf-mono-sm" style={{ color: 'var(--olive)' }}>rewriter · thinking…</span>
              </div>
            </div>
          ) : (
            <div className="hf-slide" style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--terracotta-wash)', color: 'var(--terracotta)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{I.sparkle(13)}</div>
              <div style={{ flex: 1, maxWidth: 580 }}>
                <div style={{ fontSize: 13.5, color: 'var(--olive)', marginBottom: 8 }}>给了 3 种改写方向。点击对比 / 应用：</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    { tag: '强量化', body: '主导 A/B 实验平台升级，支持 12 条业务线日均 380+ 实验，将决策周期从 14 天缩至 3 天。' },
                    { tag: '强因果', body: '使用双重差分 + PSM 对核销路径做因果分析，识别 3 个高 ROI 触达时点，转化率 +18%。' },
                    { tag: '强影响', body: '推动反欺诈模型接入实时链路，单季度拦截异常交易 ¥2.3 亿，误杀率降至 0.06%。' },
                  ].map((r, i) => (
                    <div key={i} className="hf-card" style={{ padding: 12, borderRadius: 12, cursor: 'pointer' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <HFPill tone={i === 1 ? 'terra' : ''}>{r.tag}</HFPill>
                        {i === 1 && <span className="hf-cap" style={{ color: 'var(--terracotta-strong)' }}>AI 推荐</span>}
                        <HFBtn variant="link" size="sm" style={{ marginLeft: 'auto' }}>应用 →</HFBtn>
                      </div>
                      <div style={{ fontSize: 13.5, color: 'var(--ink)', lineHeight: 1.6 }}>{r.body}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* composer */}
        <div style={{ padding: '14px 20px 18px', borderTop: '1px solid var(--border-cream)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, padding: 10, borderRadius: 14, background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border-warm)' }}>
            <div style={{ flex: 1 }}>
              <textarea
                value={composing}
                onChange={e => setComposing(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder="问我如何优化这份简历… (Shift+Enter 换行)"
                rows={1}
                style={{ width: '100%', resize: 'none', border: 0, background: 'transparent', outline: 'none', fontSize: 14, lineHeight: 1.5, color: 'var(--ink)', padding: '4px 6px' }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                <HFPill style={{ height: 22, fontSize: 11.5, cursor: 'pointer' }}>{I.bolt(10)} 强量化</HFPill>
                <HFPill style={{ height: 22, fontSize: 11.5, cursor: 'pointer' }}>{I.book(10)} 对齐 JD</HFPill>
                <HFPill style={{ height: 22, fontSize: 11.5, cursor: 'pointer' }}>{I.sparkle(10)} 再来一批</HFPill>
              </div>
            </div>
            <HFBtn variant="primary" size="sm" style={{ height: 36, width: 36, padding: 0, borderRadius: 10 }} onClick={send}>{I.arrowUp(14)}</HFBtn>
          </div>
        </div>
      </section>

      {/* ========== RIGHT (Resume preview) ========== */}
      <aside style={{ width: 480, background: 'var(--parchment)', display: 'flex', flexDirection: 'column' }}>
        <header style={{ height: 56, padding: '0 18px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border-cream)', background: 'var(--ivory)' }}>
          <span style={{ fontSize: 13.5, fontWeight: 600 }}>预览 · 林晨 简历</span>
          <HFPill tone="amber">{thinking ? '分析中' : '已同步'}</HFPill>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            <HFBtn variant="ghost" size="sm">撤销</HFBtn>
            <HFBtn variant="ghost" size="sm">对比</HFBtn>
            <HFBtn variant="primary" size="sm" icon={I.file(12)}>导出 PDF</HFBtn>
          </div>
        </header>

        <div style={{ flex: 1, overflow: 'auto', padding: 22, background: 'var(--parchment)' }}>
          <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px var(--border-warm), 0 18px 52px rgba(0,0,0,0.08)', padding: '28px 32px', minHeight: 640 }}>
            <div style={{ textAlign: 'center', paddingBottom: 14, borderBottom: '1px solid var(--border-cream)' }}>
              <div className="hf-serif" style={{ fontSize: 28, letterSpacing: '-0.02em' }}>林晨</div>
              <div style={{ fontSize: 12.5, color: 'var(--olive)', marginTop: 4, display: 'flex', justifyContent: 'center', gap: 12 }}>
                <span>数据分析师 · 上海</span><span>·</span><span>candidate@example.com</span><span>·</span><span>+86 1** **** 0000</span>
              </div>
            </div>

            <HFResumeSection title="教育背景" accent>
              <div style={{ display: 'flex', alignItems: 'baseline' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>示例大学</span>
                <span style={{ color: 'var(--olive)', fontSize: 12, marginLeft: 8 }}>统计学硕士 · GPA 3.86/4.0</span>
                <span style={{ marginLeft: 'auto', color: 'var(--stone)', fontSize: 11.5 }} className="hf-mono">2024.09 – 2026.06</span>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--olive)', marginTop: 4 }}>主修 · 贝叶斯统计 / 因果推断 / 机器学习 / 高维数据分析</div>
            </HFResumeSection>

            <HFResumeSection title="工作经历" accent>
              <div style={{ display: 'flex', alignItems: 'baseline' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>某科技公司 · 风控数据</span>
                <span style={{ color: 'var(--olive)', fontSize: 12, marginLeft: 8 }}>数据分析实习生</span>
                <span style={{ marginLeft: 'auto', color: 'var(--stone)', fontSize: 11.5 }} className="hf-mono">2025.07 – 至今</span>
              </div>
              {/* highlighted AI suggestion */}
              <div style={{ marginTop: 6, padding: '10px 12px', borderRadius: 8, background: 'var(--terracotta-wash)', borderLeft: '3px solid var(--terracotta)', fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink-soft)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, color: 'var(--terracotta-strong)', fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  {I.sparkle(10)} AI 建议替换
                </div>
                使用双重差分 + PSM 对核销路径做因果分析，识别 3 个高 ROI 触达时点，<b>转化率 +18%</b>。
              </div>
              <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: 12.5, lineHeight: 1.75, color: 'var(--ink-soft)' }}>
                <li>搭建实验看板，支持 12 条业务线日均 380+ A/B 实验</li>
                <li>用 LightGBM 对商户风险打分，AUC 由 0.79 提升至 0.84</li>
              </ul>
            </HFResumeSection>

            <HFResumeSection title="项目经历" accent>
              <div style={{ display: 'flex', alignItems: 'baseline' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>实时反欺诈链路升级</span>
                <span style={{ marginLeft: 'auto', color: 'var(--stone)', fontSize: 11.5 }} className="hf-mono">Python · Flink · GBDT</span>
              </div>
              <ul style={{ margin: '6px 0 0 16px', padding: 0, fontSize: 12.5, lineHeight: 1.75, color: 'var(--ink-soft)' }}>
                <li>将批式特征工程迁移至流式，端到端延迟 ≤ 120ms</li>
                <li>单季度拦截异常交易 ¥2.3 亿，误杀率 0.06%</li>
              </ul>
            </HFResumeSection>

            <HFResumeSection title="技能">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2 }}>
                {['Python','SQL','PyTorch','LightGBM','Airflow','Tableau','因果推断','A/B 实验','Flink'].map(s => (
                  <span key={s} style={{ padding: '3px 9px', borderRadius: 4, fontSize: 11.5, background: 'var(--library-rail)', color: 'var(--ink-soft)', boxShadow: '0 0 0 1px var(--border-warm)' }}>{s}</span>
                ))}
              </div>
            </HFResumeSection>
          </div>
        </div>
      </aside>
    </div>
  );
};

const HFResumeSection = ({ title, accent, children }) => (
  <div style={{ marginTop: 16 }}>
    <div style={{ fontSize: 12, fontWeight: 600, color: accent ? 'var(--terracotta)' : 'var(--ink)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6, paddingBottom: 3, borderBottom: accent ? '1px solid var(--border-cream)' : 'none' }}>{title}</div>
    {children}
  </div>
);

const HFTargetChip = ({ label, value }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 10px 6px 6px', borderRadius: 10, background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border-warm)' }}>
    <span style={{ fontSize: 11, color: 'var(--stone)', padding: '2px 6px', background: 'var(--ivory)', borderRadius: 6, fontWeight: 500 }}>{label}</span>
    <span style={{ fontSize: 13, color: 'var(--ink)', fontWeight: 500 }}>{value}</span>
  </div>
);

Object.assign(window, { HFWorkspace, HFResumeSection, HFTargetChip });
