import { Box, Button, Container, Stack, useMediaQuery, useTheme } from '@mui/material';
import { useMemo, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

import { DetailSkeleton, pagePhotos } from '@/features/complaints';
import { isStatus } from '@/shared/api/http';
import { PhotoGallery, uniquePhotos } from '@/shared/components/PhotoGallery';
import { EmptyState, ErrorState } from '@/shared/components/States';

import { revealSection } from '@/shared/lib/reveal';

import { useCase } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { ActionPanel, type ActionTab } from '../components/ActionPanel';
import { attachedBillPhoto } from '../components/AttachedBills';
import { CaseAssist } from '../components/CaseAssist';
import { CaseFile } from '../components/CaseFile';
import { CaseHeader } from '../components/CaseHeader';
import { EvidencePackPanel } from '../components/EvidencePackPanel';
import { CASE_SECTION } from '../model/labels';

// Printing this page prints the evidence pack alone; on screen it sits folded away in the workspace.
const SCREEN_ONLY = { '@media print': { display: 'none' } };
const PRINT_ONLY = { display: 'none', '@media print': { display: 'block' } };

const COLUMNS = { md: 'minmax(0, 1fr) 400px', lg: 'minmax(0, 1fr) 440px' };
// The action stays in view while the evidence beside it scrolls; a long form scrolls inside itself.
const PINNED = { position: 'sticky', top: 16, maxHeight: 'calc(100dvh - 32px)', overflowY: 'auto', overscrollBehavior: 'contain' } as const;

/** Evidence on the left, read first: the AI read, then the case file. The action on the right, pinned, so the AE
 * checks the bill and decides without scrolling back and forth. Below md the action comes first, then the evidence. */
function Workspace({ c }: { c: CaseDetail }) {
  const [tab, setTab] = useState<ActionTab>('decide');
  // One mount of each part, placed by width, so a half-written decision or request survives a resize.
  const wide = useMediaQuery(useTheme().breakpoints.up('md'));
  const action = <ActionPanel c={c} tab={tab} onTab={setTab} />;
  const evidence = (
    <Stack sx={{ gap: 2, minWidth: 0 }}>
      <CaseAssist c={c} onAsk={() => { setTab('ask'); revealSection(CASE_SECTION.decision); }} />
      <CaseFile c={c} />
    </Stack>
  );
  if (!wide) return <Stack sx={{ gap: 2 }}>{action}{evidence}</Stack>;
  return (
    <Box sx={{ display: 'grid', gap: 2, alignItems: 'start', gridTemplateColumns: COLUMNS }}>
      {evidence}
      <Box component="aside" aria-label="What to do on this case" sx={{ ...PINNED, minWidth: 0 }}>{action}</Box>
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
          <Stack sx={{ gap: 2.5 }}>
            <Box sx={SCREEN_ONLY}><CaseHeader c={c} /></Box>
            <Box sx={PRINT_ONLY}><EvidencePackPanel c={c} /></Box>
            <Box sx={SCREEN_ONLY}><Workspace c={c} /></Box>
          </Stack>
        </Gallery>
      )}
    </Container>
  );
}
