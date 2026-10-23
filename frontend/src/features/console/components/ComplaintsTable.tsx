import { Checkbox, Skeleton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';

import type { ComplaintRow } from '@/features/complaints';
import { dateTime } from '@/shared/lib/format';

import { ComplaintCell, complaintPath, DueCell, PriorityCell, StatusCell } from './InboxCells';

export { complaintPath };

interface ComplaintsTableProps {
  rows: ComplaintRow[] | undefined;
  loadingRows: number;
  dimmed?: boolean;
  /** Turns on a checkbox per row for bulk actions. */
  selection?: { selected: Set<string>; onToggle: (ticket: string) => void; onToggleAll: (tickets: string[]) => void };
}

const HEAD = { '& .MuiTableCell-head': { color: 'text.secondary', fontWeight: 600, fontSize: '0.75rem', letterSpacing: '0.02em', bgcolor: 'grey.50' } };
const ROW = { cursor: 'pointer', '& > td': { py: 1.5, verticalAlign: 'top' }, '&:last-child > td': { borderBottom: 0 } };

/** Rows open the complaint on click; the ticket is also a real link so keyboards and new tabs work. */
export function ComplaintsTable({ rows, loadingRows, dimmed = false, selection }: ComplaintsTableProps) {
  const navigate = useNavigate();
  const columns = selection ? 6 : 5;
  const tickets = rows?.map((r) => r.ticket) ?? [];
  const allOn = tickets.length > 0 && tickets.every((t) => selection?.selected.has(t));
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      <Table size="small" aria-label="Complaints" sx={{ tableLayout: 'fixed', minWidth: 880 }}>
        <TableHead sx={HEAD}>
          <TableRow>
            {selection && (
              <TableCell padding="checkbox" sx={{ width: 48 }}>
                <Checkbox size="small" checked={allOn} onChange={() => selection.onToggleAll(tickets)}
                  slotProps={{ input: { 'aria-label': 'Select every complaint on this page' } }} />
              </TableCell>
            )}
            <TableCell>Complaint</TableCell>
            <TableCell sx={{ width: 190 }}>Status</TableCell>
            <TableCell sx={{ width: 100 }}>Priority</TableCell>
            <TableCell sx={{ width: 130 }}>Due</TableCell>
            <TableCell sx={{ width: 150 }}>Last activity</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={columns}><Skeleton /></TableCell></TableRow>
          ))}
          {rows?.map((c) => (
            <TableRow key={c.ticket} hover onClick={() => navigate(complaintPath(c.ticket))} sx={ROW}
              selected={selection?.selected.has(c.ticket) ?? false}>
              {selection && (
                <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()}>
                  <Checkbox size="small" checked={selection.selected.has(c.ticket)} onChange={() => selection.onToggle(c.ticket)}
                    slotProps={{ input: { 'aria-label': `Select ${c.ticket}` } }} />
                </TableCell>
              )}
              <TableCell><ComplaintCell c={c} /></TableCell>
              <TableCell><StatusCell c={c} /></TableCell>
              <TableCell><PriorityCell c={c} /></TableCell>
              <TableCell><DueCell c={c} /></TableCell>
              <TableCell>
                <Typography variant="body2" noWrap>{c.last_message_at ? dateTime(c.last_message_at) : 'No messages'}</Typography>
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
