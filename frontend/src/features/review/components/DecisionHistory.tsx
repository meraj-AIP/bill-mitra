import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import { Alert, Box, Button, CircularProgress, Stack } from '@mui/material';

import { useAuth } from '@/features/auth';
import { EmptyState } from '@/shared/components/States';

import { useDecisionAction } from '../api/reviewApi';
import type { CaseDetail, Decision } from '../api/types';
import { DecisionCard } from './DecisionCard';
import { Panel } from './Panel';

function Withdraw({ c, d }: { c: CaseDetail; d: Decision }) {
  const withdraw = useDecisionAction(c.ticket, 'withdraw');
  return (
    <Stack sx={{ mt: 1.5, gap: 1, alignItems: 'flex-end' }}>
      <Button size="small" variant="outlined" color="inherit" disabled={withdraw.isPending} onClick={() => withdraw.mutate({ id: d.id })}
        startIcon={withdraw.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
        Withdraw this decision
      </Button>
      {withdraw.error && <Alert severity="error" sx={{ alignSelf: 'stretch' }}>{withdraw.error.message}</Alert>}
    </Stack>
  );
}

/** Every decision on the case, newest first. Revisions never overwrite each other; each one stays here. */
export function DecisionHistory({ c }: { c: CaseDetail }) {
  const { account } = useAuth();
  const canWithdraw = (d: Decision) => d.status === 'pending_approval' && (d.proposed_by.id === account?.id || c.can.approve);
  // Approvers see someone else's open decision in the approvals panel; their own stays here so they can withdraw it.
  const shown = c.can.approve
    ? c.decisions.filter((d) => d.status !== 'pending_approval' || d.proposed_by.id === account?.id) : c.decisions;
  return (
    <Panel title="Decision history" caption="Each approved reduction becomes the next revision of this bill. The original bill is never edited.">
      {shown.length === 0 ? (
        <Box sx={{ mx: -2 }}>
          <EmptyState icon={<HistoryOutlinedIcon />} title="No decisions yet" hint="Decisions on this case, and any revisions they create, are listed here." />
        </Box>
      ) : (
        <Stack sx={{ gap: 1.5 }}>
          {shown.map((d) => (
            <DecisionCard key={d.id} d={d}>{canWithdraw(d) && <Withdraw c={c} d={d} />}</DecisionCard>
          ))}
        </Stack>
      )}
    </Panel>
  );
}
