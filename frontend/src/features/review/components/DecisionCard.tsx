import { Box, Chip, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { dateTime, formatCount, rupees } from '@/shared/lib/format';

import type { Decision } from '../api/types';
import { DECISION_KIND, DECISION_STATUS, REASON } from '../model/labels';

function Line({ children }: { children: ReactNode }) {
  return <Typography variant="body2" sx={{ color: 'text.secondary' }}>{children}</Typography>;
}

function amounts(d: Decision): string {
  if (d.kind === 'correct' || d.reduction === 0) return `No change to ${rupees(d.original_amount)}`;
  return `${rupees(d.original_amount)} to ${rupees(d.revised_amount)}, ${rupees(d.reduction)} off`;
}

function Trail({ d }: { d: Decision }) {
  return (
    <Stack sx={{ mt: 1.25, pt: 1.25, borderTop: 1, borderColor: 'divider', gap: 0.25 }}>
      <Line>Proposed by {d.proposed_by.name}, {dateTime(d.proposed_at)}</Line>
      {d.decided_by && d.decided_at && (
        <Line>{d.status === 'rejected' ? 'Rejected' : 'Approved'} by {d.decided_by.name}, {dateTime(d.decided_at)}{d.decision_note ? `: ${d.decision_note}` : ''}</Line>
      )}
      {d.applied_at && <Line>Applied {dateTime(d.applied_at)}{d.billing_ref ? `, billing reference ${d.billing_ref}` : ''}</Line>}
    </Stack>
  );
}

/** One decision as recorded: what was proposed, by whom, on what evidence, and what happened to it. */
export function DecisionCard({ d, children }: { d: Decision; children?: ReactNode }) {
  const status = DECISION_STATUS[d.status];
  return (
    <Box component="article" sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.75 }}>
        <Typography variant="subtitle1" component="h3">{DECISION_KIND[d.kind].label}</Typography>
        <Chip size="small" label={status.label} color={status.tone} variant={d.status === 'pending_approval' ? 'filled' : 'outlined'} />
        {d.revision !== null && <Chip size="small" variant="outlined" label={`Revision ${d.revision}`} />}
        {d.applied_at && <Chip size="small" color="success" label="Applied in billing" />}
      </Stack>
      <Typography variant="h3" component="p" sx={{ fontVariantNumeric: 'tabular-nums', mb: 0.5 }}>{amounts(d)}</Typography>
      {d.corrected_present_reading !== null && (
        <Line>Corrected reading {formatCount(d.corrected_present_reading)}{d.corrected_units === null ? '' : `, ${formatCount(d.corrected_units)} units`}</Line>
      )}
      <Line>Reason: {REASON[d.reason_code]}</Line>
      <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{d.note}</Typography>
      {d.evidence.length > 0 && (
        <Stack direction="row" sx={{ gap: 0.75, mt: 1, flexWrap: 'wrap' }} aria-label="Evidence">
          {d.evidence.map((e) => <Chip key={`${e.kind}-${e.id}`} size="small" variant="outlined" label={e.label} sx={{ maxWidth: 320 }} />)}
        </Stack>
      )}
      <Trail d={d} />
      {children}
    </Box>
  );
}
