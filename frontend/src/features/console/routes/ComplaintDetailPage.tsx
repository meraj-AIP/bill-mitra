import { Alert, Box, Button, Container, Drawer, Stack, useMediaQuery, useTheme } from '@mui/material';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAuth } from '@/features/auth';
import { DetailSkeleton, pagePhotos, type ComplaintDetail } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { PhotoGallery } from '@/shared/components/PhotoGallery';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useConsoleComplaint } from '../api/consoleApi';
import { CaseFile } from '../components/CaseFile';
import { ComplaintAssist } from '../components/ComplaintAssist';
import { DetailHeader } from '../components/DetailHeader';
import { ComplaintBrief } from '../components/ComplaintBrief';
import { ComplaintSnapshot } from '../components/ComplaintSnapshot';
import { OwnerPanel } from '../components/OwnerPanel';
import { WorkPanel } from '../components/WorkPanel';
import type { Focus, FocusTarget } from '../model/focus';

const INBOX = '/console/complaints';

// Two columns from md up: the brief and the case file on the left, owner and response on the right, each column as
// tall as its own content, so neither leaves a gap in the other. Below md: brief, response, case file.
const COLUMNS = { md: 'minmax(0, 1fr) 380px', lg: 'minmax(0, 1fr) 420px' };

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
  // One mount of each panel, placed by width, so a half-typed reply survives and section ids stay unique.
  const wide = useMediaQuery(useTheme().breakpoints.up('md'));
  const brief = <ComplaintBrief complaint={data} canReply={canReply} onFocus={open} onOpenAssist={() => setAssistOpen(true)} />;
  const rail = (
    <Stack component="aside" aria-label="Owner and response" sx={{ gap: 2, minWidth: 0 }}>
      <OwnerPanel complaint={data} focus={focus} />
      <WorkPanel complaint={data} focus={focus} />
    </Stack>
  );
  const file = <CaseFile complaint={data} requests={requests} />;
  return (
    <PhotoGallery photos={photos}>
      <Stack sx={{ gap: 2 }}>
        <DetailHeader complaint={data} backTo={INBOX} onAssist={null} />
        <ComplaintSnapshot complaint={data} />
        {data.kind === 'wrong_reading' && (
          <Alert severity="info" action={canCase
            ? <Button color="inherit" size="small" component={Link} to={`/review/${encodeURIComponent(data.ticket)}`}>Open the case</Button> : undefined}>
            {canCase ? 'This is a reading check. It is decided and closed in its review case.'
              : 'This is a reading check. A section AE decides and closes it in its review case.'}
          </Alert>
        )}
        {wide ? (
          <Box sx={{ display: 'grid', gap: 2, alignItems: 'start', gridTemplateColumns: COLUMNS }}>
            <Stack sx={{ gap: 2, minWidth: 0 }}>{brief}{file}</Stack>
            {rail}
          </Box>
        ) : (
          <Stack sx={{ gap: 2 }}>{brief}{rail}{file}</Stack>
        )}
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
