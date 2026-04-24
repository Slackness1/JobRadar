import * as React from 'react';

import { cn } from '@/lib/utils';

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      'min-h-28 w-full resize-y rounded-xl border border-[var(--border)] bg-white px-4 py-3 text-[15px] leading-7 text-[var(--ink)] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-ring)] disabled:cursor-not-allowed disabled:bg-[var(--soft)] disabled:opacity-70',
      className,
    )}
    ref={ref}
    {...props}
  />
));
Textarea.displayName = 'Textarea';

export { Textarea };
