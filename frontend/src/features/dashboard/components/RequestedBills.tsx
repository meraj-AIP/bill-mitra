import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import { Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import type { ReviewSummary } from '@/features/review';
import { monthLabel } from '@/shared/lib/format';

import { useNoBills } from '../api/billsApi';
import { ActionError } from '@/shared/feedback';

function NoBillsDialog({ billId, onClose }: { billId: string; onClose: () => void }) {
  const noBills = useNoBills(billId);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>Continue without these bills?</DialogTitle>
      <DialogContent>
        <DialogContentText>We check this bill with the bills we already have and tell you the outcome.</DialogContentText>
        <ActionError error={noBills.error} sx={{ mt: 2 }} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={noBills.isPending} onClick={() => noBills.mutate(undefined, { onSuccess: onClose })}
          startIcon={noBills.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          Continue without them
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function MonthRow({ month, received, billId }: { month: string; received: boolean; billId: string | null }) {
  const upload = `/?for=${encodeURIComponent(billId ?? '')}&month=${encodeURIComponent(month)}`;
  return (
    <Stack component="li" direction="row" sx={{ gap: 1.5, alignItems: 'center', minHeight: 40 }}>
      {received
        ? <CheckCircleIcon fontSize="small" sx={{ color: 'success.main' }} aria-hidden />
        : <RadioButtonUncheckedIcon fontSize="small" sx={{ color: 'text.disabled' }} aria-hidden />}
      <Typography variant="body1" sx={{ flex: 1, fontWeight: 600 }}>{monthLabel(month)}</Typography>
      {received && <Typography variant="body2" sx={{ color: 'success.dark' }}>Received</Typography>}
      {!received && billId && (
        <Button size="small" variant="outlined" component={Link} to={upload} startIcon={<UploadFileOutlinedIcon />}>
          Upload a bill
        </Button>
      )}
      {!received && !billId && <Typography variant="body2" sx={{ color: 'text.secondary' }}>Not received yet</Typography>}
    </Stack>
  );
}

/** The earlier bills a report asked for, ticked off as each one arrives. */
export function RequestedBills({ review, billId }: { review: ReviewSummary; billId: string | null }) {
  const [confirming, setConfirming] = useState(false);
  const received = new Set(review.received_months);
  if (review.requested_months.length === 0) return null;
  return (
    <Paper component="section" variant="outlined" aria-labelledby="requested-bills" sx={{ p: { xs: 2, sm: 2.5 } }}>
      <Typography id="requested-bills" variant="h3" component="h2">Bills we need</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, maxWidth: '60ch' }}>
        A photo of each bill is enough. Bills for other months do not count towards this list.
      </Typography>
      <Box component="ul" aria-label="Requested bills" sx={{ listStyle: 'none', m: 0, mt: 1.5, p: 0, display: 'grid', gap: 0.5 }}>
        {review.requested_months.map((m) => <MonthRow key={m} month={m} received={received.has(m)} billId={billId} />)}
      </Box>
      {billId && (
        <Button size="small" color="inherit" onClick={() => setConfirming(true)} sx={{ mt: 1.5, ml: -1, color: 'text.secondary' }}>
          I don&apos;t have these bills
        </Button>
      )}
      {confirming && billId && <NoBillsDialog billId={billId} onClose={() => setConfirming(false)} />}
    </Paper>
  );
}
