import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { EmptyState, ErrorState } from '@/shared/components/States';

import { useInbox, type InboxQuery } from '../api/consoleApi';
import { ComplaintsTable } from './ComplaintsTable';

const LATEST: InboxQuery = { page: 1, pageSize: 5, status: '', discom: '', q: '', sort: 'priority', triage: '', failed: false };

/** The five complaints that need an officer most, on the summary page; the inbox has the full list. */
export function LatestComplaints() {
  const result = useInbox(LATEST);
  const data = result.data;
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ p: { xs: 2, sm: 2.5 }, gap: 1.5, alignItems: { sm: 'center' } }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h2">Needs you first</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Open and overdue first, then the biggest overcharges. {data ? `${data.total} in total.` : ''}
          </Typography>
        </Box>
        <Button variant="contained" component={Link} to="/console/complaints" endIcon={<ArrowForwardIcon />}>
          Open the complaints inbox
        </Button>
      </Stack>
      {result.isError && <Box sx={{ p: 2 }}><ErrorState message="Could not load complaints." onRetry={() => void result.refetch()} /></Box>}
      {data?.total === 0 && (
        <EmptyState icon={<InboxOutlinedIcon />} title="No complaints yet"
          hint="A complaint appears here when a consumer raises one on WhatsApp. Tickets start with BM-." />
      )}
      {!result.isError && data?.total !== 0 && <ComplaintsTable rows={data?.items} loadingRows={LATEST.pageSize} />}
    </Paper>
  );
}
