import { useEffect, useState } from 'react';
import api from '../api';
import '../styles/health-theme.css';

interface Service {
  name: string; sub: string; status: 'ok' | 'warn' | 'down'; metric: string;
}
interface Event {
  severity: 'ok' | 'warn' | 'info'; title: string; when: string; who: string;
}
interface SiteRow {
  company: string; source: string;
  last_run_at: string | null; last_status: string | null;
  today_new: number; alert_level: 'green' | 'yellow' | 'red' | 'unknown';
  last_error_short: string;
}
interface SchedulerJob { id: string; cron_expression: string; next_run: string | null; }
interface HealthResp {
  headline: {
    overall: 'ok' | 'warn' | 'bad'; today_new: number;
    alert_red: number; alert_yellow: number; alert_green: number;
    last_batch_at: string | null; last_batch_status: string | null;
    generated_at: string;
  };
  services: Service[];
  scheduler: { is_active: boolean; next_run: string | null; jobs: SchedulerJob[] };
  sites: SiteRow[];
  events: Event[];
}

function friendlyTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now.getTime() - d.getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)} 秒前`;
    if (diff < 3600) return `${Math.round(diff/60)} 分钟前`;
    if (diff < 86400) return `${Math.round(diff/3600)} 小时前`;
    return `${Math.round(diff/86400)} 天前`;
  } catch { return iso; }
}
function shortDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(/\//g, '-');
  } catch { return iso; }
}

export default function SystemHealth() {
  const [data, setData] = useState<HealthResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [recrawling, setRecrawling] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<string>('');

  async function load() {
    try {
      const resp = await api.get<HealthResp>('/system-health');
      setData(resp.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(''), 2200);
  }

  async function recrawl(company: string) {
    if (recrawling.has(company)) return;
    setRecrawling(s => new Set(s).add(company));
    try {
      await api.post(`/sites/${encodeURIComponent(company)}/recrawl`);
      flash(`已触发重爬 · ${company}`);
      // Refresh after a short delay so user sees movement
      setTimeout(load, 2500);
    } catch {
      flash(`重爬失败 · ${company}`);
    } finally {
      setTimeout(() => {
        setRecrawling(s => { const n = new Set(s); n.delete(company); return n; });
      }, 3500);
    }
  }

  if (loading || !data) {
    return (
      <div data-theme="health">
        <div className="hl-loading">加载系统状态…</div>
      </div>
    );
  }

  const h = data.headline;
  const overallPill = h.overall === 'ok' ? <span className="hl-pill hl-pill-ok">全部正常</span>
                    : h.overall === 'warn' ? <span className="hl-pill hl-pill-warn">部分预警</span>
                    : <span className="hl-pill hl-pill-bad">异常</span>;

  return (
    <div data-theme="health">
      <div className="hl-header">
        <span className="hl-title">系统健康面板</span>
        <span className="hl-subtitle">服务状态 · 爬虫节点 · 近期事件</span>
        <div className="hl-header-meta">
          <span>更新于 {friendlyTime(h.generated_at)}</span>
          {overallPill}
          <button className="hl-btn" onClick={load}>↻ 刷新</button>
        </div>
      </div>

      <div className="hl-hero-summary">
        今日新增 <strong>{h.today_new}</strong> 岗位 ·
        {' '}爬虫节点 <strong>{h.alert_green}</strong> 正常 / <strong style={{ color: 'var(--hl-amber)' }}>{h.alert_yellow}</strong> 预警 / <strong style={{ color: 'var(--hl-crimson)' }}>{h.alert_red}</strong> 异常 ·
        {' '}上次批次：<strong>{shortDate(h.last_batch_at)}</strong> ({h.last_batch_status || '—'})
      </div>

      {/* Service grid */}
      <div className="hl-services">
        {data.services.map(s => (
          <div key={s.name} className="hl-service">
            <div className="hl-service-head">
              <span className={`hl-service-dot is-${s.status}`} />
              <span className="hl-service-name">{s.name}</span>
            </div>
            <div className="hl-service-sub">{s.sub}</div>
            <div className="hl-service-metric">{s.metric}</div>
          </div>
        ))}
      </div>

      {/* Split: scheduler + events */}
      <div className="hl-split">
        <div className="hl-card">
          <div className="hl-card-title">
            APScheduler · 定时任务
            <span className={`hl-card-title-meta ${data.scheduler.is_active ? 'is-ok' : ''}`}>
              {data.scheduler.is_active ? '● 运行中' : '● 已停止'}
            </span>
          </div>
          {data.scheduler.jobs.length === 0 ? (
            <div style={{ padding: '10px 0', color: 'var(--hl-soft)', fontSize: 12 }}>无任务</div>
          ) : data.scheduler.jobs.map(j => (
            <div key={j.id} className="hl-sched-row">
              <div className="hl-sched-id">{j.id}</div>
              <div className="hl-sched-cron">{j.cron_expression}</div>
              <div className="hl-sched-next">下次：{shortDate(j.next_run)}</div>
            </div>
          ))}
        </div>

        <div className="hl-card">
          <div className="hl-card-title">
            近期事件
            <span className="hl-card-title-meta">过去 7 天</span>
          </div>
          {data.events.length === 0 ? (
            <div style={{ padding: '20px 0', color: 'var(--hl-soft)', fontSize: 12, textAlign: 'center' }}>无事件</div>
          ) : data.events.map((e, i) => (
            <div key={i} className="hl-event-row">
              <span className={`hl-event-dot is-${e.severity}`} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="hl-event-title">{e.title}</div>
                <div className="hl-event-meta" title={e.who}>{friendlyTime(e.when)} · {e.who}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sites table (absorbed from /sites) */}
      <div className="hl-sites">
        <div className="hl-sites-head">
          <span className="hl-sites-head-title">爬虫节点 · {data.sites.length} 站点</span>
          <span style={{ fontSize: 12, color: 'var(--hl-soft)' }}>
            <span className="hl-alert-dot is-red" />红 {h.alert_red}{' '}
            <span className="hl-alert-dot is-yellow" style={{ marginLeft: 10 }} />黄 {h.alert_yellow}{' '}
            <span className="hl-alert-dot is-green" style={{ marginLeft: 10 }} />绿 {h.alert_green}
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: 'var(--hl-soft)' }}>红黄优先 · 按今日新增排序</span>
        </div>
        <div className="hl-sites-table-head">
          <div>公司</div>
          <div>来源</div>
          <div>状态</div>
          <div>今日新增</div>
          <div>最近运行</div>
          <div style={{ textAlign: 'right' }}>操作</div>
        </div>
        {data.sites.map(s => (
          <div key={`${s.company}-${s.source}`} className="hl-sites-row">
            <div className="hl-site-name" title={s.last_error_short}>{s.company}</div>
            <div className="hl-site-source">{s.source}</div>
            <div>
              <span className={`hl-alert-dot is-${s.alert_level}`} />
              {s.last_status || '—'}
            </div>
            <div className={`hl-site-today ${(s.today_new || 0) === 0 ? 'is-zero' : ''}`}>
              +{s.today_new || 0}
            </div>
            <div className="hl-site-time">{friendlyTime(s.last_run_at)}</div>
            <div style={{ textAlign: 'right' }}>
              <button className="hl-recrawl"
                      disabled={recrawling.has(s.company)}
                      onClick={() => recrawl(s.company)}>
                {recrawling.has(s.company) ? '运行中…' : '重爬'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: 'var(--hl-ink)', color: 'var(--hl-ivory)',
          padding: '10px 16px', borderRadius: 8, fontSize: 13,
          boxShadow: '0 6px 24px rgba(0,0,0,0.18)', zIndex: 200,
        }}>{toast}</div>
      )}
    </div>
  );
}
