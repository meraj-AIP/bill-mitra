import { Alert, Divider, Link as MuiLink, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import type { Discom } from '@/shared/api/types';

import { useSignUpWithCode } from '../api/authApi';
import { AuthFrame } from '../components/AuthFrame';
import { CodeStep } from '../components/CodeStep';
import { SignUpDetails, type SignUpValues } from '../components/SignUpDetails';
import { WhatsAppOnly } from '../components/WhatsAppOnly';
import { useCodeFlow } from '../hooks/useCodeFlow';
import { usePhone } from '../hooks/usePhone';
import { codeProblem } from '../model/codes';

function Found({ count, discom }: { count: number | null; discom: Discom }) {
  if (!count) return null;
  return (
    <Alert severity="success" variant="outlined" sx={{ bgcolor: 'success.light' }}>
      {discom} has {count === 1 ? 'one connection' : `${count} connections`} on this number. They will be linked to your account.
    </Alert>
  );
}

function SignUp() {
  const flow = useCodeFlow();
  const signUp = useSignUpWithCode();
  const [values, setValues] = useState<SignUpValues>({ discom: null, mobile: '', name: '', consent: false });
  const { discom, mobile, name } = values;
  if (!flow.sent || !discom) return <SignUpDetails values={values} onChange={setValues} flow={flow} />;
  return (
    <Stack sx={{ gap: 2 }}>
      <Found count={flow.sent.connections} discom={discom} />
      <CodeStep key={flow.round} mobile={mobile} sent={flow.sent} verb="Create account" pending={signUp.isPending}
        resending={flow.start.isPending} error={codeProblem(signUp.error ?? flow.start.error)}
        onVerify={(code) => signUp.mutate({ mobile, code, name: name.trim(), discom, consent: true })}
        onResend={flow.resend} onBack={() => { signUp.reset(); flow.back(); }} />
    </Stack>
  );
}

export function RegisterPage() {
  const phone = usePhone();
  const lead = phone ? 'On a phone, Bill Mitra is used in WhatsApp.'
    : 'Use the mobile number registered with your DISCOM. We check it with them and send you a code.';
  return (
    <AuthFrame title="Create your account" lead={lead}>
      {phone ? <WhatsAppOnly /> : <SignUp />}
      <Divider sx={{ my: 3 }} />
      <Typography variant="body2" sx={{ textAlign: 'center' }}>
        Already have an account?{' '}
        <MuiLink component={Link} to={phone ? '/login?as=staff' : '/login'} sx={{ fontWeight: 600 }}>
          {phone ? 'Staff sign in' : 'Sign in'}
        </MuiLink>
      </Typography>
    </AuthFrame>
  );
}
