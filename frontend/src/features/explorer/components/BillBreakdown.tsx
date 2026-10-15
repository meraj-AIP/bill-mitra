import { Divider, Stack, Typography } from '@mui/material';

import { rupees } from '@/shared/lib/format';

import type { Computation } from '../api/tariffApi';

function Line({ label, value, strong = false, muted = false }: { label: string; value: string; strong?: boolean; muted?: boolean }) {
  return (
    <Stack direction="row" sx={{ justifyContent: 'space-between', py: 0.25 }}>
      <Typography variant="body2" sx={{ color: muted ? 'text.secondary' : 'text.primary', fontWeight: strong ? 700 : 400 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: strong ? 700 : 400 }}>
        {value}
      </Typography>
    </Stack>
  );
}

/** The same lines a consumer sees in the chat, straight from the rule engine. */
export function BillBreakdown({ comp }: { comp: Computation }) {
  return (
    <Stack>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {comp.tariff_order} · group {comp.group}
      </Typography>
      {comp.slab_lines.map((s) => (
        <Line key={s.start} muted label={`${s.start} to ${s.end} units × Rs ${s.rate.toFixed(2)}`} value={rupees(s.amount)} />
      ))}
      <Line label="Energy charges" value={rupees(comp.energy)} />
      <Line label="Fixed charge (2 kW)" value={rupees(comp.fixed)} />
      <Line label="Customer charge" value={rupees(comp.customer)} />
      <Line label="Electricity duty" value={rupees(comp.duty)} />
      {comp.fsa > 0 && <Line label="FSA" value={rupees(comp.fsa)} />}
      <Divider sx={{ my: 0.75 }} />
      <Line label="Bill amount" value={rupees(comp.gross)} />
      {comp.gruha_jyothi_applied && <Line label="Gruha Jyothi subsidy" value={`- ${rupees(comp.subsidy)}`} />}
      <Line strong label="To pay" value={rupees(comp.net)} />
    </Stack>
  );
}
