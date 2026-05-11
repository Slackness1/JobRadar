/**
 * Teacher-entry admin panel (Phase 1, read-only).
 *
 * Sits on /sites under the crawler health bar. Shows what teachers have
 * been submitting today/this week — KPI strip + recent draft list.
 *
 * No approve/reject actions yet (see Phase 2 in chat).
 */

import { useEffect, useState } from 'react';

import {
  approveTeacherDraft,
  fetchTeacherEntryDrafts,
  fetchTeacherEntrySummary,
  rejectTeacherDraft,
} from '../../api';
import { isAdminUser } from '../../auth/mockSession';
import type { TeacherDraftRow, TeacherEntrySummary, TeacherSourceType } from './types';

const SOURCE_LABEL: Record<TeacherSourceType | string, string> = {
  link: '🔗 链接',
  ocr: '📸 截图 OCR',
  text: '📝 JD 文本',
};

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  pending: '待审',
  approved: '已通过',
  rejected: '已驳回',
};

const TRACK_LABEL: Record<string, string> = {
  finance: '纯金融',
  fintech: 'FinTech',
  other: '其他',
};

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const sameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  if (sameDay) return `今天 ${hh}:${mm}`;
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${md} ${hh}:${mm}`;
}

interface FilterState {
  status: string;
  source_type: string;
}

export default function TeacherEntryPanel() {
  const [summary, setSummary] = useState<TeacherEntrySummary | null>(null);
  const [drafts, setDrafts] = useState<TeacherDraftRow[]>([]);
  const [loaded, setLoaded] = useState<boolean>(false);
  const [filter, setFilter] = useState<FilterState>({ status: '', source_type: '' });
  const isAdmin = isAdminUser();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [inFlight, setInFlight] = useState<Record<number, 'approve' | 'reject'>>({});
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState<string>('');
  const [actionToast, setActionToast] = useState<string>('');
  // Bumping this triggers refetch (useEffect dep)
  const [refetchKey, setRefetchKey] = useState<number>(0);

  function flashAction(msg: string) {
    setActionToast(msg);
    window.setTimeout(() => setActionToast(''), 2400);
  }

  async function handleApprove(draftId: number) {
    setInFlight((p) => ({ ...p, [draftId]: 'approve' }));
    try {
      const r = await approveTeacherDraft(draftId);
      flashAction(`已通过 → 学生可见（Job#${r.data.job_id}）`);
      setRefetchKey((k) => k + 1);
    } catch (e) {
      flashAction(`通过失败：${(e as Error).message}`);
    } finally {
      setInFlight((p) => {
        const n = { ...p }; delete n[draftId]; return n;
      });
    }
  }

  async function handleReject(draftId: number) {
    if (!rejectReason.trim()) {
      flashAction('请填驳回原因');
      return;
    }
    setInFlight((p) => ({ ...p, [draftId]: 'reject' }));
    try {
      await rejectTeacherDraft(draftId, rejectReason.trim());
      flashAction('已驳回');
      setRejectingId(null);
      setRejectReason('');
      setRefetchKey((k) => k + 1);
    } catch (e) {
      flashAction(`驳回失败：${(e as Error).message}`);
    } finally {
      setInFlight((p) => {
        const n = { ...p }; delete n[draftId]; return n;
      });
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchTeacherEntrySummary(),
      fetchTeacherEntryDrafts({
        status: filter.status || undefined,
        source_type: filter.source_type || undefined,
        limit: 30,
      }),
    ])
      .then(([s, d]) => {
        if (cancelled) return;
        setSummary(s.data);
        setDrafts(d.data);
        setLoaded(true);
      })
      .catch(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => { cancelled = true; };
  }, [filter.status, filter.source_type, refetchKey]);

  const oldestPending = summary?.pending_oldest_age_minutes ?? 0;
  const showBacklog = (summary?.today.pending ?? 0) > 0 && oldestPending > 60;

  return (
    <section className="te-panel">
      <header className="te-panel__head">
        <div>
          <div className="te-panel__overline">教师录入 · 今日 / 本周</div>
          <h2 className="te-panel__title">人工补录的岗位</h2>
        </div>
        <a href="/teacher" target="_blank" rel="noreferrer" className="te-panel__link">
          打开录入页 →
        </a>
      </header>

      {/* KPI strip */}
      <div className="te-panel__kpis">
        <div className="te-kpi">
          <div className="te-kpi__label">今日新增</div>
          <div className="te-kpi__num">{summary?.today.total ?? '—'}</div>
          <div className="te-kpi__sub">
            待审 <strong>{summary?.today.pending ?? 0}</strong> ·
            通过 <strong>{summary?.today.approved ?? 0}</strong>
          </div>
        </div>
        <div className="te-kpi">
          <div className="te-kpi__label">本周累计</div>
          <div className="te-kpi__num">{summary?.week.total ?? '—'}</div>
          <div className="te-kpi__sub">
            通过 {summary?.week.approved ?? 0} · 驳回 {summary?.week.rejected ?? 0}
          </div>
        </div>
        <div className="te-kpi">
          <div className="te-kpi__label">来源分布（今日）</div>
          {summary && summary.by_source_today.length > 0 ? (
            <div className="te-kpi__sources">
              {summary.by_source_today.map((s) => (
                <span key={s.source_type} className="te-pill">
                  {SOURCE_LABEL[s.source_type] ?? s.source_type} <strong>{s.count}</strong>
                </span>
              ))}
            </div>
          ) : (
            <div className="te-kpi__sub">—</div>
          )}
        </div>
        <div className="te-kpi">
          <div className="te-kpi__label">本周活跃教师</div>
          {summary && summary.top_teachers_week.length > 0 ? (
            <div className="te-kpi__teachers">
              {summary.top_teachers_week.slice(0, 3).map((t) => (
                <div key={t.teacher_user_key} className="te-teacher">
                  <span className="te-teacher__name">{t.teacher_name || t.teacher_user_key.slice(0, 8)}</span>
                  <span className="te-teacher__count">{t.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="te-kpi__sub">—</div>
          )}
        </div>
      </div>

      {showBacklog && (
        <div className="te-backlog-banner">
          ⚠ 最旧的待审已等了 <strong>{oldestPending}</strong> 分钟 — 看一下队列
        </div>
      )}

      {/* filters */}
      <div className="te-panel__filters">
        <span className="te-filter-label">状态</span>
        {[
          ['', '全部'],
          ['pending', '待审'],
          ['approved', '已通过'],
          ['rejected', '已驳回'],
          ['draft', '草稿'],
        ].map(([k, l]) => (
          <button
            key={k || 'all'}
            className={`te-filter-pill${filter.status === k ? ' is-active' : ''}`}
            onClick={() => setFilter((p) => ({ ...p, status: k }))}
          >{l}</button>
        ))}
        <span className="te-filter-label" style={{ marginLeft: 12 }}>来源</span>
        {[
          ['', '全部'],
          ['link', '链接'],
          ['ocr', '截图'],
          ['text', '文本'],
        ].map(([k, l]) => (
          <button
            key={k || 'all-src'}
            className={`te-filter-pill${filter.source_type === k ? ' is-active' : ''}`}
            onClick={() => setFilter((p) => ({ ...p, source_type: k }))}
          >{l}</button>
        ))}
      </div>

      {/* list */}
      {!loaded && drafts.length === 0 ? (
        <div className="te-empty">加载中…</div>
      ) : drafts.length === 0 ? (
        <div className="te-empty">
          {filter.status || filter.source_type ? '当前筛选下没有记录' : '本周还没有教师录入岗位'}
        </div>
      ) : (
        <div className="te-list">
          {drafts.map((d) => (
            <div key={d.id} className={`te-row te-row--${d.status}`}>
              <button
                className="te-row__main"
                onClick={() => setExpandedId(expandedId === d.id ? null : d.id)}
              >
                <span className="te-row__co">{(d.parsed_company || '?').slice(0, 1)}</span>
                <div className="te-row__body">
                  <div className="te-row__title-line">
                    <span className="te-row__title">{d.parsed_title || '（未识别）'}</span>
                    <span className={`te-status te-status--${d.status}`}>{STATUS_LABEL[d.status] ?? d.status}</span>
                    <span className="te-track">{TRACK_LABEL[d.track] ?? d.track}</span>
                  </div>
                  <div className="te-row__meta">
                    {[d.parsed_company, d.parsed_location].filter(Boolean).join(' · ') || '——'}
                    {' · '}
                    {SOURCE_LABEL[d.source_type] ?? d.source_type}
                    {' · 置信 '}
                    <strong>{Math.round(d.parse_confidence)}%</strong>
                    {' · '}
                    {d.teacher_name || d.teacher_dept}
                    {' · '}
                    {fmtTime(d.submitted_at ?? d.created_at)}
                  </div>
                </div>
              </button>
              {expandedId === d.id && (
                <div className="te-row__expand">
                  {d.parsed_jd_summary && (
                    <div className="te-row__field">
                      <span className="te-row__field-label">JD 摘要</span>
                      <span>{d.parsed_jd_summary}</span>
                    </div>
                  )}
                  {d.tags.length > 0 && (
                    <div className="te-row__field">
                      <span className="te-row__field-label">标签</span>
                      <span>{d.tags.map((t) => <span key={t} className="te-tag">{t}</span>)}</span>
                    </div>
                  )}
                  {d.teacher_note && (
                    <div className="te-row__field">
                      <span className="te-row__field-label">教师备注</span>
                      <span>{d.teacher_note}</span>
                    </div>
                  )}
                  {d.reject_reason && (
                    <div className="te-row__field">
                      <span className="te-row__field-label">驳回原因</span>
                      <span style={{ color: 'var(--crimson)' }}>{d.reject_reason}</span>
                    </div>
                  )}
                  {d.parsed_detail_url && (
                    <div className="te-row__field">
                      <span className="te-row__field-label">原文链接</span>
                      <a href={d.parsed_detail_url} target="_blank" rel="noreferrer">
                        {d.parsed_detail_url.length > 80 ? d.parsed_detail_url.slice(0, 80) + '…' : d.parsed_detail_url}
                      </a>
                    </div>
                  )}

                  {/* Phase 2 actions — Phase 3 gates them behind admin role */}
                  {(d.status === 'pending' || d.status === 'draft') && !isAdmin && (
                    <div className="te-row__actions te-row__actions--readonly">
                      <span className="te-row__hint">
                        只读模式 — 用 <strong>slackness</strong> 账号登录可审核
                      </span>
                    </div>
                  )}
                  {(d.status === 'pending' || d.status === 'draft') && isAdmin && (
                    <div className="te-row__actions">
                      {rejectingId === d.id ? (
                        <>
                          <input
                            className="te-reject-input"
                            placeholder="驳回原因（必填，仅审核员可见）"
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            autoFocus
                          />
                          <button
                            className="te-action te-action--reject"
                            onClick={() => handleReject(d.id)}
                            disabled={inFlight[d.id] === 'reject'}
                          >{inFlight[d.id] === 'reject' ? '驳回中…' : '确认驳回'}</button>
                          <button
                            className="te-action te-action--ghost"
                            onClick={() => { setRejectingId(null); setRejectReason(''); }}
                          >取消</button>
                        </>
                      ) : (
                        <>
                          <button
                            className="te-action te-action--approve"
                            onClick={() => handleApprove(d.id)}
                            disabled={!!inFlight[d.id]}
                          >{inFlight[d.id] === 'approve' ? '通过中…' : '✓ 通过 → 上架'}</button>
                          <button
                            className="te-action te-action--ghost"
                            onClick={() => { setRejectingId(d.id); setRejectReason(''); }}
                            disabled={!!inFlight[d.id]}
                          >驳回</button>
                          <span className="te-row__hint">通过后会进 jobs 表 & scoring，学生可在推荐里看到</span>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {actionToast && (
        <div className="te-action-toast">{actionToast}</div>
      )}
    </section>
  );
}
