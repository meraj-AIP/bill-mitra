import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { Box, Button, Typography } from '@mui/material';

import { formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { AttachedBill } from '../api/types';

function BillCard({ b }: { b: AttachedBill }) {
  return (
    <Box component="li" sx={{ p: 1.5, borderRadius: 1.5, border: 1, borderColor: 'divider', bgcolor: 'grey.50', minWidth: 0,
      '@media print': { bgcolor: 'transparent', breakInside: 'avoid' } }}>
      <Typography variant="subtitle2" component="p">{monthLabel(b.month)}</Typography>
      <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', mt: 0.25 }}>
        {b.units === null ? 'Units not read' : `${formatCount(b.units)} units`}
        {', '}
        {b.amount === null ? 'amount not read' : rupees(b.amount)}
      </Typography>
      {b.media_url ? (
        <Button size="small" href={b.media_url} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNewIcon fontSize="small" />}
          sx={{ mt: 0.5, ml: -0.75, '@media print': { display: 'none' } }}>
          Open the photo
        </Button>
      ) : (
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.5 }}>No photo stored</Typography>
      )}
    </Box>
  );
}

/** Earlier bills the consumer sent for this case, one card each. */
export function AttachedBills({ bills }: { bills: AttachedBill[] }) {
  if (bills.length === 0) {
    return <Typography variant="body2" sx={{ color: 'text.secondary' }}>No earlier bills attached yet.</Typography>;
  }
  return (
    <Box component="ul" aria-label="Attached bills" sx={{ listStyle: 'none', m: 0, p: 0, display: 'grid', gap: 1.5,
      gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))' }, '@media print': { gridTemplateColumns: '1fr' } }}>
      {bills.map((b) => <BillCard key={b.bill_id} b={b} />)}
    </Box>
  );
}
