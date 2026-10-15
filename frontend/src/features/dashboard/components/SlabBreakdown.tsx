import { Divider, Stack, Typography } from '@mui/material';

import { formatCount, rupees } from '@/shared/lib/format';

import type { Analysis, Bill, LineItem } from '../api/types';
import { ReportSection } from './ReportSection';

const TARIFF_CODES: ReadonlySet<LineItem['code']> = new Set(['energy', 'fixed', 'customer', 'duty', 'fsa']);
const STANDARD_SLAB_ENDS = new Set([50, 100, 200]);

function Line({ label, value, strong = false, muted = false }: { label: string; value: string; strong?: boolean; muted?: boolean }) {
  return (
    <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2, py: 0.5 }}>
      <Typography variant="body2" sx={{ color: muted ? 'text.secondary' : 'text.primary', fontWeight: strong ? 700 : 400 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: strong ? 700 : 400, whiteSpace: 'nowrap' }}>
        {value}
      </Typography>
    </Stack>
  );
}

function SlabNote({ analysis, bill }: { analysis: Analysis; bill: Bill | null }) {
  const firstEnd = analysis.slab_lines[0]?.end;
  if (firstEnd === undefined || STANDARD_SLAB_ENDS.has(firstEnd)) return null;
  const days = bill?.billing_days;
  return (
    <Typography variant="caption" component="p" sx={{ color: 'text.secondary', pt: 0.5 }}>
      Slab limits are stretched by billing days{days ? `: this bill covers ${formatCount(days)} days` : ''}.
    </Typography>
  );
}

/** What the bill printed beyond the tariff (surcharge, interest, rounding, arrears). Listed as printed, never summed here. */
function PrintedTotals({ bill, billAmount }: { bill: Bill; billAmount: number }) {
  const others = bill.line_items.filter((item) => !TARIFF_CODES.has(item.code) && item.amount !== 0);
  return (
    <>
      {others.length > 0 && (
        <>
          <Typography variant="subtitle2" component="h3" sx={{ pt: 1, pb: 0.25 }}>Other lines printed on the bill</Typography>
          {others.map((item, i) => <Line key={`${item.code}-${i}`} muted label={item.label} value={rupees(item.amount)} />)}
        </>
      )}
      <Divider sx={{ my: 0.75 }} />
      <Line label="Bill amount (printed)" value={rupees(billAmount)} />
      {bill.arrears > 0 && <Line label="Arrears" value={rupees(bill.arrears)} />}
      {bill.total_payable !== null && <Line strong label="Total due (printed)" value={rupees(bill.total_payable)} />}
    </>
  );
}

/** How the rule engine priced the units, slab by slab, next to what the bill printed on top. */
export function SlabBreakdown({ analysis: a, bill }: { analysis: Analysis; bill: Bill | null }) {
  return (
    <ReportSection title="How the tariff prices it"
      caption={`${a.tariff_order}, group ${a.group}, ${formatCount(a.units)} units. Tariff id ${a.tariff_id}.`}>
      {a.slab_lines.map((s) => (
        <Line key={s.start} muted label={`${s.start} to ${s.end} units, ${formatCount(s.units)} at ${rupees(s.rate)}`} value={rupees(s.amount)} />
      ))}
      <SlabNote analysis={a} bill={bill} />
      <Divider sx={{ my: 0.75 }} />
      <Line label="Energy charges" value={rupees(a.energy)} />
      <Line label="Fixed charge" value={rupees(a.fixed)} />
      <Line label="Customer charge" value={rupees(a.customer)} />
      <Line label="Electricity duty" value={rupees(a.duty)} />
      {a.fsa > 0 && <Line label="Fuel surcharge (FSA)" value={rupees(a.fsa)} />}
      <Divider sx={{ my: 0.75 }} />
      {bill?.bill_amount != null ? (
        <>
          {a.gruha_jyothi_applied && <Line label="Before subsidy" value={rupees(a.gross)} />}
          {a.gruha_jyothi_applied && <Line label="Gruha Jyothi subsidy" value={`- ${rupees(a.subsidy)}`} />}
          <Line strong label="Tariff charges" value={rupees(a.net)} />
          <PrintedTotals bill={bill} billAmount={bill.bill_amount} />
        </>
      ) : (
        <>
          <Line label="Bill amount" value={rupees(a.gross)} />
          {a.gruha_jyothi_applied && <Line label="Gruha Jyothi subsidy" value={`- ${rupees(a.subsidy)}`} />}
          <Line strong label="To pay this month" value={rupees(a.net)} />
        </>
      )}
    </ReportSection>
  );
}
