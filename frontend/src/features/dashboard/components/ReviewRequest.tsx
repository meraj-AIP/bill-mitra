import ManageSearchOutlinedIcon from '@mui/icons-material/ManageSearchOutlined';
import {
  Alert, AlertTitle, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Stack, TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';

import type { Spike } from '@/features/review';
import type { Language } from '@/shared/lib/languages';
import { isStatus } from '@/shared/api/http';
import { formatCount } from '@/shared/lib/format';

import { useReviewRequest } from '../api/billsApi';

const NOTE_LIMIT = 500;

function title(spike: Spike): string {
  if (spike.reason === 'reading_went_back') return 'The present reading on this bill is lower than the previous one';
  if (spike.ratio !== null && spike.median_units !== null) {
    return `This bill is ${spike.ratio.toFixed(1)} times your usual ${formatCount(spike.median_units)} units`;
  }
  return 'This bill is much higher than usual for your home';
}

function AskDialog({ billId, language, onClose }: { billId: string; language: Language; onClose: () => void }) {
  const ask = useReviewRequest(billId, language);
  const [note, setNote] = useState('');
  const already = isStatus(ask.error, 409);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Ask the AE to check this bill</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          The section AE looks at the meter reading on this bill against your earlier months. If the reading was wrong, they correct the bill and you get a message.
        </DialogContentText>
        <TextField label="Anything the AE should know (optional)" multiline minRows={3} fullWidth value={note}
          onChange={(e) => setNote(e.target.value)} error={note.length > NOTE_LIMIT}
          placeholder="For example: we were away for two weeks this month."
          helperText={`${note.length} of ${NOTE_LIMIT} characters`} />
        {already && <Alert severity="info" sx={{ mt: 2 }}>A check is already open for this bill. Its progress is shown on this page.</Alert>}
        {ask.error && !already && <Alert severity="error" sx={{ mt: 2 }}>{ask.error.message}</Alert>}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>{already ? 'Close' : 'Cancel'}</Button>
        {!already && (
          <Button variant="contained" disabled={ask.isPending || note.length > NOTE_LIMIT}
            onClick={() => ask.mutate(note.trim(), { onSuccess: onClose })}
            startIcon={ask.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            Send to the AE
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

/** A calm note, not an alarm: a high bill is often right, and the AE is the one who can say. */
export function SpikeBanner({ spike, billId, language }: { spike: Spike; billId: string | null; language: Language }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Alert severity="warning" variant="outlined" icon={<ManageSearchOutlinedIcon />} sx={{ bgcolor: 'warning.light' }}
        action={billId ? <Button color="inherit" size="small" variant="outlined" onClick={() => setOpen(true)} sx={{ whiteSpace: 'nowrap' }}>Ask the AE to check</Button> : undefined}>
        <AlertTitle sx={{ fontWeight: 600 }}>{title(spike)}</AlertTitle>
        <Box component="span">
          The meter may have been misread. The section AE can check the reading and correct the bill if it was wrong. It costs nothing to ask.
        </Box>
      </Alert>
      {open && billId && <AskDialog billId={billId} language={language} onClose={() => setOpen(false)} />}
    </>
  );
}

/** For a bill the engine did not flag: the consumer can still ask, but the page does not push them to. */
export function QuietReviewAsk({ billId, language }: { billId: string; language: Language }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1, alignItems: { sm: 'center' }, px: 0.5 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>Think the meter reading is wrong?</Typography>
        <Button size="small" onClick={() => setOpen(true)} sx={{ alignSelf: 'flex-start' }}>Ask the AE to check</Button>
      </Stack>
      {open && <AskDialog billId={billId} language={language} onClose={() => setOpen(false)} />}
    </>
  );
}
