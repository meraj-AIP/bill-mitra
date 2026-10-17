import { Alert, Button, Container, Grid, Stack } from '@mui/material';
import { Link, useSearchParams } from 'react-router-dom';

import { useHealth } from '@/shared/api/health';
import { BillImage } from '@/shared/components/BillImage';
import { PageHeader } from '@/shared/components/PageHeader';
import { monthLabel } from '@/shared/lib/format';

import { BillReportView } from '../components/BillReportView';
import { BillsTable } from '../components/BillsTable';
import { ReadingProgress } from '../components/ReadingProgress';
import { UploadCard } from '../components/UploadCard';
import { UscCard } from '../components/UscCard';
import { useBillsParams } from '../hooks/useBillsParams';
import { useBillUpload } from '../hooks/useBillUpload';
import type { FilePreview } from '../hooks/useFilePreview';

function Reading({ preview }: { preview: FilePreview }) {
  return (
    <Grid container spacing={{ xs: 2, md: 3 }} sx={{ alignItems: 'flex-start' }}>
      <Grid size={{ xs: 12, md: 5 }}>
        <BillImage src={preview.url} isPdf={preview.isPdf} name={preview.name} />
      </Grid>
      <Grid size={{ xs: 12, md: 7 }}>
        <ReadingProgress />
      </Grid>
    </Grid>
  );
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

export function DashboardPage() {
  const params = useBillsParams();
  const [search] = useSearchParams();
  const returnTo = search.get('for');
  const flow = useBillUpload(returnTo);
  const { preview, reading, unsaved } = flow;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: { xs: 3, md: 4 } }}>
        <PageHeader title="Check your electricity bill"
          lead="Upload a photo or PDF of your TGSPDCL or TGNPDCL bill. We check each charge against the TGERC tariff and explain it in your language." />
        <ReadingOffNotice />
        {returnTo && !reading && <ReturnNotice billId={returnTo} month={search.get('month')} />}
        {reading && <Reading preview={reading} />}
        {unsaved && (
          <BillReportView report={unsaved} language={flow.language} onLanguage={flow.setLanguage} onRetry={flow.startOver}
            imageUrl={preview && !preview.isPdf ? preview.url : undefined} />
        )}
        {!reading && !unsaved && (
          <UploadCard language={flow.language} onLanguage={flow.setLanguage} onFile={flow.onFile}
            onDismiss={flow.startOver} error={flow.error} />
        )}
        {!reading && !unsaved && !returnTo && <UscCard language={flow.language} />}
        <BillsTable query={params.query} pageSizes={params.pageSizes} onPage={params.setPage}
          onPageSize={params.setPageSize} onStatus={params.setStatus} onSort={params.setSort} />
      </Stack>
    </Container>
  );
}
