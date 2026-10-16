import { Container, Grid, Skeleton, Stack } from '@mui/material';

import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { usePolicies } from '../api/policyApi';
import { PolicyCard } from '../components/PolicyCard';

export function PolicyPage() {
  const policies = usePolicies();
  const rows = policies.data;
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Administration" title="Review policy"
          lead="Per DISCOM: which bills the engine flags as a likely wrong reading, how much a section AE can reduce alone, and how long a case may stay open." />
        {policies.isError && <ErrorState message="Could not load the review policy." onRetry={() => void policies.refetch()} />}
        {rows?.length === 0 && <EmptyState title="No DISCOM policy yet" hint="Policies are created with the DISCOM units when the server starts." />}
        <Grid container spacing={3}>
          {!rows && !policies.isError && [0, 1].map((i) => (
            <Grid key={i} size={{ xs: 12, md: 6 }}><Skeleton variant="rounded" height={560} /></Grid>
          ))}
          {rows?.map((p) => (
            <Grid key={p.discom} size={{ xs: 12, md: 6 }}>
              <PolicyCard policy={p} />
            </Grid>
          ))}
        </Grid>
      </Stack>
    </Container>
  );
}
