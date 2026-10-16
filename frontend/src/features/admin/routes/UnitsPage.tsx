import AddRoundedIcon from '@mui/icons-material/AddRounded';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import { Box, Breadcrumbs, Button, Container, Link, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useState } from 'react';

import type { Unit } from '@/shared/api/types';
import { useUnits } from '@/shared/api/units';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState, ErrorState } from '@/shared/components/States';
import { useUrlState } from '@/shared/hooks/useUrlState';

import { CHILD_KINDS, inSentence, UnitDialog } from '../components/UnitDialog';
import { ImportUnitsDialog } from '../components/ImportUnitsDialog';
import { UnitTable } from '../components/UnitTable';
import { UnmappedQueue } from '../components/UnmappedQueue';
import { useUnitTrail } from '../hooks/useUnitTrail';

type Open = { kind: 'unit'; unit: Unit | null } | { kind: 'import' } | null;

function Crumbs({ trail, goTo }: Pick<ReturnType<typeof useUnitTrail>, 'trail' | 'goTo'>) {
  return (
    <Breadcrumbs aria-label="Where you are in the unit tree">
      <Link component="button" type="button" underline="hover" onClick={() => goTo(0)} sx={{ fontSize: '0.875rem' }}>Telangana</Link>
      {trail.map((u, i) => (i === trail.length - 1
        ? <Typography key={u.id} variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }} aria-current="page">{u.name}</Typography>
        : <Link key={u.id} component="button" type="button" underline="hover" onClick={() => goTo(i + 1)} sx={{ fontSize: '0.875rem' }}>{u.name}</Link>))}
    </Breadcrumbs>
  );
}

type TrailState = ReturnType<typeof useUnitTrail>;

/** A section's ERO sits under the division, one level above its sub-division. */
function divisionOf(t: TrailState): Unit | undefined {
  if (t.current?.kind === 'division') return t.current;
  return t.current?.kind === 'subdivision' ? t.trail.at(-2) : undefined;
}

function Toolbar({ t, onAdd, onImport }: { t: TrailState; onAdd: (() => void) | null; onImport: () => void }) {
  const kinds = t.current ? CHILD_KINDS[t.current.kind] : [];
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' } }}>
      <Box sx={{ flex: 1 }}><Crumbs trail={t.trail} goTo={t.goTo} /></Box>
      <Button variant="outlined" startIcon={<UploadFileOutlinedIcon />} onClick={onImport}>Import CSV</Button>
      {onAdd && <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={onAdd}>Add {kinds.map(inSentence).join(' or ')}</Button>}
    </Stack>
  );
}

function EroLevel({ t, onEdit }: { t: TrailState; onEdit: (unit: Unit) => void }) {
  const eroRows = (t.children ?? []).filter((u) => u.kind === 'ero');
  if (t.current?.kind !== 'division' || eroRows.length === 0) return null;
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      <Typography variant="subtitle1" component="h2" sx={{ px: 2, pt: 1.5, pb: 1 }}>EROs in {t.current.name}</Typography>
      <UnitTable label="EROs" rows={eroRows} eros={[]} onOpen={t.open} onEdit={onEdit} />
    </Paper>
  );
}

function Level({ t, eros, onEdit }: { t: TrailState; eros: Unit[]; onEdit: (unit: Unit) => void }) {
  const current = t.current;
  const rows = t.children?.filter((u) => u.kind !== 'ero');
  const empty = t.children?.length === 0;
  const hint = current && CHILD_KINDS[current.kind].length > 0
    ? 'Use the Add button above, or import a CSV file of units.' : 'Sections and EROs have nothing under them.';
  return (
    <>
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        {empty ? (
          <EmptyState icon={<AccountTreeOutlinedIcon />} title={`Nothing under ${current?.name ?? 'Telangana'} yet`} hint={hint} />
        ) : (
          <UnitTable label={current ? `Units under ${current.name}` : 'DISCOMs'} rows={t.resolving ? undefined : rows} eros={eros}
            onOpen={t.open} onEdit={current ? onEdit : undefined} />
        )}
      </Paper>
      <EroLevel t={t} onEdit={onEdit} />
    </>
  );
}

function Dialogs({ open, parent, eros, onClose }: { open: Open; parent: Unit | null; eros: Unit[]; onClose: () => void }) {
  if (open?.kind === 'import') return <ImportUnitsDialog onClose={onClose} />;
  if (open?.kind !== 'unit' || !parent) return null;
  return <UnitDialog key={open.unit?.id ?? 'new'} unit={open.unit} parent={parent} eros={eros} onClose={onClose} />;
}

function Structure() {
  const t = useUnitTrail();
  const [open, setOpen] = useState<Open>(null);
  const division = divisionOf(t);
  const eros = useUnits({ parentId: division?.id ?? null, kind: 'ero' }, Boolean(division)).data ?? [];
  const canAdd = t.current !== null && CHILD_KINDS[t.current.kind].length > 0;
  return (
    <Stack sx={{ gap: 2 }}>
      <Toolbar t={t} onAdd={canAdd ? () => setOpen({ kind: 'unit', unit: null }) : null} onImport={() => setOpen({ kind: 'import' })} />
      {t.lost && <ErrorState message="This place in the tree no longer exists. Go back to Telangana and open it again." onRetry={() => t.goTo(0)} />}
      {t.childrenError && <ErrorState message={t.childrenError.message} onRetry={t.refetch} />}
      <Level t={t} eros={eros} onEdit={(unit) => setOpen({ kind: 'unit', unit })} />
      <Dialogs open={open} parent={t.current} eros={eros} onClose={() => setOpen(null)} />
    </Stack>
  );
}

export function UnitsPage() {
  const url = useUrlState();
  const view = url.pick('view', ['unmapped'] as const) || 'tree';
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Administration" title="Units"
          lead="The DISCOM structure cases are routed by: DISCOM, circle, division, sub-division and section, with EROs under their division." />
        <Tabs value={view} onChange={(_e, v: string) => url.update({ view: v === 'tree' ? null : v, at: null })}
          sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab value="tree" label="Structure" />
          <Tab value="unmapped" label="Unmapped sections" />
        </Tabs>
        {view === 'tree' ? <Structure /> : <UnmappedQueue />}
      </Stack>
    </Container>
  );
}
