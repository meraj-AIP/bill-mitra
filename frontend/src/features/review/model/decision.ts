import { dateTime, formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { CaseDetail, DecisionKind, Draft, Evidence, NewDecision, Preview, ReasonCode, ReviewState } from '../api/types';
import { MIN_NOTE } from './labels';

export interface DecisionDraft {
  kind: DecisionKind;
  reading: string;
  reduction: string;
  reason: ReasonCode | '';
  note: string;
  /** Keys are `${kind}:${id}`. */
  evidence: string[];
}

export const emptyDraft = (): DecisionDraft => ({ kind: 'correct', reading: '', reduction: '', reason: 'bill_correct', note: '', evidence: [] });

/** A decision can be recorded while nothing is waiting on someone else. */
export const OPEN_FOR_DECISION: ReadonlySet<ReviewState> = new Set(['awaiting_review', 'info_requested', 'rejected']);

const evidenceKey = (e: Pick<Evidence, 'kind' | 'id'>) => `${e.kind}:${e.id}`;

function attachedLabel(b: CaseDetail['evidence_pack']['attached_bills'][number]): string {
  const parts = [`Earlier bill, ${monthLabel(b.month)}`];
  if (b.units !== null) parts.push(`${formatCount(b.units)} units`);
  if (b.amount !== null) parts.push(rupees(b.amount));
  return parts.join(', ');
}

/** What an AE can cite: the bill itself, earlier bills attached to the case, and anything the consumer sent into the thread. */
export function evidenceOptions(c: CaseDetail): Array<Evidence & { key: string; photo: string | null }> {
  const bill = c.bill_id ? [{ kind: 'bill' as const, id: c.bill_id, label: 'The bill as uploaded', photo: null }] : [];
  // No file type comes with an attached bill and it may be a PDF, so no thumbnail is drawn for it.
  const attached = c.evidence_pack.attached_bills
    .filter((b) => b.bill_id !== c.bill_id)
    .map((b) => ({ kind: 'bill' as const, id: b.bill_id, label: attachedLabel(b), photo: null }));
  const messages = c.messages
    .filter((m) => m.author_kind === 'consumer')
    .map((m) => ({
      kind: 'message' as const,
      id: String(m.id),
      label: m.media_url ? `Photo from the consumer, ${dateTime(m.created_at)}` : `Consumer reply, ${dateTime(m.created_at)}: ${m.body.slice(0, 80)}`,
      photo: m.media_url,
    }));
  return [...bill, ...attached, ...messages].map((e) => ({ ...e, key: evidenceKey(e) }));
}

/** The form state a suggested decision fills in. The AE still checks it and records it. */
export function fromDraft(d: Draft): DecisionDraft {
  return {
    kind: d.kind,
    reading: d.kind === 'corrected_reading' && d.corrected_present_reading !== null ? String(d.corrected_present_reading) : '',
    reduction: '',
    reason: d.reason_code,
    note: d.note,
    evidence: d.evidence.map(evidenceKey),
  };
}

/**
 * A suggestion can cite a bill the case does not list yet, such as the next month's bill. It is shown, ticked, so the
 * AE sees everything the decision will rest on and can untick it.
 */
export function withCited(options: ReturnType<typeof evidenceOptions>, keys: string[]): ReturnType<typeof evidenceOptions> {
  const known = new Set(options.map((o) => o.key));
  const extra = keys.filter((k) => !known.has(k)).map((key) => {
    const [kind, ...rest] = key.split(':');
    const id = rest.join(':');
    const label = kind === 'bill' ? 'Another bill from this consumer, cited by the suggestion' : 'Consumer message cited by the suggestion';
    return { kind: kind as Evidence['kind'], id, label, key, photo: null };
  });
  return [...options, ...extra];
}

export function parseAmount(text: string): number | null {
  if (!text.trim()) return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

export interface Outcome {
  original: number | null;
  revised: number | null;
  reduction: number | null;
  needsApproval: boolean;
}

/**
 * The figures the summary shows. A corrected reading uses the engine's preview as is. A custom reduction is the AE's
 * own typed amount; no revised total is worked out here, the server records it.
 */
export function outcomeOf(d: DecisionDraft, c: CaseDetail, preview: Preview | undefined): Outcome {
  const original = c.printed_amount;
  if (d.kind === 'correct') return { original, revised: original, reduction: 0, needsApproval: false };
  if (d.kind === 'corrected_reading') {
    return preview
      ? { original, revised: preview.revised_amount, reduction: preview.reduction, needsApproval: preview.needs_approval }
      : { original, revised: null, reduction: null, needsApproval: false };
  }
  return { original, revised: null, reduction: parseAmount(d.reduction), needsApproval: c.policy.custom_needs_approval };
}

function readingProblem(d: DecisionDraft, c: CaseDetail, outcome: Outcome): string | null {
  if (d.kind !== 'corrected_reading') return null;
  const reading = parseAmount(d.reading);
  const previous = c.bill?.previous_reading ?? null;
  if (reading === null) return 'Enter the corrected present reading.';
  if (previous !== null && reading < previous) return `The reading cannot be below the previous reading, ${previous}.`;
  if (outcome.reduction !== null && outcome.reduction <= 0) return 'At this reading the bill does not go down. Choose Bill is correct instead.';
  return null;
}

function reductionProblem(d: DecisionDraft, c: CaseDetail): string | null {
  if (d.kind !== 'custom') return null;
  const reduction = parseAmount(d.reduction);
  if (reduction === null || reduction <= 0) return 'Enter the amount to take off, above zero.';
  if (c.printed_amount !== null && reduction > c.printed_amount) return 'The reduction cannot be more than the printed amount.';
  return null;
}

export function problemsOf(d: DecisionDraft, c: CaseDetail, outcome: Outcome) {
  return {
    reading: readingProblem(d, c, outcome),
    reduction: reductionProblem(d, c),
    reason: d.reason ? null : 'Pick a reason.',
    note: d.note.trim().length >= MIN_NOTE ? null : `Write at least ${MIN_NOTE} characters, so the next reader knows why.`,
    evidence: d.evidence.length > 0 ? null : 'Tick at least one piece of evidence.',
  };
}

export function toBody(d: DecisionDraft): NewDecision {
  const evidence = d.evidence.map((key) => {
    const [kind, ...rest] = key.split(':');
    return { kind: kind as Evidence['kind'], id: rest.join(':') };
  });
  const base = { kind: d.kind, reason_code: d.reason as ReasonCode, note: d.note.trim(), evidence };
  if (d.kind === 'corrected_reading') return { ...base, corrected_present_reading: Number(d.reading) };
  if (d.kind === 'custom') return { ...base, reduction: Number(d.reduction) };
  return base;
}
