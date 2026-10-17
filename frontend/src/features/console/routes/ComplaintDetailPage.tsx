import { Box, Button, Container, Stack } from '@mui/material';
import { Link, useParams } from 'react-router-dom';

import { ComplaintEvidence, ComplaintFacts, ComplaintHeader, ComplaintTimeline, DetailSkeleton } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { Panel } from '@/shared/components/Panel';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useConsoleComplaint } from '../api/consoleApi';
import { ActionsColumn } from '../components/ActionsColumn';
import { ThreadPanel } from '../components/ThreadPanel';

const INBOX = '/console/complaints';

export function ComplaintDetailPage() {
  const { ticket = '' } = useParams();
  const complaint = useConsoleComplaint(ticket);
  const data = complaint.data;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 4 } }}>
      {complaint.isPending && <DetailSkeleton />}
      {isStatus(complaint.error, 404) && (
        <EmptyState title="Complaint not found" hint="The ticket may be mistyped, or it may belong to a DISCOM outside your access."
          action={<Button variant="contained" component={Link} to={INBOX}>Back to the inbox</Button>} />
      )}
      {complaint.isError && !isStatus(complaint.error, 404) && (
        <ErrorState message={complaint.error.message} onRetry={() => void complaint.refetch()} />
      )}
      {data && (
        <Stack sx={{ gap: { xs: 3, md: 4 } }}>
          <ComplaintHeader complaint={data} backTo={INBOX} backLabel="Complaints inbox" />
          <Box sx={{ display: 'grid', gap: 3, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 1fr) 360px', lg: 'minmax(0, 1fr) 380px' } }}>
            <Stack sx={{ gap: 3, minWidth: 0 }}>
              <ComplaintFacts complaint={data} />
              <ComplaintEvidence complaint={data} staff />
              <ComplaintTimeline complaint={data} />
              <Panel title="Conversation" caption="Messages with the consumer, oldest first.">
                <ThreadPanel ticket={data.ticket} messages={data.messages} />
              </Panel>
            </Stack>
            <ActionsColumn complaint={data} />
          </Box>
        </Stack>
      )}
    </Container>
  );
}
