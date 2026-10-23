import { Alert, Box, Button, CircularProgress, Link, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { ErrorNotice } from '@/shared/feedback';

import { attemptsLeft } from '../api/uscApi';
import { useCountdown } from '../hooks/useCountdown';

interface UscCodeStepProps {
  /** The server's own words: neutral, never saying whether the number exists. */
  message: string | null;
  resendAt: number | null;
  verifying: boolean;
  resending: boolean;
  error: Error | null;
  onVerify: (code: string) => void;
  onResend: () => void;
  onChangeNumber: () => void;
}

const CODE = /^\d{6}$/;

function TriesLeft({ error }: { error: Error | null }) {
  const left = attemptsLeft(error);
  if (left === null) return null;
  const text = left === 0 ? 'No tries left on this code. Ask for a new code.' : left === 1 ? 'You have 1 try left.' : `You have ${left} tries left.`;
  return <Typography variant="body2" sx={{ color: 'text.secondary', mt: -1 }} aria-live="polite">{text}</Typography>;
}

export function UscCodeStep({ message, resendAt, verifying, resending, error, onVerify, onResend, onChangeNumber }: UscCodeStepProps) {
  const [code, setCode] = useState('');
  const left = useCountdown(resendAt);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (CODE.test(code)) onVerify(code);
  };
  return (
    <Stack component="form" onSubmit={submit} noValidate sx={{ gap: 2 }}>
      <Alert severity="info">{message ?? 'If this connection has a registered mobile, we have sent a 6 digit code to it.'}</Alert>
      <ErrorNotice error={error} action="Checking the code" />
      <TriesLeft error={error} />
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'flex-start' } }}>
        <TextField label="6 digit code" value={code} autoFocus
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          slotProps={{ htmlInput: { inputMode: 'numeric', autoComplete: 'one-time-code', maxLength: 6,
            sx: { fontVariantNumeric: 'tabular-nums', letterSpacing: '0.3em', fontSize: '1.125rem' } } }}
          sx={{ width: { xs: '100%', sm: 200 } }} />
        <Button type="submit" variant="contained" size="large" disabled={!CODE.test(code) || verifying}
          startIcon={verifying ? <CircularProgress size={16} color="inherit" aria-hidden /> : undefined}>
          {verifying ? 'Checking' : 'Get my bill'}
        </Button>
      </Stack>
      <Stack direction="row" sx={{ gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        {left > 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }} aria-live="polite">
            You can ask for a new code in {left} s.
          </Typography>
        ) : (
          <Button size="small" onClick={onResend} disabled={resending} sx={{ ml: -1 }}>
            {resending ? 'Sending' : 'Send a new code'}
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        <Link component="button" type="button" variant="body2" onClick={onChangeNumber}>Use another service number</Link>
      </Stack>
    </Stack>
  );
}
