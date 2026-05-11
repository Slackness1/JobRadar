import { useEffect, useMemo, useState } from 'react';
import api from '../api';
import '../styles/review-theme.css';

interface ReviewItem {
  id: number;
  job_id: string;
  title: string;
  company: string;
  location: string;
  source: string;
  track_predicted: string;
  track_bucket: 'FinTech' | '纯金融' | '其他';
  quality_label: string;
  publish_date: string | null;
  created_at: string | null;
  detail_url: string;
  job_req_excerpt: string;
}

interface ReviewResp {
  items: ReviewItem[];
  summary: Record<'FinTech' | '纯金融' | '其他', { queue: number; live: number }>;
  total_pending: number;
  generated_at: string;
}

const BUCKET_DESC: Record<string, string> = {
  FinTech: '金融 × 科技',
  纯金融: '投行 / 券商 / 公募',
  其他: '央国企 / 互联网 / 外企',
};
const BUCKET_COLORS: Record<string, string> = {
  FinTech: 'var(--rv-accent)',
  纯金融: 'var(--rv-blue)',
  其他: 'var(--rv-soft)',
};
const PILL_CLS: Record<string, string> = {
  FinTech: 'rv-pill rv-pill-fintech',
  纯金融:  'rv-pill rv-pill-pure',
  其他:    'rv-pill rv-pill-other',
};

const TRACK_OPTIONS: { key: string; label: string }[] = [
  { key: 'internet',         label: '互联网 (internet)' },
  { key: 'banks',            label: '银行 (banks)' },
  { key: 'securities',       label: '券商 (securities)' },
  { key: 'funds',            label: '公募 (funds)' },
  { key: 'pe_vc',            label: 'PE/VC' },
  { key: 'insurance',        label: '保险 (insurance)' },
  { key: 'state_owned',      label: '央国企 (state_owned)' },
  { key: 'consumer_foreign', label: '消费外企 (consumer_foreign)' },
  { key: 'FinTech',          label: 'FinTech' },
];

function friendlyTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.round(diffMs / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return `${mins}m`;
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.round(hrs / 24);
    return `${days}d`;
  } catch { return iso; }
}

