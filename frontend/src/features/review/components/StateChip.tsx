import { Chip, Stack } from '@mui/material';

import type { ReviewState } from '../api/types';
import { STATE } from '../model/labels';

export function StateChip({ state, size = 'small' }: { state: ReviewState; size?: 'small' | 'medium' }) {
  const s = STATE[state];
  const filled = state === 'awaiting_review' || state === 'awaiting_approval' || state === 'rejected';
  return <Chip size={size} label={s.label} title={s.hint} color={s.tone} variant={filled ? 'filled' : 'outlined'} />;
}

export function OverdueChip({ days, size = 'small' }: { days: number; size?: 'small' | 'medium' }) {
  return <Chip size={size} color="error" variant="outlined" label={`Overdue, ${days} ${days === 1 ? 'day' : 'days'} open`} />;
}

export function CaseFlags({ state, overdue, days }: { state: ReviewState; overdue: boolean; days: number }) {
  return (
    <Stack sx={{ gap: 0.5, alignItems: 'flex-start' }}>
      <StateChip state={state} />
      {overdue && <OverdueChip days={days} />}
    </Stack>
  );
}
