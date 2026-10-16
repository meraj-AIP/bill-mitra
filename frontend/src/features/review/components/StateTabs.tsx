import { Box, Tab, Tabs } from '@mui/material';

import { formatCount } from '@/shared/lib/format';

import { REVIEW_STATES, type ReviewState } from '../api/types';
import { STATE } from '../model/labels';

interface StateTabsProps {
  value: ReviewState | '';
  /** Undefined until the first page loads. Covers every case in view, whatever the filters. */
  counts: Record<string, number> | undefined;
  onChange: (state: ReviewState | '') => void;
}

function Label({ text, count }: { text: string; count: number | undefined }) {
  return (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
      {text}
      <Box component="span" aria-hidden={count === undefined}
        sx={{ minWidth: 22, px: 0.75, py: 0.125, borderRadius: 0.75, fontSize: '0.75rem', fontWeight: 600, lineHeight: 1.6,
          textAlign: 'center', bgcolor: 'grey.100', color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>
        {count === undefined ? ' ' : formatCount(count)}
      </Box>
    </Box>
  );
}

/** Counts per state across every case in the viewer's units, so the tabs read as the workload, not the filtered view. */
export function StateTabs({ value, counts, onChange }: StateTabsProps) {
  const total = counts ? REVIEW_STATES.reduce((sum, s) => sum + (counts[s] ?? 0), 0) : undefined;
  return (
    <Tabs value={value} onChange={(_e, v: ReviewState | '') => onChange(v)} variant="scrollable" scrollButtons="auto"
      aria-label="Cases by state" sx={{ borderBottom: 1, borderColor: 'divider', '& .MuiTab-root': { minHeight: 48, px: 1.75 } }}>
      <Tab value="" label={<Label text="All" count={total} />} />
      {REVIEW_STATES.map((s) => <Tab key={s} value={s} label={<Label text={STATE[s].short} count={counts ? (counts[s] ?? 0) : undefined} />} />)}
    </Tabs>
  );
}
