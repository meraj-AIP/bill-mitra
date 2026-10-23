import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Box, Button, Chip, Collapse, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { formatCount, rupees } from '@/shared/lib/format';

import type { Draft } from '../api/types';
import { REASON } from '../model/labels';
import { Figure } from './Panel';

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

/** Worked out by the rules from the bills on file. It only fills the form; the AE checks it and records it. The
 * reasons fold away: the evidence beside it already shows them. */
export function SuggestedDecision({ draft, used, onUse }: SuggestedDecisionProps) {
  const [why, setWhy] = useState(false);
  const strength = STRENGTH[draft.strength];
  const p = draft.preview;
  return (
    <Box sx={{ p: 1.75, borderRadius: 1.5, bgcolor: 'grey.50', border: 1, borderColor: 'divider' }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="overline" component="p" sx={{ color: 'text.secondary', lineHeight: 1.6 }}>Suggested by the rules</Typography>
        <Chip size="small" variant="outlined" color={strength.color} label={strength.label} />
      </Stack>
      <Typography variant="subtitle1" component="p" sx={{ fontWeight: 600 }}>{headline(draft)}</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>{REASON[draft.reason_code]}</Typography>
      {p && (
        <Stack direction="row" sx={{ gap: 2.5, flexWrap: 'wrap', mt: 1.5 }}>
          <Figure label="Corrected units" value={formatCount(p.corrected_units)} />
          <Figure label="Revised amount" value={rupees(p.revised_amount)} />
          <Figure label="Reduction" value={rupees(p.reduction)} strong note={p.needs_approval ? 'Needs approval' : 'Within the AE limit'} />
        </Stack>
      )}
      <Collapse in={why}>
        <Box component="ul" sx={{ m: 0, mt: 1.5, pl: 2.5, display: 'grid', gap: 0.5 }}>
          {draft.why.map((line) => <Typography key={line} component="li" variant="body2">{line}</Typography>)}
        </Box>
      </Collapse>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 1.5 }}>
        <Button variant="contained" size="small" startIcon={<AutoFixHighOutlinedIcon />} onClick={onUse}>{used ? 'Filled in below' : 'Use this'}</Button>
        {draft.why.length > 0 && (
          <Button size="small" onClick={() => setWhy(!why)} aria-expanded={why}
            endIcon={<ExpandMoreRoundedIcon sx={{ transform: why ? 'rotate(180deg)' : 'none', transition: 'transform 200ms' }} />}>
            Why
          </Button>
        )}
      </Stack>
      <Typography variant="caption" component="p" role="status" sx={{ color: used ? 'success.dark' : 'text.secondary', mt: 0.75 }}>
        {used ? 'Check it, then record the decision.' : 'Fills in the form. Nothing is recorded until you press the button below.'}
      </Typography>
    </Box>
  );
}
