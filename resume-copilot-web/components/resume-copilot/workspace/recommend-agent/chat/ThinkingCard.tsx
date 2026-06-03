'use client';

/**
 * ThinkingCard — border-beam「意图解析中 · flash」思考卡 (推荐工作台 NL 对话栏).
 *
 * 复用全局 `.border-beam`(app/globals.css)做 AI thinking 描边;放在
 * position:relative 父元素的最后一个 child 让它压在兄弟之上 paint.
 * cycling glyph spinner 走 setInterval — setState 在 interval 回调里,
 * 非 effect-body 顶层,react-compiler 安全.
 */

import { useEffect, useState } from 'react';

import { RecommendAvatar } from './RecommendAvatar';

const GLYPHS = ['·', '✢', '✳', '✶', '✻', '✽'];

function Spinner() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => {
      setI((x) => (x + 1) % GLYPHS.length);
    }, 120);
    return () => clearInterval(t);
  }, []);
  return <span className="recommend-chat__spinner">{GLYPHS[i]}</span>;
}

export function ThinkingCard() {
  return (
    <div className="recommend-chat__turn hf-slide">
      <RecommendAvatar />
      <div className="recommend-chat__thinking">
        <div className="border-beam" />
        <div className="recommend-chat__thinking-row">
          <Spinner />
          <span className="recommend-chat__thinking-label">意图解析中 · flash</span>
          <span className="recommend-chat__thinking-meta">1 次 LLM / 轮</span>
        </div>
      </div>
    </div>
  );
}
