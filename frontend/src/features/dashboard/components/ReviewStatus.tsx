import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import { Alert, AlertTitle, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import type { ReviewSummary } from '@/features/review';
import { dateTime, rupees } from '@/shared/lib/format';

import { REVIEW_TEXT } from '../model/labels';

type Revision = NonNullable<ReviewSummary['revision']>;

function Amount({ label, value, struck = false }: { label: string; value: number; struck?: boolean }) {
  return (
    <Box>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography component="p" sx={{ fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.25, fontVariantNumeric: 'tabular-nums',
        textDecoration: struck ? 'line-through' : 'none', color: struck ? 'text.secondary' : 'success.dark' }}>
        {rupees(value)}
      </Typography>
    </Box>
  );
}

/** The revision as the AE recorded it. The original bill is never changed; this is the amount that now applies. */
function RevisedBillCard({ r, ticket }: { r: Revision; ticket: string }) {
  const applied = r.status === 'applied';
  return (
    <Paper component="section" variant="outlined" aria-labelledby="revised-bill" sx={{ p: { xs: 2, sm: 2.5 }, borderTop: 3, borderTopColor: 'success.main' }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography id="revised-bill" variant="h3" component="h2" sx={{ flex: 1 }}>Revised bill</Typography>
        <Chip size="small" color={applied ? 'success' : 'warning'} variant={applied ? 'filled' : 'outlined'}
          label={applied ? 'Applied in your official bill' : 'Pending update in your official bill'} />
      </Stack>
      <Stack direction="row" sx={{ gap: 4, mt: 1.5, flexWrap: 'wrap' }}>
        <Amount label="Original amount" value={r.original_amount} struck />
        <Amount label="Revised amount" value={r.revised_amount} />
      </Stack>
      <Typography variant="body1" sx={{ mt: 1.5 }}>{r.reason}</Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 1 }}>
        Decided by {r.decided_by}, {dateTime(r.decided_at)}. Reference {ticket}.
        {applied ? '' : ' Until the DISCOM updates the official bill, keep this page as proof of the revised amount.'}
      </Typography>
    </Paper>
  );
}

/** Where the AE review stands, in the consumer's terms. */
export function ReviewStatus({ review }: { review: ReviewSummary }) {
  const text = REVIEW_TEXT[review.state];
  const correctAsPrinted = review.state === 'decided' && !review.revision;
  return (
    <Stack sx={{ gap: 2 }}>
      <Alert severity={text.tone} sx={{ border: 1, borderColor: 'divider' }}
        action={review.state === 'info_requested'
          ? <Button color="inherit" size="small" component={Link} to="/assistant" startIcon={<ChatOutlinedIcon />}>Open chat</Button> : undefined}>
        <AlertTitle sx={{ fontWeight: 600 }}>{text.title}</AlertTitle>
        {correctAsPrinted ? 'The AE found the reading and the bill correct as printed.' : text.body}
        <Typography variant="caption" component="p" sx={{ mt: 0.5 }}>Case {review.ticket}</Typography>
      </Alert>
      {review.revision && <RevisedBillCard r={review.revision} ticket={review.ticket} />}
    </Stack>
  );
}
