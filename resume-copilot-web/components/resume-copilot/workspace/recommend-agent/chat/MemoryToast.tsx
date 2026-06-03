'use client';

/**
 * MemoryToast — L3 偏好记忆落库提示 pill (推荐工作台 NL 对话栏).
 * agent 把这轮表达的偏好后台落进统一记忆(L3 preference)时露一条 dashed pill.
 * 纯展示.
 */

export interface MemoryToastProps {
  text: string;
}

export function MemoryToast({ text }: MemoryToastProps) {
  return (
    <div className="recommend-chat__memory hf-slide">
      <span className="recommend-chat__memory-dot" />
      <span className="recommend-chat__memory-text">{text}</span>
    </div>
  );
}
