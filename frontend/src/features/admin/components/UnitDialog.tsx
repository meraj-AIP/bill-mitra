import { Autocomplete, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Stack, Switch, TextField } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { UNIT_KIND_LABEL, type Unit, type UnitKind } from '@/shared/api/types';

import { useCreateUnit, useUpdateUnit, type NewUnit, type UnitChanges } from '../api/unitsApi';
import { ActionError } from '@/shared/feedback';

/** What may sit directly under each kind; DISCOMs are seeded and sections are leaves. */
export const CHILD_KINDS: Record<UnitKind, UnitKind[]> = {
  discom: ['circle'], circle: ['division'], division: ['subdivision', 'ero'], subdivision: ['section'], section: [], ero: [],
};

// "section" reads as a word; ERO and DISCOM stay in capitals.
export const inSentence = (kind: UnitKind) => (kind === 'ero' || kind === 'discom' ? UNIT_KIND_LABEL[kind] : UNIT_KIND_LABEL[kind].toLowerCase());

interface Form { kind: UnitKind; name: string; code: string; aliases: string[]; eroId: string; active: boolean }

function formOf(unit: Unit | null, parent: Unit): Form {
  if (unit) return { kind: unit.kind, name: unit.name, code: unit.code ?? '', aliases: unit.aliases, eroId: unit.ero_id ?? '', active: unit.active };
  return { kind: CHILD_KINDS[parent.kind][0] ?? 'section', name: '', code: '', aliases: [], eroId: '', active: true };
}

function changesOf(f: Form): UnitChanges {
  const changes: UnitChanges = { name: f.name.trim(), code: f.code.trim() || null, aliases: f.aliases, active: f.active };
  if (f.kind === 'section') changes.ero_id = f.eroId || null;
  return changes;
}

function newUnitOf(f: Form, parent: Unit): NewUnit {
  const body: NewUnit = { kind: f.kind, name: f.name.trim(), parent_id: parent.id, aliases: f.aliases };
  if (f.code.trim()) body.code = f.code.trim();
  if (f.kind === 'section') body.ero_id = f.eroId || null;
  return body;
}

const normalise = (aliases: string[]) => [...new Set(aliases.map((a) => a.trim().toUpperCase()).filter(Boolean))];

function AliasField({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  return (
    <Autocomplete multiple freeSolo options={[]} value={value} onChange={(_e, v: string[]) => onChange(normalise(v))}
      renderValue={(values, getItemProps) => values.map((v, index) => {
        const { key, ...rest } = getItemProps({ index });
        return <Chip key={key} size="small" label={v} {...rest} />;
      })}
      renderInput={(params) => (
        <TextField {...params} label="Other spellings" placeholder="Type one and press Enter"
          helperText="Names bills sometimes print instead, so they still route here." />
      )} />
  );
}

interface FieldsProps { form: Form; set: (changes: Partial<Form>) => void; kinds: UnitKind[]; editing: boolean; eros: Unit[]; nameProblem: string | null }

function Fields({ form, set, kinds, editing, eros, nameProblem }: FieldsProps) {
  return (
    <>
      {!editing && kinds.length > 1 && (
        <TextField select label="Kind" value={form.kind} onChange={(e) => set({ kind: e.target.value as UnitKind })}
          helperText="An ERO bills a group of sections; each section can point at one.">
          {kinds.map((k) => <MenuItem key={k} value={k}>{UNIT_KIND_LABEL[k]}</MenuItem>)}
        </TextField>
      )}
      <TextField label={`${UNIT_KIND_LABEL[form.kind]} name`} value={form.name} onChange={(e) => set({ name: e.target.value })} autoFocus
        error={Boolean(nameProblem)} helperText={nameProblem ?? 'As printed after Sec: on the bill, for a section.'} />
      <TextField label="Code" value={form.code} onChange={(e) => set({ code: e.target.value })} helperText="Optional. Used to link rows in a CSV import." />
      <AliasField value={form.aliases} onChange={(aliases) => set({ aliases })} />
      {form.kind === 'section' && (
        <TextField select label="ERO" value={form.eroId} onChange={(e) => set({ eroId: e.target.value })}
          helperText={eros.length ? 'The ERO that bills this section.' : 'Add an ERO under the division first to link one.'}>
          <MenuItem value="">No ERO</MenuItem>
          {eros.map((e) => <MenuItem key={e.id} value={e.id}>{e.name}</MenuItem>)}
        </TextField>
      )}
      {editing && (
        <FormControlLabel control={<Switch checked={form.active} onChange={(e) => set({ active: e.target.checked })} />}
          label={form.active ? 'Active: new cases route here' : 'Inactive: kept for old cases, no new routing'} />
      )}
    </>
  );
}

interface UnitDialogProps {
  /** The unit being edited, or null to add a child of parent. */
  unit: Unit | null;
  parent: Unit;
  /** EROs of the division above, offered to a section. */
  eros: Unit[];
  onClose: () => void;
}

/** Mount with a key per unit, so the form starts from that unit's values. */
export function UnitDialog({ unit, parent, eros, onClose }: UnitDialogProps) {
  const create = useCreateUnit();
  const update = useUpdateUnit();
  const save = unit ? update : create;
  const [form, setForm] = useState<Form>(() => formOf(unit, parent));
  const [checked, setChecked] = useState(false);
  const nameProblem = checked && !form.name.trim() ? 'Enter the name as it is printed on bills.' : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (!form.name.trim()) return;
    if (unit) update.mutate({ id: unit.id, changes: changesOf(form) }, { onSuccess: onClose });
    else create.mutate(newUnitOf(form, parent), { onSuccess: onClose });
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>{unit ? `Edit ${unit.name}` : `Add under ${parent.name}`}</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2, pt: 1 }}>
            <ActionError error={save.error} action="Saving the unit" />
            <Fields form={form} set={(changes) => setForm((f) => ({ ...f, ...changes }))} kinds={CHILD_KINDS[parent.kind]}
              editing={unit !== null} eros={eros} nameProblem={nameProblem} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={save.isPending}
            startIcon={save.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            {unit ? 'Save changes' : `Add ${inSentence(form.kind)}`}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
