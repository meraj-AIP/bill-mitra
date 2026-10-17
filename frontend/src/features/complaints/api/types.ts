export type ComplaintStatus = 'Open' | 'In progress' | 'Resolved' | 'Rejected';
export type Triage = 'overcharge' | 'needs_check' | 'bill_correct';
export const TRIAGES: Triage[] = ['overcharge', 'needs_check', 'bill_correct'];
export const COMPLAINT_STATUSES: ComplaintStatus[] = ['Open', 'In progress', 'Resolved', 'Rejected'];

export type Priority = 'urgent' | 'high' | 'normal' | 'low';
export const PRIORITIES: Priority[] = ['urgent', 'high', 'normal', 'low'];
export type Source = 'consumer_web' | 'consumer_chat' | 'whatsapp' | 'call_centre' | 'office' | 'field';
export const SOURCES: Source[] = ['consumer_web', 'consumer_chat', 'whatsapp', 'call_centre', 'office', 'field'];
/** The sources a staff member can pick when they log a complaint. */
export type StaffSource = Extract<Source, 'call_centre' | 'office' | 'field'>;
export const STAFF_SOURCES: StaffSource[] = ['call_centre', 'office', 'field'];
export type Ownership = 'verified' | 'unverified' | 'not_needed';

/** One entry of GET /api/complaint-types, labels already in the language asked for. */
export interface ComplaintType {
  code: string;
  category: string;
  /** The category name in the language asked for. */
  category_label?: string;
  label: string;
  label_key: string;
  needs_bill: boolean;
  priority: Priority;
  /** Null for wrong_reading: the review policy sets its time. */
  target_days: number | null;
  route: 'section' | 'division' | 'review';
}

export interface Person { id: string; name: string }

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
  /** A wrong-reading case is handled in the review workspace; general complaints stay in the inbox. */
  kind: 'general' | 'wrong_reading';
  /** The newest message we sent the consumer did not reach them. */
  delivery_failed: boolean;
  days_open: number;
  /** Open past the reply time promised to consumers; the server decides. */
  overdue: boolean;
  messages_count: number;
  last_message_at: string | null;
  // Added by the complaints contract. Optional so rows from an older server still render.
  type?: string;
  type_label?: string | null;
  priority?: Priority | null;
  due_at?: string | null;
  source?: Source | null;
  section?: string | null;
  demo?: boolean;
  /** Whose move it is. */
  waiting_on?: WaitingOn;
  /** Who holds it, for the inbox table. */
  assignee_name?: string | null;
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
  /** The file's type, such as image/jpeg. Older servers leave it out. */
  media_type?: string | null;
}

/** What the consumer sent back to a request. */
export interface RequestAnswer {
  message_id: number;
  media_url: string | null;
  media_type?: string | null;
  /** Null when the answer is a photo sent without words. */
  body: string | null;
  at: string;
}

/** Something staff asked the consumer for, with the answer once it came. */
export interface ComplaintRequest {
  id: number;
  kind: string;
  note: string | null;
  status: 'open' | 'answered';
  created_at: string;
  answered_at?: string | null;
  answer?: RequestAnswer | null;
}

export type WaitingOn = 'staff' | 'consumer' | 'none';

/** How the complaint reached its holder. `by` is null when the system routed it. */
export interface Handoff { by: Person | null; note: string | null; at: string | null }

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
  description?: string | null;
  /** Name of the staff member who logged it; null when the consumer raised it. */
  raised_by?: string | null;
  ownership?: Ownership | null;
  timeline?: TimelineEntry[];
  assignee?: Person | null;
  /** People this complaint can move to. Present only for accounts allowed to assign. */
  assignable?: Person[];
  // Added by the hand-off contract (section 4). Optional so an older server still renders.
  /** Null while nobody holds it. */
  handoff?: Handoff | null;
  /** The viewer holds it and may send it back to whoever handed it over. */
  can_return?: boolean;
  /** Newest first. */
  requests?: ComplaintRequest[];
}

export interface TimelineEntry {
  at: string;
  actor: { kind: 'consumer' | 'system' | 'staff'; name: string | null };
  text: string;
  /** The note written with a hand-off or a send back. */
  note?: string | null;
}

export interface NewStaffComplaint {
  type: string;
  discom: string;
  section_id: string | null;
  service_number: string | null;
  contact_mobile: string | null;
  description: string;
  source: StaffSource;
  bill_id: string | null;
}

export const REPLY_LIMIT = 1000;
