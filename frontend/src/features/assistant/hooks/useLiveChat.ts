import { useEffect, useRef } from 'react';

import { fetchAfter } from '../api/assistantApi';
import { fromHistory } from '../model/history';
import type { Conversation } from './useConversation';
import type { History } from './useHistory';

const POLL_MS = 5_000;

/**
 * Messages that reach the chat outside the person's own turn (a staff reply, a reminder, a bill read that finished
 * later) appear while the page is open, as they would on WhatsApp. Polls every few seconds while the tab is visible
 * and no turn is streaming. Messages this visit already shows are skipped by their stored id, so nothing doubles.
 */
export function useLiveChat(history: History, chat: Conversation) {
  // The newest saved id once history has loaded; 0 after New chat. A streaming turn brings its own messages.
  const ready = !history.loading && !history.error;
  const newestId = history.items.at(-1)?.serverId ?? 0;
  const { busy, items } = chat.state;
  const onNew = chat.append;
  const cursor = useRef<number | null>(null);
  const shown = useRef(new Set<number>());
  const deliver = useRef(onNew);

  useEffect(() => {
    if (ready) cursor.current = newestId;
  }, [ready, newestId]);

  useEffect(() => {
    shown.current = new Set(items.flatMap((item) => (item.serverId === undefined ? [] : [item.serverId])));
    deliver.current = onNew;
  }, [items, onNew]);

  useEffect(() => {
    if (!ready || busy) return undefined;
    const controller = new AbortController();
    let polling = false;

    const poll = async () => {
      const after = cursor.current;
      if (polling || after === null || document.visibilityState !== 'visible') return;
      polling = true;
      try {
        const page = await fetchAfter(after, controller.signal);
        const newest = page.items.at(-1)?.id;
        if (newest !== undefined) cursor.current = Math.max(cursor.current ?? 0, newest);
        const fresh = fromHistory(page.items.filter((item) => !shown.current.has(item.id)));
        if (fresh.length) deliver.current(fresh.map((item) => ({ ...item, live: true })));
      } catch {
        // A missed poll is caught up by the next one; the cursor has not moved.
      } finally {
        polling = false;
      }
    };

    const onVisible = () => void poll();
    void poll();
    const timer = window.setInterval(onVisible, POLL_MS);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [ready, busy]);
}
