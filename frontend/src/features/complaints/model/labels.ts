import type { ComplaintMessage, ComplaintStatus, Triage } from '../api/types';

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
