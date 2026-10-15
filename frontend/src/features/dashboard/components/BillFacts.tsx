import { Box, Paper, Typography } from '@mui/material';

import { calendarDate, formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { Bill } from '../api/types';

function Fact({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" component="dt" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography component="dd" sx={{ m: 0, fontWeight: 600, fontSize: strong ? '1.375rem' : '1rem', lineHeight: 1.3,
        fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Box>
  );
}

/** The headline figures as printed on the bill, before any check. */
export function BillFacts({ bill }: { bill: Bill }) {
  const readings = bill.previous_reading !== null && bill.present_reading !== null
    ? `${formatCount(bill.previous_reading)} to ${formatCount(bill.present_reading)}` : 'Not read';
  return (
    <Paper variant="outlined" component="dl"
      sx={{ m: 0, p: { xs: 2, sm: 2.5 }, display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' } }}>
      <Fact strong label="Total payable" value={bill.total_payable === null ? 'Not read' : rupees(bill.total_payable)} />
      <Fact strong label="Units" value={bill.units === null ? 'Not read' : formatCount(bill.units)} />
      <Fact label="Bill month" value={monthLabel(bill.bill_month)} />
      <Fact label="Due date" value={bill.due_date ? calendarDate(bill.due_date) : 'Not read'} />
      <Fact label="DISCOM" value={bill.discom === 'UNKNOWN' ? 'Not read' : bill.discom} />
      <Fact label="Service no." value={bill.service_masked ?? 'Not read'} />
      <Fact label="Meter readings" value={readings} />
      <Fact label="Arrears" value={rupees(bill.arrears)} />
    </Paper>
  );
}
