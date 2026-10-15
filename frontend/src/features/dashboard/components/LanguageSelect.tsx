import { ToggleButton, ToggleButtonGroup } from '@mui/material';

import { LANGUAGES, type Language } from '@/shared/lib/languages';

interface LanguageSelectProps {
  value: Language;
  onChange: (language: Language) => void;
  disabled?: boolean;
}

export function LanguageSelect({ value, onChange, disabled = false }: LanguageSelectProps) {
  return (
    <ToggleButtonGroup size="small" exclusive value={value} disabled={disabled} aria-label="Explanation language"
      onChange={(_e, next: Language | null) => next && onChange(next)}
      sx={{ flexWrap: 'wrap', '& .MuiToggleButton-root': { px: 1.5, textTransform: 'none', fontWeight: 600 } }}>
      {LANGUAGES.map((l) => (
        <ToggleButton key={l.code} value={l.code} lang={l.code}>
          {l.label}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}
