import type { AlertItem, AlertKind } from '../api/types';

const KIND: Record<AlertKind, string> = {
  misread_found: 'Misread found',
  case_overdue: 'Overdue',
  case_escalated: 'Escalated',
  digest: 'Daily summary',
  applied_auto: 'Revision applied',
  pattern_section: 'Pattern in a section',
  request_reminded: 'Consumer reminded',
  request_lapsed: 'Request closed',
};

export function kindLabel(kind: AlertItem['kind']): string {
  return KIND[kind as AlertKind] ?? 'Alert';
}

/** Where opening an alert goes: its case when it has one. */
export const alertHref = (a: Pick<AlertItem, 'ticket'>): string | null => (a.ticket ? `/review/${encodeURIComponent(a.ticket)}` : null);

/** "9+" keeps the badge narrow. */
export const badgeText = (count: number): string => (count > 9 ? '9+' : String(count));
