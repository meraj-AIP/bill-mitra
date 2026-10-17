import { FormControlLabel, MenuItem, Stack, Switch, TextField, ToggleButton, ToggleButtonGroup } from '@mui/material';

import { COMPLAINT_STATUSES, PRIORITIES, PRIORITY, SOURCE_LABEL, SOURCES, TRIAGE, TRIAGES, TypeSelect } from '@/features/complaints';
import { SearchField } from '@/shared/components/SearchField';
import { DISCOMS } from '@/shared/api/types';

import type { InboxQuery } from '../api/consoleApi';
import type { InboxFilterKey, MineFilter } from '../hooks/useInboxParams';

interface InboxFiltersProps {
  query: InboxQuery;
  /** False for an officer tied to one DISCOM, who only ever sees that one. */
  showDiscom: boolean;
  onFilter: (key: InboxFilterKey, value: string) => void;
  onFailed: (on: boolean) => void;
  onSort: (sort: InboxQuery['sort']) => void;
  mine: MineFilter;
  onMine: (value: MineFilter) => void;
}

const MINE_LABEL: Record<MineFilter, string> = { '': 'All I can see', with: 'With me', waiting: 'Waiting on me' };

/** Whose complaints: all in scope, the ones you hold, or the ones you hold where the next move is yours. */
function MineToggle({ value, onChange }: { value: MineFilter; onChange: (value: MineFilter) => void }) {
  return (
    <ToggleButtonGroup exclusive size="small" value={value} aria-label="Whose complaints"
      onChange={(_, next: MineFilter | null) => onChange(next ?? '')}
      sx={{ flexWrap: 'wrap', alignSelf: 'flex-start', '& .MuiToggleButton-root': { px: 1.75, textTransform: 'none', fontWeight: 600 } }}>
      {(Object.keys(MINE_LABEL) as MineFilter[]).map((k) => <ToggleButton key={k || 'all'} value={k}>{MINE_LABEL[k]}</ToggleButton>)}
    </ToggleButtonGroup>
  );
}

const SORT_LABEL: Record<InboxQuery['sort'], string> = { priority: 'Needs you first', newest: 'Newest first', oldest: 'Oldest first' };

export function InboxFilters({ query, showDiscom, onFilter, onFailed, onSort, mine, onMine }: InboxFiltersProps) {
  return (
    <Stack sx={{ gap: 1.5 }}>
      <MineToggle value={mine} onChange={onMine} />
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap', alignItems: { sm: 'center' } }}>
        <SearchField label="Ticket" placeholder="BM-261016-7KQ2D" value={query.q} onChange={(v) => onFilter('q', v)} />
        <TextField select size="small" label="Status" value={query.status} onChange={(e) => onFilter('status', e.target.value)} sx={{ minWidth: 150 }}>
          <MenuItem value="">All statuses</MenuItem>
          {COMPLAINT_STATUSES.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
        </TextField>
        <TypeSelect size="small" emptyLabel="All types" value={query.type} onChange={(v) => onFilter('type', v)} />
        <TextField select size="small" label="Priority" value={query.priority} onChange={(e) => onFilter('priority', e.target.value)} sx={{ minWidth: 140 }}>
          <MenuItem value="">Any priority</MenuItem>
          {PRIORITIES.map((p) => <MenuItem key={p} value={p}>{PRIORITY[p].label}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Source" value={query.source} onChange={(e) => onFilter('source', e.target.value)} sx={{ minWidth: 170 }}>
          <MenuItem value="">Any source</MenuItem>
          {SOURCES.map((s) => <MenuItem key={s} value={s}>{SOURCE_LABEL[s]}</MenuItem>)}
        </TextField>
      </Stack>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap', alignItems: { sm: 'center' } }}>
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
    </Stack>
  );
}
