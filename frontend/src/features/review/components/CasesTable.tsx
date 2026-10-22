import { Link as MuiLink, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import { Link, useNavigate } from 'react-router-dom';

import { formatCount, monthLabel, rupees, shortDate } from '@/shared/lib/format';

import type { CaseRow, ReviewState } from '../api/types';
import { headline } from '../model/headline';
import { ratioOf } from '../model/labels';
import { StateChip } from './StateChip';

export const casePath = (ticket: string) => `/review/${encodeURIComponent(ticket)}`;

const COLUMNS = ['Case', 'What it is about', 'Bill', 'Stage', 'With', 'Waiting'];

/** What has to happen next, in the words of the person doing it. */
const NEXT: Record<ReviewState, string> = {
  awaiting_review: 'Needs a decision',
  info_requested: 'Asked the consumer',
  awaiting_approval: 'Needs approval',
  rejected: 'Sent back to the AE',
  decided: 'Enter in billing',
  applied: 'Closed',
};

function Muted({ children }: { children: string }) {
  return <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{children}</Typography>;
}

function About({ c }: { c: CaseRow }) {
  const ratio = ratioOf(c.units, c.median_units);
  return (
    <>
      <Typography variant="body2" sx={{ fontWeight: 600, color: ratio !== null && ratio >= 2 ? 'warning.dark' : 'text.primary' }}>
        {headline(c)}
      </Typography>
      <Muted>{[c.section ?? 'Section not mapped', c.discom].join(', ')}</Muted>
    </>
  );
}

function Bill({ c }: { c: CaseRow }) {
  return (
    <>
      <Typography variant="body2" sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
        {c.printed_amount === null ? 'Not printed' : rupees(c.printed_amount)}
      </Typography>
      <Muted>{`${monthLabel(c.bill_month)}${c.usual_amount === null ? '' : `, usual ${rupees(c.usual_amount)}`}`}</Muted>
    </>
  );
}

function Row({ c }: { c: CaseRow }) {
  const navigate = useNavigate();
  return (
    <TableRow hover onClick={() => navigate(casePath(c.ticket))} sx={{ cursor: 'pointer', verticalAlign: 'top' }}>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <MuiLink component={Link} to={casePath(c.ticket)} onClick={(e) => e.stopPropagation()} sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
          {c.ticket}
        </MuiLink>
        <Muted>{`${shortDate(c.created_at)}, ${c.channel === 'whatsapp' ? 'WhatsApp' : 'web app'}`}</Muted>
      </TableCell>
      <TableCell sx={{ minWidth: 220 }}><About c={c} /></TableCell>
      <TableCell><Bill c={c} /></TableCell>
      <TableCell sx={{ minWidth: 150 }}>
        <Stack sx={{ gap: 0.5, alignItems: 'flex-start' }}>
          <StateChip state={c.state} />
          <Muted>{NEXT[c.state]}</Muted>
        </Stack>
      </TableCell>
      <TableCell sx={{ minWidth: 110 }}>
        {c.assignee ? c.assignee.name : <Typography variant="body2" sx={{ color: 'warning.dark' }}>Unassigned</Typography>}
      </TableCell>
      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
        <Typography variant="body2" sx={{ fontWeight: c.overdue ? 700 : 400, color: c.overdue ? 'error.dark' : 'text.primary' }}>
          {c.days_open === 1 ? '1 day' : `${formatCount(c.days_open)} days`}
        </Typography>
        {c.overdue && <Muted>Past the target</Muted>}
      </TableCell>
    </TableRow>
  );
}

/** Rows open the case on click; the ticket is also a real link, so keyboards and new tabs work. */
export function CasesTable({ rows, loadingRows, dimmed }: { rows: CaseRow[] | undefined; loadingRows: number; dimmed: boolean }) {
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      <Table size="small" aria-label="Reading checks">
        <TableHead>
          <TableRow>{COLUMNS.map((c) => <TableCell key={c} align={c === 'Waiting' ? 'right' : 'left'}>{c}</TableCell>)}</TableRow>
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
