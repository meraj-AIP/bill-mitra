import { ListSubheader, MenuItem, TextField } from '@mui/material';

import { useComplaintTypes } from '../api/typesApi';
import { groupTypes } from '../model/catalogue';

interface TypeSelectProps {
  value: string;
  onChange: (code: string) => void;
  label?: string;
  /** An "all types" choice for filters. Leave out for a form where a type is required. */
  emptyLabel?: string;
  size?: 'small' | 'medium';
  required?: boolean;
  helperText?: string;
  error?: boolean;
  fullWidth?: boolean;
}

/** The server catalogue as one select, grouped by category with Billing first. */
export function TypeSelect({ value, onChange, emptyLabel, helperText, error, fullWidth, ...field }: TypeSelectProps) {
  const types = useComplaintTypes();
  const list = types.data ?? [];
  // MUI Select takes a flat list of children, so each group is a header followed by its items.
  const items = groupTypes(list).flatMap((g) => [
    <ListSubheader key={`h-${g.category}`}>{g.label}</ListSubheader>,
    ...g.types.map((t) => <MenuItem key={t.code} value={t.code} sx={{ pl: 3 }}>{t.label}</MenuItem>),
  ]);
  // A value from the URL stays selectable while the catalogue loads, so the field does not warn.
  const known = !value || list.some((t) => t.code === value);
  const help = types.isError ? 'Could not load the complaint types. Try again in a moment.' : helperText;
  return (
    <TextField select label="Type" {...field} value={value} error={Boolean(error) || types.isError} fullWidth={Boolean(fullWidth)}
      onChange={(e) => onChange(e.target.value)} sx={{ minWidth: 190 }} {...(help ? { helperText: help } : {})}>
      {emptyLabel !== undefined && <MenuItem value="">{emptyLabel}</MenuItem>}
      {!known && <MenuItem value={value}>{value}</MenuItem>}
      {types.isPending && <MenuItem disabled value="__loading">Loading types</MenuItem>}
      {items}
    </TextField>
  );
}
