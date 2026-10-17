import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Alert, Box, Button, Chip, Collapse, Container, Drawer, Stack } from '@mui/material';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '@/features/auth';
import {
  ComplaintEvidence, ComplaintFacts, ComplaintTimeline, DetailSkeleton, pagePhotos, RequestList, type ComplaintDetail,
} from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { Panel } from '@/shared/components/Panel';
import { PhotoGallery } from '@/shared/components/PhotoGallery';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useConsoleComplaint } from '../api/consoleApi';
import { ComplaintAssist } from '../components/ComplaintAssist';
import { DetailHeader } from '../components/DetailHeader';
import { ComplaintBrief } from '../components/ComplaintBrief';
import { OwnerPanel } from '../components/OwnerPanel';
import { ThreadPanel } from '../components/ThreadPanel';
import { WorkPanel } from '../components/WorkPanel';
import type { Focus, FocusTarget } from '../model/focus';

const INBOX = '/console/complaints';

/** What we hold, the bill, requests and the timeline: there when needed, out of the way while replying. */
function MoreDetails({ data, requests, waiting }: { data: ComplaintDetail; requests: NonNullable<ComplaintDetail['requests']>; waiting: number }) {
  const [open, setOpen] = useState(false);
  return (
    <Box>
      <Button onClick={() => setOpen(!open)} aria-expanded={open} color="inherit"
        endIcon={<ExpandMoreRoundedIcon sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 200ms' }} />}>
        {open ? 'Hide full details' : 'Full details: what we hold, the bill, requests and timeline'}
      </Button>
      <Collapse in={open} unmountOnExit>
        <Stack sx={{ gap: 3, mt: 1.5 }}>
          <ComplaintFacts complaint={data} />
          <ComplaintEvidence complaint={data} staff />
          {requests.length > 0 && (
            <Panel title="Requests to the consumer"
              caption={waiting ? `${waiting} waiting for an answer.` : 'Everything asked has been answered.'}>
              <RequestList requests={requests} />
            </Panel>
          )}
          <ComplaintTimeline complaint={data} />
        </Stack>
      </Collapse>
    </Box>
  );
}

// The page band above the conversation, measured on a laptop screen, so thread and reply fit without scrolling.
const THREAD_HEIGHT = { xs: '420px', md: 'max(300px, calc(100dvh - 470px))' };

function Detail({ data }: { data: ComplaintDetail }) {
  const [focus, setFocus] = useState<Focus | null>(null);
  const [assistOpen, setAssistOpen] = useState(false);
  // The assist route needs the reply permission, so the button stays away for read-only accounts.
  const { can } = useAuth();
  const canReply = can('complaints.reply');
  const canCase = can('cases.view');
  const requests = useMemo(() => data.requests ?? [], [data.requests]);
  const photos = useMemo(() => pagePhotos(data.messages, requests), [data.messages, requests]);
  const open = (target: FocusTarget, key: string) => {
    setAssistOpen(false);
    setFocus((f) => ({ target, key, n: (f?.n ?? 0) + 1 }));
  };
  const waiting = requests.filter((r) => r.status === 'open').length;
  return (
    <PhotoGallery photos={photos}>
      <Stack sx={{ gap: 2 }}>
        <DetailHeader complaint={data} backTo={INBOX} onAssist={null} />
        {data.kind === 'wrong_reading' && (
          <Alert severity="info" action={canCase
            ? <Button color="inherit" size="small" component={Link} to={`/review/${encodeURIComponent(data.ticket)}`}>Open the case</Button> : undefined}>
            {canCase ? 'This is a reading check. It is decided and closed in its review case.'
              : 'This is a reading check. A section AE decides and closes it in its review case.'}
          </Alert>
        )}
        <Box sx={{ display: 'grid', gap: 2, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 1fr) 320px', lg: 'minmax(0, 1fr) 340px' } }}>
          <ComplaintBrief complaint={data} canReply={canReply} onFocus={open} onOpenAssist={() => setAssistOpen(true)} />
          <OwnerPanel complaint={data} focus={focus} />
        </Box>
        <Box sx={{ display: 'grid', gap: 2, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 1fr) 380px', lg: 'minmax(0, 1fr) 420px' } }}>
          <Stack sx={{ gap: 1.5, minWidth: 0 }}>
            <Panel title="Conversation" aside={waiting > 0
              ? <Chip size="small" color="info" variant="outlined" label={`${waiting} ${waiting === 1 ? 'request' : 'requests'} waiting`} /> : undefined}>
              <ThreadPanel ticket={data.ticket} messages={data.messages} inApp={data.source === 'consumer_web'} height={THREAD_HEIGHT} />
            </Panel>
          </Stack>
          <WorkPanel complaint={data} focus={focus} />
        </Box>
        <MoreDetails data={data} requests={requests} waiting={waiting} />
      </Stack>
      {canReply && (
        <Drawer anchor="right" open={assistOpen} onClose={() => setAssistOpen(false)}
          slotProps={{ paper: { sx: { width: { xs: '100%', sm: 440 }, p: 2 } } }}>
          <ComplaintAssist complaint={data} onFocus={open} />
        </Drawer>
      )}
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
