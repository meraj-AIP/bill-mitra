import { Chip, MenuItem, Stack, TextField } from '@mui/material';

import { PROPOSAL_KINDS, PROPOSAL_STATES, type ProposalKind } from '../api/approvalsApi';
import { KIND_LABEL, STATE_LABEL } from '../model/labels';

interface Props {
  kind: string;
  state: string;
  counts: Partial<Record<ProposalKind, number>> | undefined;
  onKind: (kind: string) => void;
  onState: (state: string) => void;
}

/** One chip per kind with what waits in it, and which proposals to show: waiting, or what became of them. */
export function ApprovalFilters({ kind, state, counts, onKind, onState }: Props) {
  const total = Object.values(counts ?? {}).reduce((sum, n) => sum + (n ?? 0), 0);
  return (
    <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 1.5, alignItems: { md: 'center' }, justifyContent: 'space-between' }}>
      <Stack direction="row" role="group" aria-label="Kind" sx={{ gap: 1, flexWrap: 'wrap' }}>
        <Chip label={`All · ${total}`} color={kind ? 'default' : 'primary'} variant={kind ? 'outlined' : 'filled'} onClick={() => onKind('')} />
        {PROPOSAL_KINDS.map((k) => (
          <Chip key={k} label={`${KIND_LABEL[k]} · ${counts?.[k] ?? 0}`} onClick={() => onKind(k)}
            color={kind === k ? 'primary' : 'default'} variant={kind === k ? 'filled' : 'outlined'} />
        ))}
      </Stack>
      <TextField select size="small" label="Show" value={state || 'pending'} onChange={(e) => onState(e.target.value)} sx={{ minWidth: 200 }}>
        {PROPOSAL_STATES.map((s) => <MenuItem key={s} value={s}>{STATE_LABEL[s]}</MenuItem>)}
      </TextField>
    </Stack>
  );
}
