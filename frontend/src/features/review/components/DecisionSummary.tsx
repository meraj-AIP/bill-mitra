import { Box, Stack, Typography } from '@mui/material';

import { rupees } from '@/shared/lib/format';

import type { CaseDetail, DecisionKind } from '../api/types';
import type { Outcome } from '../model/decision';

function headline(kind: DecisionKind, o: Outcome): string {
  if (kind === 'correct') return o.original === null ? 'No change to the bill' : `No change. The bill stays at ${rupees(o.original)}`;
  if (o.reduction === null || o.reduction <= 0) {
    return kind === 'corrected_reading' ? 'Enter the corrected reading to see the new amount' : 'Enter the amount to take off';
  }
  const from = o.original === null ? 'the bill' : rupees(o.original);
  // Only the engine's preview gives a revised total; a custom reduction is stated as typed.
  return o.revised === null ? `Reduces ${from} by ${rupees(o.reduction)}` : `Reduces ${from} to ${rupees(o.revised)}`;
}

function approvalLine(kind: DecisionKind, o: Outcome, c: CaseDetail): string {
  if (kind === 'correct') return 'Recorded at once. The consumer is told the bill stands.';
  if (o.needsApproval) {
    return kind === 'custom'
      ? `Needs approval: ${c.discom} sends every custom reduction to a billing approver.`
      : `Needs approval: above the ${c.discom} AE limit of ${rupees(c.policy.ae_limit ?? 0)}.`;
  }
  return 'No approval needed under the policy. The consumer is told once you submit.';
}

/** What will happen, in one place, before the AE commits. */
export function DecisionSummary({ kind, outcome, c }: { kind: DecisionKind; outcome: Outcome; c: CaseDetail }) {
  const known = outcome.reduction !== null && outcome.reduction > 0;
  return (
    <Box aria-live="polite" sx={{ p: 2, borderRadius: 2, bgcolor: outcome.needsApproval ? 'warning.light' : 'grey.50', border: 1,
      borderColor: outcome.needsApproval ? 'warning.light' : 'divider' }}>
      <Typography variant="overline" component="p" sx={{ color: 'text.secondary' }}>Summary</Typography>
      <Typography variant="h3" component="p" sx={{ fontVariantNumeric: 'tabular-nums' }}>{headline(kind, outcome)}</Typography>
      {kind !== 'correct' && known && (
        <Stack direction="row" sx={{ gap: 3, mt: 1, flexWrap: 'wrap' }}>
          <Typography variant="body2">Reduction <b>{rupees(outcome.reduction ?? 0)}</b></Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>The original bill is never edited; this becomes the next revision.</Typography>
        </Stack>
      )}
      <Typography variant="body2" sx={{ mt: 1, fontWeight: 600, color: outcome.needsApproval ? 'warning.dark' : 'success.dark' }}>
        {approvalLine(kind, outcome, c)}
      </Typography>
    </Box>
  );
}
