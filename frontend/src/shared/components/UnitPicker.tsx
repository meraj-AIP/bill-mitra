import { Autocomplete, Box, TextField, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useState, type HTMLAttributes, type Key } from 'react';

import { UNIT_KIND_LABEL, type Unit, type UnitKind, type UnitRef } from '@/shared/api/types';
import { unitsQuery } from '@/shared/api/units';
import { useDebounced } from '@/shared/hooks/useDebounced';

function emptyText(typed: string, waiting: boolean, failed: boolean): string {
  // A 403 means this account may not search units, so say so instead of claiming no match.
  if (failed) return 'Unit search is not open to your account.';
  if (typed.length === 1) return 'Type one more letter';
  if (waiting) return 'Searching';
  return typed ? 'No unit by that name' : 'No units in your area yet';
}

const toRef = (u: Unit): UnitRef => ({ unit_id: u.id, name: u.name, kind: u.kind });
const sameUnit = (a: UnitRef, b: UnitRef) => a.unit_id === b.unit_id;

interface BaseProps {
  label: string;
  helperText?: string;
  error?: boolean;
  /** Only units of this kind are offered. */
  kind?: UnitKind;
  size?: 'small' | 'medium';
  disabled?: boolean;
  /** Only units of this DISCOM are offered. */
  discom?: string;
}

interface MultiProps extends BaseProps { multiple: true; value: UnitRef[]; onChange: (value: UnitRef[]) => void }
interface SingleProps extends BaseProps { multiple?: false; value: UnitRef | null; onChange: (value: UnitRef | null) => void }

function Option({ unit, discom }: { unit: UnitRef; discom: string | undefined }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>{unit.name}</Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {UNIT_KIND_LABEL[unit.kind]}{discom ? `, ${discom}` : ''}
      </Typography>
    </Box>
  );
}

function useUnitSearch(typed: string, kind: UnitKind | undefined, disabled: boolean, discom: string | undefined) {
  const q = useDebounced(typed, 300);
  const search = useQuery({ ...unitsQuery({ q, kind: kind ?? '' }), enabled: (q.length === 0 || q.length >= 2) && !disabled });
  // Between a keystroke and the debounced search the old results do not match the text, so none are shown.
  const current = typed === q && typed.length !== 1;
  const found = current ? (search.data ?? []).filter((u) => !discom || u.discom === discom) : [];
  return { found, waiting: !current || search.isFetching, failed: search.isError };
}

/**
 * Opens on the top of the units this account covers, then searches the server as the person types (two letters or
 * more). Results from an earlier search are never shown for a newer one, so the list always matches the text.
 */
export function UnitPicker(props: MultiProps | SingleProps) {
  const { label, helperText, error = false, kind, size = 'medium', disabled = false, discom } = props;
  const [text, setText] = useState('');
  const typed = text.trim();
  const { found, waiting, failed } = useUnitSearch(typed, kind, disabled, discom);
  const discomOf = new Map(found.map((u) => [u.id, u.discom]));
  const options = found.map(toRef);
  const common = {
    options,
    disabled,
    size,
    filterOptions: (o: UnitRef[]) => o,
    isOptionEqualToValue: sameUnit,
    getOptionLabel: (o: UnitRef) => o.name,
    loading: waiting && typed.length !== 1,
    openOnFocus: true,
    // A pick in the multi select clears the text, which brings the starting list back for the next pick.
    onInputChange: (_e: unknown, v: string, reason: string) => setText(reason === 'reset' && props.multiple ? '' : v),
    noOptionsText: emptyText(typed, waiting, failed),
    renderOption: (attrs: HTMLAttributes<HTMLLIElement> & { key: Key }, o: UnitRef) => {
      const { key, ...rest } = attrs;
      return <li key={key} {...rest}><Option unit={o} discom={discomOf.get(o.unit_id)} /></li>;
    },
    renderInput: (params: object) => (
      <TextField {...params} label={label} error={error} {...(helperText ? { helperText } : {})} />
    ),
  };
  if (props.multiple) {
    return <Autocomplete {...common} multiple filterSelectedOptions value={props.value} onChange={(_e, v: UnitRef[]) => props.onChange(v)} />;
  }
  return <Autocomplete {...common} value={props.value} onChange={(_e, v: UnitRef | null) => props.onChange(v)} />;
}
