import type { ReviewState } from '@/features/review';

import type { AuditStatus, Classification, HistorySource, LineStatus, Outcome } from '../api/types';

export type Tone = 'success' | 'warning' | 'error' | 'info' | 'default';

export const AUDIT_STATUS: Record<AuditStatus, { label: string; tone: Tone }> = {
  verified: { label: 'Matches tariff', tone: 'success' },
  mismatch: { label: 'Does not match', tone: 'error' },
  partial: { label: 'Partly checked', tone: 'info' },
  not_checkable: { label: 'Could not check', tone: 'default' },
  calculated: { label: 'Calculated only', tone: 'default' },
};

export function auditStatus(status: string | null): { label: string; tone: Tone } {
  return AUDIT_STATUS[status as AuditStatus] ?? { label: status || 'Not checked', tone: 'default' };
}

/** audit.notes are engine codes. Unknown codes are dropped rather than shown raw. */
export const AUDIT_NOTE: Record<string, string> = {
  arrears: "This bill also carries arrears from earlier bills; they are not part of this month's charges.",
  net_metering: 'This home exports power, so units are billed on the net of what it used and what it sent back.',
  true_up_explained: 'The true-up line is a TGERC approved recovery of past power costs, not an error.',
  true_up_before_order: 'A true-up line appears before the TGERC order that allows it. It is worth asking the section office about it.',
  gruha_jyothi_applied: 'The Gruha Jyothi subsidy is applied to this bill.',
  gruha_jyothi_lost: 'Usage went over the Gruha Jyothi limit this month, so the free supply does not apply.',
  total_only: 'Only the total was printed, so individual charges could not be checked.',
  total_differs: 'The printed total differs from the tariff; with no breakdown we cannot say which charge.',
  from_units: 'The tariff charges were worked out from the units, because the bill did not print them line by line.',
  non_domestic: 'This is not a domestic connection. Bill Mitra checks the domestic tariff only, so the charges could not be checked.',
};

export const LINE_STATUS: Record<LineStatus, { label: string; tone: Tone }> = {
  match: { label: 'Matches', tone: 'success' },
  over: { label: 'Charged more', tone: 'error' },
  under: { label: 'Charged less', tone: 'info' },
  missing: { label: 'Not printed', tone: 'default' },
  not_checkable: { label: 'Not checkable', tone: 'default' },
};

export const OUTCOME_TITLE: Record<Outcome, string> = {
  checked: 'We read and checked this bill',
  not_a_bill: 'This does not look like an electricity bill',
  retake: 'Please take the photo again',
  reading_off: 'Bill reading is switched off',
  reading_failed: 'We could not read this bill',
};

export const OUTCOME_TONE: Record<Outcome, 'success' | 'warning' | 'error' | 'info'> = {
  checked: 'success',
  not_a_bill: 'warning',
  retake: 'warning',
  reading_off: 'info',
  reading_failed: 'error',
};

export const DOCUMENT_TYPE: Record<Classification['document_type'], string> = {
  electricity_bill: 'An electricity bill',
  meter: 'A photo of a meter',
  other_bill: 'Some other bill',
  other: 'Not a bill',
};

export const QUALITY: Record<Classification['quality'], string> = {
  good: 'Clear',
  poor: 'Hard to read',
  unreadable: 'Unreadable',
};

export const HISTORY_SOURCE: Record<HistorySource, string> = {
  printed: 'Printed on this bill',
  uploaded: 'Your earlier upload',
  this_bill: 'This bill',
};

export const PHOTO_TIPS = [
  'Lay the bill flat on a table.',
  'Fit the whole bill in the frame, all four corners.',
  'Use daylight or a bright room.',
  'Tilt the phone a little to avoid glare from lights.',
];

/** Shown while the reader works. Timings follow what the two vision calls usually take. */
export const READING_STAGES: Array<{ from: number; label: string }> = [
  { from: 0, label: 'Checking it is a bill' },
  { from: 7, label: 'Reading every field' },
  { from: 24, label: 'Checking against the TGERC tariff' },
];

/** The consumer's view of a review case. A rejected decision is internal, so it reads as still under review. */
export const REVIEW_TEXT: Record<ReviewState, { title: string; body: string; tone: 'info' | 'success' | 'warning' }> = {
  awaiting_review: { title: 'The section AE is checking this bill', body: 'You will get a message when there is a decision.', tone: 'info' },
  info_requested: { title: 'The AE has asked you for something', body: 'Reply in the chat with what they asked for, so they can finish the check.', tone: 'warning' },
  awaiting_approval: { title: 'A correction is waiting for approval', body: 'The AE has decided; a billing officer is confirming it.', tone: 'info' },
  rejected: { title: 'The section AE is checking this bill', body: 'You will get a message when there is a decision.', tone: 'info' },
  decided: { title: 'The AE has checked this bill', body: 'The decision is below.', tone: 'success' },
  applied: { title: 'Your official bill has been revised', body: 'The revised amount is in the DISCOM billing system.', tone: 'success' },
};
