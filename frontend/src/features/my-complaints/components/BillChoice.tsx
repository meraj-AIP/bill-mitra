import { MenuItem, TextField } from '@mui/material';

import { useBills, type BillSummary } from '@/features/dashboard';
import { monthLabel, rupees } from '@/shared/lib/format';

const RECENT = { page: 1, pageSize: 50, status: '' as const, sort: 'newest' as const };

function describe(b: BillSummary): string {
  const parts = [monthLabel(b.bill_month), b.discom];
  if (b.service_masked) parts.push(`service no. ${b.service_masked}`);
  if (b.total_payable !== null) parts.push(rupees(b.total_payable));
  return parts.join(', ');
}

interface BillChoiceProps {
  value: string;
  onChange: (bill: BillSummary | null) => void;
}

/** One of the consumer's checked bills, so we see the same figures they do. Optional. */
export function BillChoice({ value, onChange }: BillChoiceProps) {
  const bills = useBills(RECENT);
  const items = bills.data?.items ?? [];
  if (bills.isSuccess && items.length === 0) return null;
  const known = !value || items.some((b) => b.id === value);
  return (
    <TextField select fullWidth label="Which bill is this about? (optional)" value={known ? value : ''}
      onChange={(e) => onChange(items.find((b) => b.id === e.target.value) ?? null)}
      helperText={bills.isError ? 'Could not load your bills. You can still send the complaint.' : 'Pick a bill you checked here, or leave it empty.'}
      slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}>
      <MenuItem value="">No bill</MenuItem>
      {items.map((b) => <MenuItem key={b.id} value={b.id} sx={{ fontVariantNumeric: 'tabular-nums' }}>{describe(b)}</MenuItem>)}
    </TextField>
  );
}
