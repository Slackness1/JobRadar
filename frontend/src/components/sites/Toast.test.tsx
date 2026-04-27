import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastHost, useToast } from './ToastHost';

function HarnessButton({ label, kind }: { label: string; kind: 'success' | 'failed' }) {
  const toast = useToast();
  return <button onClick={() => toast.show(label, kind)}>fire</button>;
}

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a toast when show() is called', () => {
    render(
      <ToastHost>
        <HarnessButton label="Hello" kind="success" />
      </ToastHost>,
    );
    act(() => {
      screen.getByText('fire').click();
    });
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('auto-dismisses after 4 seconds', () => {
    render(
      <ToastHost>
        <HarnessButton label="Hello" kind="success" />
      </ToastHost>,
    );
    act(() => {
      screen.getByText('fire').click();
    });
    expect(screen.getByText('Hello')).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText('Hello')).not.toBeInTheDocument();
  });

  it('applies failed class for failed kind', () => {
    render(
      <ToastHost>
        <HarnessButton label="Boom" kind="failed" />
      </ToastHost>,
    );
    act(() => {
      screen.getByText('fire').click();
    });
    const toast = screen.getByText('Boom').closest('.sites-toast');
    expect(toast).not.toBeNull();
    expect(toast!.classList.contains('failed')).toBe(true);
  });
});
