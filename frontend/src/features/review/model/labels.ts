import type { DecisionKind, DecisionStatus, EvidenceStatus, ReasonCode, RequestKind, ReviewState, TimelineEntry } from '../api/types';

type Tone = 'warning' | 'info' | 'success' | 'error' | 'default' | 'primary';

export const STATE: Record<ReviewState, { label: string; short: string; tone: Tone; hint: string }> = {
  awaiting_review: { label: 'Awaiting review', short: 'To review', tone: 'warning', hint: 'No decision yet and nothing asked of the consumer' },
  info_requested: { label: 'Waiting on consumer', short: 'Waiting on consumer', tone: 'info', hint: 'The consumer has been asked for something' },
  awaiting_approval: { label: 'Awaiting approval', short: 'To approve', tone: 'primary', hint: 'A reduction above the AE limit needs a second person' },
  rejected: { label: 'Sent back', short: 'Sent back', tone: 'error', hint: 'The approver rejected the decision; it is back with the AE' },
  decided: { label: 'Decided', short: 'Decided', tone: 'success', hint: 'Approved; any revision waits to be applied in billing' },
  applied: { label: 'Applied in billing', short: 'Applied', tone: 'default', hint: 'The revision is in the DISCOM billing system' },
};

export const REASON: Record<ReasonCode, string> = {
  photo_misread: 'Meter reader misread the meter',
  wrong_meter: 'Reading taken from the wrong meter',
  estimated_reading: 'Estimated, not an actual reading',
  meter_faulty: 'Meter is faulty',
  category_wrong: 'Wrong tariff category',
  bill_correct: 'Bill is correct as printed',
  other: 'Other reason, explained in the note',
};

export const DECISION_KIND: Record<DecisionKind, { label: string; hint: string }> = {
  correct: { label: 'Bill is correct', hint: 'No change. The consumer is told the bill stands.' },
  corrected_reading: { label: 'Corrected reading', hint: 'Enter the right present reading. The tariff engine reprices the month.' },
  custom: { label: 'Custom reduction', hint: 'Enter the amount to take off, for cases a reading cannot fix.' },
};

export const DECISION_STATUS: Record<DecisionStatus, { label: string; tone: Tone }> = {
  approved: { label: 'Approved', tone: 'success' },
  pending_approval: { label: 'Awaiting approval', tone: 'primary' },
  rejected: { label: 'Rejected', tone: 'error' },
  withdrawn: { label: 'Withdrawn', tone: 'default' },
};

export const REQUEST_KIND: Record<RequestKind, { label: string; hint: string }> = {
  earlier_bills: { label: 'Earlier bills', hint: 'Photos of the last few months\' bills' },
  meter_photo: { label: 'Meter photo', hint: 'A clear photo of the meter display today' },
  note: { label: 'A note', hint: 'Anything else, in your own words below' },
};

export const EVIDENCE_STATUS: Record<EvidenceStatus, { label: string; tone: Tone }> = {
  included: { label: 'Included', tone: 'success' },
  partial: { label: 'Partial', tone: 'warning' },
  missing: { label: 'Missing', tone: 'error' },
  not_connected: { label: 'Not connected', tone: 'default' },
};

/** Automatic steps have no person behind them, so they read as System. */
export function actorName(actor: TimelineEntry['actor']): string {
  if (actor.kind === 'system') return 'System';
  if (actor.kind === 'consumer') return 'Consumer';
  return actor.name ?? 'Staff';
}

export const MIN_NOTE = 20;

export function ratioOf(units: number | null, median: number | null): number | null {
  if (units === null || median === null || median <= 0) return null;
  return units / median;
}

/** Parts of the case page that AI assist can bring into view. */
export const CASE_SECTION = { decision: 'case-decision', ask: 'case-ask', approval: 'case-approval', apply: 'case-apply' } as const;
