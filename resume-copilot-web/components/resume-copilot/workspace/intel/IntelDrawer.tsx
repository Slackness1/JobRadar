'use client';

/**
 * IntelDrawer — 420px 右栏抽屉,同辈情报王牌交互 (P0b, 2026-05-26).
 *
 * 展开时**严格替换** RightResumePane (决策 ②a) — WorkspaceShell 控制 swap.
 *
 * 数据源:
 *   GET /api/intel/company-card?company=<name>
 *   返回 { compensation, requirements, interview, voices, n_insights_used, summary, ... }
 *
 * 红线:
 *   - quote.text **逐字** 渲染 (knowledge pack verbatim);substring 已经在 BE 校验过.
 *   - empty / 失败 → 显 "📭 同辈情报暂未覆盖该公司".
 *   - CSS scope `.workspace-hifi__intel-drawer*` — 不污染 `.hf` / `/upload` / `/interview/*`.
 *
 * 4 tab:
 *   - 原话:hero + 小卡,底部"高频关键词" placeholder
 *   - 待遇:大字 package + details
 *   - 要求:pills + 命中绿条 (hardcode 4/5 — 真匹配 P2)
 *   - 面试题:Q1/Q2/... + "让我练 →" (P1 接 Coach)
 *
 * Onmock / 导出按钮:P0b 只占位 (console.log).
 */

import { useEffect, useState } from 'react';
import { I } from '@/components/hifi/hifi-primitives';
import { IntelTabs, type IntelTabDef, type IntelTabId } from './IntelTabs';
import { IntelQuote, type IntelQuoteData } from './IntelQuote';

// ─── backend response types (mirror RecommendCardIntelSection) ───────────────

interface CompensationField {
  package?: string | null;
  details?: string | null;
  notes?: string | null;
}

interface RequirementsField {
  hard?: string[];
  soft?: string[];
}

interface InterviewField {
  rounds?: string | null;
  format?: string | null;
  key_questions?: string[];
  difficulty?: string | null;
}

interface VoiceField {
  quote: string;
  author?: string;
  likes?: number;
  url?: string;
  speaker?: string;
}

interface IntelCard {
  company: string;
  role: string | null;
  n_insights_used: number;
  summary?: string | null;
  compensation?: CompensationField | null;
  requirements?: RequirementsField | null;
  interview?: InterviewField | null;
  voices?: VoiceField[];
  _status?: string;
  _from_cache?: boolean;
  // E5 置信度透明 (2026-05-30) — 后端 enrich() 计算并返
  confidence_tier?: 'verified' | 'high' | 'med' | 'low';
  confidence_label?: string;
  confidence_breakdown?: { verified?: number; high?: number; med?: number; low?: number };
  sources?: string[];
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function companyInitial(company: string): string {
  const trimmed = (company || '').trim();
  if (!trimmed) return '?';
  const first = trimmed[0];
  return /[A-Za-z0-9]/.test(first) ? first.toUpperCase() : first;
}

/** P0b — 简化:没有 priority 信息时统一用 'A' (terracotta);未来对接 platform.priority_letter. */
type Tone = 'A' | 'B' | 'C';

function toneFromPriority(p?: string | null): Tone {
  if (p === 'A' || p === 'B' || p === 'C') return p;
  return 'A';
}

function voicesToQuotes(voices: VoiceField[]): IntelQuoteData[] {
  return voices.map((v) => ({
    text: v.quote,
    author: v.author,
    hearts: typeof v.likes === 'number' ? v.likes : null,
    note_url: v.url || null,
  }));
}

// ─── props ───────────────────────────────────────────────────────────────────

export interface IntelDrawerProps {
  companyName: string;
  /** 公司 priority letter — PlatformCard 透传过来用来决定 logo tone (A/B/C). */
  priority?: string | null;
  /** xhs 洞察数 — 用于 header sub-line. 不传就 fallback 用 n_insights_used. */
  xhsCount?: number | null;
  /** 用户点关闭(右上角 ✕). */
  onClose: () => void;
  /** 用户点 "用这些做 Coach 定制" — P1 接 Coach mode;P0b 只 placeholder 日志. */
  onMock?: () => void;
}

export function IntelDrawer({
  companyName,
  priority,
  xhsCount,
  onClose,
  onMock,
}: IntelDrawerProps) {
  // "Adjust state when props change" idiom (React 19) — when companyName
  // changes, snap card/loading/failed back to initial without an effect.
  // The effect below only fires the network request.
  const [activeCompany, setActiveCompany] = useState<string>(companyName);
  const [tab, setTab] = useState<IntelTabId>('quotes');
  const [card, setCard] = useState<IntelCard | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [failed, setFailed] = useState<boolean>(false);

  if (companyName !== activeCompany) {
    setActiveCompany(companyName);
    setCard(null);
    setLoading(Boolean(companyName));
    setFailed(false);
    setTab('quotes');
  }

  // Fire fetch when activeCompany changes (real "external sync" — effect ok).
  useEffect(() => {
    if (!activeCompany) return;
    const controller = new AbortController();
    const params = new URLSearchParams({ company: activeCompany });
    fetch(`/api/intel/company-card?${params.toString()}`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<IntelCard>;
      })
      .then((d) => {
        setCard(d);
        setLoading(false);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        void e;
        setFailed(true);
        setLoading(false);
      });
    return () => controller.abort();
  }, [activeCompany]);

