import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import { Alert, Box, Button, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import { useAssign, useUnmask } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';

/** Shows the full number only after a deliberate click; the server records each view, and it is never cached. */
export function UnmaskControl({ c }: { c: CaseDetail }) {
  const unmask = useUnmask(c.ticket);
  const shown = unmask.data?.service_number;
  if (shown) {
    return (
      <Box>
        <Typography variant="subtitle1" component="p" sx={{ fontFamily: 'monospace', letterSpacing: '0.04em' }}>{shown}</Typography>
        <Typography variant="caption" sx={{ color: 'warning.dark' }}>This view was recorded in the audit log.</Typography>
      </Box>
    );
  }
  return (
    <Stack sx={{ alignItems: 'flex-start', gap: 0.25 }}>
      <Typography variant="subtitle1" component="p" sx={{ fontFamily: 'monospace' }}>{c.service_masked ?? 'Not printed'}</Typography>
      {c.can.unmask && c.service_masked && (
        <Button size="small" startIcon={unmask.isPending ? <CircularProgress size={14} aria-hidden /> : <VisibilityOutlinedIcon />}
          onClick={() => unmask.mutate()} disabled={unmask.isPending} sx={{ ml: -0.75, py: 0 }}>
          Show full number
        </Button>
      )}
      {unmask.error && <Typography variant="caption" sx={{ color: 'error.main' }}>{unmask.error.message}</Typography>}
    </Stack>
  );
}

export function ReassignControl({ c }: { c: CaseDetail }) {
  const assign = useAssign(c.ticket);
  const [to, setTo] = useState('');
  const others = c.assignable.filter((p) => p.id !== c.assignee?.id);
  if (!c.can.reassign) return null;
  return (
    <Stack sx={{ gap: 1, minWidth: { md: 280 } }}>
      <Stack direction="row" sx={{ gap: 1 }}>
        <TextField select size="small" label="Reassign to" value={to} onChange={(e) => setTo(e.target.value)} fullWidth
          disabled={others.length === 0} helperText={others.length === 0 ? 'Nobody else in scope can take this case.' : undefined}>
          {others.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        <Button variant="outlined" disabled={!to || assign.isPending} sx={{ flexShrink: 0, alignSelf: 'flex-start', minHeight: 40 }}
          onClick={() => assign.mutate(to, { onSuccess: () => setTo('') })}
          startIcon={assign.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
          Move
        </Button>
      </Stack>
      {assign.error && <Alert severity="error">{assign.error.message}</Alert>}
    </Stack>
  );
}
