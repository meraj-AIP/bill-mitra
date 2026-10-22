import { InputAdornment, TextField } from '@mui/material';

interface MobileFieldProps {
  label: string;
  value: string;
  onChange: (digits: string) => void;
  helperText: string;
  error?: boolean;
  autoFocus?: boolean;
  disabled?: boolean;
}

/** A 10 digit Indian mobile: the +91 is shown, never typed, and anything that is not a digit is dropped. */
export function MobileField({ label, value, onChange, helperText, error = false, autoFocus = false, disabled = false }: MobileFieldProps) {
  return (
    <TextField label={label} name="mobile" type="tel" autoComplete="tel-national" required fullWidth autoFocus={autoFocus}
      disabled={disabled} value={value} error={error} helperText={helperText}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(-10))}
      slotProps={{
        htmlInput: { inputMode: 'numeric', maxLength: 10, pattern: '[6-9][0-9]{9}' },
        input: { startAdornment: <InputAdornment position="start">+91</InputAdornment> },
      }} />
  );
}
