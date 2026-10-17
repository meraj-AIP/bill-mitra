import { Alert, Button, CircularProgress, Stack, TextField, ToggleButton, ToggleButtonGroup } from '@mui/material';
import type { FormEvent } from 'react';

import { DISCOMS, type Discom } from '@/shared/api/types';
import { USC_HINT, uscShapeOk } from '@/shared/lib/serviceNumber';

interface UscNumberStepProps {
  discom: Discom | null;
  usc: string;
  onDiscom: (discom: Discom) => void;
  onUsc: (usc: string) => void;
  pending: boolean;
  error: string | null;
  onSend: () => void;
}

export function UscNumberStep({ discom, usc, onDiscom, onUsc, pending, error, onSend }: UscNumberStepProps) {
  const typed = usc.trim() !== '';
  const bad = typed && !uscShapeOk(usc);
  const submit = (event: FormEvent) => { event.preventDefault(); onSend(); };
  return (
    <Stack component="form" onSubmit={submit} noValidate sx={{ gap: 2 }}>
      {error && <Alert severity="error">{error}</Alert>}
      <ToggleButtonGroup exclusive value={discom} onChange={(_e, v: Discom | null) => v && onDiscom(v)} aria-label="Your DISCOM"
        sx={{ flexWrap: 'wrap', '& .MuiToggleButton-root': { px: 2.5, textTransform: 'none', fontWeight: 600 } }}>
        {DISCOMS.map((d) => <ToggleButton key={d} value={d} color="primary">{d}</ToggleButton>)}
      </ToggleButtonGroup>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'flex-start' } }}>
        <TextField label="Service number (USC)" value={usc} onChange={(e) => onUsc(e.target.value)} error={bad}
          helperText={bad ? USC_HINT : 'Printed at the top of your bill.'}
          slotProps={{ htmlInput: { autoComplete: 'off', spellCheck: false, inputMode: 'numeric' } }} sx={{ width: { xs: '100%', sm: 280 } }} />
        <Button type="submit" variant="outlined" size="large" disabled={!discom || !typed || bad || pending}
          startIcon={pending ? <CircularProgress size={16} color="inherit" aria-hidden /> : undefined}>
          {pending ? 'Sending' : 'Send code'}
        </Button>
      </Stack>
    </Stack>
  );
}
