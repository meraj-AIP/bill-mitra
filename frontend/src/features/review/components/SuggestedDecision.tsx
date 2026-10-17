import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';

import { formatCount, rupees } from '@/shared/lib/format';

import type { Draft } from '../api/types';
import { REASON } from '../model/labels';
import { Figure, Panel } from './Panel';

const STRENGTH: Record<Draft['strength'], { label: string; color: 'success' | 'info' }> = {
  strong: { label: 'Strong', color: 'success' },
  likely: { label: 'Likely', color: 'info' },
};

function headline(d: Draft): string {
  if (d.kind === 'correct') return 'Bill is correct';
  return d.corrected_present_reading === null ? 'Correct the reading' : `Correct the present reading to ${formatCount(d.corrected_present_reading)}`;
}

interface SuggestedDecisionProps {
  draft: Draft;
  /** True once the AE has copied it into the form, so the card says what happened. */
  used: boolean;
  onUse: () => void;
}

/** Worked out by the rules from the bills on file. It only fills the form; the AE checks it and records it. */
export function SuggestedDecision({ draft, used, onUse }: SuggestedDecisionProps) {
  const strength = STRENGTH[draft.strength];
  const p = draft.preview;
  return (
    <Panel title="Suggested decision" caption="Worked out from the rules and the bills on file. Check it before you record anything."
      aside={<Chip size="small" variant="outlined" color={strength.color} label={strength.label} />}>
      <Stack sx={{ gap: 2 }}>
        <Box>
          <Typography variant="subtitle1" component="p" sx={{ fontWeight: 600 }}>{headline(draft)}</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>Reason: {REASON[draft.reason_code]}</Typography>
        </Box>
        {draft.why.length > 0 && (
          <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'grid', gap: 0.5 }}>
            {draft.why.map((line) => <Typography key={line} component="li" variant="body2">{line}</Typography>)}
          </Box>
        )}
        {p && (
          <Stack direction="row" sx={{ gap: 3, flexWrap: 'wrap' }}>
            <Figure label="Corrected units" value={formatCount(p.corrected_units)} />
            <Figure label="Revised amount" value={rupees(p.revised_amount)} />
            <Figure label="Reduction" value={rupees(p.reduction)} strong
              note={p.needs_approval ? 'Needs approval under the policy' : 'Within the AE limit'} />
          </Stack>
        )}
        <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' } }}>
          <Button variant="outlined" startIcon={<AutoFixHighOutlinedIcon />} onClick={onUse}>Use this</Button>
          <Typography variant="body2" role="status" sx={{ color: used ? 'success.dark' : 'text.secondary' }}>
            {used ? 'Filled in below. Check it, then record the decision.' : 'Fills in the decision form. Nothing is recorded until you press Record decision.'}
          </Typography>
        </Stack>
      </Stack>
    </Panel>
  );
}
