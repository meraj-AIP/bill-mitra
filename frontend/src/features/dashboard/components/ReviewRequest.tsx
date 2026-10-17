import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import ManageSearchOutlinedIcon from '@mui/icons-material/ManageSearchOutlined';
import {
  Alert, AlertTitle, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField,
} from '@mui/material';
import { useState } from 'react';

import type { Spike } from '@/features/review';
import type { Language } from '@/shared/lib/languages';
import { isStatus } from '@/shared/api/http';

import { useReviewRequest } from '../api/billsApi';

const NOTE_LIMIT = 500;
const ACTION = 'Report a problem with this bill';

function title(spike: Spike): string {
  if (spike.reason === 'reading_went_back') return 'The present reading on this bill is lower than the previous one';
  if (spike.ratio !== null) return `This bill is ${spike.ratio.toFixed(1)} times your usual month`;
  return 'This bill is much higher than usual for your home';
}

function ReportDialog({ billId, language, onClose }: { billId: string; language: Language; onClose: () => void }) {
  const report = useReviewRequest(billId, language);
  const [note, setNote] = useState('');
  const already = isStatus(report.error, 409);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{ACTION}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          We check the meter reading against your earlier bills and tell you the outcome. If we need older bills, we ask you for them.
        </DialogContentText>
        <TextField label="Anything we should know (optional)" multiline minRows={3} fullWidth value={note}
          onChange={(e) => setNote(e.target.value)} error={note.length > NOTE_LIMIT}
          placeholder="For example: we were away for two weeks this month."
          helperText={`${note.length} of ${NOTE_LIMIT} characters`} />
        {already && <Alert severity="info" sx={{ mt: 2 }}>This bill is already reported. Where it stands is shown on this page.</Alert>}
        {report.error && !already && <Alert severity="error" sx={{ mt: 2 }}>{report.error.message}</Alert>}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>{already ? 'Close' : 'Cancel'}</Button>
        {!already && (
          <Button variant="contained" disabled={report.isPending || note.length > NOTE_LIMIT}
            onClick={() => report.mutate(note.trim(), { onSuccess: onClose })}
            startIcon={report.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            Send report
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

/** A calm note, not an alarm: a high bill is often right, so it only offers the report. */
export function SpikeNote({ spike, billId, language }: { spike: Spike; billId: string | null; language: Language }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Alert severity="warning" variant="outlined" icon={<ManageSearchOutlinedIcon />} sx={{ bgcolor: 'warning.light' }}>
        <AlertTitle sx={{ fontWeight: 600 }}>{title(spike)}</AlertTitle>
        <Box component="span">The meter may have been misread. If you think the bill is wrong, report it and we will check the reading.</Box>
        {billId && (
          <Box sx={{ mt: 1.5 }}>
            <Button color="inherit" size="small" variant="outlined" onClick={() => setOpen(true)} startIcon={<FlagOutlinedIcon />}>
              {ACTION}
            </Button>
          </Box>
        )}
      </Alert>
      {open && billId && <ReportDialog billId={billId} language={language} onClose={() => setOpen(false)} />}
    </>
  );
}

/** For a bill the engine did not flag: the consumer can still report it, but the page does not push them to. */
export function QuietReport({ billId, language }: { billId: string; language: Language }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Box sx={{ px: 0.5 }}>
        <Button size="small" color="inherit" onClick={() => setOpen(true)} startIcon={<FlagOutlinedIcon />}
          sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary' } }}>
          {ACTION}
        </Button>
      </Box>
      {open && <ReportDialog billId={billId} language={language} onClose={() => setOpen(false)} />}
    </>
  );
}
