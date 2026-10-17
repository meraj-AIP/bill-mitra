import { Alert, Button, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import type { ComplaintDetail, Person } from '@/features/complaints';

import { useAssign } from '../api/actionsApi';

/** Moves the complaint to someone in the same units. The server sends the list of people it allows. */
export function AssignControl({ complaint, people }: { complaint: ComplaintDetail; people: Person[] }) {
  const assign = useAssign(complaint.ticket);
  const [to, setTo] = useState('');
  const others = people.filter((p) => p.id !== complaint.assignee?.id);
  if (others.length === 0) {
    return <Typography variant="body2" sx={{ color: 'text.secondary' }}>No one else in these units can take it.</Typography>;
  }
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        {complaint.assignee ? `With ${complaint.assignee.name} now.` : 'Not with anyone yet.'}
      </Typography>
      <Stack direction="row" sx={{ gap: 1 }}>
        <TextField select size="small" label="Move to" value={to} fullWidth onChange={(e) => setTo(e.target.value)}>
          {others.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        <Button variant="outlined" disabled={!to || assign.isPending} sx={{ flexShrink: 0 }}
          onClick={() => assign.mutate(to, { onSuccess: () => setTo('') })}
          startIcon={assign.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          Assign
        </Button>
      </Stack>
      {assign.error && <Alert severity="error">{assign.error.message}</Alert>}
    </Stack>
  );
}
