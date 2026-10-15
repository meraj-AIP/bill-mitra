export type ComplaintStatus = 'Open' | 'In progress' | 'Resolved' | 'Rejected';
export type Triage = 'overcharge' | 'needs_check' | 'bill_correct';
export const TRIAGES: Triage[] = ['overcharge', 'needs_check', 'bill_correct'];
export const COMPLAINT_STATUSES: ComplaintStatus[] = ['Open', 'In progress', 'Resolved', 'Rejected'];

export interface ComplaintRow {
  ticket: string;
  created_at: string;
  updated_at: string | null;
  status: ComplaintStatus;
  service_masked: string | null;
  bill_month: string | null;
  discom: string | null;
  issue: string;
  amount: number | null;
  language: string | null;
  channel: 'whatsapp' | 'web' | null;
  triage: Triage;
  /** The newest message we sent the consumer did not reach them. */
  delivery_failed: boolean;
  days_open: number;
  /** Open past the reply time promised to consumers; the server decides. */
  overdue: boolean;
  messages_count: number;
  last_message_at: string | null;
}

export interface ComplaintMessage {
  id: number;
  author_kind: 'consumer' | 'officer' | 'system';
  author_name: string | null;
  body: string;
  created_at: string;
  delivery: 'sent' | 'failed' | 'stored';
  delivery_note: string | null;
  /** A photo the consumer sent into the thread. */
  media_url: string | null;
}

export interface ComplaintAuditLine {
  code: string;
  label: string;
  printed: number | null;
  expected: number | null;
  difference: number | null;
  status: string;
}

export interface ComplaintDetail extends ComplaintRow {
  bill: {
    bill_month: string | null;
    units: number | null;
    total_payable: number | null;
    bill_amount: number | null;
    service_masked: string | null;
    discom: string;
  } | null;
  audit_lines: ComplaintAuditLine[];
  media_url: string | null;
  messages: ComplaintMessage[];
  reply_channel: 'whatsapp' | 'web';
  whatsapp_ready: boolean;
}

export const REPLY_LIMIT = 1000;
