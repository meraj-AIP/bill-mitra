import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import { Button, Container, Stack } from '@mui/material';

import { scopeLabel, useAuth } from '@/features/auth';
import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState } from '@/shared/components/States';

import { useCases } from '../api/reviewApi';
import { CasesTable } from '../components/CasesTable';
import { ExportRevisions } from '../components/ExportRevisions';
import { QueueFilters } from '../components/QueueFilters';
import { StateTabs } from '../components/StateTabs';
import { useQueueParams } from '../hooks/useQueueParams';

/** Bills the engine flagged as a likely wrong reading, in the reviewer's units. */
export function ReviewQueuePage() {
  const { account, can } = useAuth();
  const params = useQueueParams();
  const { query } = params;
  const result = useCases(query);
  const counts = result.data?.counts;

  const empty = params.filtered ? (
    <EmptyState icon={<FactCheckOutlinedIcon />} title="No cases match these filters"
      hint="Try another state, turn off a switch, or clear the ticket search."
      action={<Button variant="outlined" onClick={params.clear}>Clear filters</Button>} />
  ) : (
    <EmptyState icon={<FactCheckOutlinedIcon />} title="No cases in your units"
      hint="A case opens when the engine flags a bill as far above the household's usual, or a consumer asks for a check." />
  );

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow={scopeLabel(account) ?? 'Bill review'} title="Bill review"
          lead="Wrong-reading cases routed to your units. Open a case to see why it was flagged, talk to the consumer and record a decision."
          actions={can('cases.export') ? <ExportRevisions /> : null} />
        <StateTabs value={query.state} counts={counts} onChange={params.setState} />
        <QueueFilters params={params} overdueCount={counts?.overdue} />
        <ListPanel result={result} page={query.page} pageSize={query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={empty}>
          {(rows, dimmed) => <CasesTable rows={rows} loadingRows={Math.min(query.pageSize, 8)} dimmed={dimmed} />}
        </ListPanel>
      </Stack>
    </Container>
  );
}
