import { shortDate } from '@/shared/lib/format';

import type { ThreadItem } from './conversation';

export type ThreadRow =
  | { kind: 'day'; key: string; label: string }
  | { kind: 'message'; key: string; item: ThreadItem; first: boolean };

const DAY_MS = 86_400_000;
// Days break at India midnight, the same zone every time on the page is shown in.
const dayKey = (date: Date) => date.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });

function dayLabel(date: Date, now: Date): string {
  const key = dayKey(date);
  if (key === dayKey(now)) return 'Today';
  if (key === dayKey(new Date(now.getTime() - DAY_MS))) return 'Yesterday';
  return shortDate(date.toISOString());
}

/** Day separators plus grouping: only the first bubble of a run from one sender gets a tail. */
export function buildRows(items: ThreadItem[], now: Date): ThreadRow[] {
  const rows: ThreadRow[] = [];
  let lastDay = '';
  let lastFrom = '';
  for (const item of items) {
    const day = dayKey(item.at);
    if (day !== lastDay) {
      rows.push({ kind: 'day', key: `d${day}`, label: dayLabel(item.at, now) });
      lastDay = day;
      lastFrom = '';
    }
    rows.push({ kind: 'message', key: item.key, item, first: item.from !== lastFrom });
    lastFrom = item.from;
  }
  return rows;
}

/** Bot messages that arrived after the last one the reader saw. */
export function unreadAfter(items: ThreadItem[], seenKey: string | null): number {
  const seen = items.findIndex((item) => item.key === seenKey);
  if (seen < 0) return 0;
  return items.slice(seen + 1).filter((item) => item.from === 'bot').length;
}
