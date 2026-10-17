import { Alert, Box, Button, Container, Grid, Paper, Stack, Typography } from '@mui/material';
import { useMemo, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

import { DetailSkeleton, pagePhotos } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { BillImage } from '@/shared/components/BillImage';
import { PhotoGallery, uniquePhotos } from '@/shared/components/PhotoGallery';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useCase, useDraft } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { ApplyPanel } from '../components/ApplyPanel';
import { ApprovalsPanel } from '../components/ApprovalsPanel';
import { attachedBillPhoto } from '../components/AttachedBills';
import { CaseAssist } from '../components/CaseAssist';
import { CaseHeader } from '../components/CaseHeader';
import { ConversationPanel } from '../components/ConversationPanel';
import { DecisionHistory } from '../components/DecisionHistory';
import { DecisionPanel } from '../components/DecisionPanel';
import { EvidencePackPanel } from '../components/EvidencePackPanel';
import { FlagPanel } from '../components/FlagPanel';
import { ReadingsPanel } from '../components/ReadingsPanel';
import { SuggestedDecision } from '../components/SuggestedDecision';
import { TimelinePanel } from '../components/TimelinePanel';
import { emptyDraft, fromDraft, OPEN_FOR_DECISION, type DecisionDraft } from '../model/decision';
import { CASE_SECTION } from '../model/labels';

const WAITING: Partial<Record<CaseDetail['state'], string>> = {
  awaiting_approval: 'A decision is waiting for a billing approver. Nothing more to do here until they approve or reject it.',
  decided: 'Decided. Any revision now waits to be entered in the DISCOM billing system.',
  applied: 'Closed. The revision is in the official bill and the consumer has been told.',
};

// Printing this page prints the evidence pack alone.
const SCREEN_ONLY = { '@media print': { display: 'none' } };

function Bill({ c }: { c: CaseDetail }) {
  if (!c.media_url) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>No bill photo is stored for this case.</Typography>
      </Paper>
    );
  }
  return <BillImage src={c.media_url} isPdf={c.mime_type === 'application/pdf'} heading="Bill as uploaded" name={`Bill for ${c.ticket}`} />;
}

/** "Use this" remounts the decision form with the suggestion filled in, replacing anything typed so far. */
function DecisionArea({ c }: { c: CaseDetail }) {
  const draft = useDraft(c.ticket, c.can.decide).data;
  const [seed, setSeed] = useState<{ round: number; draft: DecisionDraft } | null>(null);
  return (
    <>
      {draft && (
        <SuggestedDecision draft={draft} used={seed !== null}
          onUse={() => setSeed((s) => ({ round: (s?.round ?? 0) + 1, draft: fromDraft(draft) }))} />
      )}
      <DecisionPanel key={seed?.round ?? 0} c={c} initial={seed?.draft ?? emptyDraft()} />
    </>
  );
}

function Workspace({ c }: { c: CaseDetail }) {
  const deciding = c.can.decide && OPEN_FOR_DECISION.has(c.state);
  const note = WAITING[c.state];
  return (
    <Grid container spacing={3} sx={{ alignItems: 'flex-start' }}>
      <Grid size={{ xs: 12, md: 5 }}>
        <Stack sx={{ gap: 2 }}>
          <Bill c={c} />
          <ReadingsPanel c={c} />
          <TimelinePanel c={c} />
        </Stack>
      </Grid>
      <Grid size={{ xs: 12, md: 7 }}>
        <Stack sx={{ gap: 2 }}>
          <CaseAssist c={c} />
          <FlagPanel c={c} />
          {c.state === 'rejected' && c.can.decide && (
            <Alert severity="error">The last decision was rejected. Read the approver&apos;s note in the history below, then decide again.</Alert>
          )}
          <ApprovalsPanel c={c} />
          <ApplyPanel c={c} />
          {deciding && (
            <Stack id={CASE_SECTION.decision} tabIndex={-1} sx={{ gap: 2, scrollMarginTop: 80, '&:focus': { outline: 'none' } }}>
              <DecisionArea c={c} />
            </Stack>
          )}
          {!deciding && note && <Alert severity="info" variant="outlined">{note}</Alert>}
          <ConversationPanel c={c} />
          <DecisionHistory c={c} />
        </Stack>
      </Grid>
    </Grid>
  );
}

/** Every photo on the case in one lightbox: the conversation, answers to requests, then earlier bills. */
function Gallery({ c, children }: { c: CaseDetail; children: ReactNode }) {
  const photos = useMemo(() => uniquePhotos([
    ...pagePhotos(c.messages, c.requests),
    ...c.evidence_pack.attached_bills.flatMap((b) => (b.media_url ? [attachedBillPhoto(b, b.media_url)] : [])),
  ]), [c.messages, c.requests, c.evidence_pack.attached_bills]);
  return <PhotoGallery photos={photos}>{children}</PhotoGallery>;
}

export function CasePage() {
  const { ticket = '' } = useParams();
  const result = useCase(ticket);
  const c = result.data;
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 4 } }}>
      {result.isPending && <DetailSkeleton />}
      {isStatus(result.error, 404) && (
        <EmptyState title="Case not found" hint="The ticket may be mistyped, or the case may sit outside your units."
          action={<Button variant="contained" component={Link} to="/review">Back to the queue</Button>} />
      )}
      {result.isError && !isStatus(result.error, 404) && <ErrorState message={result.error.message} onRetry={() => void result.refetch()} />}
      {c && (
        <Gallery c={c}>
          <Stack sx={{ gap: 3 }}>
            <Box sx={SCREEN_ONLY}><CaseHeader c={c} /></Box>
            <EvidencePackPanel c={c} />
            <Box sx={SCREEN_ONLY}><Workspace c={c} /></Box>
          </Stack>
        </Gallery>
      )}
    </Container>
  );
}
