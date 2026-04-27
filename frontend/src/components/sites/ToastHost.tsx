import { createContext, useCallback, useContext, useState } from 'react';
import type { ReactNode } from 'react';

import Toast from './Toast';

interface ToastEntry {
  id: number;
  text: string;
  kind: 'success' | 'failed';
}

interface ToastApi {
  show: (text: string, kind: 'success' | 'failed') => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TOAST_TTL_MS = 4000;

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast() must be used inside <ToastHost>');
  }
  return ctx;
}

export function ToastHost({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);

  const show = useCallback<ToastApi['show']>((text, kind) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, text, kind }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((it) => it.id !== id));
    }, TOAST_TTL_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="sites-toast-host">
        {items.map((it) => (
          <Toast key={it.id} text={it.text} kind={it.kind} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
