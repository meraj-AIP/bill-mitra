import ReceiptLongOutlinedIcon from '@mui/icons-material/ReceiptLongOutlined';
import {
  Chip, MenuItem, Paper, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow,
  TextField, Tooltip, Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';

import { EmptyState, ErrorState } from '@/shared/components/States';
import { dateTime, formatCount, monthLabel, rupees } from '@/shared/lib/format';

import { useBills } from '../api/billsApi';
import type { BillListQuery, BillSummary } from '../api/types';
import { AUDIT_STATUS, auditStatus } from '../model/labels';

const COLUMNS = ['Bill month', 'DISCOM', 'Units', 'Total payable', 'Check', 'Overcharge', 'Uploaded'];
const NUMERIC = new Set(['Units', 'Total payable', 'Overcharge']);

interface BillsTableProps {
  query: BillListQuery;
  pageSizes: number[];
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
  onStatus: (status: BillListQuery['status']) => void;
  onSort: (sort: BillListQuery['sort']) => void;
}

/** total_payable is already the final amount; the printed one is a hover away. */
function RevisedChip({ original }: { original: number | null }) {
  const chip = <Chip size="small" color="success" variant="outlined" label="Revised" sx={{ ml: 1 }} />;
  return original === null ? chip : <Tooltip title={`Printed total ${rupees(original)}`} describeChild>{chip}</Tooltip>;
}

function MonthCell({ bill }: { bill: BillSummary }) {
  const original = bill.original_total_payable ?? null;
  const revised = bill.revised_amount !== null || original !== null;
  return (
    <TableCell sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
      {monthLabel(bill.bill_month)}
      {revised && <RevisedChip original={original} />}
      {!revised && bill.under_review && <Chip size="small" color="info" variant="outlined" label="Under review" sx={{ ml: 1 }} />}
    </TableCell>
  );
}

function BillRow({ bill }: { bill: BillSummary }) {
  const navigate = useNavigate();
  const status = auditStatus(bill.audit_status);
  const open = () => navigate(`/bills/${encodeURIComponent(bill.id)}`);
  return (
    <TableRow hover tabIndex={0} onClick={open} sx={{ cursor: 'pointer' }} aria-label={`Open the ${monthLabel(bill.bill_month)} bill`}
      onKeyDown={(e) => {
        if (e.key === 'Enter') open();
      }}>
      <MonthCell bill={bill} />
      <TableCell>{bill.discom === 'UNKNOWN' ? '' : bill.discom}</TableCell>
      <TableCell align="right">{bill.units === null ? '' : formatCount(bill.units)}</TableCell>
      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{bill.total_payable === null ? '' : rupees(bill.total_payable)}</TableCell>
      <TableCell><Chip size="small" variant="outlined" label={status.label} color={status.tone} /></TableCell>
      <TableCell align="right" sx={{ whiteSpace: 'nowrap', color: bill.overcharge > 0 ? 'error.dark' : 'text.secondary', fontWeight: bill.overcharge > 0 ? 700 : 400 }}>
        {bill.overcharge > 0 ? rupees(bill.overcharge) : 'None'}
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap', color: 'text.secondary' }}>{dateTime(bill.created_at)}</TableCell>
    </TableRow>
  );
}

function Filters({ query, onStatus, onSort }: Pick<BillsTableProps, 'query' | 'onStatus' | 'onSort'>) {
  return (
    <Stack direction="row" sx={{ gap: 1 }}>
      <TextField select size="small" label="Check" value={query.status} sx={{ minWidth: 168 }}
        slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
        onChange={(e) => onStatus(e.target.value as BillListQuery['status'])}>
        <MenuItem value="">All bills</MenuItem>
        {Object.entries(AUDIT_STATUS).map(([value, s]) => <MenuItem key={value} value={value}>{s.label}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Sort" value={query.sort} sx={{ minWidth: 128 }}
        onChange={(e) => onSort(e.target.value as BillListQuery['sort'])}>
        <MenuItem value="newest">Newest first</MenuItem>
        <MenuItem value="oldest">Oldest first</MenuItem>
      </TextField>
    </Stack>
  );
}

export function BillsTable({ query, pageSizes, onPage, onPageSize, onStatus, onSort }: BillsTableProps) {
  const result = useBills(query);
  const data = result.data;
  const filtered = query.status !== '';
  return (
    <Paper component="section" variant="outlined" aria-labelledby="my-bills">
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ p: { xs: 2, sm: 2.5 }, gap: 1.5, alignItems: { sm: 'center' } }}>
        <Typography variant="h2" id="my-bills" sx={{ flex: 1 }}>My bills</Typography>
        <Filters query={query} onStatus={onStatus} onSort={onSort} />
      </Stack>
      {result.isError ? (
        <Stack sx={{ px: 2.5, pb: 2.5 }}>
          <ErrorState message="Could not load your bills." onRetry={() => void result.refetch()} />
        </Stack>
      ) : data?.total === 0 ? (
        <EmptyState icon={<ReceiptLongOutlinedIcon />} title={filtered ? 'No bills with this check result' : 'No bills yet'}
          hint={filtered ? 'Try another filter, or show all bills.' : 'Upload a bill above. It will be listed here with its check result.'} />
      ) : (
        <TableContainer sx={{ opacity: result.isPlaceholderData ? 0.6 : 1, transition: 'opacity 200ms' }}>
          <Table size="small" aria-labelledby="my-bills">
            <TableHead>
              <TableRow>
                {COLUMNS.map((c) => <TableCell key={c} align={NUMERIC.has(c) ? 'right' : 'left'}>{c}</TableCell>)}
              </TableRow>
            </TableHead>
            <TableBody>
              {result.isPending && Array.from({ length: 3 }, (_, i) => (
                <TableRow key={i}>
                  {COLUMNS.map((c) => <TableCell key={c}><Skeleton /></TableCell>)}
                </TableRow>
              ))}
              {data?.items.map((b) => <BillRow key={b.id} bill={b} />)}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {data && data.total > 0 && (
        <TablePagination component="div" count={data.total} page={query.page - 1} rowsPerPage={query.pageSize}
          rowsPerPageOptions={pageSizes} onPageChange={(_e, p) => onPage(p + 1)}
          onRowsPerPageChange={(e) => onPageSize(Number(e.target.value))} />
      )}
    </Paper>
  );
}
