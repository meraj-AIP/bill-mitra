import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import { Box, Button, Grid, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import type { Language } from '@/shared/lib/languages';
import { BillImage } from '@/shared/components/BillImage';

import type { BillReport } from '../api/types';
import { BillFacts } from './BillFacts';
import { CaptureReport } from './CaptureReport';
import { ComplainOnWhatsApp } from './ComplainOnWhatsApp';
import { ChargesCheck } from './ChargesCheck';
import { HistoryChart } from './HistoryChart';
import { MisreadNote } from './MisreadNote';
import { LanguageSelect } from './LanguageSelect';
import { OutcomeBanner, RetakeHelp } from './OutcomeBanner';
import { QuietReport, SpikeNote } from './ReviewRequest';
import { ReviewStatus } from './ReviewStatus';
import { Explanation, Outlook } from './Outlook';
import { SlabBreakdown } from './SlabBreakdown';

interface BillReportViewProps {
  report: BillReport;
  language: Language;
  onLanguage: (language: Language) => void;
  onRetry: () => void;
  /** A local preview of the file just chosen, used when nothing was saved on the server. */
  imageUrl?: string | undefined;
  reloading?: boolean;
}

function Actions({ onRetry }: { onRetry: () => void }) {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 } }}>
      <Typography variant="h3" component="h2">Questions about this bill?</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, maxWidth: '60ch' }}>
        Ask the assistant in Telugu, English, Hindi or Urdu, by typing or by voice. To raise a complaint, ask it there;
        the DISCOM replies on WhatsApp.
      </Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1, mt: 2 }}>
        <Button variant="contained" component={Link} to="/assistant" startIcon={<ChatOutlinedIcon />}>
          Ask about this bill
        </Button>
        <Button variant="outlined" onClick={onRetry}>Check another bill</Button>
      </Stack>
    </Paper>
  );
}

function Analysed({ report, language, onLanguage, reloading }: Pick<BillReportViewProps, 'report' | 'language' | 'onLanguage'> & { reloading: boolean }) {
  const { bill, capture, analysis } = report;
  return (
    <>
      {bill && <BillFacts bill={bill} final={report.final} />}
      {capture && <CaptureReport capture={capture} confidence={bill?.confidence ?? null} />}
      {analysis && (
        <>
          <ChargesCheck audit={analysis.audit} />
          <SlabBreakdown analysis={analysis} bill={bill} />
          <HistoryChart history={analysis.history} tariffId={analysis.tariff_id} />
          <Outlook analysis={analysis} />
          <Stack direction="row" sx={{ gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="subtitle2" sx={{ flex: 1 }}>Explanation language</Typography>
            <LanguageSelect value={language} onChange={onLanguage} disabled={reloading} />
          </Stack>
          <Explanation paragraphs={analysis.explanation} language={language} />
        </>
      )}
    </>
  );
}

/** A report on this bill takes the place of the spike note; the note only offers to start one. */
function Review({ report, language }: { report: BillReport; language: Language }) {
  if (report.review) return <ReviewStatus review={report.review} billId={report.id} />;
  const spike = report.analysis?.spike;
  return spike?.flagged ? <SpikeNote spike={spike} billId={report.id} language={language} /> : null;
}

/** Next steps on a checked bill. An unflagged bill with no report still gets a quiet way to report a problem. */
function Checked({ report, language, onRetry }: { report: BillReport; language: Language; onRetry: () => void }) {
  const quiet = report.id && !report.review && !report.analysis?.spike?.flagged;
  return (
    <>
      <Actions onRetry={onRetry} />
      {quiet && <QuietReport billId={report.id ?? ''} language={language} />}
    </>
  );
}

const NEEDS_RETAKE = new Set(['not_a_bill', 'retake', 'reading_failed']);

export function BillReportView({ report, language, onLanguage, onRetry, imageUrl, reloading = false }: BillReportViewProps) {
  const { outcome } = report;
  const needsRetake = NEEDS_RETAKE.has(outcome);
  // A bill fetched by its USC has no photo: the report then takes the full width instead of a broken image.
  const src = imageUrl ?? report.media_url;
  return (
    <Grid container spacing={{ xs: 2, md: 3 }} sx={{ alignItems: 'flex-start' }}>
      {src && (
        <Grid size={{ xs: 12, md: 5 }} sx={{ position: { md: 'sticky' }, top: { md: 144 } }}>
          <BillImage src={src} isPdf={report.mime_type === 'application/pdf'} />
        </Grid>
      )}
      <Grid size={{ xs: 12, md: src ? 7 : 12 }}>
        <Stack sx={{ gap: 2, opacity: reloading ? 0.6 : 1, transition: 'opacity 200ms' }} aria-busy={reloading}>
          <OutcomeBanner report={report} />
          <Review report={report} language={language} />
          {report.misread && <MisreadNote misread={report.misread} language={language} />}
          {report.analysis?.audit.status === 'mismatch' && <ComplainOnWhatsApp />}
          {needsRetake && <RetakeHelp report={report} onRetry={onRetry} />}
          {outcome === 'reading_off' && (
            <Box>
              <Button variant="outlined" onClick={onRetry}>Upload another file</Button>
            </Box>
          )}
          <Analysed report={report} language={language} onLanguage={onLanguage} reloading={reloading} />
          {outcome === 'checked' && <Checked report={report} language={language} onRetry={onRetry} />}
        </Stack>
      </Grid>
    </Grid>
  );
}
