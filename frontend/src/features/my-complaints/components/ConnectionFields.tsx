import { Alert, Box, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';

import { DISCOMS, type Discom } from '@/shared/api/types';
import { USC_HINT, uscShapeOk } from '@/shared/lib/serviceNumber';

import { BillChoice } from './BillChoice';

interface ConnectionFieldsProps {
  discom: Discom | null;
  usc: string;
  billId: string;
  /** A send was tried, so missing answers show as problems. */
  tried: boolean;
  needsBill: boolean;
  onDiscom: (discom: Discom) => void;
  onUsc: (usc: string) => void;
  onBill: (billId: string) => void;
}

const isDiscom = (value: string): value is Discom => (DISCOMS as string[]).includes(value);

export function ConnectionFields({ discom, usc, billId, tried, needsBill, onDiscom, onUsc, onBill }: ConnectionFieldsProps) {
  const uscBad = usc.trim() !== '' && !uscShapeOk(usc);
  return (
    <Stack sx={{ gap: 2.5 }}>
      <Box>
        <ToggleButtonGroup exclusive value={discom} onChange={(_e, v: Discom | null) => v && onDiscom(v)} aria-label="Your DISCOM"
          sx={{ flexWrap: 'wrap', '& .MuiToggleButton-root': { px: 2.5, textTransform: 'none', fontWeight: 600 } }}>
          {DISCOMS.map((d) => <ToggleButton key={d} value={d} color="primary">{d}</ToggleButton>)}
        </ToggleButtonGroup>
        {tried && !discom && <Typography variant="caption" sx={{ color: 'error.main', mt: 0.75, display: 'block' }}>Please pick your DISCOM.</Typography>}
      </Box>
      <TextField label="Service number (optional)" value={usc} onChange={(e) => onUsc(e.target.value)} error={uscBad}
        helperText={uscBad ? USC_HINT : 'It helps us find your connection faster.'}
        slotProps={{ htmlInput: { autoComplete: 'off', spellCheck: false, inputMode: 'numeric' } }} sx={{ maxWidth: 360 }} />
      <BillChoice value={billId} onChange={(b) => {
        onBill(b?.id ?? '');
        if (b && isDiscom(b.discom)) onDiscom(b.discom);
      }} />
      {needsBill && !billId && (
        <Alert severity="info">For this problem we need your bill. If you do not pick one, we will ask you for a photo.</Alert>
      )}
    </Stack>
  );
}