  const tone = toneFromPriority(priority);
  const initial = companyInitial(companyName);

  // ── Derived data (safe defaults if loading / empty) ─────────────────────────
  const comp = card?.compensation || {};
  const req = card?.requirements || {};
  const itv = card?.interview || {};
  const voices = card?.voices || [];
  const quotes = voicesToQuotes(voices);
  const hardReqs = req.hard || [];
  const softReqs = req.soft || [];
  const allRequirements = [...hardReqs, ...softReqs];
  const questions = itv.key_questions || [];

  const displayXhsCount =
    typeof xhsCount === 'number' && xhsCount > 0
      ? xhsCount
      : card?.n_insights_used || 0;

  // empty fallback check (matches RecommendCardIntelSection logic)
  const hasUsefulData =
    !!card &&
    (quotes.length > 0 ||
      questions.length > 0 ||
      hardReqs.length > 0 ||
      softReqs.length > 0 ||
      (comp.package && comp.package !== '未明确') ||
      Boolean(comp.details));

  const isEmpty =
    !loading &&
    (failed ||
      !card ||
      card._status === 'empty' ||
      (card.n_insights_used ?? 0) === 0 ||
      !hasUsefulData);

  const tabs: IntelTabDef[] = [
    { id: 'quotes', icon: I.quote(13), label: '原话', count: quotes.length },
    { id: 'comp', icon: I.yen(13), label: '待遇', count: null },
    { id: 'req', icon: I.clipboard(13), label: '要求', count: allRequirements.length },
    { id: 'qa', icon: I.target(13), label: '面试题', count: questions.length },
  ];

