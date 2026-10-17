import { Alert, Box, Chip, Paper, Stack, Typography } from '@mui/material';

import { calendarDate, formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { Bill, FinalAmounts } from '../api/types';
import { FINAL_STATUS } from '../model/labels';
import { isEstimated, statusMeaning } from '../model/meterStatus';

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

function EstimatedNote({ code }: { code: string | null | undefined }) {
  if (!isEstimated(code)) return null;
  return (
    <Alert severity="warning" sx={{ mb: 2 }}>
      Meter status {code}: {statusMeaning(code).toLowerCase()}. These units were not read from the meter this month,
      so the bill can be higher or lower than real use. The next actual reading adjusts it.
    </Alert>
  );
}

/** Printed for reference. Only what the bill shows appears, so a household bill stays short. */
function ReferenceFacts({ bill }: { bill: Bill }) {
  const rows: Array<[string, string]> = [];
  if (bill.present_status) rows.push(['Meter status', `${bill.present_status}, ${statusMeaning(bill.present_status)}`]);
  if (bill.phase) rows.push(['Supply', bill.phase === 3 ? 'Three phase' : 'Single phase']);
  if (bill.recorded_md !== null && bill.recorded_md !== undefined) rows.push(['Recorded max demand', `${formatCount(bill.recorded_md)} kW`]);
  if (bill.power_factor !== null && bill.power_factor !== undefined) rows.push(['Power factor', String(bill.power_factor)]);
  if (bill.security_deposit !== null && bill.security_deposit !== undefined) rows.push(['Security deposit held', rupees(bill.security_deposit)]);
  if (bill.disconnection_date) rows.push(['Disconnection date', calendarDate(bill.disconnection_date)]);
  return <>{rows.map(([label, value]) => <Fact key={label} label={label} value={value} />)}</>;
}

function Revised({ label, value, printed }: { label: string; value: number; printed: number | null }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" component="dt" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography component="dd" sx={{ m: 0, fontWeight: 600, fontSize: '1.375rem', lineHeight: 1.3, fontVariantNumeric: 'tabular-nums', color: 'success.dark' }}>
        {rupees(value)}
        {printed !== null && (
          <Box component="s" aria-label={`Printed ${rupees(printed)}`}
            sx={{ ml: 1, fontSize: '0.9375rem', fontWeight: 500, color: 'text.secondary', whiteSpace: 'nowrap' }}>
            {rupees(printed)}
          </Box>
        )}
      </Typography>
    </Box>
  );
}

/** After an approved revision the revised figures are the bill; the printed ones stay visible, struck through. */
function FinalFacts({ bill, final }: { bill: Bill; final: FinalAmounts }) {
  const status = final.status ? FINAL_STATUS[final.status] : null;
  return (
    <Box sx={{ pb: 2, mb: 2, borderBottom: 1, borderColor: 'divider' }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
        <Typography variant="subtitle2" component="p" sx={{ flex: 1 }}>Revised bill</Typography>
        {status && <Chip size="small" color={status.tone} variant={final.status === 'applied' ? 'filled' : 'outlined'} label={status.label} />}
      </Stack>
      <Box component="dl" sx={{ m: 0, display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' } }}>
        {final.total_payable !== null && <Revised label="Total to pay" value={final.total_payable} printed={bill.total_payable} />}
        <Revised label="Bill amount" value={final.bill_amount} printed={bill.bill_amount} />
      </Box>
    </Box>
  );
}

/** The headline figures from the bill. A revised bill leads with the revised amounts to pay. */
export function BillFacts({ bill, final }: { bill: Bill; final?: FinalAmounts | null | undefined }) {
  const solar = bill.export_units !== null;
  const revised = final?.revised ? final : null;
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 } }}>
      {revised && <FinalFacts bill={bill} final={revised} />}
      <EstimatedNote code={bill.present_status} />
      <Box component="dl" sx={{ m: 0, display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' } }}>
        {!revised && <Fact strong label="Total payable" value={bill.total_payable === null ? 'Not read' : rupees(bill.total_payable)} />}
        <Fact strong label={solar ? 'Billed units (net)' : 'Units'} value={count(solar ? netUnits(bill) : bill.units)} />
        <Fact label="Bill month" value={monthLabel(bill.bill_month)} />
        <Fact label="Due date" value={bill.due_date ? calendarDate(bill.due_date) : 'Not read'} />
        <Fact label="DISCOM" value={bill.discom === 'UNKNOWN' ? 'Not read' : bill.discom} />
        <Fact label="Service no." value={bill.service_masked ?? 'Not read'} />
        <Fact label="Meter readings" value={readingsText(bill)} />
        <Fact label={bill.arrears < 0 ? 'Credit from earlier bills' : 'Arrears'} value={rupees(Math.abs(bill.arrears))} />
        <ConnectionFacts bill={bill} />
        <ReferenceFacts bill={bill} />
      </Box>
    </Paper>
  );
}
