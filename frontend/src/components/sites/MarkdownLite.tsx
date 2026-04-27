import { Fragment } from 'react';
import type { ReactNode } from 'react';

const INLINE_TOKEN = /(\*\*[^*]+\*\*|`[^`]+`)/g;

function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let cursor = 0;
  let key = 0;
  let match: RegExpExecArray | null;
  while ((match = INLINE_TOKEN.exec(text)) !== null) {
    if (match.index > cursor) {
      out.push(text.slice(cursor, match.index));
    }
    const [tok] = match;
    if (tok.startsWith('**')) {
      out.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    } else {
      out.push(
        <code key={key++} className="md-lite-code">
          {tok.slice(1, -1)}
        </code>,
      );
    }
    cursor = match.index + tok.length;
  }
  if (cursor < text.length) {
    out.push(text.slice(cursor));
  }
  return out;
}

interface MarkdownLiteProps {
  text: string;
}

export default function MarkdownLite({ text }: MarkdownLiteProps) {
  const paragraphs = text.split(/\n\s*\n/);
  return (
    <div className="md-lite">
      {paragraphs.map((para, i) => {
        const lines = para.split('\n').map((l) => l.replace(/\r$/, ''));
        const nonEmpty = lines.filter((l) => l.trim());
        const isList = nonEmpty.length >= 2 && nonEmpty.every((l) => /^\s*\d+\.\s/.test(l));
        if (isList) {
          return (
            <ol className="md-lite-list" key={i}>
              {nonEmpty.map((l, j) => (
                <li key={j}>{renderInline(l.replace(/^\s*\d+\.\s/, ''))}</li>
              ))}
            </ol>
          );
        }
        return (
          <p className="md-lite-p" key={i}>
            {lines.map((line, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {renderInline(line)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
