import { Link as MuiLink, Skeleton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import { Link, useNavigate } from 'react-router-dom';

import { formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { CaseRow } from '../api/types';
import { ratioOf, ratioText } from '../model/labels';
import { CaseFlags } from './StateChip';

export const casePath = (ticket: string) => `/review/${encodeURIComponent(ticket)}`;

const COLUMNS = ['Ticket', 'State', 'Section', 'Bill month', 'Units', 'Amount', 'With', 'Open'];
const RIGHT = new Set(['Units', 'Amount', 'Open']);

function Muted({ children }: { children: string }) {
  return <Typography variant="caption" component="p" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>{children}</Typography>;
}

function Usage({ c }: { c: CaseRow }) {
  const ratio = ratioText(ratioOf(c.units, c.median_units));
  return (
    <>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>{c.units === null ? 'Not read' : formatCount(c.units)}</Typography>
      {ratio && <Typography variant="caption" component="p" sx={{ color: 'warning.dark', fontWeight: 600 }}>{ratio}</Typography>}
      {c.median_units !== null && <Muted>{`usual ${formatCount(c.median_units)}`}</Muted>}
    </>
  );
}

function Amount({ c }: { c: CaseRow }) {
  return (
    <>
      <Typography variant="body2" sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{c.printed_amount === null ? 'Not printed' : rupees(c.printed_amount)}</Typography>
      {c.usual_amount !== null && <Muted>{`usual ${rupees(c.usual_amount)}`}</Muted>}
    </>
  );
}

function Row({ c }: { c: CaseRow }) {
  const navigate = useNavigate();
  return (
    <TableRow hover onClick={() => navigate(casePath(c.ticket))} sx={{ cursor: 'pointer' }}>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <MuiLink component={Link} to={casePath(c.ticket)} onClick={(e) => e.stopPropagation()} sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
          {c.ticket}
        </MuiLink>
        <Muted>{c.service_masked ? `Service ${c.service_masked}` : (c.channel === 'whatsapp' ? 'WhatsApp' : 'Web app')}</Muted>
      </TableCell>
      <TableCell><CaseFlags state={c.state} overdue={c.overdue} days={c.days_open} /></TableCell>
      <TableCell sx={{ minWidth: 140 }}>
        <Typography variant="body2">{c.section ?? 'Not mapped yet'}</Typography>
        <Muted>{c.discom}</Muted>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>{monthLabel(c.bill_month)}</TableCell>
      <TableCell align="right"><Usage c={c} /></TableCell>
      <TableCell align="right"><Amount c={c} /></TableCell>
      <TableCell sx={{ minWidth: 120 }}>
        {c.assignee ? c.assignee.name : <Typography variant="body2" sx={{ color: 'warning.dark' }}>Unassigned</Typography>}
      </TableCell>
      <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontWeight: c.overdue ? 700 : 400, color: c.overdue ? 'error.dark' : 'text.primary' }}>
        {c.days_open === 1 ? '1 day' : `${formatCount(c.days_open)} days`}
      </TableCell>
    </TableRow>
  );
}

/** Rows open the case on click; the ticket is also a real link, so keyboards and new tabs work. */
export function CasesTable({ rows, loadingRows, dimmed }: { rows: CaseRow[] | undefined; loadingRows: number; dimmed: boolean }) {
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      <Table size="small" aria-label="Wrong-reading cases">
        <TableHead>
          <TableRow>{COLUMNS.map((c) => <TableCell key={c} align={RIGHT.has(c) ? 'right' : 'left'}>{c}</TableCell>)}</TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={COLUMNS.length}><Skeleton height={36} /></TableCell></TableRow>
          ))}
          {rows?.map((c) => <Row key={c.ticket} c={c} />)}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
