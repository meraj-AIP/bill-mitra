import { Alert, Button, Container, Grid, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useHealth } from '@/shared/api/health';
import { BillImage } from '@/shared/components/BillImage';
import { PageHeader } from '@/shared/components/PageHeader';
import type { FilePreview } from '@/shared/hooks/useFilePreview';
import { monthLabel } from '@/shared/lib/format';

import { BillReportView } from '../components/BillReportView';
import { BillsTable } from '../components/BillsTable';
import { ReadingProgress } from '../components/ReadingProgress';
import { StillReading } from '../components/StillReading';
import { UploadCard } from '../components/UploadCard';
import { UscCard } from '../components/UscCard';
import { useBillsParams } from '../hooks/useBillsParams';
import { useBillUpload, type Sending } from '../hooks/useBillUpload';

function WithPreview({ preview, children }: { preview: FilePreview; children: ReactNode }) {
  return (
    <Grid container spacing={{ xs: 2, md: 3 }} sx={{ alignItems: 'flex-start' }}>
      <Grid size={{ xs: 12, md: 5 }}>
        <BillImage src={preview.url} isPdf={preview.isPdf} name={preview.name} />
      </Grid>
      <Grid size={{ xs: 12, md: 7 }}>{children}</Grid>
    </Grid>
  );
}

/** The send gave up. The photo stays on screen so Try again needs no new pick. */
function SendFailed({ message, onTryAgain, onStartOver }: { message: string; onTryAgain: (() => void) | null; onStartOver: () => void }) {
  return (
    <Alert severity="error" action={
      <Stack sx={{ gap: 0.5 }}>
        {onTryAgain && <Button color="inherit" size="small" onClick={onTryAgain}>Try again</Button>}
        <Button color="inherit" size="small" onClick={onStartOver}>Choose another</Button>
      </Stack>
    }>
      <Typography variant="body2">{message}</Typography>
    </Alert>
  );
}

function Reading({ preview, sending }: { preview: FilePreview; sending: Sending | null }) {
  return <WithPreview preview={preview}><ReadingProgress sending={sending} /></WithPreview>;
}

function ReadingOffNotice() {
  const health = useHealth();
  if (health.data?.modes.vision !== 'off') return null;
  return (
    <Alert severity="info">Bill reading is switched off right now. You can still upload, but nothing will be read or checked.</Alert>
  );
}

/** Shown when the consumer came here to send an earlier bill that a report asked for. */
function ReturnNotice({ billId, month }: { billId: string; month: string | null }) {
  return (
    <Alert severity="info" action={<Button color="inherit" size="small" component={Link} to={`/bills/${encodeURIComponent(billId)}`}>Cancel</Button>}>
      {month ? `Upload your ${monthLabel(month)} bill.` : 'Upload your earlier bill.'} When it is read, we take you back to the bill you reported.
    </Alert>
  );
}

type Flow = ReturnType<typeof useBillUpload>;

/** The upload card, or what replaces it while a bill is sent, read, queued or has failed. */
function UploadStage({ flow, returnTo }: { flow: Flow; returnTo: string | null }) {
  const { preview, view } = flow;
  if (view === 'reading' && preview) return <Reading preview={preview} sending={flow.sending} />;
  if (view === 'waiting') return <StillReading checkFailed={flow.waitCheckFailed} onStartOver={flow.startOver} />;
  if (view === 'failed' && preview) {
    return (
      <WithPreview preview={preview}>
        <SendFailed message={flow.error ?? ''} onTryAgain={flow.tryAgain} onStartOver={flow.startOver} />
      </WithPreview>
    );
  }
  if (view === 'unsaved' && flow.unsaved) {
    return (
      <BillReportView report={flow.unsaved} language={flow.language} onLanguage={flow.setLanguage} onRetry={flow.startOver}
        imageUrl={preview && !preview.isPdf ? preview.url : undefined} />
    );
  }
  return (
    <>
      <UploadCard language={flow.language} onLanguage={flow.setLanguage} onFile={flow.onFile} onDismiss={flow.startOver} error={flow.error} />
      {!returnTo && <UscCard language={flow.language} />}
    </>
  );
}

export function DashboardPage() {
  const params = useBillsParams();
  const [search] = useSearchParams();
  const returnTo = search.get('for');
  const flow = useBillUpload(returnTo);

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: { xs: 3, md: 4 } }}>
        <PageHeader title="Check your electricity bill"
          lead="Upload a photo or PDF of your TGSPDCL or TGNPDCL bill. We check each charge against the TGERC tariff and explain it in your language." />
        <ReadingOffNotice />
        {returnTo && flow.view === 'upload' && <ReturnNotice billId={returnTo} month={search.get('month')} />}
        <UploadStage flow={flow} returnTo={returnTo} />
        <BillsTable query={params.query} pageSizes={params.pageSizes} onPage={params.setPage}
          onPageSize={params.setPageSize} onStatus={params.setStatus} onSort={params.setSort} />
      </Stack>
    </Container>
  );
}
