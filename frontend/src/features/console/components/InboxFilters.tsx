import { FormControlLabel, MenuItem, Stack, Switch, TextField } from '@mui/material';

import { COMPLAINT_STATUSES, TRIAGE, TRIAGES } from '@/features/complaints';
import { SearchField } from '@/shared/components/SearchField';
import { DISCOMS } from '@/shared/api/types';

import type { InboxQuery } from '../api/consoleApi';
import type { InboxFilterKey } from '../hooks/useInboxParams';

interface InboxFiltersProps {
  query: InboxQuery;
  /** False for an officer tied to one DISCOM, who only ever sees that one. */
  showDiscom: boolean;
  onFilter: (key: InboxFilterKey, value: string) => void;
  onFailed: (on: boolean) => void;
  onSort: (sort: InboxQuery['sort']) => void;
}

const SORT_LABEL: Record<InboxQuery['sort'], string> = { priority: 'Needs you first', newest: 'Newest first', oldest: 'Oldest first' };

export function InboxFilters({ query, showDiscom, onFilter, onFailed, onSort }: InboxFiltersProps) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap', alignItems: { sm: 'center' } }}>
      <SearchField label="Ticket" placeholder="BM-261016-7KQ2D" value={query.q} onChange={(v) => onFilter('q', v)} />
      <TextField select size="small" label="Status" value={query.status} onChange={(e) => onFilter('status', e.target.value)} sx={{ minWidth: 150 }}>
        <MenuItem value="">All statuses</MenuItem>
        {COMPLAINT_STATUSES.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Check result" value={query.triage} onChange={(e) => onFilter('triage', e.target.value)} sx={{ minWidth: 170 }}>
        <MenuItem value="">Any result</MenuItem>
        {TRIAGES.map((t) => <MenuItem key={t} value={t}>{TRIAGE[t].label}</MenuItem>)}
      </TextField>
      {showDiscom && (
        <TextField select size="small" label="DISCOM" value={query.discom} onChange={(e) => onFilter('discom', e.target.value)} sx={{ minWidth: 150 }}>
          <MenuItem value="">All DISCOMs</MenuItem>
          {DISCOMS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
        </TextField>
      )}
      <FormControlLabel control={<Switch size="small" checked={query.failed} onChange={(e) => onFailed(e.target.checked)} />}
        label="Reply not delivered" />
      <TextField select size="small" label="Sort" value={query.sort} onChange={(e) => onSort(e.target.value as InboxQuery['sort'])}
        sx={{ minWidth: 170, ml: { sm: 'auto' } }}>
        {(Object.keys(SORT_LABEL) as Array<InboxQuery['sort']>).map((s) => <MenuItem key={s} value={s}>{SORT_LABEL[s]}</MenuItem>)}
      </TextField>
    </Stack>
  );
}
