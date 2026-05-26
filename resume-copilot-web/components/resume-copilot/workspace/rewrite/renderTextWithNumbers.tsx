'use client';

/**
 * renderTextWithNumbers — 数字高亮 helper (RewritePane v0/v2 候选卡).
 *
 * 把字串切成 (数字 | 非数字) 段, 数字段包 <mark class="workspace-hifi__rc-numeric">.
 *
 * Regex 匹配:
 *   - <整数><quantifier>     例: "6 只" "8 篇" "12 个" "3 年"
 *   - 分数 n/m               例: "2/8"
 *   - 小数 n.m               例: "3.6"
 *   - 纯数字 n               例: "120"
 *
 * 设计参考: hifi-ws-intel.jsx HFRewriteOption.renderText.
 */

import type { ReactNode } from 'react';

const NUMBER_PATTERN =
  /(\d+\s*[只篇个家月年%]|\d+\/\d+|\d+\.\d+|\d+)/g;

export function renderTextWithNumbers(text: string): ReactNode {
  if (!text) return null;
  const parts = text.split(NUMBER_PATTERN);
  return parts.map((p, i) =>
    /\d/.test(p) ? (
      <mark key={i} className="workspace-hifi__rc-numeric">
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}
