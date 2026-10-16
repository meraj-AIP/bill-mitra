import { Box, Stack } from '@mui/material';

import { AuditLines } from '@/features/complaints';
import { calendarDate, formatCount } from '@/shared/lib/format';

import type { CaseDetail } from '../api/types';
import { Figure, Panel } from './Panel';

const reading = (v: number | null | undefined) => (v === null || v === undefined ? 'Not printed' : formatCount(v));

/** The meter readings as printed, then the line-by-line charges check the engine ran on them. */
export function ReadingsPanel({ c }: { c: CaseDetail }) {
  const b = c.bill;
  const back = b?.previous_reading != null && b.present_reading != null && b.present_reading < b.previous_reading;
  return (
    <Stack sx={{ gap: 2 }}>
      <Panel title="Readings on the bill" caption={b?.bill_date ? `Bill dated ${calendarDate(b.bill_date)}` : 'As read from the photo'}>
        {b ? (
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
            <Figure label="Previous reading" value={reading(b.previous_reading)} />
            <Figure label="Present reading" value={reading(b.present_reading)} strong={back} note={back ? 'Lower than the previous one' : undefined} />
            <Figure label="Units billed" value={reading(b.units)} />
            <Figure label="Billing days" value={reading(b.billing_days)} />
            <Figure label="Category" value={b.category ?? 'Not printed'} />
            <Figure label="Load" value={b.load_kw === null ? 'Not printed' : `${b.load_kw} kW`} />
          </Box>
        ) : (
          <Box sx={{ color: 'text.secondary' }}>The bill details are no longer stored for this case.</Box>
        )}
      </Panel>
      <AuditLines lines={c.audit_lines} />
    </Stack>
  );
}
