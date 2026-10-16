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

const count = (n: number | null | undefined) => (n === null || n === undefined ? 'Not read' : formatCount(n));

function readingsText(bill: Bill): string {
  if (bill.previous_reading === null || bill.present_reading === null) return 'Not read';
  return `${formatCount(bill.previous_reading)} to ${formatCount(bill.present_reading)}`;
}

/** A net-metered bill bills import minus export, so the headline is the net figure and both sides show below. */
function netUnits(bill: Bill): number | null {
  if (bill.billed_units !== undefined && bill.billed_units !== null) return bill.billed_units;
  return bill.units !== null && bill.export_units !== null ? bill.units - bill.export_units : null;
}

function ConnectionFacts({ bill }: { bill: Bill }) {
  return (
    <>
      {bill.export_units !== null && (
        <>
          <Fact label="Imported from grid" value={count(bill.units)} />
          <Fact label="Exported by solar" value={count(bill.export_units)} />
        </>
      )}
      {!bill.is_domestic && <Fact label="Category" value={bill.category ?? 'Non-domestic'} />}
      {!bill.is_domestic && <Fact label="Contracted load" value={bill.load_kw === null ? 'Not read' : `${formatCount(bill.load_kw)} kW`} />}
    </>
  );
}

/** The headline figures as printed on the bill, before any check. */
export function BillFacts({ bill }: { bill: Bill }) {
  const solar = bill.export_units !== null;
  return (
    <Paper variant="outlined" component="dl"
      sx={{ m: 0, p: { xs: 2, sm: 2.5 }, display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' } }}>
      <Fact strong label="Total payable" value={bill.total_payable === null ? 'Not read' : rupees(bill.total_payable)} />
      <Fact strong label={solar ? 'Billed units (net)' : 'Units'} value={count(solar ? netUnits(bill) : bill.units)} />
      <Fact label="Bill month" value={monthLabel(bill.bill_month)} />
      <Fact label="Due date" value={bill.due_date ? calendarDate(bill.due_date) : 'Not read'} />
      <Fact label="DISCOM" value={bill.discom === 'UNKNOWN' ? 'Not read' : bill.discom} />
      <Fact label="Service no." value={bill.service_masked ?? 'Not read'} />
      <Fact label="Meter readings" value={readingsText(bill)} />
      <Fact label={bill.arrears < 0 ? 'Credit from earlier bills' : 'Arrears'} value={rupees(Math.abs(bill.arrears))} />
      <ConnectionFacts bill={bill} />
    </Paper>
  );
}
