import * as React from 'react';

import { cn } from '@/lib/utils';

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => (
  <input
    type={type}
    className={cn(
      'h-11 w-full rounded-xl border border-[var(--border)] bg-white px-4 text-[15px] text-[var(--ink)] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-ring)] disabled:cursor-not-allowed disabled:bg-[var(--soft)] disabled:opacity-70',
      className,
    )}
    ref={ref}
    {...props}
  />
));
Input.displayName = 'Input';

export { Input };
