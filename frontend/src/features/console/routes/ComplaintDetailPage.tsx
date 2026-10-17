import { Alert, Box, Button, Container, Stack } from '@mui/material';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '@/features/auth';
import {
  ComplaintEvidence, ComplaintFacts, ComplaintHeader, ComplaintTimeline, DetailSkeleton, pagePhotos, RequestList, type ComplaintDetail,
} from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { Panel } from '@/shared/components/Panel';
import { PhotoGallery } from '@/shared/components/PhotoGallery';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useConsoleComplaint } from '../api/consoleApi';
import { ActionsColumn } from '../components/ActionsColumn';
import { ComplaintAssist } from '../components/ComplaintAssist';
import { ThreadPanel } from '../components/ThreadPanel';
import type { Focus, FocusTarget } from '../model/focus';

const INBOX = '/console/complaints';

function Detail({ data }: { data: ComplaintDetail }) {
  const [focus, setFocus] = useState<Focus | null>(null);
  // The assist route needs the reply permission, so the card stays away for read-only accounts.
  const canReply = useAuth().can('complaints.reply');
  const requests = useMemo(() => data.requests ?? [], [data.requests]);
  const photos = useMemo(() => pagePhotos(data.messages, requests), [data.messages, requests]);
  const open = (target: FocusTarget, key: string) => setFocus((f) => ({ target, key, n: (f?.n ?? 0) + 1 }));
  const waiting = requests.filter((r) => r.status === 'open').length;
  return (
    <PhotoGallery photos={photos}>
      <Stack sx={{ gap: { xs: 3, md: 4 } }}>
        <ComplaintHeader complaint={data} backTo={INBOX} backLabel="Complaints inbox" />
        {data.kind === 'wrong_reading' && (
          <Alert severity="info" action={<Button color="inherit" size="small" component={Link} to={`/review/${encodeURIComponent(data.ticket)}`}>Open the case</Button>}>
            This is a reading check. Decide it in its review case.
          </Alert>
        )}
        <Box sx={{ display: 'grid', gap: 3, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 1fr) 360px', lg: 'minmax(0, 1fr) 380px' } }}>
          <Stack sx={{ gap: 3, minWidth: 0 }}>
            {canReply && <ComplaintAssist complaint={data} onFocus={open} />}
            <ComplaintFacts complaint={data} />
            <ComplaintEvidence complaint={data} staff />
            <Panel title="Conversation" caption="Messages with the consumer, oldest first. Select a photo to see it full size.">
              <ThreadPanel ticket={data.ticket} messages={data.messages} inApp={data.source === 'consumer_web'} />
            </Panel>
            {requests.length > 0 && (
              <Panel title="Requests to the consumer"
                caption={waiting ? `${waiting} ${waiting === 1 ? 'request is' : 'requests are'} waiting for an answer.` : 'Everything asked has been answered.'}>
                <RequestList requests={requests} />
              </Panel>
            )}
            <ComplaintTimeline complaint={data} />
          </Stack>
          <ActionsColumn complaint={data} focus={focus} />
        </Box>
      </Stack>
    </PhotoGallery>
  );
}

export function ComplaintDetailPage() {
  const { ticket = '' } = useParams();
  const complaint = useConsoleComplaint(ticket);

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
      {complaint.data && <Detail key={complaint.data.ticket} data={complaint.data} />}
    </Container>
  );
}
