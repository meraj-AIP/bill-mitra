import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Button, CircularProgress, Menu, MenuItem, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, StatusChip, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';
import { SendStatus } from '@/shared/components/SendStatus';

import { useSetStatus } from '../api/consoleApi';

const closed = (s: ComplaintStatus) => s === 'Resolved' || s === 'Rejected';

/** A closed complaint can only be reopened; swapping Resolved for Rejected would tell the consumer twice. */
function choices(current: ComplaintStatus): ComplaintStatus[] {
  if (closed(current)) return ['Open', 'In progress'];
  return COMPLAINT_STATUSES.filter((s) => s !== current);
}

/** The current status, a menu of the moves that make sense, and one confirm, since the consumer is told each time. */
export function StatusControl({ complaint }: { complaint: ComplaintDetail }) {
  const setStatus = useSetStatus(complaint.ticket);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [next, setNext] = useState<ComplaintStatus | null>(null);
  const reopen = closed(complaint.status);
  const confirm = (status: ComplaintStatus) => setStatus.mutate(status, { onSuccess: () => setNext(null) });

  return (
    <Stack sx={{ gap: 1.25 }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
        <StatusChip status={complaint.status} />
        <Button size="small" endIcon={<ExpandMoreRoundedIcon />} onClick={(e) => setAnchor(e.currentTarget)} disabled={setStatus.isPending}>
          {reopen ? 'Reopen' : 'Change'}
        </Button>
      </Stack>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        {choices(complaint.status).map((s) => (
          <MenuItem key={s} onClick={() => { setNext(s); setAnchor(null); }}>{reopen ? `Reopen as ${s}` : s}</MenuItem>
        ))}
      </Menu>
      {next && (
        <Stack sx={{ gap: 1, p: 1.25, borderRadius: 1.5, bgcolor: 'grey.50', border: 1, borderColor: 'divider' }}>
          <Typography variant="body2">Set to <b>{next}</b>? The consumer gets a short message about it.</Typography>
          <Stack direction="row" sx={{ gap: 1 }}>
            <Button size="small" variant="contained" disabled={setStatus.isPending}
              startIcon={setStatus.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}
              onClick={() => confirm(next)}>
              Confirm
            </Button>
            <Button size="small" onClick={() => setNext(null)}>Cancel</Button>
          </Stack>
        </Stack>
      )}
      <SendStatus state={setStatus} onTryAgain={next ? () => confirm(next) : undefined} />
    </Stack>
  );
}
