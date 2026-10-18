import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import { Box, Button, Checkbox, Chip, CircularProgress, Link as MuiLink, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { dateTime, monthLabel, shortDate } from '@/shared/lib/format';

import type { Proposal } from '../api/approvalsApi';
import { KIND_ACTION, KIND_COLOR, KIND_LABEL, STATE_LABEL } from '../model/labels';

export interface CardActions {
  /** The proposal an action is running on, so only that card shows a spinner. */
  busyId: number | null;
  selected: boolean;
  onSelect: (id: number, on: boolean) => void;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}

const caseLink = (p: Proposal) => (p.complaint_kind === 'wrong_reading' ? `/review/${p.ticket}` : `/console/complaints/${p.ticket}`);

function Meta({ p }: { p: Proposal }) {
  const parts = [p.section ?? p.discom, p.bill_month ? `Bill ${monthLabel(p.bill_month)}` : null, `Raised ${shortDate(p.complaint_created_at)}`];
  return (
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      {parts.filter(Boolean).join(' · ')}
    </Typography>
  );
}

function Outcome({ p }: { p: Proposal }) {
  const who = p.decided_by_name ? ` by ${p.decided_by_name}` : '';
  const when = p.decided_at ? ` on ${dateTime(p.decided_at)}` : '';
  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
      <Chip size="small" variant="outlined" label={STATE_LABEL[p.state]} color={p.state === 'approved' ? 'success' : 'default'} />
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>{`${who}${when}`.trim() || 'System'}</Typography>
      {p.note && <Typography variant="body2" sx={{ color: 'text.secondary' }}>{`· ${p.note}`}</Typography>}
    </Stack>
  );
}

function Pending({ p, actions }: { p: Proposal; actions: CardActions }) {
  const busy = actions.busyId === p.id;
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' }, justifyContent: 'space-between' }}>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>{KIND_ACTION[p.kind]}</Typography>
      <Stack direction="row" sx={{ gap: 1, flexShrink: 0 }}>
        <Button size="small" color="inherit" disabled={busy} onClick={() => actions.onReject(p.id)}>Reject</Button>
        <Button size="small" variant="contained" disabled={busy} onClick={() => actions.onApprove(p.id)}
          startIcon={busy ? <CircularProgress size={14} color="inherit" aria-hidden /> : <CheckRoundedIcon />}>
          Approve
        </Button>
      </Stack>
    </Stack>
  );
}

/** One prepared action: what it is, the complaint it is for, why the rules propose it, and Approve or Reject. */
export function ProposalCard({ p, actions }: { p: Proposal; actions: CardActions }) {
  const pending = p.state === 'pending';
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 }, borderColor: actions.selected ? 'primary.main' : 'divider' }}>
      <Stack direction="row" sx={{ gap: 1.5, alignItems: 'flex-start' }}>
        {pending && (
          <Checkbox checked={actions.selected} onChange={(e) => actions.onSelect(p.id, e.target.checked)} sx={{ mt: -0.75, ml: -1 }}
            slotProps={{ input: { 'aria-label': `Select ${p.ticket}` } }} />
        )}
        <Stack sx={{ gap: 1.25, flex: 1, minWidth: 0 }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip size="small" color={KIND_COLOR[p.kind]} label={KIND_LABEL[p.kind]} />
            <MuiLink component={Link} to={caseLink(p)} variant="subtitle2" sx={{ fontFamily: 'monospace' }}>{p.ticket}</MuiLink>
            <Typography variant="subtitle2" component="span">{p.type_label ?? 'Complaint'}</Typography>
          </Stack>
          <Meta p={p} />
          <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'grid', gap: 0.5 }}>
            {p.why.map((line) => <Typography key={line} component="li" variant="body2">{line}</Typography>)}
          </Box>
          {pending ? <Pending p={p} actions={actions} /> : <Outcome p={p} />}
        </Stack>
      </Stack>
    </Paper>
  );
}
