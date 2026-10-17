import type { Page } from '@/shared/api/types';

export type AlertKind =
  | 'misread_found' | 'case_overdue' | 'case_escalated' | 'digest'
  | 'applied_auto' | 'pattern_section' | 'request_reminded' | 'request_lapsed'
  | 'complaint_assigned' | 'consumer_replied' | 'case_assigned' | 'decision_returned';

export interface AlertItem {
  id: number;
  /** Kept as a string so a kind added on the server still renders. */
  kind: AlertKind | (string & {});
  title: string;
  body: string;
  ticket: string | null;
  /** The page the alert opens, decided by the server. Older servers leave it out. */
  href?: string | null;
  unit_name: string | null;
  created_at: string;
  read: boolean;
}

/** `unread` counts every unread alert for this account, whatever the filter. */
export interface AlertPage extends Page<AlertItem> { unread: number }

export interface AlertQuery {
  page: number;
  pageSize: number;
  unread: boolean;
}
