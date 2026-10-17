import { Box, Skeleton, Stack } from '@mui/material';

/** Mirrors the detail layout: header, a main column of panels and the side column. */
export function DetailSkeleton() {
  return (
    <Stack sx={{ gap: { xs: 3, md: 4 } }} aria-busy aria-label="Loading the complaint">
      <Stack sx={{ gap: 1.5 }}>
        <Skeleton width={140} />
        <Skeleton width={220} height={18} />
        <Skeleton variant="rounded" height={40} sx={{ maxWidth: 440 }} />
        <Stack direction="row" sx={{ gap: 1 }}>
          <Skeleton variant="rounded" width={88} height={32} />
          <Skeleton variant="rounded" width={120} height={32} />
          <Skeleton variant="rounded" width={100} height={32} />
        </Stack>
      </Stack>
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 1fr) 360px', lg: 'minmax(0, 1fr) 380px' } }}>
        <Stack sx={{ gap: 3 }}>
          <Skeleton variant="rounded" height={190} />
          <Skeleton variant="rounded" height={260} />
          <Skeleton variant="rounded" height={160} />
        </Stack>
        <Skeleton variant="rounded" height={420} />
      </Box>
    </Stack>
  );
}
