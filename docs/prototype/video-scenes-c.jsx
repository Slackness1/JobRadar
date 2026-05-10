/* global React, Easing, clamp, useSprite, JRLogo, Overline, Pill, RadarDot */

// ─────────────────────────────────────────────────────────────────────
// SCENE 6 · VALUE PROPS (92 - 115s)
// 4 value cards animating in sequentially on parchment grid
// ─────────────────────────────────────────────────────────────────────
function SceneValue() {
  const { localTime, duration } = useSprite();

  const titleT = clamp(localTime / 0.6, 0, 1);
  const exitT = clamp((duration - localTime) / 0.8, 0, 1);

  const cards = [
    {
      num: '3,486+',
      title: '重点公司全覆盖',
      desc: '互联网 T1 · 券商 · 央国企 · 银行 · 金融科技 · 新能源 · 制造 · 高校选调',
      accent: '#c96442',
    },
    {
      num: '1,087/日',
      title: '日均更新次数',
      desc: '7×24 持续抓取与清洗，信息比人脉群早一天到达',
      accent: '#141413',
    },
    {
      num: 'Top 5',
      title: 'AI 深度匹配',
      desc: 'Agent 读完完整 JD，给出岗位-简历匹配分与增强解释',
      accent: '#c96442',
    },
    {
      num: '6.4s',
      title: '端到端上手',
      desc: '一份 PDF · 六秒解析 · 立即开始对话式改简历',
      accent: '#141413',
    },
  ];

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#f5f4ed',
      backgroundImage:
        'linear-gradient(to right, rgba(0,0,0,0.025) 1px, transparent 1px),' +
        'linear-gradient(to bottom, rgba(0,0,0,0.025) 1px, transparent 1px)',
      backgroundSize: '60px 60px',
      padding: 80,
      opacity: exitT,
    }}>
      <div style={{ opacity: titleT, transform: `translateY(${(1 - titleT) * 10}px)` }}>
        <div style={{ marginBottom: 12 }}><Overline>Why · 05</Overline></div>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 52, fontWeight: 500, letterSpacing: '-0.025em',
          lineHeight: 1.05, color: '#141413', maxWidth: 900,
        }}>
          四个理由，<span style={{ color: '#c96442', fontStyle: 'italic' }}>让雷达一直开着</span>。
        </div>
      </div>

      <div style={{
        marginTop: 60,
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 24,
      }}>
        {cards.map((c, i) => {
          const delay = 0.6 + i * 0.35;
          const t = Easing.easeOutCubic(clamp((localTime - delay) / 0.5, 0, 1));
          return (
            <div key={i} style={{
              background: '#faf9f5', borderRadius: 20, padding: 36,
              boxShadow: '0 0 0 1px #e8e6dc, 0 14px 36px rgba(0,0,0,0.05)',
              opacity: t,
              transform: `translateY(${(1 - t) * 20}px)`,
              display: 'flex', flexDirection: 'column', gap: 14,
              minHeight: 220,
            }}>
              <div style={{
                fontFamily: "'Fraunces', serif", fontSize: 64, fontWeight: 500,
                letterSpacing: '-0.035em', color: c.accent, lineHeight: 1,
              }}>{c.num}</div>
              <div style={{
                fontFamily: "'Fraunces', serif", fontSize: 26, fontWeight: 500,
                letterSpacing: '-0.02em', color: '#141413',
              }}>{c.title}</div>
              <div style={{ fontSize: 16, lineHeight: 1.55, color: '#5e5d59' }}>
                {c.desc}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// SCENE 7 · HOW IT WORKS (115 - 140s)
// 3-step flow summary with mini screen thumbnails
// ─────────────────────────────────────────────────────────────────────
function SceneHow() {
  const { localTime, duration } = useSprite();

  const titleT = clamp(localTime / 0.5, 0, 1);
  const exitT = clamp((duration - localTime) / 0.7, 0, 1);

  const steps = [
    {
      n: '01',
      title: '上传简历',
      desc: '拖入 PDF · 一次就够',
      mini: (progress) => (
        <div style={{
          width: '100%', height: '100%', background: '#f0eee6',
          borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
        }}>
          <div style={{
            width: 70, height: 90, background: '#faf9f5',
            boxShadow: '0 0 0 1.5px #d1cfc5',
            borderRadius: 6, position: 'relative',
            transform: `translateY(${(1 - progress) * -40}px) rotate(${(1 - progress) * -8}deg)`,
          }}>
            <div style={{
              position: 'absolute', top: 6, right: 6,
              fontSize: 9, color: '#c96442', fontWeight: 700,
            }}>PDF</div>
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              width: 38, height: 2, background: '#d1cfc5',
              boxShadow: '0 5px 0 0 #d1cfc5, 0 10px 0 0 #d1cfc5',
            }} />
          </div>
          {/* dropzone dashed */}
          <div style={{
            position: 'absolute', inset: 16, borderRadius: 10,
            border: '1.5px dashed #d1cfc5',
          }} />
        </div>
      ),
    },
    {
      n: '02',
      title: 'AI 解读',
      desc: 'Agent 读 JD · 算匹配分',
      mini: (progress) => (
        <div style={{
          width: '100%', height: '100%', background: '#141413',
          borderRadius: 10, padding: 16,
          fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#b0aea5',
          lineHeight: 1.8, display: 'flex', flexDirection: 'column', gap: 2,
        }}>
          <div><span style={{ color: '#c96442' }}>$</span> parser.run()</div>
          {progress > 0.2 && <div><span style={{ color: '#86b97a' }}>✓</span> read_pdf</div>}
          {progress > 0.4 && <div><span style={{ color: '#86b97a' }}>✓</span> extract_sections</div>}
          {progress > 0.6 && <div><span style={{ color: '#86b97a' }}>✓</span> match_companies</div>}
          {progress > 0.8 && <div><span style={{ color: '#86b97a' }}>✓</span> infer_target</div>}
          {progress > 0.95 && <div style={{ color: '#fff' }}>→ session_ready</div>}
        </div>
      ),
    },
    {
      n: '03',
      title: '改简历 / 投递',
      desc: '对话即改写 · 一键应用',
      mini: (progress) => (
        <div style={{
          width: '100%', height: '100%', background: '#faf9f5',
          borderRadius: 10, padding: 14,
          boxShadow: '0 0 0 1px #e8e6dc',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{
            alignSelf: 'flex-end',
            background: '#c96442', color: '#fff', padding: '6px 10px', borderRadius: 10,
            fontSize: 10, maxWidth: 140, opacity: clamp(progress * 3, 0, 1),
          }}>改写工作经历的量化指标</div>
          <div style={{
            background: '#f0eee6', padding: '6px 10px', borderRadius: 10,
            fontSize: 10, color: '#141413', maxWidth: 160,
            opacity: clamp((progress - 0.3) * 3, 0, 1),
          }}>转化率 +18% · PSM 因果分析</div>
          <div style={{
            background: '#f8ecd9', padding: '6px 10px', borderRadius: 6,
            borderLeft: '3px solid #c96442',
            fontSize: 10, color: '#3d3d3a',
            opacity: clamp((progress - 0.6) * 3, 0, 1),
          }}>✦ 应用到简历 →</div>
        </div>
      ),
    },
  ];

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#f5f4ed',
      padding: 80, opacity: exitT,
    }}>
      <div style={{ opacity: titleT, transform: `translateY(${(1 - titleT) * 10}px)` }}>
        <div style={{ marginBottom: 12 }}><Overline>How · 06</Overline></div>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 52, fontWeight: 500, letterSpacing: '-0.025em',
          lineHeight: 1.05, color: '#141413',
        }}>
          三步，<span style={{ color: '#c96442', fontStyle: 'italic' }}>从简历到投递</span>。
        </div>
      </div>

      <div style={{
        marginTop: 60, display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)', gap: 28,
        alignItems: 'stretch',
      }}>
        {steps.map((s, i) => {
          const delay = 0.6 + i * 0.6;
          const t = Easing.easeOutCubic(clamp((localTime - delay) / 0.5, 0, 1));
          const miniProgress = clamp((localTime - (delay + 0.3)) / 1.8, 0, 1);
          return (
            <div key={i} style={{
              opacity: t,
              transform: `translateY(${(1 - t) * 20}px)`,
              display: 'flex', flexDirection: 'column', gap: 16,
            }}>
              {/* Mini screen */}
              <div style={{ height: 260 }}>{s.mini(miniProgress)}</div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                <div style={{
                  fontFamily: "'Fraunces', serif", fontSize: 48, fontWeight: 500,
                  letterSpacing: '-0.02em', color: '#c96442', lineHeight: 1,
                }}>{s.n}</div>
                <div style={{ flex: 1, height: 1, background: '#e8e6dc' }} />
              </div>

              <div>
                <div style={{
                  fontFamily: "'Fraunces', serif", fontSize: 28, fontWeight: 500,
                  letterSpacing: '-0.02em', color: '#141413', marginBottom: 6,
                }}>{s.title}</div>
                <div style={{ fontSize: 15, color: '#5e5d59', lineHeight: 1.5 }}>
                  {s.desc}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Arrow / continuity flourish */}
      <div style={{
        position: 'absolute', left: 80, right: 80, bottom: 80,
        display: 'flex', alignItems: 'center', gap: 14,
        opacity: clamp((localTime - 3.0) / 0.5, 0, 1),
      }}>
        <RadarDot time={localTime} size={12} />
        <span style={{
          fontFamily: "'Inter','Noto Sans SC', sans-serif",
          fontSize: 14, color: '#141413', fontWeight: 500,
        }}>
          每一次投递，都值得更精准 — jobradar.app
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// SCENE 8 · OUTRO  (140 - 150s)
// ─────────────────────────────────────────────────────────────────────
function SceneOutro() {
  const { localTime, duration } = useSprite();

  const logoT = Easing.easeOutBack(clamp(localTime / 0.8, 0, 1));
  const ctaT = clamp((localTime - 0.6) / 0.6, 0, 1);
  const urlT = clamp((localTime - 1.2) / 0.6, 0, 1);

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#141413',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 36, color: '#faf9f5',
    }}>
      <div style={{ transform: `scale(${logoT})`, opacity: logoT }}>
        <JRLogo size={2.2} dark pulse time={localTime} />
      </div>

      <div style={{
        opacity: ctaT, transform: `translateY(${(1 - ctaT) * 12}px)`,
        textAlign: 'center', maxWidth: 900,
      }}>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 42, fontWeight: 500, letterSpacing: '-0.025em',
          color: '#faf9f5', lineHeight: 1.15,
        }}>
          上传简历，<span style={{ color: '#c96442', fontStyle: 'italic' }}>让雷达替你看岗位。</span>
        </div>
      </div>

      <div style={{
        opacity: urlT, display: 'flex', alignItems: 'center', gap: 12,
        marginTop: 10,
      }}>
        <div style={{
          background: '#c96442', color: '#faf9f5',
          padding: '14px 28px', borderRadius: 10,
          fontSize: 16, fontWeight: 500,
        }}>立即开始 →</div>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 14, color: '#b0aea5', letterSpacing: '0.08em',
        }}>jobradar.app</div>
      </div>
    </div>
  );
}

Object.assign(window, { SceneValue, SceneHow, SceneOutro });
