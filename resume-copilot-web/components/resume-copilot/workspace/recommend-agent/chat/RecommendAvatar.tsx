'use client';

/**
 * RecommendAvatar — agent 头像圆点 (推荐工作台 NL 对话栏).
 * terracotta 实心圆 + sparkle glyph. 纯展示.
 */

export interface RecommendAvatarProps {
  size?: number;
}

export function RecommendAvatar({ size = 28 }: RecommendAvatarProps) {
  return (
    <div
      className="recommend-chat__avatar"
      style={{ width: size, height: size }}
    >
      <svg
        width={size * 0.52}
        height={size * 0.52}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
        <circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}
