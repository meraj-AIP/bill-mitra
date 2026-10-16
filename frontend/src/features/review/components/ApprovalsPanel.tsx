import { Alert, Button, CircularProgress, Stack, TextField } from '@mui/material';
import { useState } from 'react';

import { useAuth } from '@/features/auth';

import { useDecisionAction } from '../api/reviewApi';
import type { CaseDetail, Decision } from '../api/types';
import { DecisionCard } from './DecisionCard';
import { Panel } from './Panel';

function Review({ c, d }: { c: CaseDetail; d: Decision }) {
  const { account } = useAuth();
  const approve = useDecisionAction(c.ticket, 'approve');
  const reject = useDecisionAction(c.ticket, 'reject');
  const [note, setNote] = useState('');
  const own = d.proposed_by.id === account?.id;
  const busy = approve.isPending || reject.isPending;
  const error = approve.error ?? reject.error;
  const body = note.trim() ? { note: note.trim() } : undefined;
  return (
    <DecisionCard d={d}>
      <Stack sx={{ gap: 1.5, mt: 2 }}>
        {own ? (
          <Alert severity="info">You proposed this decision, so someone else must approve or reject it. To change it, withdraw it from the history below.</Alert>
        ) : (
          <TextField size="small" label="Note to the AE" multiline minRows={2} value={note} onChange={(e) => setNote(e.target.value)}
            helperText="Needed to reject, so the AE knows what to change. Optional when approving." />
        )}
        {error && <Alert severity="error">{error.message}</Alert>}
        <Stack direction="row" sx={{ gap: 1, justifyContent: 'flex-end' }}>
          <Button color="error" variant="outlined" disabled={own || busy || !note.trim()}
            onClick={() => reject.mutate({ id: d.id, body: { note: note.trim() } })}
            startIcon={reject.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            Reject
          </Button>
          <Button variant="contained" color="success" disabled={own || busy}
            onClick={() => approve.mutate(body ? { id: d.id, body } : { id: d.id })}
            startIcon={approve.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            Approve
          </Button>
        </Stack>
      </Stack>
    </DecisionCard>
  );
}

/** Decisions above the AE's limit wait here for a billing approver. */
export function ApprovalsPanel({ c }: { c: CaseDetail }) {
  const pending = c.decisions.filter((d) => d.status === 'pending_approval');
  if (!c.can.approve || pending.length === 0) return null;
  return (
    <Panel title="Waiting for your approval" tone="primary"
      caption="Approving records the revision and tells the consumer. Rejecting sends the case back to the AE with your note.">
      <Stack sx={{ gap: 2 }}>{pending.map((d) => <Review key={d.id} c={c} d={d} />)}</Stack>
    </Panel>
  );
}
