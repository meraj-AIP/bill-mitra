import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Alert, Box, Button, Chip, Container, Paper, Skeleton, Stack, Typography } from '@mui/material';
import { Link, useParams } from 'react-router-dom';

import { ReplyBox } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { Panel } from '@/shared/components/Panel';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useMyComplaint, useReplyToComplaint } from '../api/myComplaintsApi';
import type { MyComplaintDetail } from '../api/types';
import { ConsumerThread } from '../components/ConsumerThread';
import { OnFile } from '../components/OnFile';
import { StatusSteps } from '../components/StatusSteps';
import { statusOf } from '../model/status';

function Loading() {
  return (
    <Stack sx={{ gap: 3 }} aria-busy aria-label="Loading your complaint">
      <Skeleton width={200} />
      <Skeleton variant="rounded" height={40} sx={{ maxWidth: 380 }} />
      <Skeleton variant="rounded" height={96} />
      <Skeleton variant="rounded" height={240} />
    </Stack>
  );
}

function Detail({ c }: { c: MyComplaintDetail }) {
  const reply = useReplyToComplaint(c.ticket);
  const s = statusOf(c.status, c.status_label);
  const asked = c.status === 'waiting_for_you';
  return (
    <Stack sx={{ gap: 3 }}>
      <Stack component="header" sx={{ gap: 1 }}>
        <Typography component="p" sx={{ fontFamily: 'monospace', fontSize: '0.875rem', fontWeight: 600, color: 'text.secondary' }}>{c.ticket}</Typography>
        <Typography variant="h1">{c.type_label}</Typography>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Chip label={s.label} color={s.tone} variant={asked ? 'filled' : 'outlined'} />
          {s.hint && <Typography variant="body2" sx={{ color: 'text.secondary' }}>{s.hint}</Typography>}
        </Stack>
      </Stack>
      <Paper variant="outlined" sx={{ px: { xs: 2, sm: 3 }, py: { xs: 2, sm: 3 } }}>
        <StatusSteps status={c.status} />
      </Paper>
      <Box sx={{ display: 'grid', gap: 3, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 7fr) minmax(0, 5fr)' } }}>
        <Panel title="Conversation with Bill Mitra" tone={asked ? 'warning' : undefined}>
          <ConsumerThread messages={c.messages} />
          {asked && (
            <Stack sx={{ mt: 3, pt: 2.5, borderTop: 1, borderColor: 'divider', gap: 1.5 }}>
              <Alert severity="warning">We asked you something above. Please answer here so we can carry on.</Alert>
              <ReplyBox label="Your answer" placeholder="Write your answer here." pending={reply.isPending}
                error={reply.error?.message ?? null} onSend={(body) => reply.mutateAsync(body)} />
            </Stack>
          )}
        </Panel>
        <OnFile c={c} />
      </Box>
    </Stack>
  );
}

export function MyComplaintPage() {
  const { ticket = '' } = useParams();
  const complaint = useMyComplaint(ticket);
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Button component={Link} to="/complaints" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1, mb: 2 }}>Your complaints</Button>
      {complaint.isPending && <Loading />}
      {isStatus(complaint.error, 404) && (
        <EmptyState title="Complaint not found" hint="Check the ticket number, or open it from your list of complaints."
          action={<Button variant="contained" component={Link} to="/complaints">Your complaints</Button>} />
      )}
      {complaint.isError && !isStatus(complaint.error, 404) && (
        <ErrorState message={complaint.error.message} onRetry={() => void complaint.refetch()} />
      )}
      {complaint.data && <Detail c={complaint.data} />}
    </Container>
  );
}
