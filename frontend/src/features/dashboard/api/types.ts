import type { ReviewSummary, Spike } from '@/features/review';

export type Outcome = 'checked' | 'not_a_bill' | 'retake' | 'reading_off' | 'reading_failed';
export type Discom = 'TGSPDCL' | 'TGNPDCL' | 'OTHER' | 'UNKNOWN';
export type AuditStatus = 'verified' | 'mismatch' | 'partial' | 'not_checkable' | 'calculated';
export type LineStatus = 'match' | 'over' | 'under' | 'missing' | 'not_checkable';
export type HistorySource = 'printed' | 'uploaded' | 'discom' | 'this_bill';

export interface Classification {
  document_type: 'electricity_bill' | 'meter' | 'other_bill' | 'other';
  discom: Discom;
  quality: 'good' | 'poor' | 'unreadable';
  quality_issue: string | null;
  reason: string;
}

export interface LineItem {
  code: 'energy' | 'fixed' | 'customer' | 'duty' | 'fsa' | 'true_up' | 'surcharge' | 'adjustment' | 'other';
  label: string;
  amount: number;
}

export interface Bill {
  discom: Discom;
  service_masked: string | null;
  section: string | null;
  category: string | null;
  is_domestic: boolean;
  bill_month: string | null;
  bill_date: string | null;
  due_date: string | null;
  previous_reading: number | null;
  present_reading: number | null;
  units: number | null;
  export_units: number | null;
  /** Import minus export, as printed on a net-metered bill. */
  billed_units?: number | null;
  /** Meter status ("Sts") beside the present and previous readings; anything but 01 means estimated units. */
  present_status?: string | null;
  previous_status?: string | null;
  phase?: number | null;
  multiplying_factor?: number | null;
  recorded_md?: number | null;
  power_factor?: number | null;
  security_deposit?: number | null;
  carry_forward_units?: number | null;
  disconnection_date?: string | null;
  last_paid_date?: string | null;
  load_kw: number | null;
  billing_days?: number | null;
  line_items: LineItem[];
  bill_amount: number | null;
  arrears: number;
  total_payable: number | null;
  gruha_jyothi_household: boolean | null;
  subsidy_amount: number | null;
  confidence: number;
  usage_history: Array<{ month: string; units: number }>;
  unreadable_fields: string[];
  source: 'vision' | 'sms' | 'manual';
}

export interface Capture {
  captured: number;
  expected: number;
  fields: Array<{ key: string; label: string; status: 'captured' | 'missing' | 'unreadable'; value: string | null }>;
  checks: Array<{ key: string; label: string; status: 'pass' | 'fail' | 'skipped'; detail: string }>;
}

export interface AuditLine {
  code: string;
  label: string;
  printed: number | null;
  expected: number | null;
  difference: number | null;
  status: LineStatus;
}

export interface SlabLine {
  start: number;
  end: number;
  units: number;
  rate: number;
  amount: number;
}

export interface Prediction {
  month: string;
  units_low: number;
  units_high: number;
  units: number;
  amount: number;
  method: string;
  crosses: number | null;
}

export interface Saving {
  target_units: number;
  cut_units: number;
  saving: number;
  ac_minutes_per_day: number;
  geyser_minutes_per_day: number;
}

export interface Analysis {
  tariff_id: string;
  tariff_order: string;
  group: string;
  units: number;
  energy: number;
  fixed: number;
  customer: number;
  duty: number;
  fsa: number;
  gross: number;
  subsidy: number;
  net: number;
  gruha_jyothi_applied: boolean;
  slab_lines: SlabLine[];
  audit: { status: AuditStatus; lines: AuditLine[]; overcharge: number; undercharge: number; notes: string[] };
  prediction: Prediction;
  history: Array<{ month: string; units: number; amount: number; source: HistorySource }>;
  cliffs: Array<{ threshold: number; amount_at: number; amount_after: number; jump: number }>;
  saving: Saving | null;
  explanation: string[];
  /** Rule-engine check against the household's usual month. Older reports may not carry it. */
  spike?: Spike;
}

export interface BillReport {
  id: string | null;
  created_at: string | null;
  media_url: string | null;
  mime_type: string;
  outcome: Outcome;
  outcome_reason: string | null;
  classification: Classification | null;
  bill: Bill | null;
  capture: Capture | null;
  analysis: Analysis | null;
  /** The consumer's report on this bill, when they made one. */
  review?: ReviewSummary | null;
  /** The amounts to pay. After an approved revision these are the revised figures, not the printed ones. */
  final?: FinalAmounts | null;
  /** This bill's previous reading is below an earlier bill's present reading, so the earlier one was likely read too high. */
  misread?: Misread | null;
}

/** Readings as printed on the two bills. No amounts here. */
export interface Misread {
  earlier_bill_id: string;
  /** YYYY-MM */
  earlier_month: string;
  printed_present: number;
  next_previous: number;
}

export interface FinalAmounts {
  bill_amount: number;
  total_payable: number | null;
  revised: boolean;
  status: 'pending_update' | 'applied' | null;
}

export interface BillSummary {
  id: string;
  created_at: string;
  bill_month: string | null;
  discom: string;
  units: number | null;
  /** The final total: the revised one once a revision is approved. */
  total_payable: number | null;
  /** The printed total, kept when a revision changed it. */
  original_total_payable?: number | null;
  audit_status: string;
  overcharge: number;
  service_masked: string | null;
  /** The latest approved revision of this bill, or null when it has none. */
  revised_amount: number | null;
  /** A report on this bill is still being reviewed. */
  under_review: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface BillListQuery {
  page: number;
  pageSize: number;
  status: AuditStatus | '';
  sort: 'newest' | 'oldest';
}

/** A bill read that failed for a passing reason is kept as a job; the server answers 202 with this and the page polls it. */
export interface ExtractJob {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  /** Set when status is done: the saved bill to open. */
  bill_id: string | null;
  /** Set when status is failed: why, in words a consumer can act on. */
  detail: string | null;
}

export type UploadOutcome = { kind: 'report'; report: BillReport } | { kind: 'job'; job: ExtractJob };
