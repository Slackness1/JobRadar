'use client';

/**
 * IntelQuote — 同辈情报"原话"卡片. Hero + 小卡 两种形态.
 *
 * 红线: knowledge pack verbatim — quote.text **逐字渲染**,不 truncate / 不二次包装 /
 *      不让 LLM 改写。原帖链接(note_url)如果后端有就显示;没有就省略。
 *
 * P0b — see IntelDrawer.tsx (退役了 RecommendCardIntelSection).
 */

export interface IntelQuoteData {
  text: string;
  author?: string | null;
  hearts?: number | null;
  note_url?: string | null;
}

export interface IntelQuoteProps {
  q: IntelQuoteData;
  hero?: boolean;
}

export function IntelQuote({ q, hero = false }: IntelQuoteProps) {
  const author = (q.author || '').trim() || '?';
  const showHearts = typeof q.hearts === 'number' && q.hearts > 0;
  return (
    <div
      className={`workspace-hifi__intel-quote${hero ? ' is-hero' : ''}`}
    >
      {hero && (
        <span className="workspace-hifi__intel-quote-badge" aria-hidden>
          VERBATIM
        </span>
      )}
      <div className="workspace-hifi__intel-quote-text">
        &ldquo;{q.text}&rdquo;
      </div>
      <div className="workspace-hifi__intel-quote-meta">
        <span>@{author}</span>
        {showHearts && (
          <>
            <span className="workspace-hifi__intel-quote-sep">·</span>
            <span className="workspace-hifi__intel-quote-hearts">
              <span aria-hidden>❤</span> {q.hearts}
            </span>
          </>
        )}
        {q.note_url && (
          <>
            <span className="workspace-hifi__intel-quote-sep">·</span>
            <a
              className="workspace-hifi__intel-quote-link"
              href={q.note_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              原帖 ↗
            </a>
          </>
        )}
      </div>
    </div>
  );
}
