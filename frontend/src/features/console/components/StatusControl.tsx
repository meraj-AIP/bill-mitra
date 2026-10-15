import { Alert, Button, CircularProgress, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';

import { useSetStatus } from '../api/consoleApi';

/** Changing status on its own also sends the consumer a short status message. */
export function StatusControl({ complaint }: { complaint: ComplaintDetail }) {
  const setStatus = useSetStatus(complaint.ticket);
  const [next, setNext] = useState<ComplaintStatus | ''>('');

  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: { md: 300 } }}>
      <Typography variant="subtitle2" component="h2">Change status</Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mb: 1.5 }}>
        The consumer gets a short message about the change.
      </Typography>
      <Stack direction="row" sx={{ gap: 1 }}>
        <TextField select size="small" label="New status" value={next} fullWidth
          onChange={(e) => setNext(e.target.value as ComplaintStatus | '')}>
          {COMPLAINT_STATUSES.filter((s) => s !== complaint.status).map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
        </TextField>
        <Button variant="outlined" disabled={!next || setStatus.isPending}
          onClick={() => next && setStatus.mutate(next, { onSuccess: () => setNext('') })}
          startIcon={setStatus.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          Update
        </Button>
      </Stack>
      {setStatus.error && <Alert severity="error" sx={{ mt: 1.5 }}>{setStatus.error.message}</Alert>}
    </Paper>
  );
}
