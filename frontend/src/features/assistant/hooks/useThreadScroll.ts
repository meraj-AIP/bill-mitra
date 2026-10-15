import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

import type { ThreadItem } from '../model/conversation';
import { unreadAfter } from '../model/thread';

const NEAR_BOTTOM_PX = 96;

/**
 * Keeps the thread pinned to the newest message while the reader is at the bottom,
 * holds their place when earlier messages are added above, and counts what they have not seen.
 */
export function useThreadScroll(items: ThreadItem[]) {
  const box = useRef<HTMLDivElement | null>(null);
  const content = useRef<HTMLDivElement | null>(null);
  const stick = useRef(true);
  const anchor = useRef<{ height: number; top: number } | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [seenKey, setSeenKey] = useState<string | null>(null);

  const firstKey = items[0]?.key;
  const last = items.at(-1);
  const lastKey = last?.key ?? null;
  const lastFromUser = last?.from === 'user';

  // Content grows for many reasons (a new reply, an image finishing loading, the typing dots); follow it all.
  useEffect(() => {
    const el = box.current;
    const inner = content.current;
    if (!el || !inner) return undefined;
    const observer = new ResizeObserver(() => {
      if (stick.current) el.scrollTop = el.scrollHeight;
    });
    observer.observe(inner);
    return () => observer.disconnect();
  }, []);

  useLayoutEffect(() => {
    const el = box.current;
    const saved = anchor.current;
    if (!el || !saved) return;
    el.scrollTop = el.scrollHeight - saved.height + saved.top;
    anchor.current = null;
  }, [firstKey]);

  // Sending something always brings the reader back down, like any messenger.
  useEffect(() => {
    const el = box.current;
    if (!el || !lastFromUser) return;
    stick.current = true;
    el.scrollTop = el.scrollHeight;
  }, [lastKey, lastFromUser]);

  const onScroll = () => {
    const el = box.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    stick.current = near;
    setAtBottom(near);
    if (near) setSeenKey(lastKey);
  };

  const jumpToLatest = useCallback(() => {
    const el = box.current;
    if (!el) return;
    stick.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, []);

  /** Call just before fetching earlier messages so the view does not jump when they land. */
  const holdPosition = useCallback(() => {
    const el = box.current;
    if (el) anchor.current = { height: el.scrollHeight, top: el.scrollTop };
  }, []);

  return {
    box,
    content,
    onScroll,
    atBottom,
    unread: atBottom ? 0 : unreadAfter(items, seenKey),
    jumpToLatest,
    holdPosition,
  };
}
