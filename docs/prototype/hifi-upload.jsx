/* global React, HFLogo, HFBtn, HFPill, I */
const { useState, useEffect, useRef } = React;

// ------------------------------------------------------------------
// UPLOAD + PARSING FLOW — interactive
// states: idle → uploading → parsing → done
// ------------------------------------------------------------------
const HFUpload = () => {
  const [state, setState] = useState('idle'); // idle | uploading | parsing | done
  const [progress, setProgress] = useState(0);
  const [parseStep, setParseStep] = useState(0);
  const [dragOver, setDragOver] = useState(false);

  const STEPS = [
    { icon: I.file(14), label: '读取 PDF · 3 页 · 1.4MB', hint: '文本层 OK' },
    { icon: I.search(14), label: '识别结构 · 教育 / 工作 / 项目 / 技能', hint: '12 段 · 28 项' },
    { icon: I.radar(14), label: '匹配公司库 · 补齐梯队与标签', hint: '14 命中 / 16' },
    { icon: I.sparkle(14), label: '推断目标方向与画像', hint: '金融科技 · 数据分析' },
  ];

  // simulate upload
  useEffect(() => {
    if (state !== 'uploading') return;
    let p = 0;
    const t = setInterval(() => {
      p += 7 + Math.random() * 6;
      if (p >= 100) { p = 100; setProgress(100); clearInterval(t); setTimeout(() => setState('parsing'), 250); }
      else setProgress(p);
    }, 80);
    return () => clearInterval(t);
  }, [state]);

  useEffect(() => {
    if (state !== 'parsing') return;
    setParseStep(0);
    const t = setInterval(() => {
      setParseStep(s => {
        if (s >= STEPS.length) { clearInterval(t); setTimeout(() => setState('done'), 500); return s; }
        return s + 1;
      });
    }, 900);
    return () => clearInterval(t);
  }, [state]);

  const reset = () => { setState('idle'); setProgress(0); setParseStep(0); };
  const start = () => setState('uploading');

  return (
    <div className="hf" style={{ width: 1280, height: 820, background: 'var(--parchment)', position: 'relative', overflow: 'hidden' }}>
      {/* top strip */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '22px 48px' }}>
        <HFLogo />
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <HFStepper current={state === 'idle' ? 0 : state === 'uploading' ? 0 : state === 'parsing' ? 1 : 2} />
          <HFBtn variant="ghost" size="sm" onClick={reset}>取消并重来</HFBtn>
        </div>
      </div>

      <div style={{ padding: '0 48px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 36 }}>
        {/* LEFT: dropzone / file card */}
        <div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>第 1 步 · 上传简历</div>

          {state === 'idle' && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); start(); }}
              style={{
                height: 440, borderRadius: 24, padding: 28,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12,
                background: dragOver ? 'var(--terracotta-wash)' : 'var(--ivory)',
                boxShadow: `0 0 0 ${dragOver ? 2 : 1.5}px ${dragOver ? 'var(--terracotta)' : 'var(--border-strong)'}`,
                backgroundImage: dragOver ? undefined : 'radial-gradient(circle, var(--border-strong) 1px, transparent 1px)',
                backgroundSize: '12px 12px',
                transition: 'all .18s',
              }}
            >
              <div style={{ width: 72, height: 72, borderRadius: 36, background: 'var(--terracotta-wash)', color: 'var(--terracotta)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {I.upload(26)}
              </div>
              <div className="hf-h2" style={{ margin: 0 }}>把 PDF 简历拖进来</div>
              <div className="hf-body" style={{ marginTop: -4 }}>也支持 .docx · 最大 10 MB · 扫描件可 OCR</div>
              <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                <HFBtn variant="primary" onClick={start} icon={I.upload(14)}>选择本地文件</HFBtn>
                <HFBtn variant="ghost" onClick={start}>使用示例简历</HFBtn>
              </div>
              <div className="hf-cap" style={{ marginTop: 14 }}>安全提示 · 文件仅用于推理与结构化，不会入库训练</div>
            </div>
          )}

          {state !== 'idle' && (
            <div className="hf-card paper" style={{ padding: 22, borderRadius: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 44, height: 54, background: 'var(--ivory)', border: '1px solid var(--border-warm)', borderRadius: 6, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ position: 'absolute', top: 4, right: 4, fontSize: 9, color: 'var(--terracotta)', fontWeight: 700 }}>PDF</div>
                  <div style={{ width: 22, height: 2, background: 'var(--border-strong)', boxShadow: '0 4px 0 0 var(--border-strong), 0 8px 0 0 var(--border-strong)' }}/>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>周传博_简历_2026春.pdf</div>
                  <div className="hf-cap">1.4 MB · 3 页 · 刚刚上传</div>
                </div>
                <HFPill tone="terra">{state === 'uploading' ? '上传中' : state === 'parsing' ? '解析中' : '已完成'}</HFPill>
              </div>

              <div style={{ marginTop: 18 }}>
                <div style={{ height: 8, borderRadius: 99, background: 'var(--library-rail)', overflow: 'hidden', boxShadow: 'inset 0 0 0 1px var(--border-cream)' }}>
                  <div className={state === 'uploading' ? 'hf-bar-stripe' : ''} style={{
                    width: `${state === 'uploading' ? progress : 100}%`, height: '100%', background: 'var(--terracotta)', transition: 'width .2s',
                  }}/>
                </div>
                <div className="hf-cap" style={{ textAlign: 'right', marginTop: 6 }}>
                  {state === 'uploading' && `${Math.round(progress)}% · 正在传输`}
                  {state === 'parsing' && '100% · 文件已就绪'}
                  {state === 'done' && '完成 · 共用时 6.4s'}
                </div>
              </div>

              {/* mini extracted fields preview */}
              <div style={{ marginTop: 18, padding: 14, background: 'var(--library-rail)', borderRadius: 12 }}>
                <div className="hf-overline" style={{ marginBottom: 8 }}>结构化预览</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', rowGap: 8, columnGap: 14, fontSize: 13 }}>
                  <div style={{ color: 'var(--stone)' }}>姓名</div><div style={{ color: 'var(--ink)', fontWeight: 500 }}>周传博</div>
                  <div style={{ color: 'var(--stone)' }}>目标</div><div style={{ color: 'var(--ink)' }}>数据科学家 / 数据分析</div>
                  <div style={{ color: 'var(--stone)' }}>学历</div><div style={{ color: 'var(--ink)' }}>复旦大学 · 统计硕士 · 2026</div>
                  <div style={{ color: 'var(--stone)' }}>经历</div><div style={{ color: 'var(--ink)' }}>蚂蚁 风控 · 字节 数据 · 字节 增长</div>
                  <div style={{ color: 'var(--stone)' }}>技能</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {['Python','SQL','PyTorch','因果推断','A/B','Tableau'].map(s => <span key={s} className="hf-pill" style={{ height: 22, fontSize: 11.5 }}>{s}</span>)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: agent trace */}
        <div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>
            {state === 'idle' ? '待命 · Agent 将在解析时启动' :
             state === 'uploading' ? 'Agent · 待命' :
             state === 'parsing' ? 'Agent · 推理中' : 'Agent · 完成'}
          </div>

          <div className="hf-card lift" style={{ padding: 22, borderRadius: 20, minHeight: 440, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--deep-dark)', position: 'relative' }}>
                <div style={{ position: 'absolute', top: 10, left: 10, width: 8, height: 8, borderRadius: 4, background: 'var(--terracotta)', boxShadow: '0 0 0 3px rgba(201,100,66,0.2)' }}/>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Resume Parser Agent</div>
                <div className="hf-cap">ReAct loop · Haiku 4.5 · 4 tools</div>
              </div>
              {state === 'parsing' && <span className="hf-spin cool"/>}
              {state === 'done' && <span className="hf-pill emerald">{I.check(12)} 完成</span>}
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {STEPS.map((s, i) => {
                const active = state === 'parsing' && i === parseStep;
                const done = (state === 'parsing' && i < parseStep) || state === 'done';
                const pending = !active && !done;
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 12,
                    background: active ? 'var(--terracotta-wash)' : done ? 'var(--emerald-soft)' : 'var(--library-rail)',
                    boxShadow: `0 0 0 1px ${active ? '#eccfb6' : done ? '#c7d9c2' : 'var(--border-cream)'}`,
                    opacity: pending && state !== 'idle' ? 0.5 : 1,
                    transition: 'all .25s',
                  }}>
                    <span style={{ width: 26, height: 26, borderRadius: 13, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      background: active ? 'var(--terracotta)' : done ? 'var(--emerald)' : 'var(--ivory)',
                      color: (active || done) ? '#fff' : 'var(--stone)',
                      boxShadow: (active || done) ? 'none' : '0 0 0 1px var(--border-warm)',
                    }}>{active ? <span className="hf-spin" style={{ width: 12, height: 12, borderColor: 'rgba(255,255,255,0.4)', borderTopColor: '#fff' }}/> : done ? I.check(14) : <span style={{ fontSize: 11, fontWeight: 600 }}>{i + 1}</span>}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--ink)' }}>{s.label}</div>
                      <div className="hf-cap" style={{ marginTop: 1 }}>{active ? '推理中…' : done ? s.hint : '等待'}</div>
                    </div>
                    <span className="hf-mono-sm" style={{ color: 'var(--stone)', fontSize: 11 }}>
                      {done ? `${(1 + i * 0.9).toFixed(1)}s` : active ? '…' : '—'}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* terminal-ish trace */}
            <div style={{ marginTop: 14, padding: '12px 14px', background: 'var(--deep-dark)', borderRadius: 12, fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.7, color: 'var(--warm-silver)' }}>
              <div><span style={{ color: 'var(--terracotta)' }}>$</span> parser.run(file=resume.pdf)</div>
              {state !== 'idle' && <div><span style={{ color: '#86b97a' }}>✓</span> read_pdf → 3 pages</div>}
              {(state === 'parsing' && parseStep >= 1) || state === 'done' ? <div><span style={{ color: '#86b97a' }}>✓</span> extract_sections → ok</div> : null}
              {(state === 'parsing' && parseStep >= 2) || state === 'done' ? <div><span style={{ color: '#86b97a' }}>✓</span> match_companies → 14/16</div> : null}
              {(state === 'parsing' && parseStep >= 3) || state === 'done' ? <div><span style={{ color: '#86b97a' }}>✓</span> infer_target → 数据分析</div> : null}
              {state === 'done' && <div style={{ color: '#fff' }}>→ session_ready<span className="hf-caret" style={{ color: 'var(--terracotta)', height: '0.9em' }}/></div>}
            </div>
          </div>

          {state === 'done' && (
            <div className="hf-slide" style={{ marginTop: 14, padding: 14, background: 'var(--ivory)', borderRadius: 12, boxShadow: 'var(--sh-ring)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ color: 'var(--terracotta)' }}>{I.sparkle(16)}</div>
              <div style={{ flex: 1, fontSize: 13.5, color: 'var(--ink-soft)' }}>已推断目标：<b>金融科技 · 数据分析师 · 上海</b>。下一步可微调。</div>
              <HFBtn variant="primary" size="sm" iconRight={I.arrowRight(12)}>进入工作台</HFBtn>
            </div>
          )}
        </div>
      </div>

      {/* footer help */}
      <div style={{ position: 'absolute', bottom: 20, left: 48, right: 48, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="hf-cap">💡 三步流程：上传 · 解析 · 确认偏好 — 每步都可撤回</div>
        <div className="hf-cap hf-mono" style={{ letterSpacing: '0.04em' }}>session #a7d · feature/big-wip</div>
      </div>
    </div>
  );
};

const HFStepper = ({ current = 0 }) => {
  const items = ['上传', '解析', '确认偏好'];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {items.map((label, i) => {
        const active = i === current;
        const done = i < current;
        return (
          <React.Fragment key={i}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                width: 22, height: 22, borderRadius: 11, fontSize: 11, fontWeight: 600,
                background: (active || done) ? 'var(--terracotta)' : 'var(--library-rail)',
                color: (active || done) ? '#fff' : 'var(--stone)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: active ? '0 0 0 4px rgba(201,100,66,0.18)' : 'none',
              }}>{done ? I.check(12) : i + 1}</span>
              <span style={{ fontSize: 13, fontWeight: active ? 600 : 400, color: active ? 'var(--ink)' : 'var(--stone)' }}>{label}</span>
            </div>
            {i < 2 && <span style={{ width: 24, height: 1, background: 'var(--border-warm)' }}/>}
          </React.Fragment>
        );
      })}
    </div>
  );
};

Object.assign(window, { HFUpload, HFStepper });
