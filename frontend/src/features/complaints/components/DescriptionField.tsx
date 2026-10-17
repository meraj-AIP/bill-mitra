import { TextField } from '@mui/material';

import { REPLY_LIMIT } from '../api/types';

interface DescriptionFieldProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  /** Show the empty field as a problem, after a send was tried. */
  showEmpty?: boolean;
}

/** A description box with a live counter against the 1000 character limit the server keeps. */
export function DescriptionField({ value, onChange, label, placeholder, showEmpty = false }: DescriptionFieldProps) {
  const over = value.length > REPLY_LIMIT;
  const empty = showEmpty && value.trim().length < MIN;
  const count = `${value.length} of ${REPLY_LIMIT} characters`;
  const helperText = over ? `${count}, too long to send` : empty ? 'Please describe the problem in a line or two.' : count;
  return (
    <TextField label={label} value={value} onChange={(e) => onChange(e.target.value)} multiline minRows={4} maxRows={12} fullWidth required
      error={over || empty} helperText={helperText} {...(placeholder ? { placeholder } : {})}
      slotProps={{ formHelperText: { sx: { fontVariantNumeric: 'tabular-nums' }, 'aria-live': 'polite' } }} />
  );
}

// The server asks for at least 3 characters once trimmed.
const MIN = 3;

export function descriptionOk(value: string): boolean {
  return value.trim().length >= MIN && value.length <= REPLY_LIMIT;
}
