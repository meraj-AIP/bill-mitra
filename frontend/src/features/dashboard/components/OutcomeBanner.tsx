import { Alert, AlertTitle, Box, Button, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { rupees } from '@/shared/lib/format';

import type { BillReport } from '../api/types';
import { OUTCOME_TITLE, OUTCOME_TONE, PHOTO_TIPS } from '../model/labels';

const isMeter = (report: BillReport) => report.classification?.document_type === 'meter';

function bannerTitle(report: BillReport): string {
  const audit = report.analysis?.audit;
  if (report.outcome === 'not_a_bill' && isMeter(report)) return 'This looks like a photo of the meter';
  if (report.outcome !== 'checked' || !audit) return OUTCOME_TITLE[report.outcome];
  if (audit.status === 'mismatch') return `This bill looks overcharged by ${rupees(audit.overcharge)}`;
  if (audit.status === 'verified') return 'Every charge matches the TGERC tariff';
  return OUTCOME_TITLE.checked;
}

function bannerTone(report: BillReport) {
  if (report.outcome === 'checked' && report.analysis?.audit.status === 'mismatch') return 'error';
  if (report.outcome === 'checked' && report.analysis?.audit.status !== 'verified') return 'info';
  return OUTCOME_TONE[report.outcome];
}

/** The outcome reason is the server's translated sentence; model text from the classifier is never shown. */
export function OutcomeBanner({ report }: { report: BillReport }) {
  return (
    <Alert severity={bannerTone(report)} variant="standard" sx={{ border: 1, borderColor: 'divider' }}>
      <AlertTitle sx={{ fontWeight: 600, mb: report.outcome_reason ? 0.5 : 0 }}>{bannerTitle(report)}</AlertTitle>
      {report.outcome_reason}
    </Alert>
  );
}

/** Opens the assistant with an example of how to type the units, for when no photo will read. */
const TYPE_UNITS_PATH = '/assistant?hint=units';

/** The parts of the slip that could not be read or did not add up, in the server's own labels. */
function partsToRetake(report: BillReport): string[] {
  const capture = report.capture;
  if (!capture) return [];
  const fields = capture.fields.filter((f) => f.status !== 'captured').map((f) => f.label);
  const checks = capture.checks.filter((c) => c.status === 'fail').map((c) => c.label);
  return [...new Set([...fields, ...checks])];
}

function Guidance({ report }: { report: BillReport }) {
  if (report.outcome === 'reading_failed') {
    return <Typography variant="body2">The reading did not work this time. Upload the bill again, or type the units from it.</Typography>;
  }
  if (report.outcome === 'not_a_bill') {
    return (
      <Typography variant="body2">
        {isMeter(report)
          ? 'We need the bill itself: the printed slip the meter reader leaves. Upload a photo of that, or type the units printed on it.'
          : 'We check TGSPDCL and TGNPDCL electricity bills. Upload a photo of one, or type the units printed on it.'}
      </Typography>
    );
  }
  const parts = partsToRetake(report);
  return (
    <>
      {parts.length > 0 && (
        <>
          <Typography variant="subtitle2">Make sure these are clear in the new photo</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.25 }}>{parts.join(', ')}</Typography>
        </>
      )}
      <Typography variant="subtitle2" sx={{ mt: parts.length ? 2 : 0 }}>For a photo we can read</Typography>
      <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5, color: 'text.secondary', '& li': { mb: 0.5 } }}>
        {PHOTO_TIPS.map((tip) => (
          <Typography component="li" variant="body2" key={tip}>{tip}</Typography>
        ))}
      </Box>
    </>
  );
}

/** For "not a bill", "retake" and a read that failed: what to do next, with typing the units as the way out. */
export function RetakeHelp({ report, onRetry }: { report: BillReport; onRetry: () => void }) {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 } }}>
      <Typography variant="h3" component="h2" sx={{ mb: 1 }}>What to do next</Typography>
      <Guidance report={report} />
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1, mt: 2 }}>
        <Button variant="contained" onClick={onRetry}>
          {report.outcome === 'reading_failed' ? 'Upload again' : 'Upload another photo'}
        </Button>
        <Button variant="outlined" component={Link} to={TYPE_UNITS_PATH}>Type the units</Button>
      </Stack>
    </Paper>
  );
}
