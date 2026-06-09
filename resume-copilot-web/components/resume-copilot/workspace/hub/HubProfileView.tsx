'use client';

/**
 * HubProfileView — 个人档案 B 闭环视图(统一对话 Hub 右栏 profile 槽).
 *
 * 个人档案是唯一**不是技能**的模块 —— 是学生自己的数据, 点开直接看, 没有思考卡,
 *   没有结果卡(spec exception). 两层结构:
 *   1. 确认信息(权威, 顶部): 你拍板的, 喂推荐 + 骨架. 当前从 working query 取目标赛道,
 *      其余字段(城市 / 求职阶段 / 投递类型)暂用静态兜底(TODO 接 prefs).
 *   2. AI 推断 · 待确认(底部): 从 KB 拉未确认条目, 学生「确认·升为确认信息」或「否掉」.
 *      乐观更新: 确认 → 绿色已升态; 否掉 → 删划线移除. 失败回滚 + 内联提示.
 *
 * 隐私铁律(产品红线): category === 'weakness_signal' 的条目**永不**展示给学生 ——
 *   这是内部弱点信号, 露给学生是产品违规. 过滤无条件执行, 不受任何开关影响.
 *
 * 真实数据: listStudentExperiences({ includeArchived:false }) 取未归档 KB 条目;
 *   confirmStudentExperience / archiveStudentExperience 做确认 / 否掉.
 *   目标赛道走 getWorkingQuery → working_query.seed_sub_cats(廉价, 进场拉一次).
 *
 * Token 全取自 `.hf`(外层 HubShell className="hf").
 */

import { useEffect, useState } from 'react';
import {
  archiveStudentExperience,
  confirmStudentExperience,
  getWorkingQuery,
  listStudentExperiences,
  type StudentExperienceDetail,
} from '../../api';

