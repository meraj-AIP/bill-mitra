import type { ComplaintMessage } from '@/features/complaints';
import type { AuditLine, Bill } from '@/features/dashboard';
import type { Discom, Page } from '@/shared/api/types';

export type ReviewState = 'awaiting_review' | 'info_requested' | 'awaiting_approval' | 'decided' | 'applied' | 'rejected';
export const REVIEW_STATES: ReviewState[] = ['awaiting_review', 'info_requested', 'awaiting_approval', 'rejected', 'decided', 'applied'];

export type ReasonCode = 'photo_misread' | 'wrong_meter' | 'estimated_reading' | 'meter_faulty' | 'category_wrong' | 'bill_correct' | 'other';
export type DecisionKind = 'correct' | 'corrected_reading' | 'custom';
export type DecisionStatus = 'approved' | 'pending_approval' | 'rejected' | 'withdrawn';
export type RequestKind = 'earlier_bills' | 'meter_photo' | 'note';

export interface Person { id: string; name: string }

export interface Policy {
  discom: Discom;
  /** Rupees an AE may reduce alone on a corrected reading; null means no limit. */
  ae_limit: number | null;
  custom_needs_approval: boolean;
  spike_ratio: number;
  spike_min_increase: number;
  min_history_months: number;
  decision_sla_days: number;
}

export interface Spike {
  flagged: boolean;
  reason: 'above_normal' | 'reading_went_back' | null;
  units: number;
  median_units: number | null;
  months_used: number;
  ratio: number | null;
  usual_amount: number | null;
}

export interface CaseRow {
  ticket: string;
  bill_id: string | null;
  section_id: string | null;
  created_at: string;
  state: ReviewState;
  overdue: boolean;
  days_open: number;
  section: string | null;
  discom: string;
  bill_month: string | null;
  service_masked: string | null;
  units: number | null;
  median_units: number | null;
  printed_amount: number | null;
  usual_amount: number | null;
  assignee: Person | null;
  channel: 'whatsapp' | 'web';
}

export interface Evidence { kind: 'message' | 'bill' | 'note'; id: string; label: string }

export interface Decision {
  id: number;
  kind: DecisionKind;
  status: DecisionStatus;
  original_amount: number;
  revised_amount: number;
  reduction: number;
  corrected_present_reading: number | null;
  corrected_units: number | null;
  reason_code: ReasonCode;
  note: string;
  evidence: Evidence[];
  proposed_by: Person;
  proposed_at: string;
  decided_by: Person | null;
  decided_at: string | null;
  decision_note: string | null;
  applied_at: string | null;
  billing_ref: string | null;
  revision: number | null;
}

export interface InfoRequest {
  id: number;
  kind: RequestKind;
  note: string | null;
  status: 'open' | 'answered';
  created_at: string;
}

export interface CaseDetail extends CaseRow {
  bill: Bill | null;
  media_url: string | null;
  mime_type: string | null;
  audit_lines: AuditLine[];
  spike: Spike;
  history: Array<{ month: string; units: number; amount: number; source: HistorySource }>;
  messages: ComplaintMessage[];
  requests: InfoRequest[];
  /** Newest first. */
  decisions: Decision[];
  policy: Policy;
  can: { decide: boolean; approve: boolean; mark_applied: boolean; request_info: boolean; reassign: boolean; unmask: boolean };
  assignable: Person[];
  evidence_pack: EvidencePack;
  /** Oldest first. */
  timeline: TimelineEntry[];
}

export type HistorySource = 'printed' | 'uploaded' | 'discom' | 'this_bill';

export type EvidenceStatus = 'included' | 'partial' | 'missing' | 'not_connected';

export interface EvidenceSource {
  key: 'this_bill' | 'printed_history' | 'uploads' | 'discom_records' | 'spike' | 'requested_bills';
  label: string;
  status: EvidenceStatus;
  /** YYYY-MM */
  months: string[];
  detail: string;
}

export interface AttachedBill { bill_id: string; month: string; units: number | null; amount: number | null; media_url: string | null }

export interface EvidencePack {
  sources: EvidenceSource[];
  requested_months: string[];
  received_months: string[];
  attached_bills: AttachedBill[];
}

export interface TimelineEntry { at: string; actor: { kind: 'consumer' | 'system' | 'staff'; name: string | null }; text: string }

export type ReportState = 'received' | 'waiting_for_you' | 'revised' | 'no_change';

/** The consumer's view of a report. It never names who reviews the bill. */
export interface ReviewSummary {
  ticket: string;
  state: ReportState;
  /** YYYY-MM */
  requested_months: string[];
  received_months: string[];
  revision: {
    original_amount: number;
    revised_amount: number;
    original_total: number | null;
    revised_total: number | null;
    /** Already in the consumer's language. */
    reason: string;
    /** The DISCOM, for example TGSPDCL. */
    office: string;
    decided_at: string;
    status: 'pending_update' | 'applied';
  } | null;
}

/** Counts cover every case the viewer may see, by state plus `overdue`; list filters do not narrow them. */
export interface CasePageResult extends Page<CaseRow> { counts: Record<string, number> }

export interface SectionOption { id: string; name: string }

export interface CaseQuery {
  page: number;
  pageSize: number;
  state: ReviewState | '';
  mine: boolean;
  overdue: boolean;
  sectionId: string;
  q: string;
  sort: 'oldest' | 'newest';
}

export interface Preview { corrected_units: number; revised_amount: number; reduction: number; needs_approval: boolean }

export interface NewDecision {
  kind: DecisionKind;
  corrected_present_reading?: number;
  reduction?: number;
  reason_code: ReasonCode;
  note: string;
  evidence: Array<{ kind: Evidence['kind']; id: string }>;
}
