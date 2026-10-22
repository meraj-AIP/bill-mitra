import { Box, Button, Container, Stack, useMediaQuery, useTheme } from '@mui/material';
import { useMemo, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

import { DetailSkeleton, pagePhotos } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { PhotoGallery, uniquePhotos } from '@/shared/components/PhotoGallery';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { useCase, useDraft } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { ApplyPanel } from '../components/ApplyPanel';
import { ApprovalsPanel } from '../components/ApprovalsPanel';
import { attachedBillPhoto } from '../components/AttachedBills';
import { CaseAssist } from '../components/CaseAssist';
import { CaseFile } from '../components/CaseFile';
import { CaseHeader } from '../components/CaseHeader';
import { ConversationPanel } from '../components/ConversationPanel';
import { DecisionPanel } from '../components/DecisionPanel';
import { EvidencePackPanel } from '../components/EvidencePackPanel';
import { SuggestedDecision } from '../components/SuggestedDecision';
import { emptyDraft, fromDraft, OPEN_FOR_DECISION, type DecisionDraft } from '../model/decision';
import { CASE_SECTION } from '../model/labels';

// Printing this page prints the evidence pack alone; on screen it sits folded away in the workspace.
const SCREEN_ONLY = { '@media print': { display: 'none' } };
const PRINT_ONLY = { display: 'none', '@media print': { display: 'block' } };

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

const ANCHOR = { scrollMarginTop: 80, '&:focus': { outline: 'none' }, '&:empty': { display: 'none' } };
const COLUMNS = { md: 'minmax(0, 1fr) 380px', lg: 'minmax(0, 1fr) 420px' };

/** Left, wide: what this person does now (decide, approve or apply), the AI read, then the case file. Right: the
 * conversation with the consumer, where asking for more happens. The same shape as the complaint page. Below md it
 * stacks: the action, the AI read, the conversation, then the case file. */
function Workspace({ c }: { c: CaseDetail }) {
  const deciding = c.can.decide && OPEN_FOR_DECISION.has(c.state);
  // One mount of each part, placed by width, so a half-written decision or request survives a resize.
  const wide = useMediaQuery(useTheme().breakpoints.up('md'));
  const work = (
    <>
      {deciding && (
        <Stack id={CASE_SECTION.decision} tabIndex={-1} sx={{ gap: 2, ...ANCHOR }}>
          <DecisionArea c={c} />
        </Stack>
      )}
      <Box id={CASE_SECTION.approval} tabIndex={-1} sx={ANCHOR}><ApprovalsPanel c={c} /></Box>
      <Box id={CASE_SECTION.apply} tabIndex={-1} sx={ANCHOR}><ApplyPanel c={c} /></Box>
      <CaseAssist c={c} />
    </>
  );
  const rail = <Box component="aside" aria-label="Conversation with the consumer" sx={{ minWidth: 0 }}><ConversationPanel c={c} /></Box>;
  const file = <CaseFile c={c} />;
  if (!wide) return <Stack sx={{ gap: 2 }}>{work}{rail}{file}</Stack>;
  return (
    <Box sx={{ display: 'grid', gap: 2, alignItems: 'start', gridTemplateColumns: COLUMNS }}>
      <Stack sx={{ gap: 2, minWidth: 0 }}>{work}{file}</Stack>
      {rail}
    </Box>
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
            <Box sx={PRINT_ONLY}><EvidencePackPanel c={c} /></Box>
            <Box sx={SCREEN_ONLY}><Workspace c={c} /></Box>
          </Stack>
        </Gallery>
      )}
    </Container>
  );
}
