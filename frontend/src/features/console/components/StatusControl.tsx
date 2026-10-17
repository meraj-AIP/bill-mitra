import { Alert, Button, CircularProgress, MenuItem, Stack, TextField } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';

import { useSetStatus } from '../api/consoleApi';

/** Changing status on its own also sends the consumer a short status message. */
export function StatusControl({ complaint }: { complaint: ComplaintDetail }) {
  const setStatus = useSetStatus(complaint.ticket);
  const [next, setNext] = useState<ComplaintStatus | ''>('');

  return (
    <Stack sx={{ gap: 1.5 }}>
      <Stack direction="row" sx={{ gap: 1 }}>
        <TextField select size="small" label="New status" value={next} fullWidth
          onChange={(e) => setNext(e.target.value as ComplaintStatus | '')}>
          {COMPLAINT_STATUSES.filter((s) => s !== complaint.status).map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
        </TextField>
        <Button variant="outlined" disabled={!next || setStatus.isPending} sx={{ flexShrink: 0 }}
          onClick={() => next && setStatus.mutate(next, { onSuccess: () => setNext('') })}
          startIcon={setStatus.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          Update
        </Button>
      </Stack>
      {setStatus.error && <Alert severity="error">{setStatus.error.message}</Alert>}
    </Stack>
  );
}
