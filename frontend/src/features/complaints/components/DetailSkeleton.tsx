import { Grid, Skeleton, Stack } from '@mui/material';

export function DetailSkeleton() {
  return (
    <Stack sx={{ gap: 3 }} aria-busy aria-label="Loading the complaint">
      <Skeleton width={120} />
      <Skeleton variant="rounded" height={44} sx={{ maxWidth: 420 }} />
      <Skeleton variant="rounded" height={76} />
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 5 }}>
          <Skeleton variant="rounded" height={380} />
        </Grid>
        <Grid size={{ xs: 12, md: 7 }}>
          <Stack sx={{ gap: 1.5 }}>
            <Skeleton variant="rounded" height={84} sx={{ width: '70%' }} />
            <Skeleton variant="rounded" height={84} sx={{ width: '60%', alignSelf: 'flex-end' }} />
            <Skeleton variant="rounded" height={140} />
          </Stack>
        </Grid>
      </Grid>
    </Stack>
  );
}