export default function ReviewQueue() {
  const [data, setData] = useState<ReviewResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [bucket, setBucket] = useState<'all' | 'FinTech' | '纯金融' | '其他'>('all');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [retrackOpen, setRetrackOpen] = useState<{ ids: number[] } | null>(null);
  const [retrackChoice, setRetrackChoice] = useState<string>('');
  const [toast, setToast] = useState<string>('');

  async function load() {
    setLoading(true);
    try {
      const resp = await api.get<ReviewResp>('/review-queue');
      setData(resp.data);
    } catch (e) {
      console.error(e);
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  const items = useMemo(() => {
    if (!data) return [];
    return bucket === 'all' ? data.items : data.items.filter(it => it.track_bucket === bucket);
  }, [data, bucket]);

  const totals = useMemo(() => {
    const s = data?.summary ?? { FinTech: { queue: 0, live: 0 }, 纯金融: { queue: 0, live: 0 }, 其他: { queue: 0, live: 0 } };
    return s;
  }, [data]);

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(''), 2200);
  }

  function toggle(id: number) {
    setSelected(s => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }
  function toggleAllVisible() {
    setSelected(s => {
      const visibleIds = items.map(i => i.id);
      const allChecked = visibleIds.every(i => s.has(i));
      const n = new Set(s);
      if (allChecked) visibleIds.forEach(i => n.delete(i));
      else visibleIds.forEach(i => n.add(i));
      return n;
    });
  }

  async function approve(ids: number[]) {
    if (ids.length === 1) {
      await api.post(`/review-queue/${ids[0]}/approve`);
    } else {
      await api.post('/review-queue/batch', { ids, action: 'approve' });
    }
    flash(`已通过 ${ids.length} 条`);
    setSelected(new Set());
    load();
  }
  async function reject(ids: number[]) {
    if (ids.length === 1) {
      await api.post(`/review-queue/${ids[0]}/reject`);
    } else {
      await api.post('/review-queue/batch', { ids, action: 'reject' });
    }
    flash(`已驳回 ${ids.length} 条`);
    setSelected(new Set());
    load();
  }
  async function applyRetrack() {
    if (!retrackOpen || !retrackChoice) return;
    const ids = retrackOpen.ids;
    if (ids.length === 1) {
      await api.post(`/review-queue/${ids[0]}/retrack`, { track_predicted: retrackChoice });
    } else {
      await api.post('/review-queue/batch', { ids, action: 'retrack', track_predicted: retrackChoice });
    }
    flash(`已改赛道 → ${retrackChoice}`);
    setRetrackOpen(null); setRetrackChoice(''); setSelected(new Set());
    load();
  }

  const selectedArr = useMemo(() => Array.from(selected), [selected]);
  const hasSelection = selectedArr.length > 0;
  const slaAvg = '22s';

  return (
    <div data-theme="review">
      <div className="rv-header">
        <span className="rv-title">审核队列</span>
        <span className="rv-subtitle">
          {loading
            ? '加载中…'
            : `${data?.total_pending ?? 0} 条待审 · 来源：爬虫 LLM 标注不确定`}
        </span>
        <div className="rv-header-actions">
          {hasSelection && (
            <span className="rv-selected-count">已选 {selectedArr.length} 条 ↓</span>
          )}
          <button className="rv-btn"
                  disabled={!hasSelection}
                  onClick={() => { setRetrackOpen({ ids: selectedArr }); }}>
            批量改赛道
          </button>
          <button className="rv-btn rv-btn-accent"
                  disabled={!hasSelection}
                  onClick={() => approve(selectedArr)}>
            批量通过
          </button>
          <button className="rv-btn rv-btn-danger"
                  disabled={!hasSelection}
                  onClick={() => reject(selectedArr)}>
            批量驳回
          </button>
          <button className="rv-btn" onClick={load}>↻ 刷新</button>
        </div>
      </div>

      {/* Tier strip */}
      <div className="rv-tier-strip">
        {(['FinTech', '纯金融', '其他'] as const).map(t => (
          <div key={t} className="rv-tier-card">
            <span className="rv-tier-card-stripe" style={{ background: BUCKET_COLORS[t] }} />
            <div>
              <div className="rv-tier-card-name">{t}</div>
              <div className="rv-tier-card-desc">{BUCKET_DESC[t]}</div>
            </div>
            <div className="rv-tier-card-numbers">
              <div className="rv-tier-card-queue">
                {totals[t].queue}<span style={{ fontSize: 11, color: 'var(--rv-soft)', fontFamily: 'var(--rv-font-sans)', fontWeight: 400 }}> 待审</span>
              </div>
              <div className="rv-tier-card-live">已上线 {totals[t].live}</div>
            </div>
          </div>
        ))}
        <div className="rv-sla-cell">
          <span className="rv-sla-cell-label">SLA</span>
          <span className="rv-sla-cell-value">{slaAvg}</span>
          <span style={{ fontSize: 10, color: 'var(--rv-soft)', marginTop: 2 }}>平均处理</span>
        </div>
      </div>

      {/* Bucket tabs */}
      <div className="rv-tabs">
        {(['all', 'FinTech', '纯金融', '其他'] as const).map(b => {
          const count = b === 'all'
            ? (totals.FinTech.queue + totals.纯金融.queue + totals.其他.queue)
            : totals[b].queue;
          return (
            <button key={b} className={`rv-tab ${bucket === b ? 'is-active' : ''}`} onClick={() => setBucket(b)}>
              {b === 'all' ? '全部' : b}<span className="rv-tab-count">{count}</span>
            </button>
          );
        })}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: 'var(--rv-soft)' }}>
          {items.length > 0 && `显示 ${items.length} 条`}
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="rv-loading">加载中…</div>
      ) : items.length === 0 ? (
        <div className="rv-empty">🎉 当前没有待审岗位</div>
      ) : (
        <div className="rv-table">
          <div className="rv-table-head">
            <div>
              <input type="checkbox" className="rv-checkbox"
                     checked={items.length > 0 && items.every(i => selected.has(i.id))}
                     onChange={toggleAllVisible} />
            </div>
            <div>来源</div>
            <div>岗位 / 公司</div>
            <div>抓取时间</div>
            <div>城市</div>
            <div>建议赛道</div>
            <div>置信度</div>
            <div style={{ textAlign: 'right' }}>操作</div>
          </div>
          {items.map(it => {
            const isSel = selected.has(it.id);
            const confBucket = it.quality_label === 'low_signal' ? 'bad' :
                               it.track_predicted ? 'ok' : 'warn';
            const confLabel = confBucket === 'bad' ? 'low_signal'
                           : confBucket === 'warn' ? '未分类'
                           : it.track_predicted;
            return (
              <div key={it.id} className={`rv-table-row ${isSel ? 'is-selected' : ''}`}>
                <div>
                  <input type="checkbox" className="rv-checkbox"
                         checked={isSel} onChange={() => toggle(it.id)} />
                </div>
                <div className="rv-cell-source">🤖</div>
                <div>
                  <div className="rv-cell-title">{it.title || '(无标题)'}</div>
                  <div className="rv-cell-company">{it.company || '—'}</div>
                </div>
                <div className="rv-cell-meta">{it.source} · {friendlyTime(it.created_at)}</div>
                <div className="rv-cell-loc">{it.location || '—'}</div>
                <div>
                  <span className={PILL_CLS[it.track_bucket]}>{it.track_bucket}</span>
                </div>
                <div className={`rv-cell-conf ${confBucket === 'bad' ? 'is-bad' : confBucket === 'warn' ? 'is-warn' : ''}`}>
                  {confBucket === 'bad' && '⚠ '}{confLabel}
                </div>
                <div className="rv-cell-actions">
                  <span className="rv-icon-approve" title="通过" onClick={() => approve([it.id])}>✓</span>
                  <span className="rv-icon-reject" title="驳回" onClick={() => reject([it.id])}>×</span>
                  <span className="rv-icon-detail" onClick={() => setRetrackOpen({ ids: [it.id] })}>改赛道</span>
                  {it.detail_url && (
                    <a className="rv-icon-detail" href={it.detail_url} target="_blank" rel="noreferrer">↗</a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {retrackOpen && (
        <div className="rv-modal-back" onClick={() => setRetrackOpen(null)}>
          <div className="rv-modal" onClick={e => e.stopPropagation()}>
            <h3>改赛道 · {retrackOpen.ids.length} 条岗位</h3>
            <div className="rv-modal-tracks">
              {TRACK_OPTIONS.map(opt => (
                <div key={opt.key}
                     className={`rv-track-opt ${retrackChoice === opt.key ? 'is-selected' : ''}`}
                     onClick={() => setRetrackChoice(opt.key)}>
                  {opt.label}
                </div>
              ))}
            </div>
            <div className="rv-modal-actions">
              <button className="rv-btn" onClick={() => { setRetrackOpen(null); setRetrackChoice(''); }}>取消</button>
              <button className="rv-btn rv-btn-accent" disabled={!retrackChoice} onClick={applyRetrack}>
                确认 · 改为「{retrackChoice || '...'}」
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: 'var(--rv-ink)', color: 'var(--rv-ivory)',
          padding: '10px 16px', borderRadius: 8, fontSize: 13,
          boxShadow: '0 6px 24px rgba(0,0,0,0.18)', zIndex: 200,
        }}>{toast}</div>
      )}
    </div>
  );
}
