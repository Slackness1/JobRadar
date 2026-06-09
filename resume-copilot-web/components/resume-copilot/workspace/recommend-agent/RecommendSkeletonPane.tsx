'use client';

/**
 * RecommendSkeletonPane — 「推荐工作台」左·主栏:梯队骨架 (Phase G 子项①).
 *
 * 复用子项② 已建好的梯队骨架组件 `PlatformTierGroup`(头部/腰部 tier + 公司卡 +
 * 嵌套在招岗),与 LeftRecommendRail 的骨架段同源 —— 不重建. 这里只负责:
 *   1. 按「确认赛道」拉骨架(getPlatformsByTier,不传 sub_cat → 后端自动取第一偏好;
 *      毫秒级缓存读,不走 LLM)
 *   2. loading / 空骨架(has_skeleton=false)占位
 *   3. highlightCompany 命中时给对应公司卡描边 + scrollIntoView(feed→骨架点联落点)
 *   4. reloadKey 变化时 refetch(子项④ 切换赛道后由 Shell 自增触发)
 *
 * react-compiler:所有 setState 都在 async 回调或事件内,render/effect-body 顶层纯净.
 * 设计系统:骨架卡沿用 `.workspace-hifi__*`(workspace-theme.css),故包一层
 * `.workspace-hifi` 容器接入;外层 wrapper 走 [data-theme="recommend"] scope.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  getPlatformsByTier,
  type PlatformSkeleton,
} from '../../api';
import { PlatformTierGroup } from '../recommend/PlatformTierGroup';

import '../workspace-theme.css';

const HIGHLIGHT_CLASS = 'recommend-skeleton__card--highlight';

export interface RecommendSkeletonPaneProps {
  sessionId: number;
  /** feed 卡点击时传入公司名 → 对应骨架卡高亮 + 滚动到视野 */
  highlightCompany?: string | null;
  /** Shell 自增此值触发 refetch(子项④ 切换赛道后用) */
  reloadKey?: number;
  /** 公司卡情报 CTA 回调(透传给 PlatformTierGroup) */
  onOpenIntel?: (company: string, ctx?: { n_insights?: number }) => void;
  /**
   * 公司卡「定制深挖」CTA 回调(透传给 PlatformTierGroup) —— 仅 Hub 梯队骨架视图传入.
   * 不传 → 按钮不渲染, /recommend 行为字节一致.
   */
  onOpenCoach?: (company: string) => void;
}

export function RecommendSkeletonPane({
  sessionId,
  highlightCompany,
  reloadKey,
  onOpenIntel,
  onOpenCoach,
}: RecommendSkeletonPaneProps) {
  // loading 由「已落地的请求 key」与「当前 key」比较派生,避免在 effect body
  // 顶层 setState(true) 触发 set-state-in-effect 告警.
  const requestKey = `${sessionId}:${reloadKey ?? 0}`;
  const [result, setResult] = useState<{
    key: string;
    data: PlatformSkeleton;
  } | null>(null);
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(
    () => new Set(),
  );
  const bodyRef = useRef<HTMLDivElement | null>(null);

  const loading = result === null || result.key !== requestKey;
  const skeleton = loading ? null : result.data;

  // 拉骨架 — sessionId / reloadKey 变化时重拉(不传 sub_cat,后端取第一偏好)
  useEffect(() => {
    let cancelled = false;
    getPlatformsByTier(sessionId)
      .then((r) => {
        if (!cancelled) setResult({ key: requestKey, data: r });
      })
      .catch(() => {
        if (!cancelled) {
          // 失败兜底成「无骨架」占位,绝不停在永久转圈
          setResult({
            key: requestKey,
            data: { sub_cat: '', has_skeleton: false, tiers: [] } as PlatformSkeleton,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, requestKey]);

  // 多卡展开/收起(Set,非互斥) — 对齐 LeftRecommendRail
  const handleCompanyToggle = useCallback((companyName: string) => {
    setExpandedCompanies((prev) => {
      const next = new Set(prev);
      if (next.has(companyName)) next.delete(companyName);
      else next.add(companyName);
      return next;
    });
  }, []);

  // feed→骨架点联:命中公司卡描边 + scrollIntoView.
  // PlatformTierGroup 不暴露 per-card ref,这里用容器内 DOM 查询(按公司名文本)
  // 在 effect 里做 class toggle —— 不在 render/effect-body 顶层 setState.
  useEffect(() => {
    const root = bodyRef.current;
    if (!root) return;
    // 先清掉上一轮高亮
    root
      .querySelectorAll(`.${HIGHLIGHT_CLASS}`)
      .forEach((el) => el.classList.remove(HIGHLIGHT_CLASS));
    if (!highlightCompany) return;
    const nameEls = root.querySelectorAll('.workspace-hifi__tier-company-name');
    for (const el of Array.from(nameEls)) {
      if (el.textContent?.trim() === highlightCompany) {
        const card = el.closest('.workspace-hifi__tier-company-card');
        if (card) {
          card.classList.add(HIGHLIGHT_CLASS);
          card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        break;
      }
    }
  }, [highlightCompany, skeleton, expandedCompanies]);

  const hasTiers =
    skeleton !== null && skeleton.has_skeleton && skeleton.tiers.length > 0;

  return (
    <div className="recommend-skeleton">
      <div className="recommend-skeleton__head">
        <div className="recommend-skeleton__head-title">梯队骨架</div>
        <div className="recommend-skeleton__head-sub">
          {skeleton?.sub_cat
            ? `${skeleton.sub_cat} · 按梯队展示平台格局`
            : '按你的确认赛道展示头部 / 腰部平台'}
        </div>
      </div>

      <div className="recommend-skeleton__body" ref={bodyRef}>
        {loading && (
          <div className="recommend-skeleton__state">
            <span className="recommend-skeleton__spin" aria-hidden />
            <div className="recommend-skeleton__state-sub">正在加载梯队骨架…</div>
          </div>
        )}

        {!loading && hasTiers && (
          <div className="workspace-hifi">
            {skeleton.tiers.map((tier, idx) => (
              <PlatformTierGroup
                key={tier.tier}
                tier={tier}
                expandedCompanies={expandedCompanies}
                onToggle={handleCompanyToggle}
                onOpenIntel={onOpenIntel}
                onOpenCoach={onOpenCoach}
                isFirst={idx === 0}
                isLast={idx === skeleton.tiers.length - 1}
              />
            ))}
          </div>
        )}

        {!loading && !hasTiers && (
          <div className="recommend-skeleton__state">
            <div className="recommend-skeleton__state-title">该赛道梯队整理中</div>
            <div className="recommend-skeleton__state-sub">
              暂未生成梯队骨架。换个确认赛道，或等数据补全后这里会自动展示头部 /
              腰部平台。
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
