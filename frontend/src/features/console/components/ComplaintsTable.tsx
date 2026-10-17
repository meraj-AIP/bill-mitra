import { Checkbox, Chip, Link as MuiLink, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import { Link, useNavigate } from 'react-router-dom';

import { CHANNEL_LABEL, DemoChip, DueChip, PriorityChip, SOURCE_LABEL, StatusChip, TRIAGE, type ComplaintRow } from '@/features/complaints';
import { dateTime, monthLabel, rupees } from '@/shared/lib/format';

interface ComplaintsTableProps {
  rows: ComplaintRow[] | undefined;
  loadingRows: number;
  dimmed?: boolean;
  /** Turns on a checkbox per row for bulk actions. */
  selection?: { selected: Set<string>; onToggle: (ticket: string) => void; onToggleAll: (tickets: string[]) => void };
}

/** The server decides what is overdue, from the reply time promised to consumers. */
function Flags({ c }: { c: ComplaintRow }) {
  const triage = TRIAGE[c.triage];
  return (
    <Stack sx={{ gap: 0.5, alignItems: 'flex-start' }}>
      <StatusChip status={c.status} />
      <DueChip c={c} />
      <Chip size="small" variant="outlined" color={triage.tone} label={triage.label} title={triage.hint} />
      {c.delivery_failed && <Chip size="small" color="error" label="Reply not delivered" />}
    </Stack>
  );
}

/** Who holds it and whether the consumer owes an answer, under the ticket so they show first on a phone. */
function HolderChips({ c }: { c: ComplaintRow }) {
  if (!c.assignee_name && c.waiting_on !== 'consumer') return null;
  return (
    <Stack sx={{ gap: 0.5, mt: 0.5, alignItems: 'flex-start' }}>
      {c.assignee_name && (
        <Chip size="small" variant="outlined" label={`With ${c.assignee_name}`} title={`With ${c.assignee_name}`}
          sx={{ maxWidth: 160, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }} />
      )}
      {c.waiting_on === 'consumer' && <Chip size="small" color="info" label="Waiting on consumer" />}
    </Stack>
  );
}

/** Type, priority, source and place: the columns the complaints contract added. */
function DetailCells({ c }: { c: ComplaintRow }) {
  return (
    <>
      <TableCell sx={{ minWidth: 220, maxWidth: 340 }}>
        {c.type_label && <Typography variant="subtitle2" component="p">{c.type_label}</Typography>}
        <Typography variant="body2" sx={{ color: c.type_label ? 'text.secondary' : 'text.primary', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {c.issue}
        </Typography>
      </TableCell>
      <TableCell>{c.priority ? <PriorityChip priority={c.priority} /> : '-'}</TableCell>
      <TableCell sx={{ minWidth: 120 }}>
        <Typography variant="body2">{source(c)}</Typography>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        {c.discom ?? 'Unknown'}
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{c.section ?? monthLabel(c.bill_month)}</Typography>
      </TableCell>
    </>
  );
}

function source(c: ComplaintRow): string {
  if (c.source) return SOURCE_LABEL[c.source];
  return c.channel ? CHANNEL_LABEL[c.channel] : 'Unknown';
}

export function complaintPath(ticket: string): string {
  return `/console/complaints/${encodeURIComponent(ticket)}`;
}

/** Rows open the complaint on click; the ticket is also a real link so keyboards and new tabs work. */
export function ComplaintsTable({ rows, loadingRows, dimmed = false, selection }: ComplaintsTableProps) {
  const navigate = useNavigate();
  const columns = selection ? 9 : 8;
  const tickets = rows?.map((r) => r.ticket) ?? [];
  const allOn = tickets.length > 0 && tickets.every((t) => selection?.selected.has(t));
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      <Table size="small" aria-label="Complaints">
        <TableHead>
          <TableRow>
            {selection && (
              <TableCell padding="checkbox">
                <Checkbox size="small" checked={allOn} onChange={() => selection.onToggleAll(tickets)}
                  slotProps={{ input: { 'aria-label': 'Select every complaint on this page' } }} />
              </TableCell>
            )}
            <TableCell>Ticket</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Type and issue</TableCell>
            <TableCell>Priority</TableCell>
            <TableCell>Source</TableCell>
            <TableCell>DISCOM</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell>Last activity</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={columns}><Skeleton /></TableCell></TableRow>
          ))}
          {rows?.map((c) => (
            <TableRow key={c.ticket} hover onClick={() => navigate(complaintPath(c.ticket))} sx={{ cursor: 'pointer' }}
              selected={selection?.selected.has(c.ticket) ?? false}>
              {selection && (
                <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()}>
                  <Checkbox size="small" checked={selection.selected.has(c.ticket)} onChange={() => selection.onToggle(c.ticket)}
                    slotProps={{ input: { 'aria-label': `Select ${c.ticket}` } }} />
                </TableCell>
              )}
              <TableCell sx={{ whiteSpace: 'nowrap' }}>
                <MuiLink component={Link} to={complaintPath(c.ticket)} onClick={(e) => e.stopPropagation()}
                  sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                  {c.ticket}
                </MuiLink>
                <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{dateTime(c.created_at)}</Typography>
                {c.demo && <DemoChip />}
                <HolderChips c={c} />
              </TableCell>
              <TableCell><Flags c={c} /></TableCell>
              <DetailCells c={c} />
              <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{c.amount ? rupees(c.amount) : '-'}</TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>
                {c.last_message_at ? dateTime(c.last_message_at) : 'No messages'}
                <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
                  {c.messages_count === 1 ? '1 message' : `${c.messages_count} messages`}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
