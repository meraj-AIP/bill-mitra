import { Box, Checkbox, FormControl, FormControlLabel, FormGroup, FormHelperText, FormLabel, Stack, Typography } from '@mui/material';

import type { evidenceOptions } from '../model/decision';

interface EvidencePickerProps {
  options: ReturnType<typeof evidenceOptions>;
  value: string[];
  onChange: (value: string[]) => void;
  error: string | null;
}

/** What the decision rests on. At least one item is required; the approver and the audit see the same list. */
export function EvidencePicker({ options, value, onChange, error }: EvidencePickerProps) {
  const toggle = (key: string, on: boolean) => onChange(on ? [...value, key] : value.filter((k) => k !== key));
  return (
    <FormControl component="fieldset" error={Boolean(error)} variant="standard">
      <FormLabel component="legend" sx={{ fontWeight: 600, fontSize: '0.8125rem', color: 'text.primary', mb: 0.5 }}>Evidence</FormLabel>
      <FormGroup sx={{ gap: 0.5 }}>
        {options.map((o) => (
          <FormControlLabel key={o.key} sx={{ alignItems: 'center', mr: 0 }}
            control={<Checkbox size="small" checked={value.includes(o.key)} onChange={(e) => toggle(o.key, e.target.checked)} />}
            label={
              <Stack direction="row" sx={{ gap: 1.25, alignItems: 'center', minWidth: 0 }}>
                {o.photo && (
                  <Box component="img" src={o.photo} alt="" loading="lazy"
                    sx={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 1, border: 1, borderColor: 'divider', flexShrink: 0 }} />
                )}
                <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{o.label}</Typography>
              </Stack>
            } />
        ))}
      </FormGroup>
      <FormHelperText>{error ?? (options.length <= 1 ? 'Ask the consumer for a meter photo if the bill alone does not settle it.' : ' ')}</FormHelperText>
    </FormControl>
  );
}
