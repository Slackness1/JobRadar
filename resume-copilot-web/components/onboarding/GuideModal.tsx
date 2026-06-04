'use client';

import type { ReactNode } from 'react';

import { I } from '@/components/hifi/hifi-primitives';

interface GuideModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function GuideModal({ open, onClose, children }: GuideModalProps) {
  if (!open) return null;
  return (
    <div className="hf og-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="og-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="og-close" aria-label="关闭" onClick={onClose}>
          {I.close(16)}
        </button>
        {children}
      </div>
    </div>
  );
}
