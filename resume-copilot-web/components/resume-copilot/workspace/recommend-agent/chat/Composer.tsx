'use client';

/**
 * Composer — 输入框 + 快捷 chip (推荐工作台 NL 对话栏).
 *
 * chip 点击 = 直接把该文案当一条消息发出. 输入框 Enter / 发送按钮提交.
 * disabled(thinking 中)时锁住,避免连发. 仅 val 一个本地 state,
 * setState 全在事件回调里,react-compiler 安全.
 */

import { useState } from 'react';

export interface ComposerChip {
  key: string;
  label: string;
}

export interface ComposerProps {
  chips: ComposerChip[];
  placeholder: string;
  disabled?: boolean;
  onSend: (text: string) => void;
}

export function Composer({ chips, placeholder, disabled, onSend }: ComposerProps) {
  const [val, setVal] = useState('');

  const send = () => {
    const v = val.trim();
    if (!v || disabled) return;
    onSend(v);
    setVal('');
  };

  return (
    <div className="recommend-chat__composer">
      {chips.length > 0 && (
        <div className="recommend-chat__chips">
          {chips.map((c) => (
            <button
              key={c.key}
              type="button"
              className="recommend-chat__chip hf-pill"
              disabled={disabled}
              onClick={() => {
                if (disabled) return;
                onSend(c.label);
              }}
            >
              {c.label}
            </button>
          ))}
        </div>
      )}
      <div className="recommend-chat__input-row">
        <input
          className="recommend-chat__input"
          value={val}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send();
          }}
        />
        <button
          type="button"
          className="recommend-chat__send hf-btn primary"
          title="发送"
          disabled={disabled}
          onClick={send}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>
    </div>
  );
}
