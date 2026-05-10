/* global React, Easing, clamp, interpolate, useTime, useSprite, Sprite,
   JRLogo, BrowserFrame, Pill, Overline, RadarDot, ProgressBar, CountNumber, Caption, FadeBox */

const { useState, useEffect, useMemo } = React;

// ─────────────────────────────────────────────────────────────────────
// SCENE 1 · INTRO (0 - 8s)
// Logo reveal on parchment
// ─────────────────────────────────────────────────────────────────────
function SceneIntro() {
  const { localTime, duration } = useSprite();
  const logoT = Easing.easeOutBack(clamp(localTime / 1.0, 0, 1));
  const taglineT = clamp((localTime - 0.8) / 0.8, 0, 1);
  const urlT = clamp((localTime - 1.8) / 0.6, 0, 1);

  // fade all out near the end
  const exitT = clamp((duration - localTime) / 0.8, 0, 1);

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#f5f4ed',
      backgroundImage:
        'linear-gradient(to right, rgba(0,0,0,0.025) 1px, transparent 1px),' +
        'linear-gradient(to bottom, rgba(0,0,0,0.025) 1px, transparent 1px)',
      backgroundSize: '60px 60px',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 48,
      opacity: exitT,
    }}>
      <div style={{
        transform: `scale(${logoT})`,
        opacity: logoT,
      }}>
        <JRLogo size={2.2} pulse time={localTime} />
      </div>

      <div style={{
        opacity: taglineT,
        transform: `translateY(${(1 - taglineT) * 16}px)`,
        textAlign: 'center', maxWidth: 900,
      }}>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 48, fontWeight: 500, letterSpacing: '-0.025em',
          color: '#141413', lineHeight: 1.15,
        }}>
          更快发现 <span style={{ color: '#c96442', fontStyle: 'italic' }}>真正值得投递</span> 的岗位
        </div>
        <div style={{
          marginTop: 20, fontSize: 22, color: '#5e5d59',
          fontFamily: "'Inter','Noto Sans SC', sans-serif",
        }}>
          面向高校就业与职业发展 · AI 简历 · 岗位情报
        </div>
      </div>

      <div style={{
        opacity: urlT,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 14, color: '#87867f', letterSpacing: '0.08em',
      }}>
        · · · jobradar.app · · ·
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// SCENE 2 · PROBLEM  (8 - 22s)
// Cards stack showing fragmented job boards, then converge into JobRadar
// ─────────────────────────────────────────────────────────────────────
function SceneProblem() {
  const { localTime, duration } = useSprite();

  const sources = [
    { label: '拉勾 · 互联网', x: 80, y: 140, rot: -4 },
    { label: '猎聘 · 券商', x: 340, y: 90, rot: 2 },
    { label: '智联 · 央国企', x: 620, y: 160, rot: -2 },
    { label: '校招公众号 #1', x: 900, y: 100, rot: 5 },
    { label: 'BOSS 直聘', x: 220, y: 380, rot: 3 },
    { label: '内推群 · excel', x: 520, y: 420, rot: -3 },
    { label: '学校就业系统', x: 820, y: 390, rot: 4 },
  ];

  // Stagger entries
  const titleT = clamp((localTime - 0.2) / 0.6, 0, 1);
  // Converge phase: cards fly to center and condense
  const convergeStart = duration - 3.5;
  const convergeT = clamp((localTime - convergeStart) / 2.0, 0, 1);
  const convergeEased = Easing.easeInOutCubic(convergeT);

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#f5f4ed',
      overflow: 'hidden',
    }}>
      {/* Title */}
      <div style={{
        position: 'absolute', top: 90, left: 80, right: 80,
        opacity: titleT, transform: `translateY(${(1 - titleT) * 20}px)`,
      }}>
        <div style={{ marginBottom: 18 }}><Overline>Problem · 01</Overline></div>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 56, fontWeight: 500, letterSpacing: '-0.025em',
          lineHeight: 1.05, color: '#141413',
        }}>
          岗位信息散落<span style={{ color: '#c96442', fontStyle: 'italic' }}>七八个</span>来源，<br/>
          重要的不一定看得见。
        </div>
      </div>

      {/* Floating source cards */}
      <div style={{ position: 'absolute', inset: 0, top: 340 }}>
        {sources.map((s, i) => {
          const delay = 1.0 + i * 0.15;
          const entryT = Easing.easeOutBack(clamp((localTime - delay) / 0.5, 0, 1));

          // During converge: move toward center (960, 460)
          const centerX = 960 - 90;
          const centerY = 460 - 40;
          const x = s.x + (centerX - s.x) * convergeEased;
          const y = s.y + (centerY - s.y) * convergeEased;
          const scale = entryT * (1 - 0.6 * convergeEased);
          const opacity = entryT * (1 - convergeEased);
          const rot = s.rot * (1 - convergeEased);

          return (
            <div key={i} style={{
              position: 'absolute',
              left: x, top: y,
              width: 180, height: 80,
              background: '#faf9f5',
              borderRadius: 12,
              boxShadow: '0 0 0 1px #e8e6dc, 0 12px 30px rgba(0,0,0,0.08)',
              padding: 14,
              transform: `rotate(${rot}deg) scale(${scale})`,
              opacity,
              display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
            }}>
              <div style={{
                fontSize: 12, color: '#87867f',
                fontFamily: "'JetBrains Mono', monospace",
              }}>source / {String(i + 1).padStart(2, '0')}</div>
              <div style={{
                fontSize: 14, fontWeight: 500, color: '#141413',
                fontFamily: "'Inter','Noto Sans SC', sans-serif",
              }}>{s.label}</div>
            </div>
          );
        })}

        {/* Convergent JobRadar mark appears at center */}
        {convergeT > 0.3 && (
          <div style={{
            position: 'absolute', left: 960, top: 460,
            transform: `translate(-50%, -50%) scale(${Easing.easeOutBack(clamp((convergeT - 0.3) / 0.5, 0, 1))})`,
            opacity: clamp((convergeT - 0.3) / 0.5, 0, 1),
          }}>
            <JRLogo size={1.6} pulse time={localTime} />
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// SCENE 3 · HERO (22 - 40s)
// Mini landing page fills in: ticker → headline → metrics → top5 card
// ─────────────────────────────────────────────────────────────────────
function SceneHero() {
  const { localTime, duration } = useSprite();

  const tickerItems = [
    { track: '互联网', company: '字节跳动', title: '算法工程师', location: '北京' },
    { track: '券商', company: '中金公司', title: '研究助理', location: '上海' },
    { track: '央国企', company: '国家电网', title: '信息技术岗', location: '南京' },
    { track: '金融科技', company: '蚂蚁集团', title: 'AI 应用研发', location: '杭州' },
    { track: '银行', company: '招商银行', title: '数据分析岗', location: '深圳' },
  ];

  const top5 = [
    { rank: 1, title: '【应届补招】AI 工程师', company: '蚂蚁集团 · T1', score: 98 },
    { rank: 2, title: 'AI 应用研发工程师', company: '字节跳动 · T1', score: 95 },
    { rank: 3, title: '智能体 / 大模型应用', company: '腾讯金融 · T1', score: 93 },
    { rank: 4, title: '数据分析岗（春招）', company: '招商银行 · T2', score: 91 },
    { rank: 5, title: '大模型应用全栈', company: '华泰证券 · T2', score: 90 },
  ];

  const frameT = Easing.easeOutCubic(clamp(localTime / 0.8, 0, 1));
  const contentT = clamp((localTime - 0.5) / 0.5, 0, 1);
  const captionT = clamp((localTime - 1.2) / 0.6, 0, 1);
  const exitT = clamp((duration - localTime) / 0.8, 0, 1);

  // Metric count-up active when content visible
  const metricStartT = clamp((localTime - 1.0) / 1.6, 0, 1);
  const metricEase = Easing.easeOutCubic(metricStartT);

  // Top 5 items stagger
  const topStart = 1.8;

  // ticker scroll offset
  const tickerOffset = (localTime * 80) % 1600;

  const frameW = 1120;
  const frameH = 720;

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#f5f4ed',
      backgroundImage:
        'linear-gradient(to right, rgba(0,0,0,0.025) 1px, transparent 1px),' +
        'linear-gradient(to bottom, rgba(0,0,0,0.025) 1px, transparent 1px)',
      backgroundSize: '60px 60px',
      opacity: exitT,
    }}>
      {/* Caption top-left */}
      <div style={{
        position: 'absolute', top: 70, left: 80, maxWidth: 560,
        opacity: captionT, transform: `translateY(${(1 - captionT) * 12}px)`, zIndex: 2,
      }}>
        <div style={{ marginBottom: 12 }}><Overline>Solution · 02</Overline></div>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 46, fontWeight: 500, letterSpacing: '-0.025em',
          lineHeight: 1.08, color: '#141413',
        }}>
          一个雷达，<br/>盯住所有重点岗位。
        </div>
        <div style={{
          marginTop: 14, fontSize: 17, lineHeight: 1.5,
          color: '#5e5d59',
        }}>
          互联网 · 券商 · 央国企 · 银行 · 金融科技<br/>
          覆盖、筛选、更新时效 — 一次看清
        </div>
      </div>

      {/* Browser frame on right */}
      <div style={{
        position: 'absolute', top: 80, right: 80,
        opacity: frameT,
        transform: `scale(${0.94 + 0.06 * frameT}) translateY(${(1 - frameT) * 20}px)`,
        transformOrigin: 'top right',
      }}>
        <BrowserFrame url="jobradar.app" width={frameW} height={frameH}>
          <div style={{
            position: 'absolute', inset: 0,
            background: '#f5f4ed',
            opacity: contentT,
            padding: 22,
            display: 'flex', flexDirection: 'column', gap: 14,
          }}>
            {/* Top nav */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <JRLogo size={0.7} />
              <div style={{ display: 'flex', gap: 24, fontSize: 13, color: '#3d3d3a' }}>
                <span>产品</span><span>覆盖范围</span><span>工作方式</span><span>关于</span>
              </div>
              <div style={{
                background: '#c96442', color: '#faf9f5',
                padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              }}>上传简历 →</div>
            </div>

            {/* Live ticker */}
            <div style={{
              background: '#faf9f5', borderRadius: 10,
              boxShadow: '0 0 0 1px #e8e6dc',
              padding: '8px 14px',
              display: 'flex', alignItems: 'center', gap: 14, overflow: 'hidden',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                paddingRight: 12, borderRight: '1px solid #e8e6dc', flexShrink: 0,
              }}>
                <RadarDot time={localTime} size={10} />
                <span style={{
                  fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
                  textTransform: 'uppercase', color: '#c96442',
                }}>LIVE</span>
              </div>
              <div style={{ flex: 1, overflow: 'hidden', position: 'relative', height: 20 }}>
                <div style={{
                  display: 'flex', gap: 32, whiteSpace: 'nowrap', position: 'absolute',
                  transform: `translateX(${-tickerOffset}px)`,
                }}>
                  {[...tickerItems, ...tickerItems, ...tickerItems].map((it, i) => (
                    <span key={i} style={{ fontSize: 12, color: '#5e5d59' }}>
                      <strong style={{ color: '#c96442', fontSize: 10, letterSpacing: '0.1em', marginRight: 6 }}>{it.track.toUpperCase()}</strong>
                      {it.company} · {it.title} · {it.location}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Main grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: 32, alignItems: 'start', marginTop: 6 }}>
              <div>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '5px 11px', borderRadius: 999, background: '#f8ecd9',
                  marginBottom: 18,
                }}>
                  <span style={{ width: 5, height: 5, borderRadius: 3, background: '#c96442' }} />
                  <span style={{
                    fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
                    color: '#a84f34', fontWeight: 600,
                  }}>情报增强 · 内测 v0.9</span>
                </div>
                <div style={{
                  fontFamily: "'Fraunces','Noto Serif SC', serif",
                  fontSize: 56, fontWeight: 500, letterSpacing: '-0.035em',
                  lineHeight: 0.98, color: '#141413',
                }}>
                  更快发现<br/>真正值得
                  <span style={{ color: '#c96442', fontStyle: 'italic', fontWeight: 500 }}>投递</span><br/>的岗位。
                </div>
                <div style={{
                  marginTop: 18, fontSize: 14, lineHeight: 1.55, color: '#5e5d59', maxWidth: 420,
                }}>
                  聚合互联网、券商、央国企、银行等重点平台岗位。覆盖、筛选、更新时效—一次看清。
                </div>

                <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
                  <div style={{
                    background: '#c96442', color: '#faf9f5',
                    padding: '10px 18px', borderRadius: 10, fontSize: 13.5, fontWeight: 500,
                  }}>上传简历 →</div>
                  <div style={{
                    background: 'transparent', color: '#141413',
                    padding: '10px 18px', borderRadius: 10, fontSize: 13.5,
                    boxShadow: '0 0 0 1px #e8e6dc',
                  }}>看示例推荐</div>
                </div>

                {/* Metrics */}
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(3, auto)', gap: 32,
                  marginTop: 28, paddingTop: 18, borderTop: '1px solid #e8e6dc',
                }}>
                  {[
                    { v: 3486, label: '重点覆盖公司', suffix: '+', accent: false },
                    { v: 12834, label: '今日新岗位', suffix: '', accent: false },
                    { v: 1087, label: '日均更新次数', suffix: '', accent: true },
                  ].map((m, i) => (
                    <div key={i}>
                      <div style={{
                        fontFamily: "'Fraunces', serif",
                        fontSize: 28, letterSpacing: '-0.02em',
                        color: m.accent ? '#c96442' : '#141413',
                      }}>
                        {Math.round(m.v * metricEase).toLocaleString()}
                        {m.suffix && <span style={{ fontSize: 15, color: '#87867f', marginLeft: 3 }}>{m.suffix}</span>}
                      </div>
                      <div style={{ fontSize: 11, color: '#87867f', marginTop: 3 }}>{m.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right preview card */}
              <div style={{ paddingTop: 4, position: 'relative' }}>
                <div style={{
                  background: '#faf9f5', borderRadius: 14, overflow: 'hidden',
                  boxShadow: '0 0 0 1px #e8e6dc, 0 18px 40px rgba(0,0,0,0.08)',
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '8px 12px',
                    background: '#f0eee6', borderBottom: '1px solid #e8e6dc',
                  }}>
                    <span style={{ width: 8, height: 8, borderRadius: 4, background: '#e68786' }} />
                    <span style={{ width: 8, height: 8, borderRadius: 4, background: '#ebc17a' }} />
                    <span style={{ width: 8, height: 8, borderRadius: 4, background: '#a6c79d' }} />
                    <div style={{
                      margin: '0 auto', fontSize: 10, color: '#87867f',
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>jobradar.app / recommendations</div>
                  </div>
                  <div style={{ padding: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
                      <div style={{
                        fontFamily: "'Fraunces', serif", fontSize: 16, color: '#141413',
                      }}>真实岗位推荐 · Top 5</div>
                      <span style={{
                        marginLeft: 'auto', fontSize: 10, background: '#e5efe2', color: '#3f9a5d',
                        padding: '3px 8px', borderRadius: 999,
                        boxShadow: '0 0 0 1px #c7d9c2',
                      }}>已完成分析</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {top5.map((j, i) => {
                        const delay = topStart + i * 0.14;
                        const itemT = Easing.easeOutCubic(clamp((localTime - delay) / 0.4, 0, 1));
                        return (
                          <div key={i} style={{
                            display: 'flex', alignItems: 'center', gap: 10,
                            padding: '8px 10px', borderRadius: 10,
                            background: '#f5f4ed',
                            boxShadow: '0 0 0 1px #e8e6dc',
                            opacity: itemT,
                            transform: `translateY(${(1 - itemT) * 8}px)`,
                          }}>
                            <span style={{
                              fontFamily: "'Fraunces', serif", fontSize: 14, color: '#87867f', width: 20,
                            }}>{String(j.rank).padStart(2, '0')}</span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{
                                fontSize: 12, fontWeight: 600, color: '#141413',
                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              }}>{j.title}</div>
                              <div style={{ fontSize: 10, color: '#87867f', marginTop: 1 }}>{j.company}</div>
                            </div>
                            <span style={{
                              fontFamily: "'Fraunces', serif", fontSize: 18, color: '#c96442',
                            }}>{j.score}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
                {/* floating agent pill */}
                <div style={{
                  position: 'absolute', top: -10, right: 10,
                  padding: '6px 10px', background: '#141413', color: '#faf9f5',
                  borderRadius: 999, display: 'inline-flex', alignItems: 'center', gap: 6,
                  fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                  boxShadow: '0 12px 30px rgba(0,0,0,0.22)',
                  opacity: clamp((localTime - 1.5) / 0.4, 0, 1),
                }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%', background: '#c96442',
                  }} />
                  agent · 12.4s · 3 tools
                </div>
              </div>
            </div>
          </div>
        </BrowserFrame>
      </div>
    </div>
  );
}

Object.assign(window, { SceneIntro, SceneProblem, SceneHero });
