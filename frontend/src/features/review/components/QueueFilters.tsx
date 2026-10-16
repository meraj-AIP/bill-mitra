import { Autocomplete, FormControlLabel, MenuItem, Stack, Switch, TextField } from '@mui/material';

import { SearchField } from '@/shared/components/SearchField';
import { formatCount } from '@/shared/lib/format';

import { useSections } from '../api/reviewApi';
import type { SectionOption } from '../api/types';
import type { useQueueParams } from '../hooks/useQueueParams';

type Params = ReturnType<typeof useQueueParams>;

/** Only sections that hold cases this account can see, so every choice returns something. */
function SectionFilter({ params }: { params: Params }) {
  const sections = useSections();
  const options = sections.data ?? [];
  if (sections.isSuccess && options.length < 2) return null;
  const value = options.find((s) => s.id === params.query.sectionId) ?? null;
  return (
    <Autocomplete<SectionOption> size="small" options={options} value={value} loading={sections.isPending}
      getOptionLabel={(o) => o.name} isOptionEqualToValue={(a, b) => a.id === b.id}
      onChange={(_e, v: SectionOption | null) => params.setSection(v?.id ?? null)} sx={{ minWidth: 240 }}
      noOptionsText="No section by that name"
      renderInput={(input) => <TextField {...input} label="Section" error={sections.isError}
        {...(sections.isError ? { helperText: 'Could not load sections' } : {})} />} />
  );
}

export function QueueFilters({ params, overdueCount }: { params: Params; overdueCount: number | undefined }) {
  const { query } = params;
  const overdueLabel = overdueCount ? `Overdue only (${formatCount(overdueCount)})` : 'Overdue only';
  return (
    <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap', alignItems: { md: 'center' } }}>
      <SearchField label="Ticket" placeholder="BM-261016-7KQ2D" value={query.q} onChange={params.setQ} />
      <SectionFilter params={params} />
      <FormControlLabel label="Assigned to me"
        control={<Switch size="small" checked={query.mine} onChange={(e) => params.setFlag('mine', e.target.checked)} />} />
      <FormControlLabel label={overdueLabel}
        control={<Switch size="small" checked={query.overdue} onChange={(e) => params.setFlag('overdue', e.target.checked)} />} />
      <TextField select size="small" label="Sort" value={query.sort} sx={{ minWidth: 170, ml: { md: 'auto' } }}
        onChange={(e) => params.setSort(e.target.value === 'newest' ? 'newest' : 'oldest')}>
        <MenuItem value="oldest">Oldest first</MenuItem>
        <MenuItem value="newest">Newest first</MenuItem>
      </TextField>
    </Stack>
  );
}
