import { useState } from 'react';

import { triggerSiteRecrawl } from '../../api';
import type { SiteRecrawlOut } from './types';

interface RecrawlButtonProps {
  company: string;
  inFlight: boolean;
  onSubmit: (company: string, result: SiteRecrawlOut | null) => void;
}

export default function RecrawlButton({ company, inFlight, onSubmit }: RecrawlButtonProps) {
  const [submitting, setSubmitting] = useState(false);
  const disabled = inFlight || submitting;

  const handleClick = async () => {
    setSubmitting(true);
    try {
      const res = await triggerSiteRecrawl(company);
      onSubmit(company, res.data);
    } catch {
      onSubmit(company, null);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <button
      type="button"
      className="hf-btn primary lg"
      style={{ width: '100%' }}
      disabled={disabled}
      onClick={handleClick}
    >
      {disabled ? (
        <>
          <span className="hf-spin" /> 重跑中…
        </>
      ) : (
        '立即重跑这个节点'
      )}
    </button>
  );
}
