import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { Container, MenuItem, Stack, TextField, Typography } from '@mui/material';

import { useHealth } from '@/shared/api/health';
import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { SendStatus } from '@/shared/components/SendStatus';
import { EmptyState } from '@/shared/components/States';

import { PARKED_KINDS, useDismissParked, useParkedJobs, useRetryParked } from '../api/operationsApi';
import { ParkedTable } from '../components/ParkedTable';
import { QueueCounts } from '../components/QueueCounts';
import { useOperationsParams } from '../hooks/useAdminParams';
import { PARKED_KIND_LABEL } from '../model/labels';

const REFRESH_MS = 30_000;

function Filters({ kind, sort, onKind, onSort }: { kind: string; sort: string; onKind: (k: string) => void; onSort: (s: string) => void }) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5 }}>
      <TextField select size="small" label="Kind" value={kind} onChange={(e) => onKind(e.target.value)} sx={{ minWidth: 220 }}>
        <MenuItem value="">All kinds</MenuItem>
        {PARKED_KINDS.map((k) => <MenuItem key={k} value={k}>{PARKED_KIND_LABEL[k]}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Sort" value={sort || 'newest'} onChange={(e) => onSort(e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="newest">Newest first</MenuItem>
        <MenuItem value="oldest">Oldest first</MenuItem>
      </TextField>
    </Stack>
  );
}

/** Queue sizes and the jobs that ran out of attempts, with Retry and Dismiss. No message text is shown. */
export function OperationsPage() {
  const params = useOperationsParams();
  const health = useHealth(REFRESH_MS);
  const result = useParkedJobs(params.query);
  const retry = useRetryParked();
  const dismiss = useDismissParked();
  const running = retry.isPending ? retry : dismiss.isPending ? dismiss : null;
  const failed = retry.isError ? retry : dismiss.isError ? dismiss : null;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Administration" title="Operations"
          lead="What is waiting in each queue, and the jobs that ran out of attempts. Retry puts a job back in its queue; Dismiss takes it off this list." />
        <QueueCounts queues={health.data?.queues} loading={health.isPending} />
        <Typography variant="h2">Parked failures</Typography>
        <Filters kind={params.query.kind} sort={params.query.sort} onKind={params.setKind} onSort={params.setSort} />
        {running && <SendStatus state={running} />}
        {failed && (
          <SendStatus state={failed} onTryAgain={failed.variables ? () => failed.mutate(failed.variables) : undefined} />
        )}
        <ListPanel result={result} page={params.query.page} pageSize={params.query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={<EmptyState icon={<TaskAltOutlinedIcon />} title="Nothing parked"
            hint={params.query.kind ? 'No parked jobs of this kind. Pick another, or All kinds.' : 'Every job either finished or is still being retried.'} />}>
          {(rows, dimmed) => (
            <ParkedTable rows={rows} loadingRows={params.query.pageSize} dimmed={dimmed}
              action={{ busyId: running?.variables?.id ?? null, onRetry: (job) => retry.mutate(job), onDismiss: (job) => dismiss.mutate(job) }} />
          )}
        </ListPanel>
      </Stack>
    </Container>
  );
}
