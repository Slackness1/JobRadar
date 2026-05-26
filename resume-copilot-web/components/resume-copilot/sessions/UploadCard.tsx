'use client';

/**
 * UploadCard — dashed-border "upload new" card that lives at the end of the
 * Sessions page grid. Click → router.push('/upload').
 */

import { I } from '@/components/hifi/hifi-primitives';

interface UploadCardProps {
  onUpload: () => void;
}

export function UploadCard({ onUpload }: UploadCardProps) {
  return (
    <button
      type="button"
      onClick={onUpload}
      className="rc-sessions__upload-card"
      data-testid="rc-session-upload-card"
    >
      <span className="rc-sessions__upload-icon" aria-hidden>
        {I.upload(26)}
      </span>
      <div>
        <div className="hf-h3 rc-sessions__upload-title">上传新简历</div>
        <div className="rc-sessions__upload-blurb">
          换一份简历 (或同一份的不同方向),开始一个新会话
        </div>
      </div>
      <div className="rc-sessions__upload-tags">
        <span className="rc-sessions__upload-tag">PDF</span>
        <span className="rc-sessions__upload-tag">DOCX</span>
        <span className="rc-sessions__upload-tag">≤ 10 MB</span>
      </div>
    </button>
  );
}
