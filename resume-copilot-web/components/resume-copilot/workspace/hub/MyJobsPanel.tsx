'use client';

/**
 * MyJobsPanel — 「我的岗位」视图.
 *
 * 展示三组:收藏想投 / 已投递 / 不合适.
 * 每行: 公司文字头像(前2字) + 公司/岗名/地点 + 收录日期 + 「去投递 ↗」链接 + 状态操作.
 * .hf scope; props: { sessionId, onClose }.
 */

import { useCallback, useEffect, useState } from 'react';
import { getMyJobs, markJobState } from '../../api';
import type { JobState, MyJobItem, MyJobsResult } from '../../types';

export interface MyJobsPanelProps {
  sessionId: number;
  onClose?: () => void;
}

// 公司名前两个字作为文字头像
function CompanyAvatar({ name }: { name: string }) {
  const chars = name.replace(/\s/g, '').slice(0, 2) || '??';
  return (
    <div
      style={{
        width: 36,
        height: 36,
        borderRadius: 9,
        background: 'var(--terracotta-wash)',
        border: '1px solid var(--terracotta-ring)',
        color: 'var(--terracotta-strong)',
        font: '600 12px var(--font-sans)',
        display: 'grid',
        placeItems: 'center',
        flex: 'none',
        letterSpacing: '-0.5px',
      }}
    >
      {chars}
    </div>
  );
}

// 日期格式化: publish_date || scraped_at → 「收录于 MM-DD」
function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  let s = iso.includes('T') ? iso : iso.replace(' ', 'T');
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s += 'Z';
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return '';
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `收录于 ${mm}-${dd}`;
}

interface GroupConfig {
  key: keyof Pick<MyJobsResult, 'saved' | 'applied' | 'dismissed'>;
  label: string;
  emptyText: string;
  nextState: JobState | '';
  nextLabel: string;
  removeLabel: string;
}

const GROUPS: GroupConfig[] = [
  {
    key: 'saved',
    label: '收藏想投',
    emptyText: '还没有收藏的岗位',
    nextState: 'applied',
    nextLabel: '已投递',
    removeLabel: '取消收藏',
  },
  {
    key: 'applied',
    label: '已投递',
    emptyText: '还没有标记已投递的岗位',
    nextState: '',
    nextLabel: '',
    removeLabel: '撤销投递',
  },
  {
    key: 'dismissed',
    label: '不合适',
    emptyText: '还没有标记不合适的岗位',
    nextState: '',
    nextLabel: '',
    removeLabel: '取消屏蔽',
  },
];

