import CloudOffOutlinedIcon from '@mui/icons-material/CloudOffOutlined';
import { Container, Stack, Typography } from '@mui/material';

import { useOnline } from '@/shared/hooks/useOnline';

/** A thin strip under the header while the browser is offline. Pages keep what they already loaded. */
export function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <Stack role="status" aria-live="polite" sx={{ bgcolor: 'warning.light', borderBottom: 1, borderColor: 'warning.main', '@media print': { display: 'none' } }}>
      <Container maxWidth="lg">
        <Stack direction="row" sx={{ py: 1, gap: 1, alignItems: 'center' }}>
          <CloudOffOutlinedIcon fontSize="small" sx={{ color: 'warning.dark' }} />
          <Typography variant="body2" sx={{ color: 'warning.dark' }}>
            You are offline. Anything you send now will go when the connection is back.
          </Typography>
        </Stack>
      </Container>
    </Stack>
  );
}
