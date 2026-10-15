import { Alert, AlertTitle, Box, Button, Paper, Stack, Typography } from '@mui/material';

import { rupees } from '@/shared/lib/format';

import type { BillReport } from '../api/types';
import { DOCUMENT_TYPE, OUTCOME_TITLE, OUTCOME_TONE, PHOTO_TIPS, QUALITY } from '../model/labels';

function bannerTitle(report: BillReport): string {
  const audit = report.analysis?.audit;
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

export function OutcomeBanner({ report }: { report: BillReport }) {
  return (
    <Alert severity={bannerTone(report)} variant="standard" sx={{ border: 1, borderColor: 'divider' }}>
      <AlertTitle sx={{ fontWeight: 600, mb: report.outcome_reason ? 0.5 : 0 }}>{bannerTitle(report)}</AlertTitle>
      {report.outcome_reason}
    </Alert>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>{value}</Typography>
    </Box>
  );
}

/** For "not a bill" and "retake": what the reader saw, and how to get a photo it can read. */
export function RetakeHelp({ report, onRetry }: { report: BillReport; onRetry: () => void }) {
  const c = report.classification;
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 } }}>
      {c && (
        <>
          <Typography variant="h3" component="h2">What we saw</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>{c.reason}</Typography>
          <Stack direction="row" sx={{ gap: 3, mt: 1.5, flexWrap: 'wrap' }}>
            <Fact label="Looks like" value={DOCUMENT_TYPE[c.document_type]} />
            <Fact label="Photo quality" value={QUALITY[c.quality]} />
            {c.quality_issue && <Fact label="Problem" value={c.quality_issue} />}
          </Stack>
        </>
      )}
      <Typography variant="h3" component="h2" sx={{ mt: c ? 3 : 0 }}>For a photo we can read</Typography>
      <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5, color: 'text.secondary', '& li': { mb: 0.5 } }}>
        {PHOTO_TIPS.map((tip) => (
          <Typography component="li" variant="body2" key={tip}>{tip}</Typography>
        ))}
      </Box>
      <Button variant="contained" onClick={onRetry} sx={{ mt: 2 }}>
        Upload another photo
      </Button>
    </Paper>
  );
}
