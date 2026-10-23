import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Button, Container, Grid, Skeleton, Stack, Typography } from '@mui/material';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/shared/api/http';
import { EmptyState } from '@/shared/components/States';
import { ErrorNotice } from '@/shared/feedback';
import { dateTime, monthLabel } from '@/shared/lib/format';
import { toLanguage, type Language } from '@/shared/lib/languages';

import { useBill } from '../api/billsApi';
import type { BillReport } from '../api/types';
import { BillReportView } from '../components/BillReportView';

function ReportSkeleton() {
  return (
    <Grid container spacing={{ xs: 2, md: 3 }} aria-busy aria-label="Loading the bill report">
      <Grid size={{ xs: 12, md: 5 }}>
        <Skeleton variant="rounded" height={520} />
      </Grid>
      <Grid size={{ xs: 12, md: 7 }}>
        <Stack sx={{ gap: 2 }}>
          <Skeleton variant="rounded" height={72} />
          <Skeleton variant="rounded" height={140} />
          <Skeleton variant="rounded" height={280} />
          <Skeleton variant="rounded" height={220} />
        </Stack>
      </Grid>
    </Grid>
  );
}

function Heading({ report }: { report: BillReport | undefined }) {
  const bill = report?.bill;
  const details = [
    report?.created_at ? `Uploaded ${dateTime(report.created_at)}` : null,
    bill?.discom && bill.discom !== 'UNKNOWN' ? bill.discom : null,
    bill?.service_masked ? `service no. ${bill.service_masked}` : null,
  ].filter(Boolean);
  return (
    <Stack sx={{ gap: 1, alignItems: 'flex-start' }}>
      <Button component={Link} to="/" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1 }}>
        All bills
      </Button>
      <Typography variant="h1">{bill ? `${monthLabel(bill.bill_month)} bill` : 'Bill report'}</Typography>
      {details.length > 0 && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>{details.join(', ')}</Typography>
      )}
    </Stack>
  );
}

export function BillPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const language = toLanguage(params.get('lang'));
  const bill = useBill(id, language);
  const report = bill.data;
  const notFound = bill.error instanceof ApiError && bill.error.status === 404;

  const setLanguage = (next: Language) => setParams(next === 'te' ? {} : { lang: next }, { replace: true });

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <Heading report={report} />
        {bill.isPending && <ReportSkeleton />}
        {notFound && (
          <EmptyState title="We could not find this bill"
            hint="It may belong to another account, or the link may be mistyped."
            action={<Button variant="contained" component={Link} to="/">Go to the dashboard</Button>} />
        )}
        {bill.isError && !notFound && <ErrorNotice error={bill.error} title="Could not load this bill" retrySafe onRetry={() => void bill.refetch()} />}
        {report && (
          <BillReportView report={report} language={language} onLanguage={setLanguage} onRetry={() => navigate('/')}
            reloading={bill.isPlaceholderData} />
        )}
      </Stack>
    </Container>
  );
}
