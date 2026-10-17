import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PrintOutlinedIcon from '@mui/icons-material/PrintOutlined';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';

import { dateTime, monthLabel, rupees } from '@/shared/lib/format';

import type { CaseDetail, EvidenceSource } from '../api/types';
import { EVIDENCE_STATUS } from '../model/labels';
import { AttachedBills } from './AttachedBills';
import { Panel } from './Panel';

/** A long run of months reads better as its two ends. */
function monthsText(months: string[]): string {
  if (months.length === 0) return 'No months';
  const sorted = [...months].sort();
  if (sorted.length <= 3) return sorted.map(monthLabel).join(', ');
  return `${monthLabel(sorted[0])} to ${monthLabel(sorted[sorted.length - 1])}, ${sorted.length} months`;
}

function SourceRow({ s }: { s: EvidenceSource }) {
  const status = EVIDENCE_STATUS[s.status];
  return (
    <Box component="li" sx={{ display: 'grid', gap: { xs: 0.5, sm: 2 }, py: 1.25, borderTop: 1, borderColor: 'divider', alignItems: 'baseline',
      gridTemplateColumns: { xs: '1fr', sm: '112px minmax(0, 1fr)' }, '&:first-of-type': { borderTop: 0, pt: 0 },
      '@media print': { gridTemplateColumns: '112px minmax(0, 1fr)', breakInside: 'avoid' } }}>
      <Box>
        <Chip size="small" label={status.label} color={status.tone} variant={s.status === 'included' ? 'filled' : 'outlined'} />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <Typography variant="subtitle2" component="p">{s.label}</Typography>
          {s.months.length > 0 && <Typography variant="caption" sx={{ color: 'text.secondary' }}>{monthsText(s.months)}</Typography>}
        </Stack>
        <Typography variant="body2" sx={{ color: 'text.secondary', overflowWrap: 'anywhere' }}>{s.detail}</Typography>
      </Box>
    </Box>
  );
}

/** A month is waiting only while a request for earlier bills is still open; once answered, a gap stays a gap. */
function RequestedMonths({ requested, received, open }: { requested: string[]; received: string[]; open: boolean }) {
  if (requested.length === 0) {
    return <Typography variant="body2" sx={{ color: 'text.secondary' }}>No earlier bills were needed; the months before this bill are on file.</Typography>;
  }
  const got = new Set(received);
  return (
    <Stack direction="row" component="ul" aria-label="Requested months" sx={{ listStyle: 'none', m: 0, p: 0, gap: 1, flexWrap: 'wrap' }}>
      {requested.map((m) => (
        <Chip component="li" key={m} size="small" label={`${monthLabel(m)}, ${got.has(m) ? 'received' : open ? 'waiting' : 'not sent'}`}
          color={got.has(m) ? 'success' : 'default'} variant="outlined"
          icon={got.has(m) ? <CheckCircleIcon fontSize="small" /> : undefined} />
      ))}
    </Stack>
  );
}

function Subheading({ children }: { children: string }) {
  return <Typography variant="subtitle1" component="h3" sx={{ mt: 2.5, mb: 1 }}>{children}</Typography>;
}

/** Only on paper: the case facts a printed pack needs, since the page header is not printed. */
function PrintHeading({ c }: { c: CaseDetail }) {
  const facts = [
    `Section: ${c.section ?? 'not mapped'}`, `DISCOM: ${c.discom}`, `Bill month: ${monthLabel(c.bill_month)}`,
    `Service number: ${c.service_masked ?? 'not read'}`, c.printed_amount === null ? null : `Printed amount: ${rupees(c.printed_amount)}`,
    `Opened: ${dateTime(c.created_at)}`,
  ].filter(Boolean);
  return (
    <Box sx={{ display: 'none', mb: 2, '@media print': { display: 'block' } }}>
      <Typography variant="h1" component="p" sx={{ fontSize: '1.5rem' }}>Evidence pack, case {c.ticket}</Typography>
      <Typography variant="body2" sx={{ mt: 0.5 }}>{facts.join('. ')}.</Typography>
    </Box>
  );
}

/** What the system gathered on its own when the consumer reported the bill. */
export function EvidencePackPanel({ c }: { c: CaseDetail }) {
  const pack = c.evidence_pack;
  return (
    <Box sx={{ '@media print': { '& .MuiPaper-root': { border: 0 }, '& [data-screen-only]': { display: 'none' } } }}>
      <Panel title="Evidence pack" caption="Gathered automatically when the consumer reported the bill."
        aside={(
          <Box data-screen-only>
            <Button size="small" variant="outlined" startIcon={<PrintOutlinedIcon />} onClick={() => window.print()}>Print evidence pack</Button>
          </Box>
        )}>
        <PrintHeading c={c} />
        <Box component="ul" aria-label="Evidence sources" sx={{ listStyle: 'none', m: 0, p: 0 }}>
          {pack.sources.map((s) => <SourceRow key={s.key} s={s} />)}
        </Box>
        <Subheading>Earlier bills requested</Subheading>
        <RequestedMonths requested={pack.requested_months} received={pack.received_months}
          open={c.requests.some((r) => r.kind === 'earlier_bills' && r.status === 'open')} />
        <Subheading>Attached bills</Subheading>
        <AttachedBills bills={pack.attached_bills} />
      </Panel>
    </Box>
  );
}
