'use client';

/**
 * RecommendCardIntelSection — 推荐卡展开后挂载的同辈情报区.
 *
 * 行为:
 *   - Mount 时 fetch /api/intel/company-card?company=...&role=...
 *   - Loading: 显示一行 "📚 正在召唤同辈情报..." (LLM 总结一次 6-7s,缓存命中 4ms)
 *   - 数据为空 / 接口出错: 渲染 null,不打扰
 *   - 成功: 渲染 summary + 待遇 / 要求 / 面试真题 / 同辈原话 4 个 section
 *
 * 渲染只在 isVisible=true 时触发(父在 isExpanded 时传 true);
 * unmount 不会 abort 已发出的请求,但 setState 会跳过(用 mounted flag 守).
 */

import { useEffect, useState } from 'react';

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
}

export interface RecommendCardIntelSectionProps {
  company: string;
  /** 推荐 item 里没有 canonical role — 传 job_title 给后端 semantic 兜底。 */
  jobTitle?: string;
  isVisible: boolean;
}

export function RecommendCardIntelSection({
  company,
  jobTitle,
  isVisible,
}: RecommendCardIntelSectionProps) {
  // Props-derived request key — when (isVisible, company, jobTitle) changes
  // we reset state in render phase (React 19 "adjusting on prop change"
  // idiom) and the effect below dispatches the actual fetch.
  const requestKey = isVisible && company
    ? `${company}${jobTitle ?? ''}`
    : '';

  const [activeKey, setActiveKey] = useState<string>(requestKey);
  const [card, setCard] = useState<IntelCard | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(requestKey));
  const [failed, setFailed] = useState<boolean>(false);

  if (requestKey !== activeKey) {
    setActiveKey(requestKey);
    setCard(null);
    setLoading(Boolean(requestKey));
    setFailed(false);
  }

  useEffect(() => {
    if (!activeKey) return;
    const controller = new AbortController();
    const params = new URLSearchParams({ company });
    if (jobTitle) params.set('role', jobTitle);
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
  }, [activeKey, company, jobTitle]);

  if (!isVisible) return null;
  if (loading) {
    return (
      <div className="workspace-hifi__rec-intel workspace-hifi__rec-intel--loading">
        <span className="workspace-hifi__rec-intel-loading-dot" aria-hidden />
        <span>正在召唤同辈情报...</span>
      </div>
    );
  }
  if (failed || !card) return null;
  if (card._status === 'empty' || (card.n_insights_used ?? 0) === 0) return null;

  const comp = card.compensation || {};
  const req = card.requirements || {};
  const itv = card.interview || {};
  const voices = (card.voices || []).slice(0, 2);
  const hardReqs = (req.hard || []).slice(0, 4);
  const softReqs = (req.soft || []).slice(0, 3);
  const questions = (itv.key_questions || []).slice(0, 5);

  return (
    <section
      className="workspace-hifi__rec-intel"
      aria-label={`${card.company} 同辈情报`}
    >
      <header className="workspace-hifi__rec-intel-header">
        <span aria-hidden>📚</span>
        <span className="workspace-hifi__rec-intel-title">同辈情报</span>
        <span className="workspace-hifi__rec-intel-count">
          {card.n_insights_used} 条洞察
        </span>
      </header>

      {card.summary && (
        <p className="workspace-hifi__rec-intel-summary">{card.summary}</p>
      )}

      <div className="workspace-hifi__rec-intel-grid">
        {(comp.package || comp.details) && (
          <div className="workspace-hifi__rec-intel-cell">
            <div className="workspace-hifi__rec-intel-cell-label">💰 待遇</div>
            {comp.package && comp.package !== '未明确' && (
              <div className="workspace-hifi__rec-intel-cell-strong">{comp.package}</div>
            )}
            {comp.details && (
              <div className="workspace-hifi__rec-intel-cell-text">{comp.details}</div>
            )}
          </div>
        )}

        {(hardReqs.length > 0 || softReqs.length > 0) && (
          <div className="workspace-hifi__rec-intel-cell">
            <div className="workspace-hifi__rec-intel-cell-label">📋 要求</div>
            {hardReqs.length > 0 && (
              <ul className="workspace-hifi__rec-intel-chips">
                {hardReqs.map((r, i) => (
                  <li key={`hard-${i}`} className="workspace-hifi__rec-intel-chip">
                    {r}
                  </li>
                ))}
              </ul>
            )}
            {softReqs.length > 0 && (
              <div className="workspace-hifi__rec-intel-cell-text">
                软:{softReqs.join(' · ')}
              </div>
            )}
          </div>
        )}

        {questions.length > 0 && (
          <div className="workspace-hifi__rec-intel-cell workspace-hifi__rec-intel-cell--wide">
            <div className="workspace-hifi__rec-intel-cell-label">
              🎯 面试真题 / 高频考点
              {itv.rounds && (
                <span className="workspace-hifi__rec-intel-cell-meta">
                  · {itv.rounds}
                </span>
              )}
            </div>
            <ul className="workspace-hifi__rec-intel-bullets">
              {questions.map((q, i) => (
                <li key={`q-${i}`}>{q}</li>
              ))}
            </ul>
          </div>
        )}

        {voices.length > 0 && (
          <div className="workspace-hifi__rec-intel-cell workspace-hifi__rec-intel-cell--wide">
            <div className="workspace-hifi__rec-intel-cell-label">
              💬 同辈原话(逐字引用)
            </div>
            <div className="workspace-hifi__rec-intel-voices">
              {voices.map((v, i) => (
                <div key={`v-${i}`} className="workspace-hifi__rec-intel-voice">
                  <blockquote className="workspace-hifi__rec-intel-voice-quote">
                    {v.quote}
                  </blockquote>
                  <div className="workspace-hifi__rec-intel-voice-meta">
                    — @{v.author || '?'}
                    {typeof v.likes === 'number' && v.likes > 0 && (
                      <span> · ❤ {v.likes}</span>
                    )}
                    {v.url && (
                      <>
                        {' · '}
                        <a
                          href={v.url}
                          target="_blank"
                          rel="noreferrer"
                          className="workspace-hifi__rec-intel-voice-link"
                        >
                          原帖
                        </a>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
