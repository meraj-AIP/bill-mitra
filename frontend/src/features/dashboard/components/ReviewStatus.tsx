import { Alert, AlertTitle, Box, Chip, Paper, Stack, Typography } from '@mui/material';

import type { ReviewSummary } from '@/features/review';
import { dateTime, rupees } from '@/shared/lib/format';

import { FINAL_STATUS, REPORT_TEXT } from '../model/labels';
import { RequestedBills } from './RequestedBills';

type Revision = NonNullable<ReviewSummary['revision']>;

function Amount({ label, value, struck = false }: { label: string; value: number; struck?: boolean }) {
  return (
    <Box>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography component="p" sx={{ fontSize: struck ? '1.125rem' : '1.5rem', fontWeight: 600, lineHeight: 1.25, fontVariantNumeric: 'tabular-nums',
        textDecoration: struck ? 'line-through' : 'none', color: struck ? 'text.secondary' : 'success.dark' }}>
        {rupees(value)}
      </Typography>
    </Box>
  );
}

/** The revised bill. The original is never edited; these figures are what the consumer now pays for the month. */
function RevisedBillCard({ r, ticket }: { r: Revision; ticket: string }) {
  const status = FINAL_STATUS[r.status];
  return (
    <Paper component="section" variant="outlined" aria-labelledby="revised-bill" sx={{ p: { xs: 2, sm: 2.5 }, borderTop: 3, borderTopColor: 'success.main' }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography id="revised-bill" variant="h3" component="h2" sx={{ flex: 1 }}>Revised bill</Typography>
        <Chip size="small" color={status.tone} variant={r.status === 'applied' ? 'filled' : 'outlined'} label={status.label} />
      </Stack>
      <Stack direction="row" sx={{ gap: { xs: 3, sm: 5 }, mt: 1.5, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        {r.revised_total !== null && <Amount label="Total to pay" value={r.revised_total} />}
        <Amount label="Bill amount" value={r.revised_amount} />
        <Amount label="Printed bill amount" value={r.original_amount} struck />
        {r.original_total !== null && <Amount label="Printed total" value={r.original_total} struck />}
      </Stack>
      <Typography variant="body1" sx={{ mt: 1.5, maxWidth: '65ch' }}>{r.reason}</Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 1 }}>
        Revised by {r.office}, {dateTime(r.decided_at)}. Reference {ticket}.
        {r.status === 'applied' ? '' : ' Until your official bill is updated, keep this page as proof of the revised amount.'}
      </Typography>
    </Paper>
  );
}

/** Where the consumer's report stands, in their terms. It never says who reviews the bill. */
export function ReviewStatus({ review, billId }: { review: ReviewSummary; billId: string | null }) {
  const text = REPORT_TEXT[review.state];
  return (
    <Stack sx={{ gap: 2 }}>
      <Alert severity={text.tone} sx={{ border: 1, borderColor: 'divider' }}>
        <AlertTitle sx={{ fontWeight: 600 }}>{text.title}</AlertTitle>
        {text.body}
        <Typography variant="caption" component="p" sx={{ mt: 0.5 }}>Reference {review.ticket}</Typography>
      </Alert>
      {review.state === 'waiting_for_you' && <RequestedBills review={review} billId={billId} />}
      {review.state === 'revised' && review.revision && <RevisedBillCard r={review.revision} ticket={review.ticket} />}
    </Stack>
  );
}
