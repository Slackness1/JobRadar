'use client';

/**
 * RewriteOption — 单候选卡 (RewritePane 内, P1).
 *
 * 设计参考 `hifi-ws-intel.jsx::HFRewriteOption`.
 *
 * 决策 ①a: 当前 v0v2 endpoint 只返 2 个候选 (v0 echo + v2 thesis-aware),
 * 不强行加 v3 placeholder. 学生可点 "再来 2 版" ghost 按钮重新拉.
 */

import { I } from '@/components/hifi/hifi-primitives';
import { renderTextWithNumbers } from './renderTextWithNumbers';

export interface RewriteOptionData {
  /** 'v0' | 'v2' — 字面 label, 不是数字 idx. */
  versionId: 'v0' | 'v2';
  /** 候选副标签 — 来自 backend tag/rationale, 缺省时使用 fallback. */
  tag?: string;
  /** 改写文本 — render 时数字高亮. */
  text: string;
  /** "为什么" 解释行 — 来自 backend rationale 或 soft_hint, 11.5px. */
  why?: string;
}

export interface RewriteOptionProps {
  option: RewriteOptionData;
  selected: boolean;
  onSelect: (versionId: 'v0' | 'v2') => void;
  onRegenerate?: (versionId: 'v0' | 'v2') => void;
}

export function RewriteOption({
  option,
  selected,
  onSelect,
  onRegenerate,
}: RewriteOptionProps) {
  const len = option.text.length;
  return (
    <button
      type="button"
      onClick={() => onSelect(option.versionId)}
      className={`workspace-hifi__rewrite-option${selected ? ' is-selected' : ''}`}
      aria-pressed={selected}
    >
      <div className="workspace-hifi__rewrite-option-head">
        <span
          className={`hf-pill${selected ? ' terra' : ''} workspace-hifi__rewrite-option-pill`}
        >
          {option.versionId} {option.tag ? `· ${option.tag}` : ''}
        </span>
        {selected && (
          <span className="hf-pill emerald workspace-hifi__rewrite-option-selected-pill">
            <span style={{ display: 'inline-flex' }}>{I.check(11)}</span>
            已选
          </span>
        )}
        <span className="workspace-hifi__rewrite-option-len">{len} 字</span>
        {onRegenerate ? (
          <button
            type="button"
            className="workspace-hifi__rewrite-option-regen"
            onClick={(e) => {
              e.stopPropagation();
              onRegenerate(option.versionId);
            }}
            title="再改一版"
            aria-label={`重新生成 ${option.versionId}`}
          >
            ↺
          </button>
        ) : null}
      </div>
      <div className="workspace-hifi__rewrite-option-text">
        {renderTextWithNumbers(option.text)}
      </div>
      {option.why ? (
        <div className="workspace-hifi__rewrite-option-why">{option.why}</div>
      ) : null}
    </button>
  );
}