  // package split into "big" line + sub bullets (compensation.details).
  // Hifi design used `split('·')` on a single string; backend gives us a 2-field
  // shape — keep big = package, sub lines = details (split on `·` then `\n`).
  const compBig = (comp.package || '').trim() || '未明确';
  const compSubs: string[] = [];
  if (comp.details) {
    const raw = String(comp.details).trim();
    // Split on common separators so each line ends up as one `·` row.
    raw.split(/[·\n]+/).map((s) => s.trim()).filter(Boolean).forEach((s) => {
      compSubs.push(s);
    });
  }
  if (comp.notes) {
    String(comp.notes)
      .split(/[·\n]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((s) => compSubs.push(s));
  }

  return (
    <aside
      className="workspace-hifi__intel-drawer"
      aria-label={`${companyName} 同辈情报`}
    >
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="workspace-hifi__intel-drawer-header">
        <div
          className="workspace-hifi__intel-drawer-logo"
          data-tone={tone}
          aria-hidden
        >
          {initial}
        </div>
        <div className="workspace-hifi__intel-drawer-title-wrap">
          <div className="workspace-hifi__intel-drawer-title">
            <span className="workspace-hifi__intel-drawer-company">{companyName}</span>
            <span className="workspace-hifi__intel-drawer-suffix">· 同辈情报</span>
          </div>
          <div className="workspace-hifi__intel-drawer-subtitle">
            {loading ? '正在召唤同辈情报…' :
              displayXhsCount > 0
                ? `${displayXhsCount} 条洞察 · 来源 ${(card?.sources || []).join('+') || '小红书'}`
                : '暂无同辈洞察'}
          </div>
          {card?.confidence_tier ? (
            <div
              className={`workspace-hifi__intel-conf-badge workspace-hifi__intel-conf-badge--${card.confidence_tier}`}
              title={
                card.confidence_breakdown
                  ? `verified ${card.confidence_breakdown.verified ?? 0} · high ${card.confidence_breakdown.high ?? 0} · med ${card.confidence_breakdown.med ?? 0} · low ${card.confidence_breakdown.low ?? 0}`
                  : undefined
              }
            >
              {card.confidence_tier === 'verified' ? '✓ ' : ''}{card.confidence_label}
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className="workspace-hifi__intel-drawer-close"
          aria-label="关闭情报抽屉"
          onClick={onClose}
        >
          {I.close(16)}
        </button>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <IntelTabs active={tab} onChange={setTab} tabs={tabs} />

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      <div className="workspace-hifi__intel-drawer-body">
        {loading && (
          <div className="workspace-hifi__intel-loading">
            <span className="workspace-hifi__intel-loading-dot" aria-hidden />
            <span>正在召唤同辈情报…</span>
          </div>
        )}

        {!loading && isEmpty && (
          <div className="workspace-hifi__intel-empty">
            <span aria-hidden>📭</span>
            <span>同辈情报暂未覆盖该公司</span>
          </div>
        )}

        {!loading && !isEmpty && tab === 'quotes' && (
          <div className="workspace-hifi__intel-section">
            <div className="workspace-hifi__intel-guard">
              <b>守卫:</b> 每段引用都 substring 校验过原帖,LLM 不能改一个字。
            </div>
            {quotes.length === 0 && (
              <div className="workspace-hifi__intel-empty">
                <span aria-hidden>📭</span>
                <span>暂无逐字原话</span>
              </div>
            )}
            {quotes.map((q, i) => (
              <IntelQuote key={`q-${i}`} q={q} hero={i === 0} />
            ))}
            <div className="workspace-hifi__intel-keywords">
              <div className="hf-overline workspace-hifi__intel-keywords-title">
                高频关键词 · 从原话提炼
              </div>
              <div className="workspace-hifi__intel-keywords-row">
                {/* P0b: hardcode 5 placeholder — TODO P1 接 LLM keyword extraction */}
                {['投行四百问', '流水抽凭', '递延所得税', 'DCF 假设', '疯狂质疑假设'].map((t) => (
                  <span key={t} className="hf-pill workspace-hifi__intel-keyword-pill">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {!loading && !isEmpty && tab === 'comp' && (
          <div className="workspace-hifi__intel-section">
            <div className="workspace-hifi__intel-section-title">
              待遇{card?.n_insights_used ? ` (${card.n_insights_used} 条 insight)` : ''}
            </div>
            <div className="workspace-hifi__intel-comp-card">
              <div className="workspace-hifi__intel-comp-big">{compBig}</div>
              {compSubs.map((s, i) => (
                <div key={`csub-${i}`} className="workspace-hifi__intel-comp-sub">
                  · {s}
                </div>
              ))}
            </div>
            <div className="workspace-hifi__intel-comp-footnote">
              数字来自小红书 insight 的明确段位 — 否则会显示「未明确」。
            </div>
          </div>
        )}

        {!loading && !isEmpty && tab === 'req' && (
          <div className="workspace-hifi__intel-section">
            <div className="workspace-hifi__intel-section-title">
              硬条件 + 软条件
            </div>
            {allRequirements.length > 0 ? (
              <div className="workspace-hifi__intel-req-pills">
                {allRequirements.map((r, i) => (
                  <span
                    key={`req-${i}`}
                    className="workspace-hifi__intel-req-pill"
                  >
                    {r}
                  </span>
                ))}
              </div>
            ) : (
              <div className="workspace-hifi__intel-empty workspace-hifi__intel-empty--inline">
                <span aria-hidden>📭</span>
                <span>暂无要求洞察</span>
              </div>
            )}
            <div className="workspace-hifi__intel-req-match">
              <b>✓ 你已满足</b> 985 / GPA 3.6+ / 抗压 / 主动 — 4/5 命中
            </div>
          </div>
        )}

        {!loading && !isEmpty && tab === 'qa' && (
          <div className="workspace-hifi__intel-section">
            <div className="workspace-hifi__intel-section-title">
              {itv.rounds ? `${itv.rounds} · ` : ''}
              共 {questions.length} 道
            </div>
            {questions.length === 0 ? (
              <div className="workspace-hifi__intel-empty workspace-hifi__intel-empty--inline">
                <span aria-hidden>📭</span>
                <span>暂无面试真题</span>
              </div>
            ) : (
              questions.map((q, i) => (
                <div key={`q-${i}`} className="workspace-hifi__intel-qa-row">
                  <span className="workspace-hifi__intel-qa-num">Q{i + 1}</span>
                  <span className="workspace-hifi__intel-qa-text">{q}</span>
                  <button
                    type="button"
                    className="workspace-hifi__intel-qa-practice"
                    onClick={() => {
                      // P0b placeholder — P1 wire to Coach plan-mode.
                      console.log('[IntelDrawer] practice question:', q);
                    }}
                  >
                    让我练 →
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <div className="workspace-hifi__intel-drawer-footer">
        <button
          type="button"
          className="hf-btn primary workspace-hifi__intel-footer-primary"
          onClick={() => {
            if (onMock) {
              onMock();
            } else {
              console.log('[IntelDrawer] mock CTA — P1 wire to Coach');
            }
          }}
        >
          <span style={{ display: 'inline-flex' }}>{I.target(14)}</span>
          <span>用这些做 Coach 定制</span>
        </button>
        <button
          type="button"
          className="hf-btn ghost workspace-hifi__intel-footer-export"
          title="导出"
          onClick={() => {
            // P0b placeholder — P1 wire to export.
            console.log('[IntelDrawer] export — P1');
          }}
        >
          <span style={{ display: 'inline-flex' }}>{I.download(14)}</span>
        </button>
      </div>
    </aside>
  );
}
