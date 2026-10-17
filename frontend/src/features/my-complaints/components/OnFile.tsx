import { Box, Typography } from '@mui/material';

import { Panel } from '@/shared/components/Panel';
import { dateTime, monthLabel } from '@/shared/lib/format';

import type { MyComplaintDetail } from '../api/types';

/** What we hold for the complaint, in the consumer's terms. */
export function OnFile({ c }: { c: MyComplaintDetail }) {
  const facts: Array<[string, string]> = [
    ['Problem', c.type_label],
    ['Service number', c.service_masked ?? 'Not given'],
    ['Bill month', c.bill_month ? monthLabel(c.bill_month) : 'No bill linked'],
    ['Raised', dateTime(c.created_at)],
  ];
  if (c.discom) facts.splice(1, 0, ['DISCOM', c.discom]);
  return (
    <Panel title="What we have on file">
      <Box component="dl" sx={{ m: 0, display: 'grid', columnGap: 3, rowGap: 1.75, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))', md: 'repeat(2, minmax(0, 1fr))' } }}>
        {facts.map(([label, value]) => (
          <Box key={label} sx={{ minWidth: 0 }}>
            <Typography component="dt" variant="caption" sx={{ color: 'text.secondary' }}>{label}</Typography>
            <Typography component="dd" variant="body2" sx={{ m: 0, fontWeight: 600, fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' }}>{value}</Typography>
          </Box>
        ))}
      </Box>
      {c.description && (
        <Box sx={{ mt: 2.5, pt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mb: 0.5 }}>What you told us</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{c.description}</Typography>
        </Box>
      )}
    </Panel>
  );
}
