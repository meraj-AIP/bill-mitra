import SearchIcon from '@mui/icons-material/Search';
import { InputAdornment, TextField } from '@mui/material';
import { useEffect, useState } from 'react';

import { useDebounced } from '@/shared/hooks/useDebounced';

interface SearchFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

/** Typing stays local and only settles into the URL after a short pause, so each key press is not a request. */
export function SearchField({ label, value, onChange, placeholder }: SearchFieldProps) {
  const [text, setText] = useState(value);
  const [seen, setSeen] = useState(value);
  const settled = useDebounced(text, 350).trim();

  // The URL can change from outside (Clear filters, back button); follow it.
  if (value !== seen) {
    setSeen(value);
    if (value !== text.trim()) setText(value);
  }

  useEffect(() => {
    // Only push once the pause has caught up with what is typed, so a stale value never comes back.
    if (settled === text.trim() && settled !== value) onChange(settled);
  }, [settled, text, value, onChange]);

  return (
    <TextField size="small" type="search" label={label} value={text} onChange={(e) => setText(e.target.value)}
      {...(placeholder ? { placeholder } : {})} sx={{ minWidth: { sm: 220 } }}
      slotProps={{
        htmlInput: { spellCheck: false, autoCapitalize: 'none' },
        input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> },
      }} />
  );
}
