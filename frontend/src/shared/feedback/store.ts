import { useSyncExternalStore } from 'react';

export type ToastSeverity = 'success' | 'info' | 'warning' | 'error';

export interface Toast {
  id: number;
  severity: ToastSeverity;
  title: string;
  message?: string | undefined;
  /** The server's request id for a failure, shown small. */
  reference?: string | null | undefined;
  action?: { label: string; run: () => void } | undefined;
}

// Errors stay until read; good news goes on its own.
const LIFETIME_MS: Record<ToastSeverity, number | null> = { success: 4_000, info: 6_000, warning: 10_000, error: null };
const MAX_SHOWN = 4;

let toasts: Toast[] = [];
let next = 1;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function dismiss(id: number): void {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

/** Show a message from anywhere, including outside React (the mutation cache). The same title and message shown
 * twice in a row is not stacked. */
export function notify(toast: Omit<Toast, 'id'>): number {
  const same = toasts.find((t) => t.title === toast.title && t.message === toast.message);
  if (same) return same.id;
  const id = next++;
  toasts = [...toasts, { ...toast, id }].slice(-MAX_SHOWN);
  emit();
  const life = LIFETIME_MS[toast.severity];
  if (life) setTimeout(() => dismiss(id), life);
  return id;
}

export function useToasts(): Toast[] {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => toasts);
}
