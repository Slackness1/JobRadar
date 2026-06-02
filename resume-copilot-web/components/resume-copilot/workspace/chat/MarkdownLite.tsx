'use client';

/**
 * MarkdownLite — coach 聊天消息的轻量 markdown 渲染。
 *
 * 后端 coach 消息是 markdown（**加粗** / - 列表 / 1. 有序 / 段落），之前直接当
 * 纯文本渲染，`**` / `-` 都露出来了。这里做一个最小、安全的渲染器：
 *   - **加粗** → <strong>
 *   - `- ` / `* ` / `• ` 行 → 无序列表
 *   - `1. ` 行 → 有序列表
 *   - 其余非空行 → 段落（顺手剥掉行首 markdown 标题 #）
 * 纯 React 文本节点，不用 dangerouslySetInnerHTML —— 无 XSS 风险。覆盖不到的
 * 复杂构造（表格 / 链接 / 代码块）会优雅退化成接近原文，不报错。
 */

import React from 'react';

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // 按 **加粗** 切分；偶数段是普通文本，匹配段是加粗。
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.forEach((part, i) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) {
      nodes.push(<strong key={`${keyPrefix}-b${i}`}>{part.slice(2, -2)}</strong>);
    } else if (part) {
      nodes.push(<React.Fragment key={`${keyPrefix}-t${i}`}>{part}</React.Fragment>);
    }
  });
  return nodes;
}

export function MarkdownLite({ text }: { text: string }) {
  const lines = (text || '').split('\n');
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  let ordered: string[] = [];
  let key = 0;

  const flushBullets = () => {
    if (!bullets.length) return;
    const items = bullets;
    const k = key++;
    blocks.push(
      <ul className="workspace-hifi__md-list" key={`ul${k}`}>
        {items.map((it, i) => (
          <li key={i}>{renderInline(it, `ul${k}-${i}`)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };
  const flushOrdered = () => {
    if (!ordered.length) return;
    const items = ordered;
    const k = key++;
    blocks.push(
      <ol className="workspace-hifi__md-list" key={`ol${k}`}>
        {items.map((it, i) => (
          <li key={i}>{renderInline(it, `ol${k}-${i}`)}</li>
        ))}
      </ol>,
    );
    ordered = [];
  };
  const flushAll = () => {
    flushBullets();
    flushOrdered();
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const ul = line.match(/^\s*[-*•]\s+(.*)$/);
    if (ul) {
      flushOrdered();
      bullets.push(ul[1]);
      continue;
    }
    const ol = line.match(/^\s*\d+[.、)]\s+(.*)$/);
    if (ol) {
      flushBullets();
      ordered.push(ol[1]);
      continue;
    }
    flushAll();
    if (line.trim() === '') continue;
    const clean = line.replace(/^\s*#{1,6}\s+/, '');
    const k = key++;
    blocks.push(
      <p className="workspace-hifi__md-p" key={`p${k}`}>
        {renderInline(clean, `p${k}`)}
      </p>,
    );
  }
  flushAll();

  return <>{blocks}</>;
}
