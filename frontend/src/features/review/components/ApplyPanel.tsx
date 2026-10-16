import { Alert, Button, CircularProgress, Stack, TextField } from '@mui/material';
import { useState } from 'react';

import { useAuth } from '@/features/auth';
import { rupees } from '@/shared/lib/format';

import { useDecisionAction } from '../api/reviewApi';
import type { CaseDetail, Decision } from '../api/types';
import { Panel } from './Panel';

function Apply({ c, d }: { c: CaseDetail; d: Decision }) {
  const { account } = useAuth();
  const applied = useDecisionAction(c.ticket, 'applied');
  const [ref, setRef] = useState('');
  const own = d.proposed_by.id === account?.id;
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Alert severity="success" variant="outlined">
        Revision {d.revision ?? ''} approved: {rupees(d.original_amount)} to {rupees(d.revised_amount)}. Enter it in the DISCOM billing system, then record the reference here.
      </Alert>
      {own && <Alert severity="info">You proposed this decision, so someone else marks it applied.</Alert>}
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1, alignItems: { sm: 'flex-start' } }}>
        <TextField size="small" label="Billing reference" value={ref} onChange={(e) => setRef(e.target.value)} disabled={own}
          helperText="The adjustment or voucher number from the billing system." sx={{ flex: 1, maxWidth: 360 }} />
        <Button variant="contained" disabled={own || !ref.trim() || applied.isPending}
          onClick={() => applied.mutate({ id: d.id, body: { billing_ref: ref.trim() } })}
          startIcon={applied.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
          Mark applied
        </Button>
      </Stack>
      {applied.error && <Alert severity="error">{applied.error.message}</Alert>}
    </Stack>
  );
}

/** The last step: the revision is in the official bill. The consumer is told when this is recorded. */
export function ApplyPanel({ c }: { c: CaseDetail }) {
  const waiting = c.decisions.filter((d) => d.status === 'approved' && d.reduction > 0 && !d.applied_at);
  if (!c.can.mark_applied || waiting.length === 0) return null;
  return (
    <Panel title="Apply in billing" tone="primary">
      <Stack sx={{ gap: 2 }}>{waiting.map((d) => <Apply key={d.id} c={c} d={d} />)}</Stack>
    </Panel>
  );
}
