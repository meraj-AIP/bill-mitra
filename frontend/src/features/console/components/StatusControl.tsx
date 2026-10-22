import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Button, CircularProgress, Menu, MenuItem, Stack } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, StatusChip, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';
import { SendStatus } from '@/shared/components/SendStatus';
import { useConfirm } from '@/shared/feedback';

import { useSetStatus } from '../api/consoleApi';

const closed = (s: ComplaintStatus) => s === 'Resolved' || s === 'Rejected';

/** A closed complaint can only be reopened; swapping Resolved for Rejected would tell the consumer twice. */
function choices(current: ComplaintStatus): ComplaintStatus[] {
  if (closed(current)) return ['Open', 'In progress'];
  return COMPLAINT_STATUSES.filter((s) => s !== current);
}

/** The current status, a menu of the moves that make sense, and one confirmation, since the consumer is told each time. */
export function StatusControl({ complaint }: { complaint: ComplaintDetail }) {
  const setStatus = useSetStatus(complaint.ticket);
  const confirm = useConfirm();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const reopen = closed(complaint.status);
  const change = async (next: ComplaintStatus) => {
    setAnchor(null);
    const closing = closed(next);
    if (!(await confirm({ title: reopen ? `Reopen as ${next}?` : `Set to ${next}?`, confirmLabel: reopen ? 'Reopen' : `Set to ${next}`,
      tone: closing ? 'warning' : 'default', body: 'The consumer gets a short message about it.',
      points: closing ? ['It leaves the open queue. It can be reopened later if needed.'] : undefined }))) return;
    setStatus.mutate(next);
  };

  return (
    <Stack sx={{ gap: 1.25 }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
        <StatusChip status={complaint.status} />
        <Button size="small" endIcon={setStatus.isPending ? <CircularProgress size={14} aria-hidden /> : <ExpandMoreRoundedIcon />}
          onClick={(e) => setAnchor(e.currentTarget)} disabled={setStatus.isPending}>
          {reopen ? 'Reopen' : 'Change'}
        </Button>
      </Stack>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        {choices(complaint.status).map((s) => (
          <MenuItem key={s} onClick={() => void change(s)}>{reopen ? `Reopen as ${s}` : s}</MenuItem>
        ))}
      </Menu>
      <SendStatus state={setStatus} />
    </Stack>
  );
}
