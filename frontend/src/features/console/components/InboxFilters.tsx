import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import { Badge, Button, Collapse, FormControlLabel, MenuItem, Stack, Switch, TextField, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useState } from 'react';

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
  /** Only people who can answer complaints ever hold one, so only they get With me and Waiting on me. */
  canHold?: boolean;
}

const MINE_LABEL: Record<MineFilter, string> = { '': 'All', with: 'With me', waiting: 'Waiting on me' };
const SORT_LABEL: Record<InboxQuery['sort'], string> = { priority: 'Needs you first', newest: 'Newest first', oldest: 'Oldest first' };

function MineToggle({ value, onChange }: { value: MineFilter; onChange: (value: MineFilter) => void }) {
  return (
    <ToggleButtonGroup exclusive size="small" value={value} aria-label="Whose complaints"
      onChange={(_, next: MineFilter | null) => onChange(next ?? '')}
      sx={{ '& .MuiToggleButton-root': { px: 1.5, textTransform: 'none', fontWeight: 600 } }}>
      {(Object.keys(MINE_LABEL) as MineFilter[]).map((k) => <ToggleButton key={k || 'all'} value={k}>{MINE_LABEL[k]}</ToggleButton>)}
    </ToggleButtonGroup>
  );
}

/** The filters used less often, behind one button. */
function MoreFilters({ query, showDiscom, onFilter, onFailed }: Omit<InboxFiltersProps, 'onSort' | 'mine' | 'onMine'>) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap', alignItems: { sm: 'center' }, pt: 0.5 }}>
      <TypeSelect size="small" emptyLabel="All types" value={query.type} onChange={(v) => onFilter('type', v)} />
      <TextField select size="small" label="Priority" value={query.priority} onChange={(e) => onFilter('priority', e.target.value)} sx={{ minWidth: 140 }}>
        <MenuItem value="">Any priority</MenuItem>
        {PRIORITIES.map((p) => <MenuItem key={p} value={p}>{PRIORITY[p].label}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Source" value={query.source} onChange={(e) => onFilter('source', e.target.value)} sx={{ minWidth: 160 }}>
        <MenuItem value="">Any source</MenuItem>
        {SOURCES.map((s) => <MenuItem key={s} value={s}>{SOURCE_LABEL[s]}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Check result" value={query.triage} onChange={(e) => onFilter('triage', e.target.value)} sx={{ minWidth: 160 }}>
        <MenuItem value="">Any result</MenuItem>
        {TRIAGES.map((t) => <MenuItem key={t} value={t}>{TRIAGE[t].label}</MenuItem>)}
      </TextField>
      {showDiscom && (
        <TextField select size="small" label="DISCOM" value={query.discom} onChange={(e) => onFilter('discom', e.target.value)} sx={{ minWidth: 140 }}>
          <MenuItem value="">All DISCOMs</MenuItem>
          {DISCOMS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
        </TextField>
      )}
      <FormControlLabel control={<Switch size="small" checked={query.failed} onChange={(e) => onFailed(e.target.checked)} />}
        label="Reply not delivered" />
    </Stack>
  );
}

const extraCount = (q: InboxQuery, showDiscom: boolean) =>
  [q.type, q.priority, q.source, q.triage, showDiscom ? q.discom : '', q.failed ? 'on' : ''].filter(Boolean).length;

/** One row for what people use every day; the rest opens on demand and says how many are set. */
export function InboxFilters({ query, showDiscom, onFilter, onFailed, onSort, mine, onMine, canHold = true }: InboxFiltersProps) {
  const active = extraCount(query, showDiscom);
  const [open, setOpen] = useState(active > 0);
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap', alignItems: { md: 'center' } }}>
        {canHold && <MineToggle value={mine} onChange={onMine} />}
        <SearchField label="Ticket" placeholder="BM-261016-7KQ2D" value={query.q} onChange={(v) => onFilter('q', v)} />
        <TextField select size="small" label="Status" value={query.status} onChange={(e) => onFilter('status', e.target.value)} sx={{ minWidth: 140 }}>
          <MenuItem value="">All statuses</MenuItem>
          {COMPLAINT_STATUSES.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
        </TextField>
        <Badge badgeContent={active} color="primary">
          <Button variant={open ? 'contained' : 'outlined'} color="inherit" startIcon={<TuneRoundedIcon />} onClick={() => setOpen(!open)}
            aria-expanded={open} sx={{ borderColor: 'divider' }}>
            More filters
          </Button>
        </Badge>
        <TextField select size="small" label="Sort" value={query.sort} onChange={(e) => onSort(e.target.value as InboxQuery['sort'])}
          sx={{ minWidth: 160, ml: { md: 'auto' } }}>
          {(Object.keys(SORT_LABEL) as Array<InboxQuery['sort']>).map((s) => <MenuItem key={s} value={s}>{SORT_LABEL[s]}</MenuItem>)}
        </TextField>
      </Stack>
      <Collapse in={open}>
        <MoreFilters query={query} showDiscom={showDiscom} onFilter={onFilter} onFailed={onFailed} />
      </Collapse>
    </Stack>
  );
}
