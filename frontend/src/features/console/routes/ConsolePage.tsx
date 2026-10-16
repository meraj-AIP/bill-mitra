import { Button, Container, Stack } from '@mui/material';
import { Link } from 'react-router-dom';

import { scopeLabel, spansDiscoms, useAuth } from '@/features/auth';
import { PageHeader } from '@/shared/components/PageHeader';
import { ErrorState } from '@/shared/components/States';

import { useSummary } from '../api/consoleApi';
import { ActivityGrid } from '../components/ActivityGrid';
import { LatestComplaints } from '../components/LatestComplaints';
import { SummaryFilters } from '../components/SummaryFilters';
import { SummaryTiles } from '../components/SummaryTiles';
import { WeekPanel } from '../components/WeekPanel';
import { useSummaryParams } from '../hooks/useSummaryParams';

/** What a DISCOM officer sees. Real activity only, counts only; no consumer names or full numbers. */
export function ConsolePage() {
  const { account, can } = useAuth();
  const params = useSummaryParams();
  const summary = useSummary(true, params.filters);
  // A DISCOM filter only means something to someone who sees both DISCOMs; the server scopes everyone else.
  const canPickDiscom = spansDiscoms(account);
  const scope = scopeLabel(account);
  const scopeNote = !canPickDiscom && scope ? `Showing ${scope}` : null;
  const data = summary.data;
  // The tile groups already say when the window is empty, so the charts simply step aside.
  const quiet = data !== undefined && data.bills_read === 0 && data.questions === 0;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="For DISCOM staff" title="Department console"
          lead="Bills read and checked, questions asked and complaints raised. Updates every 15 seconds."
          actions={can('complaints.view') ? <Button variant="outlined" component={Link} to="/console/complaints">Complaints inbox</Button> : null} />
        {summary.isError && <ErrorState message="Could not load the console." onRetry={() => void summary.refetch()} />}
        <SummaryFilters filters={params.filters} canPickDiscom={canPickDiscom} scopeNote={scopeNote}
          onDays={params.setDays} onDiscom={params.setDiscom} />
        <WeekPanel data={data} />
        <SummaryTiles data={data} />
        {!quiet && <ActivityGrid data={data} />}
        {can('complaints.view') && <LatestComplaints />}
      </Stack>
    </Container>
  );
}
