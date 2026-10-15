import { Alert, Container, Grid, Stack } from '@mui/material';

import { useHealth } from '@/shared/api/health';
import { BillImage } from '@/shared/components/BillImage';
import { PageHeader } from '@/shared/components/PageHeader';

import { BillReportView } from '../components/BillReportView';
import { BillsTable } from '../components/BillsTable';
import { ReadingProgress } from '../components/ReadingProgress';
import { UploadCard } from '../components/UploadCard';
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

export function DashboardPage() {
  const params = useBillsParams();
  const flow = useBillUpload();
  const { preview, reading, unsaved } = flow;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: { xs: 3, md: 4 } }}>
        <PageHeader title="Check your electricity bill"
          lead="Upload a photo or PDF of your TGSPDCL or TGNPDCL bill. We check each charge against the TGERC tariff and explain it in your language." />
        <ReadingOffNotice />
        {reading && <Reading preview={reading} />}
        {unsaved && (
          <BillReportView report={unsaved} language={flow.language} onLanguage={flow.setLanguage} onRetry={flow.startOver}
            imageUrl={preview && !preview.isPdf ? preview.url : undefined} />
        )}
        {!reading && !unsaved && (
          <UploadCard language={flow.language} onLanguage={flow.setLanguage} onFile={flow.onFile}
            onDismiss={flow.startOver} error={flow.error} />
        )}
        <BillsTable query={params.query} pageSizes={params.pageSizes} onPage={params.setPage}
          onPageSize={params.setPageSize} onStatus={params.setStatus} onSort={params.setSort} />
      </Stack>
    </Container>
  );
}
