'use client';

import { useRouter } from 'next/navigation';

import { HFBtn, I } from './hifi-primitives';

export function DemoBanner() {
  const router = useRouter();
  return (
    <div
      className="hf"
      style={{
        background: 'var(--terracotta-wash)',
        borderBottom: '1px solid #eccfb6',
        padding: '10px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <span style={{ color: 'var(--terracotta)', display: 'inline-flex' }}>{I.sparkle(14)}</span>
      <span
        style={{
          fontSize: 13.5,
          color: 'var(--terracotta-strong)',
          flex: 1,
          minWidth: 220,
        }}
      >
        这是<strong>示例会话（只读）</strong>。要体验上传简历、生成推荐、改写、模拟面试的完整流程，请上传你自己的简历。
      </span>
      <HFBtn
        variant="primary"
        size="sm"
        iconRight={I.arrowRight(12)}
        onClick={() => router.push('/upload')}
      >
        上传我的简历
      </HFBtn>
    </div>
  );
}
