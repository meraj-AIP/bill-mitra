import { Autocomplete, Box, TextField, Typography } from '@mui/material';
import { useState, type HTMLAttributes, type Key } from 'react';

import { UNIT_KIND_LABEL, type Unit, type UnitKind, type UnitRef } from '@/shared/api/types';
import { useUnits } from '@/shared/api/units';
import { useDebounced } from '@/shared/hooks/useDebounced';

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

/** Searches units on the server as the person types; nothing is loaded until two letters are in. */
export function UnitPicker(props: MultiProps | SingleProps) {
  const { label, helperText, error = false, kind, size = 'medium', disabled = false } = props;
  const [text, setText] = useState('');
  const q = useDebounced(text.trim(), 300);
  const search = useUnits({ q, kind: kind ?? '' }, q.length >= 2 && !disabled);
  const found = search.data ?? [];
  const discomOf = new Map(found.map((u) => [u.id, u.discom]));
  const options = found.map(toRef);
  const common = {
    options,
    disabled,
    size,
    filterOptions: (o: UnitRef[]) => o,
    isOptionEqualToValue: sameUnit,
    getOptionLabel: (o: UnitRef) => o.name,
    loading: search.isFetching,
    onInputChange: (_e: unknown, v: string) => setText(v),
    noOptionsText: q.length < 2 ? 'Type two or more letters' : 'No unit by that name',
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
