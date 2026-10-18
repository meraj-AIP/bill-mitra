import { Box, Stack } from '@mui/material';

import { usePendingApprovals } from '../api/approvalsApi';

/** The tab's name with how many proposals wait for this account. */
export function ApprovalsTabLabel({ label }: { label: string }) {
  const { data } = usePendingApprovals(true);
  const waiting = data?.pending ?? 0;
  return (
    <Stack direction="row" component="span" sx={{ gap: 0.75, alignItems: 'center' }}>
      {label}
      {waiting > 0 && (
        <Box component="span" aria-label={`${waiting} waiting`}
          sx={{ px: 0.75, minWidth: 20, borderRadius: 5, bgcolor: 'primary.main', color: 'primary.contrastText', typography: 'caption', fontWeight: 600, lineHeight: '20px', textAlign: 'center' }}>
          {waiting > 99 ? '99+' : waiting}
        </Box>
      )}
    </Stack>
  );
}
