/* global React, Easing, clamp, useSprite,
   JRLogo, BrowserFrame, Pill, Overline, RadarDot, ProgressBar */

const { useState, useEffect } = React;

// ─────────────────────────────────────────────────────────────────────
// SCENE 4 · UPLOAD  (40 - 62s)
// PDF drops in → progress bar → parsing steps → terminal trace → done
// ─────────────────────────────────────────────────────────────────────
function SceneUpload() {
  const { localTime, duration } = useSprite();

  const steps = [
    { label: '读取 PDF · 3 页 · 1.4MB', hint: '文本层 OK' },
    { label: '识别结构 · 教育 / 工作 / 项目 / 技能', hint: '12 段 · 28 项' },
    { label: '匹配公司库 · 补齐梯队与标签', hint: '14 命中 / 16' },
    { label: '推断目标方向与画像', hint: '金融科技 · 数据分析' },
  ];

  // timeline:
  // 0-1s: frame entry + title
  // 1-3s: PDF drag + progress 0 → 100
  // 3-11s: 4 steps, ~2s each
  // 11-end: done banner
  const frameT = clamp(localTime / 0.7, 0, 1);
  const titleT = clamp((localTime - 0.3) / 0.5, 0, 1);

  // File drop
  const dropStart = 0.8;
  const dropT = clamp((localTime - dropStart) / 0.5, 0, 1);

  // Upload progress
  const uploadStart = 1.3;
  const uploadEnd = 3.0;
  const uploadT = clamp((localTime - uploadStart) / (uploadEnd - uploadStart), 0, 1);
  const uploadEased = Easing.easeOutCubic(uploadT);

  // Steps timeline
  const stepStart = 3.2;
  const stepDur = 1.8;
  const currentStep = Math.min(steps.length, Math.floor((localTime - stepStart) / stepDur));

  // Done banner
  const doneT = clamp((localTime - (stepStart + steps.length * stepDur + 0.3)) / 0.5, 0, 1);

  const exitT = clamp((duration - localTime) / 0.7, 0, 1);

  return (
    <div style={{
      position: 'absolute', inset: 0, background: '#f5f4ed',
      opacity: exitT,
      padding: 60,
    }}>
      {/* Title */}
      <div style={{
        opacity: titleT,
        transform: `translateY(${(1 - titleT) * 12}px)`,
        marginBottom: 24,
      }}>
        <div style={{ marginBottom: 12 }}><Overline>Step · 03 · 上传 + 解析</Overline></div>
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 44, fontWeight: 500, letterSpacing: '-0.025em',
          color: '#141413',
        }}>
          把 PDF 拖进来。<span style={{ color: '#c96442', fontStyle: 'italic' }}>6 秒</span>读懂整份简历。
        </div>
      </div>

      {/* Two columns: dropzone + agent */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 36,
        opacity: frameT,
      }}>
        {/* LEFT dropzone / file */}
        <div style={{
          background: '#faf9f5', borderRadius: 20, padding: 24,
          boxShadow: '0 0 0 1.5px #d1cfc5',
          minHeight: 540,
          position: 'relative',
          backgroundImage: uploadT < 0.05 ? 'radial-gradient(circle, #d1cfc5 1px, transparent 1px)' : undefined,
          backgroundSize: '12px 12px',
        }}>
          {uploadT < 0.05 ? (
            <div style={{
              height: 480, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 14,
            }}>
              <div style={{
                width: 80, height: 80, borderRadius: 40,
                background: '#f8ecd9', color: '#c96442',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
                  <path d="M12 15V4M7 9l5-5 5 5M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"
                    stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div style={{
                fontFamily: "'Fraunces', serif", fontSize: 30, color: '#141413',
              }}>把 PDF 简历拖进来</div>
              <div style={{ fontSize: 14, color: '#5e5d59' }}>
                也支持 .docx · 最大 10 MB · 扫描件可 OCR
              </div>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 50, height: 64, background: '#faf9f5',
                  boxShadow: '0 0 0 1px #e8e6dc',
                  borderRadius: 6, position: 'relative',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <div style={{
                    position: 'absolute', top: 5, right: 5,
                    fontSize: 9, color: '#c96442', fontWeight: 700,
                  }}>PDF</div>
                  <div style={{
                    width: 26, height: 2, background: '#d1cfc5',
                    boxShadow: '0 5px 0 0 #d1cfc5, 0 10px 0 0 #d1cfc5',
                  }}/>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 16, color: '#141413' }}>
                    周传博_简历_2026春.pdf
                  </div>
                  <div style={{ fontSize: 12, color: '#87867f', marginTop: 2 }}>
                    1.4 MB · 3 页 · 刚刚上传
                  </div>
                </div>
                <Pill tone={uploadT < 1 ? 'terra' : currentStep >= steps.length ? 'emerald' : 'terra'}>
                  {uploadT < 1 ? '上传中' : currentStep >= steps.length ? '已完成' : '解析中'}
                </Pill>
              </div>

              <div style={{ marginTop: 20 }}>
                <ProgressBar progress={uploadEased} />
                <div style={{
                  textAlign: 'right', marginTop: 6, fontSize: 12, color: '#87867f',
                }}>
                  {uploadT < 1
                    ? `${Math.round(uploadEased * 100)}% · 正在传输`
                    : currentStep >= steps.length
                      ? '完成 · 共用时 6.4s'
                      : '100% · 文件已就绪'}
                </div>
              </div>

              {/* Extracted fields */}
              {uploadT >= 1 && (
                <div style={{
                  marginTop: 20, padding: 16,
                  background: '#f0eee6', borderRadius: 12,
                  opacity: clamp((localTime - uploadEnd) / 0.5, 0, 1),
                }}>
                  <div style={{
                    fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
                    textTransform: 'uppercase', color: '#87867f', marginBottom: 8,
                  }}>结构化预览</div>
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'auto 1fr',
                    rowGap: 8, columnGap: 14, fontSize: 13,
                  }}>
                    {[
                      ['姓名', '周传博'],
                      ['目标', '数据分析师 / 金融科技'],
                      ['学历', '复旦大学 · 统计硕士 · 2026'],
                      ['经历', '蚂蚁 风控 · 字节 数据'],
                    ].map(([k, v], i) => (
                      <React.Fragment key={i}>
                        <div style={{ color: '#87867f' }}>{k}</div>
                        <div style={{ color: '#141413', fontWeight: 500 }}>{v}</div>
                      </React.Fragment>
                    ))}
                    <div style={{ color: '#87867f' }}>技能</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {['Python','SQL','PyTorch','因果推断','A/B'].map(s => (
                        <span key={s} style={{
                          padding: '2px 8px', fontSize: 11, borderRadius: 999,
                          background: '#faf9f5', boxShadow: '0 0 0 1px #e8e6dc',
                          color: '#3d3d3a',
                        }}>{s}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT agent steps */}
        <div style={{
          background: '#faf9f5', borderRadius: 20, padding: 22,
          boxShadow: '0 0 0 1px #e8e6dc, 0 10px 30px rgba(0,0,0,0.06)',
          minHeight: 540, display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <div style={{
              width: 30, height: 30, borderRadius: 8, background: '#141413',
              position: 'relative', flexShrink: 0,
            }}>
              <div style={{
                position: 'absolute', top: 11, left: 11,
                width: 8, height: 8, borderRadius: 4, background: '#c96442',
                boxShadow: '0 0 0 3px rgba(201,100,66,0.2)',
              }} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#141413' }}>Resume Parser Agent</div>
              <div style={{ fontSize: 11, color: '#87867f' }}>ReAct loop · Haiku 4.5 · 4 tools</div>
            </div>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {steps.map((s, i) => {
              const active = currentStep === i && localTime >= stepStart;
              const done = currentStep > i || doneT > 0;
              const pending = !active && !done;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 14px', borderRadius: 12,
                  background: active ? '#f8ecd9' : done ? '#e5efe2' : '#f0eee6',
                  boxShadow: `0 0 0 1px ${active ? '#eccfb6' : done ? '#c7d9c2' : '#e8e6dc'}`,
                  opacity: pending ? 0.55 : 1,
                  transition: 'all 0.25s',
                }}>
                  <span style={{
                    width: 26, height: 26, borderRadius: 13,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    background: active ? '#c96442' : done ? '#3f9a5d' : '#faf9f5',
                    color: (active || done) ? '#fff' : '#87867f',
                    boxShadow: (active || done) ? 'none' : '0 0 0 1px #e8e6dc',
                    flexShrink: 0,
                  }}>
                    {active ? (
                      <div style={{
                        width: 12, height: 12, borderRadius: '50%',
                        border: '2px solid rgba(255,255,255,0.4)',
                        borderTopColor: '#fff',
                        animation: 'spin 0.9s linear infinite',
                      }} />
                    ) : done ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                        <path d="M4 12l5 5L20 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    ) : (
                      <span style={{ fontSize: 11, fontWeight: 600 }}>{i + 1}</span>
                    )}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500, color: '#141413' }}>{s.label}</div>
                    <div style={{ fontSize: 11.5, color: '#87867f', marginTop: 1 }}>
                      {active ? '推理中…' : done ? s.hint : '等待'}
                    </div>
                  </div>
                  <span style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11, color: '#87867f',
                  }}>
                    {done ? `${(1 + i * 0.9).toFixed(1)}s` : active ? '…' : '—'}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Terminal trace */}
          <div style={{
            marginTop: 14, padding: '12px 14px',
            background: '#141413', borderRadius: 12,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11.5, lineHeight: 1.7, color: '#b0aea5',
          }}>
            <div><span style={{ color: '#c96442' }}>$</span> parser.run(file=resume.pdf)</div>
            {uploadT >= 1 && <div><span style={{ color: '#86b97a' }}>✓</span> read_pdf → 3 pages</div>}
            {currentStep >= 1 && <div><span style={{ color: '#86b97a' }}>✓</span> extract_sections → ok</div>}
            {currentStep >= 2 && <div><span style={{ color: '#86b97a' }}>✓</span> match_companies → 14/16</div>}
            {currentStep >= 3 && <div><span style={{ color: '#86b97a' }}>✓</span> infer_target → 数据分析</div>}
            {doneT > 0 && <div style={{ color: '#fff' }}>→ session_ready<span style={{
              display: 'inline-block', width: 7, height: '0.9em',
              background: '#c96442', marginLeft: 3,
              animation: 'blink 1s steps(1) infinite',
            }} /></div>}
          </div>
        </div>
      </div>

      {/* Floating PDF that "drops" */}
      {dropT > 0 && dropT < 1 && uploadT < 0.05 && (
        <div style={{
          position: 'absolute',
          top: 230 + (1 - dropT) * -250,
          left: 260 + (1 - dropT) * -120,
          transform: `rotate(${-12 + dropT * 12}deg) scale(${1.2 - dropT * 0.4})`,
          opacity: dropT < 0.8 ? 1 : (1 - dropT) * 5,
          pointerEvents: 'none',
          filter: 'drop-shadow(0 20px 40px rgba(0,0,0,0.25))',
        }}>
          <div style={{
            width: 80, height: 102, background: '#faf9f5',
            boxShadow: '0 0 0 1.5px #d1cfc5',
            borderRadius: 8, position: 'relative',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              position: 'absolute', top: 8, right: 8,
              fontSize: 11, color: '#c96442', fontWeight: 700,
            }}>PDF</div>
            <div style={{
              width: 42, height: 2, background: '#d1cfc5',
              boxShadow: '0 6px 0 0 #d1cfc5, 0 12px 0 0 #d1cfc5, 0 18px 0 0 #d1cfc5',
            }}/>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// SCENE 5 · WORKSPACE (62 - 92s)
// Three-pane view: rail → chat → resume preview. Messages animate in.
// ─────────────────────────────────────────────────────────────────────
function SceneWorkspace() {
  const { localTime, duration } = useSprite();

  const frameT = Easing.easeOutCubic(clamp(localTime / 0.8, 0, 1));
  const titleT = clamp((localTime - 0.2) / 0.5, 0, 1);

  const msg1T = clamp((localTime - 1.8) / 0.5, 0, 1); // agent greeting
  const msg2T = clamp((localTime - 4.0) / 0.4, 0, 1); // user msg
  const thinkT = clamp((localTime - 5.2) / 0.3, 0, 1);
  const rewriteT = clamp((localTime - 7.0) / 0.6, 0, 1);
  const applyT = clamp((localTime - 10.0) / 0.5, 0, 1);  // highlight in resume
  const captionT = clamp((localTime - 11.0) / 0.5, 0, 1);
  const thinkingDone = localTime >= 7.0;

  const exitT = clamp((duration - localTime) / 0.7, 0, 1);

  return (
    <div style={{
      position: 'absolute', inset: 0, background: '#f5f4ed',
      opacity: exitT,
    }}>
      {/* Title top strip */}
      <div style={{
        position: 'absolute', top: 40, left: 80, right: 80,
        opacity: titleT, transform: `translateY(${(1 - titleT) * 10}px)`,
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', zIndex: 2,
      }}>
        <div>
          <div style={{ marginBottom: 8 }}><Overline>Step · 04 · AI 工作台</Overline></div>
          <div style={{
            fontFamily: "'Fraunces','Noto Serif SC', serif",
            fontSize: 38, fontWeight: 500, letterSpacing: '-0.025em', color: '#141413',
          }}>
            对话式改简历 · <span style={{ color: '#c96442', fontStyle: 'italic' }}>看得见</span>的每一次迭代
          </div>
        </div>
        <Pill tone="terra">目标：数据分析师 · 金融科技 · 上海</Pill>
      </div>

      {/* Workspace frame */}
      <div style={{
        position: 'absolute', top: 150, left: 80, right: 80, bottom: 80,
        opacity: frameT,
        transform: `scale(${0.96 + 0.04 * frameT})`, transformOrigin: 'top center',
      }}>
        <BrowserFrame url="jobradar.app / workspace" width="100%" height="100%">
          <div style={{ position: 'absolute', inset: 0, display: 'flex', background: '#f5f4ed' }}>
            {/* Left rail */}
            <div style={{
              width: 200, background: '#f0eee6',
              borderRight: '1px solid #e8e6dc',
              padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <JRLogo size={0.5} />
              </div>
              <div style={{
                background: '#c96442', color: '#faf9f5',
                padding: '7px 10px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                textAlign: 'center',
              }}>+ 新建会话</div>
              <div style={{
                fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: '#87867f', padding: '6px 4px',
              }}>我的简历 · 3</div>
              {[
                { t: '周传博 · 数据分析', meta: '今天 · 分析中', active: true },
                { t: '周传博 · AI 工程', meta: '2 天前' },
                { t: '周传博 · 券商研究', meta: '5 天前' },
              ].map((it, i) => (
                <div key={i} style={{
                  padding: '9px 11px', borderRadius: 8,
                  background: it.active ? '#faf9f5' : 'transparent',
                  boxShadow: it.active ? '0 0 0 1px #e8e6dc' : 'none',
                }}>
                  <div style={{
                    fontSize: 12, fontWeight: it.active ? 600 : 500, color: '#141413',
                  }}>{it.t}</div>
                  <div style={{ fontSize: 10.5, color: '#87867f', marginTop: 2 }}>{it.meta}</div>
                </div>
              ))}
            </div>

            {/* Middle chat */}
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              borderRight: '1px solid #e8e6dc', background: '#faf9f5',
            }}>
              <div style={{
                height: 46, display: 'flex', alignItems: 'center',
                padding: '0 18px', gap: 10,
                borderBottom: '1px solid #f0eee6',
              }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 6, background: '#141413',
                  position: 'relative', flexShrink: 0,
                }}>
                  <div style={{
                    position: 'absolute', top: 8, left: 8,
                    width: 8, height: 8, borderRadius: 4, background: '#c96442',
                  }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#141413' }}>AI 简历助手</div>
                  <div style={{ fontSize: 10.5, color: '#87867f' }}>ReAct · 已连接岗位库</div>
                </div>
                <div style={{ marginLeft: 'auto' }}>
                  <Pill tone="emerald" style={{ height: 22, fontSize: 11 }}>✓ 在线</Pill>
                </div>
              </div>

              <div style={{
                flex: 1, padding: '16px 20px',
                display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden',
              }}>
                {/* Prefs summary */}
                <div style={{
                  background: '#faf9f5', borderRadius: 12,
                  boxShadow: '0 0 0 1px #e8e6dc', padding: 14,
                  opacity: msg1T,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <span style={{ color: '#c96442', fontSize: 13 }}>◎</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#141413' }}>当前目标</span>
                    <Pill tone="terra" style={{ height: 22, fontSize: 11 }}>已填写</Pill>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {[
                      ['岗位', '数据分析师'],
                      ['行业', '金融科技'],
                      ['城市', '上海'],
                      ['期望薪资', '20k-35k'],
                    ].map(([k, v], i) => (
                      <div key={i} style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '4px 9px 4px 4px', borderRadius: 8,
                        background: '#f0eee6', boxShadow: '0 0 0 1px #e8e6dc',
                      }}>
                        <span style={{
                          fontSize: 10, color: '#87867f',
                          padding: '2px 6px', background: '#faf9f5', borderRadius: 5,
                          fontWeight: 500,
                        }}>{k}</span>
                        <span style={{ fontSize: 12, fontWeight: 500, color: '#141413' }}>{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Agent greeting */}
                {msg1T > 0 && (
                  <div style={{
                    display: 'flex', gap: 10, alignItems: 'flex-start',
                    opacity: msg1T, transform: `translateY(${(1 - msg1T) * 6}px)`,
                  }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: 6,
                      background: '#f8ecd9', color: '#c96442',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, flexShrink: 0,
                    }}>✦</div>
                    <div style={{
                      maxWidth: 420, padding: '9px 12px', borderRadius: 12,
                      background: '#f0eee6', fontSize: 12.5, color: '#141413', lineHeight: 1.5,
                    }}>
                      简历已解析完成。根据你"数据分析 · 金融科技"的目标，我读了前 5 个高匹配岗位的 JD，发现<b>量化指标偏弱</b>与<b>因果推断缺失</b>两处可提升。
                    </div>
                  </div>
                )}

                {/* User message */}
                {msg2T > 0 && (
                  <div style={{
                    display: 'flex', justifyContent: 'flex-end',
                    opacity: msg2T, transform: `translateY(${(1 - msg2T) * 6}px)`,
                  }}>
                    <div style={{
                      maxWidth: 360, padding: '9px 12px', borderRadius: 12,
                      background: '#c96442', color: '#fff', fontSize: 12.5, lineHeight: 1.5,
                    }}>
                      帮我把第一段工作经历的量化指标再强一点
                    </div>
                  </div>
                )}

                {/* Thinking */}
                {thinkT > 0 && !thinkingDone && (
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center', opacity: thinkT }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: 6,
                      background: '#f8ecd9', color: '#c96442',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12,
                    }}>✦</div>
                    <div style={{
                      padding: '9px 12px', borderRadius: 12, background: '#f0eee6',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}>
                      <div style={{
                        width: 12, height: 12, borderRadius: '50%',
                        border: '2px solid #d1cfc5', borderTopColor: '#7c9ef7',
                        animation: 'spin 0.9s linear infinite',
                      }} />
                      <span style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11, color: '#5e5d59',
                      }}>rewriter · thinking…</span>
                    </div>
                  </div>
                )}

                {/* Rewrites */}
                {rewriteT > 0 && (
                  <div style={{
                    display: 'flex', gap: 10, alignItems: 'flex-start',
                    opacity: rewriteT, transform: `translateY(${(1 - rewriteT) * 6}px)`,
                  }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: 6,
                      background: '#f8ecd9', color: '#c96442',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, flexShrink: 0,
                    }}>✦</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11.5, color: '#5e5d59', marginBottom: 6 }}>
                        给了 3 种改写方向。点击应用：
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {[
                          { tag: '强量化', body: '支持 12 条业务线日均 380+ 实验，决策周期 14 天 → 3 天。' },
                          { tag: '强因果', body: '双重差分 + PSM 分析核销路径，转化率 +18%。', rec: true },
                          { tag: '强影响', body: '实时反欺诈链路，单季度拦截 ¥2.3 亿，误杀 0.06%。' },
                        ].map((r, i) => {
                          const itemT = clamp((localTime - (7.0 + i * 0.25)) / 0.4, 0, 1);
                          return (
                            <div key={i} style={{
                              background: '#faf9f5', borderRadius: 10,
                              boxShadow: '0 0 0 1px #e8e6dc',
                              padding: 10,
                              opacity: itemT,
                              transform: `translateY(${(1 - itemT) * 6}px)`,
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                                <Pill tone={r.rec ? 'terra' : 'default'} style={{ height: 20, fontSize: 10.5, padding: '0 8px' }}>{r.tag}</Pill>
                                {r.rec && <span style={{ fontSize: 10, color: '#a84f34' }}>AI 推荐</span>}
                                <span style={{ marginLeft: 'auto', fontSize: 11, color: '#c96442' }}>应用 →</span>
                              </div>
                              <div style={{ fontSize: 12, color: '#141413', lineHeight: 1.55 }}>{r.body}</div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Composer */}
              <div style={{ padding: '12px 18px 14px', borderTop: '1px solid #f0eee6' }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: 8,
                  background: '#f0eee6', borderRadius: 12,
                  boxShadow: '0 0 0 1px #e8e6dc',
                }}>
                  <span style={{ flex: 1, fontSize: 12, color: '#87867f', padding: '0 6px' }}>
                    问我如何优化这份简历…
                  </span>
                  <div style={{
                    width: 28, height: 28, borderRadius: 8, background: '#c96442', color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                      <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* Resume preview */}
            <div style={{
              width: 400, background: '#f5f4ed',
              display: 'flex', flexDirection: 'column',
            }}>
              <div style={{
                height: 46, padding: '0 14px', background: '#faf9f5',
                borderBottom: '1px solid #f0eee6',
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#141413' }}>预览 · 周传博</span>
                <Pill tone="terra" style={{ height: 20, fontSize: 10.5 }}>
                  {thinkingDone ? '已同步' : '分析中'}
                </Pill>
                <div style={{ marginLeft: 'auto' }}>
                  <div style={{
                    padding: '5px 10px', borderRadius: 6,
                    background: '#c96442', color: '#fff', fontSize: 11, fontWeight: 500,
                  }}>导出 PDF</div>
                </div>
              </div>

              <div style={{ flex: 1, padding: 16, overflow: 'hidden' }}>
                <div style={{
                  background: '#fff', borderRadius: 6,
                  boxShadow: '0 0 0 1px #e8e6dc, 0 12px 30px rgba(0,0,0,0.06)',
                  padding: 20, height: '100%',
                }}>
                  <div style={{ textAlign: 'center', paddingBottom: 10, borderBottom: '1px solid #f0eee6' }}>
                    <div style={{
                      fontFamily: "'Fraunces', serif", fontSize: 22, color: '#141413', letterSpacing: '-0.02em',
                    }}>周传博</div>
                    <div style={{ fontSize: 10.5, color: '#5e5d59', marginTop: 3 }}>
                      数据分析师 · 上海 · chuanbo@fudan.edu.cn
                    </div>
                  </div>

                  <div style={{ marginTop: 12 }}>
                    <div style={{
                      fontSize: 10, fontWeight: 600, color: '#c96442',
                      letterSpacing: '0.12em', textTransform: 'uppercase',
                      paddingBottom: 3, borderBottom: '1px solid #f0eee6', marginBottom: 6,
                    }}>工作经历</div>
                    <div style={{ fontSize: 11.5, fontWeight: 600, color: '#141413' }}>
                      蚂蚁集团 · 风控数据 · <span style={{ fontWeight: 400, color: '#5e5d59' }}>数据分析实习生</span>
                    </div>

                    {/* The AI-suggested replacement highlight */}
                    {applyT > 0 && (
                      <div style={{
                        marginTop: 6, padding: '8px 10px', borderRadius: 6,
                        background: '#f8ecd9', borderLeft: '3px solid #c96442',
                        fontSize: 11, lineHeight: 1.6, color: '#3d3d3a',
                        opacity: applyT,
                        transform: `translateY(${(1 - applyT) * 6}px)`,
                      }}>
                        <div style={{
                          fontSize: 9, fontWeight: 700, color: '#a84f34',
                          letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 3,
                        }}>✦ AI 建议替换</div>
                        双重差分 + PSM 对核销路径做因果分析，识别 3 个高 ROI 触达时点，<b>转化率 +18%</b>。
                      </div>
                    )}

                    <ul style={{ margin: '8px 0 0 14px', padding: 0, fontSize: 11, lineHeight: 1.7, color: '#3d3d3a' }}>
                      <li>搭建实验看板，支持 12 条业务线日均 380+ A/B 实验</li>
                      <li>LightGBM 对商户风险打分，AUC 0.79 → 0.84</li>
                    </ul>
                  </div>

                  <div style={{ marginTop: 14 }}>
                    <div style={{
                      fontSize: 10, fontWeight: 600, color: '#141413',
                      letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4,
                    }}>技能</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {['Python','SQL','PyTorch','因果推断','A/B 实验'].map(s => (
                        <span key={s} style={{
                          padding: '2px 7px', fontSize: 10, borderRadius: 4,
                          background: '#f0eee6', color: '#3d3d3a',
                          boxShadow: '0 0 0 1px #e8e6dc',
                        }}>{s}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </BrowserFrame>
      </div>

      {/* Bottom caption */}
      <div style={{
        position: 'absolute', bottom: 20, left: 80, right: 80,
        opacity: captionT, transform: `translateY(${(1 - captionT) * 8}px)`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontSize: 14, color: '#5e5d59' }}>
          每一条建议都来自 <b style={{ color: '#141413' }}>真实 JD</b>，点一下就能替换进简历。
        </div>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#87867f',
        }}>session #a7d · 3 tools · 12.4s</div>
      </div>
    </div>
  );
}

Object.assign(window, { SceneUpload, SceneWorkspace });
