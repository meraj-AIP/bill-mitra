import { Alert, Button, CircularProgress, Link, Stack, TextField, Typography } from '@mui/material';
import { useEffect, useState, type FormEvent } from 'react';

import type { CodeSent } from '../api/authApi';
import { CHANNEL_LABEL } from '../model/codes';
import { FormError } from './AuthFrame';

interface CodeStepProps {
  mobile: string;
  sent: CodeSent;
  verb: string;
  pending: boolean;
  resending: boolean;
  error: string | null;
  onVerify: (code: string) => void;
  onResend: () => void;
  onBack: () => void;
}

function useCountdown(seconds: number): number {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    const timer = window.setInterval(() => setLeft((s) => (s <= 1 ? 0 : s - 1)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return left;
}

/** The second step: type the six digit code. Resend waits a little so a slow SMS is not chased by a second one. Each
 * new code remounts this step (the caller keys it), which restarts the wait. */
export function CodeStep({ mobile, sent, verb, pending, resending, error, onVerify, onResend, onBack }: CodeStepProps) {
  const [code, setCode] = useState('');
  const wait = useCountdown(sent.resend_in);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (code.length === 6) onVerify(code);
  };
  return (
    <Stack component="form" noValidate onSubmit={submit} sx={{ gap: 2 }} aria-busy={pending}>
      <Typography variant="body2">
        We sent a 6 digit code to <strong>+91 {mobile}</strong> by {CHANNEL_LABEL[sent.channel]}. It works for {Math.round(sent.expires_in / 60)} minutes.
      </Typography>
      {sent.dev_code && (
        <Alert severity="info" variant="outlined" sx={{ bgcolor: 'info.light' }}>
          Demo server, nothing is sent. Your code is <strong data-testid="dev-code">{sent.dev_code}</strong>
        </Alert>
      )}
      <FormError message={error} />
      <TextField label="Code" name="one-time-code" autoComplete="one-time-code" autoFocus required fullWidth value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
        slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6, sx: { letterSpacing: '0.5em', fontSize: 20, fontWeight: 600 } } }} />
      <Button type="submit" variant="contained" size="large" fullWidth disabled={pending || code.length !== 6}
        startIcon={pending ? <CircularProgress size={18} color="inherit" aria-hidden /> : null} sx={{ py: 1.4 }}>
        {pending ? 'Checking' : verb}
      </Button>
      <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
        <Link component="button" type="button" variant="body2" onClick={onBack}>Change number</Link>
        <Link component="button" type="button" variant="body2" onClick={onResend} disabled={wait > 0 || resending}
          sx={{ color: wait > 0 ? 'text.disabled' : undefined, pointerEvents: wait > 0 ? 'none' : undefined }}>
          {wait > 0 ? `Send again in ${wait}s` : 'Send a new code'}
        </Link>
      </Stack>
    </Stack>
  );
}
