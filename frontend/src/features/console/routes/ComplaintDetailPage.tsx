import { Button, Container, Grid, Paper, Stack, Typography } from '@mui/material';
import { Link, useParams } from 'react-router-dom';

import { ComplaintEvidence, ComplaintHeader, DetailSkeleton } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useConsoleComplaint } from '../api/consoleApi';
import { ReplyPanel } from '../components/ReplyPanel';
import { StatusControl } from '../components/StatusControl';
import { ThreadPanel } from '../components/ThreadPanel';

export function ComplaintDetailPage() {
  const { ticket = '' } = useParams();
  const complaint = useConsoleComplaint(ticket);
  const data = complaint.data;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 4 } }}>
      {complaint.isPending && <DetailSkeleton />}
      {isStatus(complaint.error, 404) && (
        <EmptyState title="Complaint not found" hint="The ticket may be mistyped, or it may belong to a DISCOM outside your access."
          action={<Button variant="contained" component={Link} to="/console/complaints">Back to the inbox</Button>} />
      )}
      {complaint.isError && !isStatus(complaint.error, 404) && (
        <ErrorState message={complaint.error.message} onRetry={() => void complaint.refetch()} />
      )}
      {data && (
        <Stack sx={{ gap: 3 }}>
          {/* A zero amount means none was given; the header shows that as not stated rather than Rs 0. */}
          <ComplaintHeader complaint={{ ...data, amount: data.amount || null }} backTo="/console/complaints" backLabel="Complaints inbox"
            actions={<StatusControl complaint={data} />} />
          <Grid container spacing={3} sx={{ alignItems: 'flex-start' }}>
            <Grid size={{ xs: 12, md: 7 }} sx={{ order: { md: 2 } }}>
              <Paper variant="outlined" component="section" aria-labelledby="thread-title" sx={{ p: { xs: 2, sm: 2.5 } }}>
                <Typography id="thread-title" variant="h2" sx={{ mb: 2 }}>Conversation</Typography>
                <ThreadPanel ticket={data.ticket} messages={data.messages} />
                <Stack sx={{ mt: 3, pt: 2.5, borderTop: 1, borderColor: 'divider' }}>
                  <ReplyPanel complaint={data} />
                </Stack>
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 5 }} sx={{ order: { md: 1 } }}>
              <ComplaintEvidence complaint={data} staff />
            </Grid>
          </Grid>
        </Stack>
      )}
    </Container>
  );
}
