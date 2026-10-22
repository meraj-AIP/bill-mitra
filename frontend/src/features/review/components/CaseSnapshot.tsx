import { Snapshot, type Tile } from '@/shared/components/Snapshot';
import { dateTime, formatCount, parseUtc, rupees, shortDate } from '@/shared/lib/format';

import type { CaseDetail } from '../api/types';
import { ratioOf } from '../model/labels';

const DAY = 86_400_000;

function usageTiles(c: CaseDetail): Tile[] {
  const ratio = ratioOf(c.units, c.median_units);
  const high = ratio !== null && ratio >= c.policy.spike_ratio;
  return [
    { label: 'Units billed', value: c.units === null ? 'Not read' : formatCount(c.units), tone: high ? 'warning' : 'default',
      note: c.median_units === null ? 'No usual month on file' : `Usual ${formatCount(c.median_units)} a month` },
    { label: 'Amount printed', value: c.printed_amount === null ? 'Not printed' : rupees(c.printed_amount),
      note: c.usual_amount === null ? null : `A usual month costs ${rupees(c.usual_amount)}` },
  ];
}

function readingTile(c: CaseDetail): Tile {
  const b = c.bill;
  if (!b || b.previous_reading == null || b.present_reading == null) return { label: 'Readings', value: 'Not printed' };
  const back = b.present_reading < b.previous_reading;
  return { label: 'Readings', value: `${formatCount(b.previous_reading)} to ${formatCount(b.present_reading)}`, tone: back ? 'error' : 'default',
    note: back ? 'Present is below previous' : b.billing_days ? `${b.billing_days} billing days` : null };
}

function chargesTile(c: CaseDetail): Tile {
  if (!c.audit_lines.length) return { label: 'Charges vs tariff', value: 'Not checked' };
  const over = c.audit_lines.reduce((sum, l) => sum + (l.status === 'over' && l.difference ? l.difference : 0), 0);
  if (over > 0) return { label: 'Charges vs tariff', value: `${rupees(over)} over`, tone: 'error', note: 'For the units billed' };
  return { label: 'Charges vs tariff', value: 'All match', tone: 'success', note: 'For the units billed' };
}

function dueTile(c: CaseDetail): Tile {
  const by = new Date(parseUtc(c.created_at).getTime() + c.policy.decision_sla_days * DAY).toISOString();
  const open = `${c.days_open} ${c.days_open === 1 ? 'day' : 'days'} open`;
  if (c.overdue) return { label: 'Decide by', value: shortDate(by), tone: 'error', note: `Overdue, ${open}` };
  return { label: 'Decide by', value: shortDate(by), note: open };
}

/** Why the case exists and how long is left, in one row, with the consumer's own words under it. */
export function CaseSnapshot({ c }: { c: CaseDetail }) {
  const first = c.messages.find((m) => m.author_kind === 'consumer' && m.body.trim());
  const quote = first ? { text: first.body, meta: `Consumer, ${c.channel === 'whatsapp' ? 'WhatsApp' : 'web app'}, ${dateTime(first.created_at)}` } : null;
  return <Snapshot tiles={[...usageTiles(c), readingTile(c), chargesTile(c), dueTile(c)]} quote={quote} />;
}
