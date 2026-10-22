import type { ComplaintMessage, ComplaintStatus, Ownership, Priority, Source, Triage } from '../api/types';

type Tone = 'warning' | 'info' | 'success' | 'default';

export const STATUS_TONE: Record<ComplaintStatus, Tone> = {
  Open: 'warning',
  'In progress': 'info',
  Resolved: 'success',
  Rejected: 'default',
};

export const DELIVERY: Record<ComplaintMessage['delivery'], { label: string; tone: 'success' | 'error' | 'default' }> = {
  sent: { label: 'Sent on WhatsApp', tone: 'success' },
  failed: { label: 'Not delivered', tone: 'error' },
  stored: { label: 'Saved here only', tone: 'default' },
};

export const CHANNEL_LABEL: Record<'whatsapp' | 'web', string> = {
  whatsapp: 'WhatsApp',
  web: 'Web app',
};

export const TRIAGE: Record<Triage, { label: string; hint: string; tone: 'error' | 'warning' | 'success' }> = {
  overcharge: { label: 'Overcharge', hint: 'A charge is above the TGERC tariff', tone: 'error' },
  needs_check: { label: 'Needs a look', hint: 'The check could not confirm every line', tone: 'warning' },
  bill_correct: { label: 'Bill is correct', hint: 'Every charge matches the tariff', tone: 'success' },
};

export const PRIORITY: Record<Priority, { label: string; tone: 'error' | 'warning' | 'default' }> = {
  urgent: { label: 'Urgent', tone: 'error' },
  high: { label: 'High', tone: 'warning' },
  normal: { label: 'Normal', tone: 'default' },
  low: { label: 'Low', tone: 'default' },
};

export const SOURCE_LABEL: Record<Source, string> = {
  consumer_web: 'Consumer, web app',
  consumer_chat: 'Consumer, web chat',
  whatsapp: 'Consumer, WhatsApp',
  call_centre: 'Call centre (1912)',
  office: 'Walk-in at office',
  field: 'Field visit',
};

/** Whether the connection is shown to be the consumer's. The registered mobile is a separate check (SenderChip). */
export const OWNERSHIP_LABEL: Record<Ownership, string> = {
  verified: 'Shown: their own bill is linked',
  unverified: 'Service number given, not shown',
  not_needed: 'Not needed for this type',
};

/** Request kinds from both the complaint and the review case, read as "Asked for ...". */
const REQUEST_LABEL: Record<string, string> = {
  meter_photo: 'a meter photo',
  bill_photo: 'a bill photo',
  earlier_bills: 'earlier bills',
  payment_proof: 'proof of payment',
  details: 'more details',
  note: 'an answer to a question',
};

export function requestLabel(kind: string): string {
  return REQUEST_LABEL[kind] ?? kind.replace(/_/g, ' ');
}
