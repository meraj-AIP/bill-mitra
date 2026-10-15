import { Alert, Button, CircularProgress, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, type ComplaintStatus } from '@/features/complaints';

import { useBulk, type BulkResult } from '../api/actionsApi';

interface BulkBarProps {
  tickets: string[];
  onDone: () => void;
}

function Outcome({ result }: { result: BulkResult }) {
  const skipped = result.skipped.map((s) => `${s.ticket} (${s.reason})`).join(', ');
  return (
    <Alert severity={result.skipped.length ? 'warning' : 'success'}>
      Done for {result.done.length}.{skipped ? ` Skipped: ${skipped}.` : ''}
    </Alert>
  );
}

/** Acts on the selected complaints. The explanation is the rules-only draft for each bill, with no model wording. */
export function BulkBar({ tickets, onDone }: BulkBarProps) {
  const bulk = useBulk();
  const [status, setStatus] = useState<ComplaintStatus | ''>('');
  const [result, setResult] = useState<BulkResult | null>(null);
  const run = async (body: { status?: ComplaintStatus; send_explanation: boolean }) => {
    setResult(await bulk.mutateAsync({ tickets, ...body }));
    setStatus('');
    onDone();
  };

  return (
    <Stack sx={{ gap: 1 }}>
      {result && <Outcome result={result} />}
      {bulk.isError && <Alert severity="error">{bulk.error.message}</Alert>}
      {tickets.length > 0 && (
        <Paper variant="outlined" sx={{ p: 1.5, display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center', bgcolor: 'info.light' }}>
          <Typography variant="subtitle2" sx={{ flex: 1, minWidth: 140 }}>{tickets.length} selected</Typography>
          <Button variant="contained" size="small" disabled={bulk.isPending}
            startIcon={bulk.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : undefined}
            onClick={() => void run({ status: 'Resolved', send_explanation: true })}>
            Send the checked explanation and resolve
          </Button>
          <TextField select size="small" label="Set status" value={status} sx={{ minWidth: 160 }} disabled={bulk.isPending}
            onChange={(e) => { const s = e.target.value as ComplaintStatus; setStatus(s); void run({ status: s, send_explanation: false }); }}>
            {COMPLAINT_STATUSES.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
          </TextField>
        </Paper>
      )}
    </Stack>
  );
}
