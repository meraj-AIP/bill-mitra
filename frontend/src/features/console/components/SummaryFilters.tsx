import { MenuItem, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';

import { DISCOMS } from '@/shared/api/types';

import { SUMMARY_DAYS, type SummaryFilters as Filters } from '../api/consoleApi';

const DAY_LABEL: Record<number, string> = { 7: '7 days', 30: '30 days', 90: '90 days', 365: '1 year' };

interface SummaryFiltersProps {
  filters: Filters;
  /** Only admins choose; an officer is scoped by the server to their DISCOM. */
  canPickDiscom: boolean;
  scopeNote: string | null;
  onDays: (days: number) => void;
  onDiscom: (discom: string) => void;
}

export function SummaryFilters({ filters, canPickDiscom, scopeNote, onDays, onDiscom }: SummaryFiltersProps) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' }, flexWrap: 'wrap' }}>
      <ToggleButtonGroup size="small" exclusive value={filters.days} aria-label="Date range"
        onChange={(_e, v: number | null) => { if (v) onDays(v); }}>
        {SUMMARY_DAYS.map((d) => <ToggleButton key={d} value={d} sx={{ px: 1.75 }}>{DAY_LABEL[d]}</ToggleButton>)}
      </ToggleButtonGroup>
      {canPickDiscom && (
        <TextField select size="small" label="DISCOM" value={filters.discom} onChange={(e) => onDiscom(e.target.value)} sx={{ minWidth: 160 }}>
          <MenuItem value="">All DISCOMs</MenuItem>
          {DISCOMS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
        </TextField>
      )}
      <Typography variant="caption" sx={{ color: 'text.secondary', flex: 1, minWidth: 200 }}>
        {scopeNote ? `${scopeNote}. ` : ''}Complaints and overcharge figures cover the selected window.
      </Typography>
    </Stack>
  );
}
