import { Checkbox, Chip, Link as MuiLink, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import { Link, useNavigate } from 'react-router-dom';

import { CHANNEL_LABEL, DemoChip, DueChip, PriorityChip, SOURCE_LABEL, StatusChip, TRIAGE, type ComplaintRow } from '@/features/complaints';
import { dateTime, rupees } from '@/shared/lib/format';

interface ComplaintsTableProps {
  rows: ComplaintRow[] | undefined;
  loadingRows: number;
  dimmed?: boolean;
  /** Turns on a checkbox per row for bulk actions. */
  selection?: { selected: Set<string>; onToggle: (ticket: string) => void; onToggleAll: (tickets: string[]) => void };
}

/** The status, plus only the most urgent flag: a reply that did not arrive, then overdue, then an overcharge. */
function StatusCell({ c }: { c: ComplaintRow }) {
  const flag = c.delivery_failed ? <Chip size="small" color="error" label="Reply not delivered" />
    : c.overdue ? <DueChip c={c} />
      : c.triage === 'overcharge' ? <Chip size="small" variant="outlined" color={TRIAGE.overcharge.tone} label={TRIAGE.overcharge.label} /> : null;
  const holder = c.waiting_on === 'consumer' ? 'Waiting on consumer' : c.assignee_name ? `With ${c.assignee_name}` : null;
  return (
    <Stack sx={{ gap: 0.5, alignItems: 'flex-start' }}>
      <StatusChip status={c.status} />
      {flag}
      {holder && <Typography variant="caption" sx={{ color: 'text.secondary' }} noWrap>{holder}</Typography>}
    </Stack>
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
  const columns = selection ? 6 : 5;
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
            <TableCell>Issue</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Priority</TableCell>
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
                <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
                  {dateTime(c.created_at)}, {source(c)}{c.discom ? `, ${c.discom}` : ''}
                </Typography>
                {c.demo && <DemoChip />}
              </TableCell>
              <TableCell sx={{ minWidth: 220, maxWidth: 380 }}>
                <Typography variant="subtitle2" component="p">{c.type_label ?? 'Complaint'}</Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary', display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {c.amount ? `${rupees(c.amount)}. ` : ''}{c.issue}
                </Typography>
              </TableCell>
              <TableCell><StatusCell c={c} /></TableCell>
              <TableCell>{c.priority ? <PriorityChip priority={c.priority} /> : '-'}</TableCell>
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
