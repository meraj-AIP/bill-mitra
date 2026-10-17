import { Box, Typography } from '@mui/material';

import { Panel } from '@/shared/components/Panel';
import { monthLabel, rupees } from '@/shared/lib/format';

import type { ComplaintDetail } from '../api/types';
import { CHANNEL_LABEL, OWNERSHIP_LABEL, SOURCE_LABEL } from '../model/labels';

function Fact({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography component="dt" variant="caption" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography component="dd" variant="body2"
        sx={{ m: 0, fontWeight: muted ? 400 : 600, color: muted ? 'text.secondary' : 'text.primary', fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Box>
  );
}

function source(c: ComplaintDetail): string | null {
  if (c.source) return SOURCE_LABEL[c.source];
  return c.channel ? CHANNEL_LABEL[c.channel] : null;
}

const STAFF_SOURCES = new Set(['call_centre', 'office', 'field']);

function raisedBy(c: ComplaintDetail): string {
  if (c.raised_by) return c.raised_by;
  return c.source && STAFF_SOURCES.has(c.source) ? 'Staff' : 'The consumer';
}

function where(c: ComplaintDetail): Array<[string, string | null]> {
  const month = c.bill_month ?? c.bill?.bill_month ?? null;
  return [
    ['Service number', c.service_masked ?? c.bill?.service_masked ?? null],
    ['DISCOM', c.discom ?? c.bill?.discom ?? null],
    ['Section', c.section ?? null],
    ['Bill month', month ? monthLabel(month) : null],
  ];
}

function how(c: ComplaintDetail): Array<[string, string | null]> {
  return [
    // A zero amount means none was given, so it reads as not recorded rather than Rs 0.
    ['Amount in question', c.amount ? rupees(c.amount) : null],
    ['Source', source(c)],
    ['Raised by', raisedBy(c)],
    ['Ownership', c.ownership ? OWNERSHIP_LABEL[c.ownership] : null],
    ['Handled by', c.assignee?.name ?? null],
  ];
}

/** What we know about the consumer and the complaint. The service number is always masked. */
export function ComplaintFacts({ complaint: c }: { complaint: ComplaintDetail }) {
  const facts = [...where(c), ...how(c)];
  return (
    <Panel title="On file" caption="What we hold for this complaint.">
      <Box component="dl" sx={{ m: 0, display: 'grid', columnGap: 3, rowGap: 2, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))' } }}>
        {facts.map(([label, value]) => <Fact key={label} label={label} value={value ?? 'Not recorded'} muted={!value} />)}
      </Box>
      {c.description && (
        <Box sx={{ mt: 2.5, pt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mb: 0.5 }}>In their words</Typography>
          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxWidth: '70ch' }}>{c.description}</Typography>
        </Box>
      )}
    </Panel>
  );
}
