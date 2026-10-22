import { Button, CircularProgress, Stack } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { useSignInWithCode } from '../api/authApi';
import { useCodeFlow } from '../hooks/useCodeFlow';
import { codeProblem } from '../model/codes';
import { MOBILE_PATTERN } from '../model/roles';
import { FormError } from './AuthFrame';
import { ChannelPicker } from './ChannelPicker';
import { CodeStep } from './CodeStep';
import { MobileField } from './MobileField';

/** Consumers sign in with their mobile and a one-time code. Where to go next is decided by PublicOnly. */
export function ConsumerSignIn({ mobile, onMobile }: { mobile: string; onMobile: (m: string) => void }) {
  const flow = useCodeFlow();
  const verify = useSignInWithCode();
  const [checked, setChecked] = useState(false);
  const bad = checked && !MOBILE_PATTERN.test(mobile);

  if (flow.sent) {
    return (
      <CodeStep key={flow.round} mobile={mobile} sent={flow.sent} verb="Sign in" pending={verify.isPending} resending={flow.start.isPending}
        error={codeProblem(verify.error ?? flow.start.error)} onVerify={(code) => verify.mutate({ mobile, code })}
        onResend={flow.resend} onBack={() => { verify.reset(); flow.back(); }} />
    );
  }
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (MOBILE_PATTERN.test(mobile)) flow.send({ mobile, purpose: 'login' });
  };
  return (
    <Stack component="form" noValidate onSubmit={submit} sx={{ gap: 2.25 }} aria-busy={flow.start.isPending}>
      <FormError message={codeProblem(flow.start.error)} />
      <MobileField label="Mobile number" value={mobile} onChange={onMobile} autoFocus error={bad}
        helperText={bad ? 'Enter a 10 digit mobile number starting with 6, 7, 8 or 9.' : 'The number you signed up with.'} />
      {flow.channels.length > 0 && <ChannelPicker channels={flow.channels} value={flow.channel} onChange={flow.pick} />}
      <Button type="submit" variant="contained" size="large" fullWidth disabled={flow.start.isPending || flow.channels.length === 0}
        startIcon={flow.start.isPending ? <CircularProgress size={18} color="inherit" aria-hidden /> : null} sx={{ mt: 0.5, py: 1.4 }}>
        {flow.start.isPending ? 'Sending' : 'Send code'}
      </Button>
    </Stack>
  );
}
