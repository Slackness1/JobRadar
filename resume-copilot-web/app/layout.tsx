import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';

import './globals.css';
import '@/components/resume-copilot/entry-login.css';

export const metadata: Metadata = {
  title: 'Resume Copilot | JobRadar',
  description: 'Upload a resume, confirm a structured profile, and get role recommendations from JobRadar.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className={`${GeistSans.variable} ${GeistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
