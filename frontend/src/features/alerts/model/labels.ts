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
  complaint_assigned: 'Handed to you',
  consumer_replied: 'Consumer replied',
  case_assigned: 'Case for you',
  decision_returned: 'Decision sent back',
};


export function kindLabel(kind: AlertItem['kind']): string {
  return KIND[kind as AlertKind] ?? 'Alert';
}

/** Where opening an alert goes, as the server says. Only a path inside this app is followed. */
export function alertHref(a: Pick<AlertItem, 'href'>): string | null {
  const href = a.href ?? null;
  return href && href.startsWith('/') && !href.startsWith('//') ? href : null;
}

/** "9+" keeps the badge narrow. */
export const badgeText = (count: number): string => (count > 9 ? '9+' : String(count));
