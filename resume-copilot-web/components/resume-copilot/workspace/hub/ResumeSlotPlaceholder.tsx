'use client';

/**
 * ResumeSlotPlaceholder — 简历优化画布槽占位视图.
 *
 * 产品决策: 简历优化模块（打分报告 / 深度优化 / 写回预览）归属 resume-copilot 分支,
 * 由平行开发线负责. 本期 Hub 外壳只留接口位 —— 入口路径与其它模块完全一致
 * (arm → fire → 思考卡 → 结果卡 → 「查看打分报告」→ openView('resume') → 此占位),
 * 日后 resume-copilot 分支把真实视图塞进这个槽，外壳不动.
 *
 * 样式: 单色 `.hf` token，虚线图标块 + 两行说明 + 状态 pill。
 */

export default function ResumeSlotPlaceholder() {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 18,
        padding: '32px 28px',
        textAlign: 'center',
      }}
    >
      {/* 虚线文件图标块 */}
      <span
        style={{
          width: 60,
          height: 60,
          borderRadius: 16,
          display: 'grid',
          placeItems: 'center',
          color: 'var(--warm-silver)',
          boxShadow: '0 0 0 1.5px var(--border-strong)',
          borderStyle: 'dashed',
        }}
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      </span>

      {/* 说明文字 */}
      <div>
        <div
          style={{
            font: '600 14px var(--font-sans)',
            color: 'var(--olive)',
            marginBottom: 8,
          }}
        >
          简历优化在 resume-copilot 分支
        </div>
        <div
          style={{
            font: '400 12px/1.65 var(--font-sans)',
            color: 'var(--stone)',
            maxWidth: 272,
          }}
        >
          日后它的视图（打分 / 深度优化）直接塞进同一个槽，不动外壳。
        </div>
      </div>

      {/* 状态 pill */}
      <span
        className="hf-pill amber"
        style={{ height: 28, fontSize: 12 }}
      >
        等 HiFi · 可见不可用
      </span>
    </div>
  );
}
