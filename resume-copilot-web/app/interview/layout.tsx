import type { ReactNode } from 'react';
import './interview-theme.css';

/**
 * Interview-only theme: scopes the terracotta design system + Google fonts to
 * `/interview/*` routes. Other parts of the app keep the default purple theme.
 */
export default function InterviewLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link
        href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;600;700&family=Noto+Serif+SC:wght@400;500;600;700&display=swap"
        rel="stylesheet"
      />
      <div data-theme="interview">{children}</div>
    </>
  );
}
