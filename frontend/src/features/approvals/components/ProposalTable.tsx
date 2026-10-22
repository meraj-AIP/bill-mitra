import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import {
  Box, Button, Checkbox, Chip, CircularProgress, Link as MuiLink, Skeleton, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Typography,
} from '@mui/material';
import { Link } from 'react-router-dom';

import { daysSince, monthLabel, shortDate } from '@/shared/lib/format';

import type { Proposal } from '../api/approvalsApi';
import { KIND_ACTION, KIND_COLOR, KIND_EFFECT, KIND_LABEL, STATE_LABEL } from '../model/labels';

export interface RowActions {
  /** The proposal an action is running on, so only that row shows a spinner. */
  busyId: number | null;
  isSelected: (id: number) => boolean;
  onSelect: (id: number, on: boolean) => void;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}

const caseLink = (p: Proposal) => (p.complaint_kind === 'wrong_reading' ? `/review/${p.ticket}` : `/console/complaints/${p.ticket}`);
const waited = (iso: string) => { const d = daysSince(iso); return d === 0 ? 'Today' : d === 1 ? '1 day' : `${d} days`; };

function Muted({ children }: { children: string }) {
  return <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{children}</Typography>;
}

function Decide({ p, actions }: { p: Proposal; actions: RowActions }) {
  const busy = actions.busyId === p.id;
  return (
    <Stack direction="row" sx={{ gap: 0.5, justifyContent: 'flex-end' }}>
      <Button size="small" color="inherit" disabled={busy} onClick={() => actions.onReject(p.id)}>Reject</Button>
      <Button size="small" variant="contained" disabled={busy} onClick={() => actions.onApprove(p.id)} title={KIND_ACTION[p.kind]}
        startIcon={busy ? <CircularProgress size={14} color="inherit" aria-hidden /> : <CheckRoundedIcon />}>
        Approve
      </Button>
    </Stack>
  );
}

function Outcome({ p }: { p: Proposal }) {
  return (
    <Box sx={{ textAlign: 'right' }}>
      <Chip size="small" variant="outlined" label={STATE_LABEL[p.state]} color={p.state === 'approved' ? 'success' : 'default'} />
      <Muted>{[p.decided_by_name, p.decided_at ? shortDate(p.decided_at) : null].filter(Boolean).join(', ') || 'System'}</Muted>
      {p.note && <Muted>{p.note}</Muted>}
    </Box>
  );
}

function Row({ p, actions }: { p: Proposal; actions: RowActions }) {
  const pending = p.state === 'pending';
  const selected = actions.isSelected(p.id);
  return (
    <TableRow hover selected={selected} sx={{ verticalAlign: 'top' }}>
      <TableCell padding="checkbox">
        {pending && <Checkbox checked={selected} onChange={(e) => actions.onSelect(p.id, e.target.checked)} slotProps={{ input: { 'aria-label': `Select ${p.ticket}` } }} />}
      </TableCell>
      <TableCell sx={{ minWidth: 190 }}>
        <Chip size="small" color={KIND_COLOR[p.kind]} label={KIND_LABEL[p.kind]} />
        <Muted>{KIND_EFFECT[p.kind]}</Muted>
      </TableCell>
      <TableCell sx={{ minWidth: 180 }}>
        <MuiLink component={Link} to={caseLink(p)} variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{p.ticket}</MuiLink>
        <Typography variant="body2">{p.type_label ?? 'Complaint'}</Typography>
        <Muted>{[p.section ?? p.discom, p.bill_month ? `${monthLabel(p.bill_month)} bill` : null].filter(Boolean).join(', ')}</Muted>
      </TableCell>
      <TableCell sx={{ minWidth: 260 }}>
        <Box component="ul" sx={{ m: 0, pl: 2, display: 'grid', gap: 0.25 }}>
          {p.why.map((line) => <Typography key={line} component="li" variant="body2">{line}</Typography>)}
        </Box>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <Typography variant="body2">{waited(p.created_at)}</Typography>
        <Muted>{`Raised ${shortDate(p.complaint_created_at)}`}</Muted>
      </TableCell>
      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{pending ? <Decide p={p} actions={actions} /> : <Outcome p={p} />}</TableCell>
    </TableRow>
  );
}

/** One row per prepared action: what approving does, the complaint, why the rules propose it, and the decision. */
export function ProposalTable({ rows, loadingRows, dimmed, actions }: { rows: Proposal[] | undefined; loadingRows: number; dimmed: boolean; actions: RowActions }) {
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      <Table size="small" aria-label="Prepared actions">
        <TableHead>
          <TableRow>
            <TableCell padding="checkbox" />
            <TableCell>Proposed action</TableCell>
            <TableCell>Complaint</TableCell>
            <TableCell>Why the rules propose it</TableCell>
            <TableCell>Waiting</TableCell>
            <TableCell align="right">Decision</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={6}><Skeleton height={36} /></TableCell></TableRow>
          ))}
          {rows?.map((p) => <Row key={p.id} p={p} actions={actions} />)}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
