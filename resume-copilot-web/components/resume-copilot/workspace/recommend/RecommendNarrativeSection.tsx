'use client';

/**
 * RecommendNarrativeSection — 推荐卡展开后 LLM 个性化叙事区 (Phase 7).
 *
 * 行为:
 *   - Mount + isVisible=true 时 fetch /api/.../recommendations/{job_id}/narrative
 *   - Loading: "正在为你写匹配理由…" 灯泡占位
 *   - 数据为空(status=empty / 无 XHS 命中且简历空白): 短 fallback 不打扰
 *   - 成功: 渲染 narrative + action_tip,带 ✦ icon 强调「定制」
 *
 * 跟 RecommendCardIntelSection 同款 SWR-by-prop-change pattern (React 19 idiom)。
 */

import { useEffect, useState } from 'react';
import { getResumeCopilotNarrative, type RecommendNarrativeOut } from '../../api';

export interface RecommendNarrativeSectionProps {
  sessionId: number;
  jobId: string;
  isVisible: boolean;
}

export function RecommendNarrativeSection({
  sessionId,
  jobId,
  isVisible,
}: RecommendNarrativeSectionProps) {
  const requestKey = isVisible && sessionId && jobId
    ? `${sessionId}::${jobId}`
    : '';

  const [activeKey, setActiveKey] = useState<string>(requestKey);
  const [data, setData] = useState<RecommendNarrativeOut | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(requestKey));
  const [failed, setFailed] = useState<boolean>(false);

  if (requestKey !== activeKey) {
    setActiveKey(requestKey);
    setData(null);
    setLoading(Boolean(requestKey));
    setFailed(false);
  }

  useEffect(() => {
    if (!activeKey) return;
    let cancelled = false;
    getResumeCopilotNarrative(sessionId, jobId)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeKey, sessionId, jobId]);

  if (!isVisible) return null;
  if (loading) {
    return (
      <div className="workspace-hifi__narrative workspace-hifi__narrative--loading">
        <span className="workspace-hifi__narrative-spark" aria-hidden>✦</span>
        <span>正在为你写匹配理由…</span>
      </div>
    );
  }
  if (failed || !data || !data.narrative) return null;

  return (
    <section className="workspace-hifi__narrative" aria-label="个性化匹配理由">
      <header className="workspace-hifi__narrative-header">
        <span aria-hidden>✦</span>
        <span className="workspace-hifi__narrative-title">为你定制</span>
        {data.evidence_refs.length > 0 && (
          <span className="workspace-hifi__narrative-evidence-count">
            ⓘ {data.evidence_refs.length} 条同辈情报支撑
          </span>
        )}
      </header>
      <p className="workspace-hifi__narrative-body">{data.narrative}</p>
      {data.action_tip && (
        <p className="workspace-hifi__narrative-tip">
          <span aria-hidden className="workspace-hifi__narrative-tip-icon">🎯</span>
          {data.action_tip}
        </p>
      )}
    </section>
  );
}
