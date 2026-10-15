import { Stack } from '@mui/material';

import { formatCount, rupees } from '@/shared/lib/format';

import type { Summary } from '../api/consoleApi';
import { TileGroup, type Tile } from './TileGroup';

const share = (part: number, whole: number) => `${Math.round((part / whole) * 100)}%`;
const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;
const pending = (labels: string[]): Tile[] => labels.map((label) => ({ label, value: undefined }));

function billTiles(d: Summary): Tile[] {
  const verified = d.audit.verified ?? 0;
  const mismatches = d.audit.mismatch ?? 0;
  return [
    { label: 'Bills explained', value: formatCount(d.bills_read), note: 'Read and checked' },
    { label: 'Matched the tariff', value: share(verified, d.bills_read), note: `${formatCount(verified)} checked line by line` },
    { label: 'Possible overcharges', value: formatCount(mismatches), emphasis: mismatches > 0 ? 'alert' : 'default',
      note: d.overcharge_flagged > 0 ? `${rupees(d.overcharge_flagged)} flagged` : 'Nothing flagged' },
    { label: 'Slab warnings sent', value: formatCount(d.alerts), note: 'Homes close to a slab limit' },
  ];
}

function readTiles(r: Summary['reads']): Tile[] {
  const time = r.median_ms === null
    ? { value: 'Too few reads', note: 'Needs a few more bills' }
    : { value: seconds(r.median_ms), note: r.p90_ms === null ? 'Median' : `Median. 9 in 10 within ${seconds(r.p90_ms)}` };
  return [
    { label: 'Right first time', value: share(r.trusted_first_time, r.total), note: `${formatCount(r.trusted_first_time)} of ${formatCount(r.total)} reads` },
    { label: 'Saved by a second read', value: formatCount(r.reread_rescued), note: 'First read was unsure' },
    { label: 'Asked to retake', value: formatCount(r.retake), note: 'Blurred or cut off' },
    { label: 'Not a bill', value: formatCount(r.not_a_bill), note: 'Meters and other photos' },
    { label: 'Reading failed', value: formatCount(r.failed), note: 'Could not be read', emphasis: r.failed > 0 ? 'alert' : 'default' },
    { label: 'Typical read time', ...time },
  ];
}

function replyTiles(d: Summary): Tile[] {
  const ex = d.explanations;
  const s = d.complaints_by_status;
  return [
    { label: 'Questions answered', value: formatCount(d.questions), note: 'Text and voice' },
    { label: 'Explanations checked', value: formatCount(ex.llm_pass),
      note: `${formatCount(ex.llm_fallback)} fell back to a template, ${formatCount(ex.template)} template only` },
    { label: 'Complaints raised', value: formatCount(d.complaints),
      note: `${formatCount(s.Open ?? 0)} open, ${formatCount(s['In progress'] ?? 0)} in progress, ${formatCount(s.Resolved ?? 0)} resolved` },
    { label: 'Complaints overdue', value: formatCount(d.complaints_overdue), note: `Not closed after ${d.reply_days} days`,
      emphasis: d.complaints_overdue > 0 ? 'alert' : 'default' },
  ];
}

const BILL_LABELS = ['Bills explained', 'Matched the tariff', 'Possible overcharges', 'Slab warnings sent'];
const READ_LABELS = ['Right first time', 'Saved by a second read', 'Asked to retake', 'Not a bill', 'Reading failed', 'Typical read time'];
const REPLY_LABELS = ['Questions answered', 'Explanations checked', 'Complaints raised', 'Complaints overdue'];

/** The summary figures in three short groups. A group with nothing in the window says so in one line. */
export function SummaryTiles({ data }: { data: Summary | undefined }) {
  const quietReplies = data !== undefined && data.questions === 0 && data.complaints === 0 && data.complaints_overdue === 0;
  return (
    <Stack sx={{ gap: 3 }}>
      <TileGroup title="Bills" columns={4} tiles={data ? billTiles(data) : pending(BILL_LABELS)}
        empty={data?.bills_read === 0 ? 'No bills read in this window yet.' : null} />
      <TileGroup title="Bill reading" columns={6} tiles={data ? readTiles(data.reads) : pending(READ_LABELS)}
        empty={data?.reads.total === 0 ? 'No reads yet. Figures on read quality appear after the first photo.' : null} />
      <TileGroup title="Questions and complaints" columns={4} tiles={data ? replyTiles(data) : pending(REPLY_LABELS)}
        empty={quietReplies ? 'No questions or complaints in this window yet.' : null} />
    </Stack>
  );
}
