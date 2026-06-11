'use client';

import { useState } from 'react';

import { HFBtn } from '@/components/hifi/hifi-primitives';
import {
  GUIDE_CTA_LABEL,
  GUIDE_DISMISS_LABEL,
  GUIDE_STEPS,
  GUIDE_SUBTITLE,
  GUIDE_TITLE,
} from './guide-content';
import './onboarding-guide.css';

interface GuidePanelProps {
  onStart: () => void;
  onDismiss: () => void;
}

export function GuidePanel({ onStart, onDismiss }: GuidePanelProps) {
  const [openStep, setOpenStep] = useState<number | null>(null);
  return (
    <div className="og-panel">
      <h2 className="og-title">{GUIDE_TITLE}</h2>
      <p className="og-sub">{GUIDE_SUBTITLE}</p>
      <div className="og-steps">
        {GUIDE_STEPS.map((step) => (
          <div
            key={step.no}
            className="og-step"
            onMouseEnter={() => setOpenStep(step.no)}
            onMouseLeave={() => setOpenStep((s) => (s === step.no ? null : s))}
            onClick={() => setOpenStep((s) => (s === step.no ? null : step.no))}
          >
            <span className="og-step__icon">{step.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="og-step__no">STEP {step.no}</div>
              <div className="og-step__title">{step.title}</div>
              <div className="og-step__what">{step.what}</div>
              <div className="og-step__value">{step.value}</div>
              {openStep === step.no ? <div className="og-step__detail">{step.detail}</div> : null}
            </div>
          </div>
        ))}
      </div>
      <div className="og-foot">
        <HFBtn variant="primary" size="lg" onClick={onStart}>
          {GUIDE_CTA_LABEL}
        </HFBtn>
        <button type="button" className="og-dismiss" onClick={onDismiss}>
          {GUIDE_DISMISS_LABEL}
        </button>
      </div>
    </div>
  );
}