// ── 图标(对齐原型 HI.user / check / close) ──────────────────────────────────
function UserIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function CheckIcon({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function CloseIcon({ size = 14 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
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
  );
}

// ── 确认信息行(权威, 学生拍板的) ─────────────────────────────────────────────
interface ConfirmedRow {
  k: string;
  v: string;
}

// ── 置信度数值 → 中文标签(对齐原型 conf: 高 / 中 / 低) ───────────────────────
function confLabel(confidence: number): string {
  if (confidence >= 0.75) return '高';
  if (confidence >= 0.5) return '中';
  return '低';
}

// 卡片三态: pending(待确认) / confirmed(已升) / rejected(已否)
type CardState = 'pending' | 'confirmed' | 'rejected';

interface InferredCardProps {
  item: StudentExperienceDetail;
  state: CardState;
  error?: string;
  onConfirm: () => void;
  onReject: () => void;
}

function InferredCard({ item, state, error, onConfirm, onReject }: InferredCardProps) {
  const claim = item.summary;

  if (state === 'confirmed') {
    return (
      <div
        className="hf-slide"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 14px',
          borderRadius: 13,
          background: 'var(--emerald-soft)',
          boxShadow: '0 0 0 1px #c7d9c2',
        }}
      >
        <span style={{ color: 'var(--emerald)', display: 'inline-flex' }}>
          <CheckIcon size={15} />
        </span>
        <span style={{ font: '500 13px var(--font-sans)', color: 'var(--ink-soft)', flex: 1 }}>{claim}</span>
        <span className="hf-pill emerald" style={{ height: 24 }}>已升为确认信息</span>
      </div>
    );
  }

  if (state === 'rejected') {
    return (
      <div
        className="hf-slide"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 14px',
          borderRadius: 13,
          background: 'transparent',
          boxShadow: '0 0 0 1px var(--border-warm)',
          opacity: 0.7,
        }}
      >
        <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>
          <CloseIcon size={14} />
        </span>
        <span
          style={{
            font: '500 13px var(--font-sans)',
            color: 'var(--stone)',
            textDecoration: 'line-through',
            flex: 1,
          }}
        >
          {claim}
        </span>
        <span style={{ font: '500 11px var(--font-sans)', color: 'var(--stone)' }}>已否掉 · 不再喂画像</span>
      </div>
    );
  }

  // pending
  const from = (item.raw_excerpt || '').trim();
  return (
    <div
      style={{
        padding: '13px 15px',
        borderRadius: 14,
        background: 'var(--ivory)',
        boxShadow: '0 0 0 1px var(--border-strong)',
        borderStyle: 'dashed',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)', flex: 1 }}>{claim}</span>
        <span className="hf-pill amber" style={{ height: 24, flexShrink: 0, whiteSpace: 'nowrap' }}>
          AI 推断 · 待确认
        </span>
      </div>
      <div style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--muted)', marginBottom: 11 }}>
        {from ? <>依据：{from} </> : <>依据：从对话推断 </>}
        <span style={{ color: 'var(--stone)', fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>
          · 置信 {confLabel(item.confidence)}
        </span>
      </div>
      {error && (
        <div
          style={{
            font: '500 11px var(--font-sans)',
            color: 'var(--terracotta-strong)',
            marginBottom: 9,
          }}
        >
          {error}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" className="hf-btn primary sm" style={{ flex: 1 }} onClick={onConfirm}>
          确认 · 升为确认信息
        </button>
        <button type="button" className="hf-btn ghost sm" onClick={onReject}>
          否掉
        </button>
      </div>
    </div>
  );
}

export interface HubProfileViewProps {
  sessionId: number;
  onClose: () => void;
}

export default function HubProfileView({ sessionId, onClose }: HubProfileViewProps) {
  // 确认信息(权威): 目标赛道走 working query, 其余暂静态兜底.
  const [tracks, setTracks] = useState<string[]>([]);

  // AI 推断条目(已硬过滤掉 weakness_signal)
  const [items, setItems] = useState<StudentExperienceDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 每条的乐观态 + 失败提示
  const [cardState, setCardState] = useState<Record<number, CardState>>({});
  const [cardError, setCardError] = useState<Record<number, string>>({});

  useEffect(() => {
    let cancelled = false;

    getWorkingQuery(sessionId)
      .then((r) => {
        if (!cancelled) setTracks(r.working_query?.seed_sub_cats ?? []);
      })
      .catch(() => {
        if (!cancelled) setTracks([]);
      });

    // 未确认 + 未归档的 KB 条目 → AI 推断待确认层.
    listStudentExperiences({ includeArchived: false })
      .then((r) => {
        if (cancelled) return;
        const pending = (r.items ?? []).filter(
          (it) =>
            // 隐私铁律: 弱点信号永不展示(无条件过滤)
            it.category !== 'weakness_signal' &&
            // 只要未确认的(确认信息层是另一回事)
            it.user_confirmed === false &&
            it.is_archived === false,
        );
        setItems(pending);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError('档案加载失败，稍后重试。');
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // 目标赛道 → 确认信息行(其余字段暂静态兜底)
  const confirmedRows: ConfirmedRow[] = [
    { k: '目标赛道', v: tracks.length > 0 ? tracks.join(' · ') : '未锁定' },
    // TODO 接 prefs: 城市 / 求职阶段 / 投递类型 暂用静态兜底, 待 preferences API 接入.
    { k: '城市', v: '上海 · 北京' },
    { k: '求职阶段', v: '2026 应届 · 校招' },
    { k: '投递类型', v: '全职 + 实习' },
  ];

  async function onConfirm(id: number) {
    if (cardState[id]) return; // 已操作过
    // 乐观: 立即升为已确认
    setCardState((s) => ({ ...s, [id]: 'confirmed' }));
    setCardError((e) => {
      const next = { ...e };
      delete next[id];
      return next;
    });
    try {
      await confirmStudentExperience(id);
    } catch {
      // 回滚 + 内联提示
      setCardState((s) => {
        const next = { ...s };
        delete next[id];
        return next;
      });
      setCardError((e) => ({ ...e, [id]: '确认失败，已撤销，请重试。' }));
    }
  }

  async function onReject(id: number) {
    if (cardState[id]) return;
    setCardState((s) => ({ ...s, [id]: 'rejected' }));
    setCardError((e) => {
      const next = { ...e };
      delete next[id];
      return next;
    });
    try {
      await archiveStudentExperience(id);
    } catch {
      setCardState((s) => {
        const next = { ...s };
        delete next[id];
        return next;
      });
      setCardError((e) => ({ ...e, [id]: '否掉失败，已撤销，请重试。' }));
    }
  }

  return (
    <>
      {/* 头部(对齐原型 SlotHead): 标题 + 关闭 */}
      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-warm)',
          background: 'var(--ivory)',
          display: 'flex',
          alignItems: 'center',
          gap: 11,
          flex: 'none',
        }}
      >
        <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex' }}>
          <UserIcon size={18} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>个人档案</div>
          <div style={{ font: '400 11.5px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>
            确认信息 + AI 推断待确认 · B 闭环
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          title="关掉 · 回到全宽对话"
          aria-label="关闭面板"
          style={{
            width: 28,
            height: 28,
            flex: 'none',
            borderRadius: 8,
            display: 'grid',
            placeItems: 'center',
            color: 'var(--stone)',
            cursor: 'pointer',
            background: 'transparent',
            border: 0,
            boxShadow: '0 0 0 1px var(--border-warm)',
          }}
        >
          <CloseIcon size={14} />
        </button>
      </div>

      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: 18,
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
        }}
      >
        {/* layer 1 — 确认信息(权威) */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 11 }}>
            <span className="hf-overline">确认信息</span>
            <span style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)' }}>
              · 你拍板的 · 喂推荐 + 骨架
            </span>
          </div>
          <div
            style={{
              background: 'var(--ivory)',
              borderRadius: 16,
              padding: '6px 16px',
              boxShadow: 'var(--sh-ring)',
            }}
          >
            {confirmedRows.map((row, i) => (
              <div
                key={row.k}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 12,
                  padding: '11px 0',
                  borderBottom: i < confirmedRows.length - 1 ? '1px solid var(--border-cream)' : 'none',
                }}
              >
                <span style={{ flex: 'none', width: 64, font: '500 12px var(--font-sans)', color: 'var(--stone)' }}>
                  {row.k}
                </span>
                <span style={{ font: '500 13.5px var(--font-sans)', color: 'var(--ink)', flex: 1, lineHeight: 1.5 }}>
                  {row.v}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* layer 2 — AI 推断待确认 */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 11 }}>
            <span className="hf-overline" style={{ color: 'var(--amber-fg)' }}>
              AI 推断 · 待确认
            </span>
            <span style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)' }}>
              · 从对话推断 · 确认后才喂画像
            </span>
          </div>

          {loading ? (
            <div style={{ font: '400 12.5px/1.6 var(--font-sans)', color: 'var(--stone)', padding: '4px 2px' }}>
              正在读你的档案…
            </div>
          ) : loadError ? (
            <div style={{ font: '500 12.5px var(--font-sans)', color: 'var(--terracotta-strong)', padding: '4px 2px' }}>
              {loadError}
            </div>
          ) : items.length === 0 ? (
            <div style={{ font: '400 12.5px/1.6 var(--font-sans)', color: 'var(--stone)', padding: '4px 2px' }}>
              暂无待确认的推断 —— 多聊几句目标和经历，AI 会在这里把推断攒出来给你拍板。
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {items.map((it) => (
                <InferredCard
                  key={it.id}
                  item={it}
                  state={cardState[it.id] ?? 'pending'}
                  error={cardError[it.id]}
                  onConfirm={() => onConfirm(it.id)}
                  onReject={() => onReject(it.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