export default function MyJobsPanel({ sessionId, onClose }: MyJobsPanelProps) {
  const [data, setData] = useState<MyJobsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [acting, setActing] = useState<string | null>(null); // 正在操作的 job_id

  const reload = useCallback(() => {
    setLoading(true);
    setError(false);
    getMyJobs()
      .then((r) => {
        setData(r);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleAction = useCallback(
    async (jobId: string, state: '' | JobState) => {
      setActing(jobId);
      try {
        await markJobState(sessionId, jobId, state);
        reload();
      } catch {
        /* 操作失败静默,不阻断 */
      } finally {
        setActing(null);
      }
    },
    [sessionId, reload],
  );

  const totalCount = data
    ? data.counts.saved + data.counts.applied + data.counts.dismissed
    : 0;

  return (
    <div
      className="hf"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--parchment)',
        minWidth: 0,
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '14px 16px 12px',
          borderBottom: '1px solid var(--border-warm)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flex: 'none',
          background: 'var(--ivory)',
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 15px var(--font-sans)', color: 'var(--ink)' }}>我的岗位</div>
          {data && (
            <div style={{ font: '400 11.5px var(--font-sans)', color: 'var(--stone)', marginTop: 2 }}>
              共 {totalCount} 个 · 收藏 {data.counts.saved} · 已投递 {data.counts.applied} · 不合适 {data.counts.dismissed}
            </div>
          )}
        </div>
        {onClose && (
          <button
            type="button"
            className="hf-btn ghost sm"
            onClick={onClose}
            aria-label="关闭"
            style={{
              width: 28,
              height: 28,
              minWidth: 28,
              padding: 0,
              borderRadius: 999,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flex: 'none',
            }}
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* 内容区 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--stone)', font: '400 13px var(--font-sans)' }}>
            加载中…
          </div>
        )}

        {error && !loading && (
          <div style={{ textAlign: 'center', padding: '32px 16px' }}>
            <div style={{ font: '500 13px var(--font-sans)', color: 'var(--ink-soft)' }}>加载失败</div>
            <button type="button" className="hf-btn ghost sm" style={{ marginTop: 10 }} onClick={reload}>
              重试
            </button>
          </div>
        )}

        {!loading && !error && data && (
          <>
            {GROUPS.map((g) => {
              const items: MyJobItem[] = data[g.key];
              return (
                <div key={g.key}>
                  {/* 分组标题 */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 7,
                      marginBottom: 8,
                    }}
                  >
                    <span
                      className="hf-cap"
                      style={{ font: '600 10.5px var(--font-sans)', letterSpacing: '0.06em', color: 'var(--stone)', textTransform: 'uppercase' }}
                    >
                      {g.label}
                    </span>
                    <span
                      className="hf-pill terra"
                      style={{ fontSize: 10, padding: '1px 7px' }}
                    >
                      {items.length}
                    </span>
                  </div>

                  {items.length === 0 ? (
                    <div
                      style={{
                        padding: '10px 12px',
                        borderRadius: 10,
                        background: 'var(--library-rail)',
                        font: '400 12px var(--font-sans)',
                        color: 'var(--stone)',
                      }}
                    >
                      {g.emptyText}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {items.map((it) => (
                        <div
                          key={it.job_id}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 10,
                            padding: '10px 12px',
                            borderRadius: 12,
                            background: 'var(--ivory)',
                            boxShadow: '0 0 0 1px var(--border-warm)',
                          }}
                        >
                          <CompanyAvatar name={it.company} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div
                              style={{
                                font: '600 13px var(--font-sans)',
                                color: 'var(--ink)',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {it.job_title}
                            </div>
                            <div
                              style={{
                                font: '400 11.5px var(--font-sans)',
                                color: 'var(--ink-soft)',
                                marginTop: 1,
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {it.company}
                              {it.location ? ` · ${it.location}` : ''}
                            </div>
                            <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)', marginTop: 2 }}>
                              {formatDate(it.publish_date || it.scraped_at)}
                            </div>
                            {/* 操作行 */}
                            <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                              {it.detail_url && (
                                <a
                                  href={it.detail_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="hf-btn sand sm"
                                  style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                >
                                  去投递
                                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                    <polyline points="15 3 21 3 21 9" />
                                    <line x1="10" y1="14" x2="21" y2="3" />
                                  </svg>
                                </a>
                              )}
                              {g.nextState !== '' && (
                                <button
                                  type="button"
                                  className="hf-btn primary sm"
                                  disabled={acting === it.job_id}
                                  onClick={() => void handleAction(it.job_id, g.nextState as JobState)}
                                >
                                  {g.nextLabel}
                                </button>
                              )}
                              <button
                                type="button"
                                className="hf-btn ghost sm"
                                disabled={acting === it.job_id}
                                onClick={() => void handleAction(it.job_id, '')}
                              >
                                {g.removeLabel}
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {totalCount === 0 && (
              <div
                style={{
                  textAlign: 'center',
                  padding: '40px 16px',
                  color: 'var(--stone)',
                  font: '400 13px var(--font-sans)',
                  lineHeight: 1.7,
                }}
              >
                <div style={{ font: '500 14px var(--font-sans)', color: 'var(--ink-soft)', marginBottom: 6 }}>
                  还没有标记任何岗位
                </div>
                在职位推荐里点「收藏想投」「标记已投递」「不合适」<br />
                就会汇总到这里
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
