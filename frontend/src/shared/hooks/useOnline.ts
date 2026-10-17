import { onlineManager } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';

/** The same online state React Query uses to pause and resume requests, so the banner and the queue agree. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    (notify) => onlineManager.subscribe(notify),
    () => onlineManager.isOnline(),
    () => true,
  );
}
