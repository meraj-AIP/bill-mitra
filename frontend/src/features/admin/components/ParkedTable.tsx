import { Button, CircularProgress, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';

import { dateTime, formatCount } from '@/shared/lib/format';

import type { ParkedJob } from '../api/operationsApi';
import { PARKED_KIND_LABEL } from '../model/labels';

export interface RowAction {
  /** The job id an action is running on, so only that row shows a spinner. */
  busyId: string | null;
  onRetry: (job: ParkedJob) => void;
  onDismiss: (job: ParkedJob) => void;
}

function Row({ job, action }: { job: ParkedJob; action: RowAction }) {
  const busy = action.busyId === job.id;
  return (
    <TableRow hover>
      <TableCell>{PARKED_KIND_LABEL[job.kind] ?? job.kind}</TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>{job.ticket ?? 'None'}</TableCell>
      <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }}>{formatCount(job.attempts)}</TableCell>
      <TableCell sx={{ overflowWrap: 'anywhere' }}>
        <Typography variant="body2" component="code" sx={{ fontFamily: 'monospace' }}>{job.last_error ?? 'Unknown'}</Typography>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap', color: 'text.secondary' }}>{dateTime(job.failed_at)}</TableCell>
      <TableCell align="right">
        <Stack direction="row" sx={{ gap: 0.5, justifyContent: 'flex-end' }}>
          <Button size="small" variant="outlined" disabled={busy} onClick={() => action.onRetry(job)}
            startIcon={busy ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            Retry
          </Button>
          <Button size="small" color="inherit" disabled={busy} onClick={() => action.onDismiss(job)}>Dismiss</Button>
        </Stack>
      </TableCell>
    </TableRow>
  );
}

export function ParkedTable({ rows, loadingRows, dimmed, action }: { rows: ParkedJob[] | undefined; loadingRows: number; dimmed: boolean; action: RowAction }) {
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1 }}>
      <Table size="small" aria-label="Parked failures">
        <TableHead>
          <TableRow>
            <TableCell>Kind</TableCell>
            <TableCell>Ticket</TableCell>
            <TableCell align="right">Attempts</TableCell>
            <TableCell>Last error</TableCell>
            <TableCell>Parked at</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={6}><Skeleton /></TableCell></TableRow>
          ))}
          {rows?.map((job) => <Row key={`${job.kind}-${job.id}`} job={job} action={action} />)}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
