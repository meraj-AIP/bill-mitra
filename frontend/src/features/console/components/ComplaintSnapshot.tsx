import { CHANNEL_LABEL, SOURCE_LABEL, TRIAGE, type ComplaintDetail } from '@/features/complaints';
import { Snapshot, type Tile } from '@/shared/components/Snapshot';
import { dateTime, formatCount, monthLabel, rupees, shortDate } from '@/shared/lib/format';

const OPEN = new Set(['Open', 'In progress']);

export const sourceOf = (c: ComplaintDetail) => (c.source ? SOURCE_LABEL[c.source] : c.channel ? CHANNEL_LABEL[c.channel] : 'Staff');

function billTiles(c: ComplaintDetail): Tile[] {
  const amount = c.bill?.bill_amount ?? c.amount;
  if (!c.bill && !amount) return [{ label: 'Bill', value: 'Not sent', note: 'No bill on this complaint yet', tone: 'warning' }];
  const over = c.audit_lines.reduce((sum, l) => sum + (l.status === 'over' && l.difference ? l.difference : 0), 0);
  const check = TRIAGE[c.triage];
  return [
    { label: 'Bill amount', value: amount ? rupees(amount) : 'Not printed', note: c.bill_month ? `${monthLabel(c.bill_month)} bill` : null },
    { label: 'Units billed', value: c.bill?.units != null ? formatCount(c.bill.units) : 'Not read' },
    { label: 'Bill check', value: check.label, tone: check.tone, note: over > 0 ? `${rupees(over)} above the tariff` : check.hint },
  ];
}

function moveTile(c: ComplaintDetail): Tile {
  if (!OPEN.has(c.status)) return { label: 'Whose move', value: 'Closed', note: c.status };
  if (c.waiting_on === 'consumer') return { label: 'Whose move', value: 'Consumer', note: 'Waiting for their answer', tone: 'info' };
  return { label: 'Whose move', value: 'Ours', note: c.assignee?.name ? `With ${c.assignee.name}` : 'Not with anyone yet', tone: c.assignee ? 'default' : 'warning' };
}

function dueTile(c: ComplaintDetail): Tile {
  if (c.overdue) return { label: 'Due', value: 'Overdue', note: `${c.days_open} days open`, tone: 'error' };
  return { label: 'Due', value: c.due_at ? shortDate(c.due_at) : 'No date', note: `${c.days_open} ${c.days_open === 1 ? 'day' : 'days'} open` };
}

/** The bill, the check, whose move it is and when it is due, then the consumer's own words. */
export function ComplaintSnapshot({ complaint: c }: { complaint: ComplaintDetail }) {
  const first = c.messages.find((m) => m.author_kind === 'consumer' && m.body.trim());
  const said = c.description?.trim() || first?.body;
  const who = c.raised_by ? `Logged by ${c.raised_by}, ${sourceOf(c)}` : sourceOf(c);
  const quote = said ? { text: said, meta: `${who}, ${dateTime(c.created_at)}` } : null;
  return <Snapshot tiles={[...billTiles(c), moveTile(c), dueTile(c)]} quote={quote} />;
}
