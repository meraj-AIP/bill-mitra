import { Alert, Box, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useState } from 'react';

import { useDraft } from '../api/reviewApi';
import type { CaseDetail } from '../api/types';
import { emptyDraft, fromDraft, OPEN_FOR_DECISION, type DecisionDraft } from '../model/decision';
import { CASE_SECTION } from '../model/labels';
import { decideHint, waitingOn } from '../model/waiting';
import { ApplyPanel } from './ApplyPanel';
import { ApprovalsPanel } from './ApprovalsPanel';
import { AskConsumer } from './ConversationPanel';
import { DecisionPanel } from './DecisionPanel';
import { SuggestedDecision } from './SuggestedDecision';

export type ActionTab = 'decide' | 'ask';

/** "Use this" remounts the decision form with the suggestion filled in, replacing anything typed so far. */
function Decide({ c }: { c: CaseDetail }) {
  const draft = useDraft(c.ticket, c.can.decide).data;
  const [seed, setSeed] = useState<{ round: number; draft: DecisionDraft } | null>(null);
  const hint = decideHint(c);
  return (
    <Stack sx={{ gap: 2 }}>
      {hint && <Alert severity={c.state === 'rejected' ? 'warning' : 'info'}>{hint}</Alert>}
      {draft && (
        <SuggestedDecision draft={draft} used={seed !== null}
          onUse={() => setSeed((s) => ({ round: (s?.round ?? 0) + 1, draft: fromDraft(draft) }))} />
      )}
      <DecisionPanel key={seed?.round ?? 0} c={c} initial={seed?.draft ?? emptyDraft()} />
    </Stack>
  );
}

/** Both forms stay mounted, so switching tabs never loses a half-written decision or request. */
function DecideOrAsk({ c, tab, onTab }: { c: CaseDetail; tab: ActionTab; onTab: (t: ActionTab) => void }) {
  const ask = c.can.request_info;
  const shown = ask ? tab : 'decide';
  return (
    <Paper variant="outlined" id={CASE_SECTION.decision} tabIndex={-1} sx={{ overflow: 'hidden', '&:focus': { outline: 'none' } }}>
      <Tabs value={shown} onChange={(_, t: ActionTab) => onTab(t)} variant="fullWidth" aria-label="What to do"
        sx={{ borderBottom: 1, borderColor: 'divider', minHeight: 44, '& .MuiTab-root': { minHeight: 44, fontWeight: 600 } }}>
        <Tab value="decide" label="Decide" />
        {ask && <Tab value="ask" label="Ask the consumer" />}
      </Tabs>
      <Box sx={{ p: 2 }}>
        <Box hidden={shown !== 'decide'}><Decide c={c} /></Box>
        {ask && (
          <Box hidden={shown !== 'ask'}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
              When the bill and the history do not settle it. The case waits on the consumer until they answer.
            </Typography>
            <AskConsumer c={c} />
          </Box>
        )}
      </Box>
    </Paper>
  );
}

/** What this viewer does on the case, in one place: decide or ask, approve, mark applied, or nothing (and why). */
export function ActionPanel({ c, tab, onTab }: { c: CaseDetail; tab: ActionTab; onTab: (t: ActionTab) => void }) {
  if (c.can.decide && OPEN_FOR_DECISION.has(c.state)) return <DecideOrAsk c={c} tab={tab} onTab={onTab} />;
  const approving = c.can.approve && c.decisions.some((d) => d.status === 'pending_approval');
  const applying = c.can.mark_applied && c.decisions.some((d) => d.status === 'approved' && d.reduction > 0 && !d.applied_at);
  if (approving) return <Box id={CASE_SECTION.approval} tabIndex={-1}><ApprovalsPanel c={c} /></Box>;
  if (applying) return <Box id={CASE_SECTION.apply} tabIndex={-1}><ApplyPanel c={c} /></Box>;
  const canAsk = c.can.request_info && OPEN_FOR_DECISION.has(c.state);
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" component="h2">Where it stands</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>{waitingOn(c)}</Typography>
      {canAsk && (
        <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" component="h3" sx={{ mb: 1 }}>Ask the consumer</Typography>
          <AskConsumer c={c} />
        </Box>
      )}
    </Paper>
  );
}
