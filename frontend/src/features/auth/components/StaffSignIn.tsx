import { Button, CircularProgress, Stack, TextField } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { describeError } from '@/shared/feedback';

import { useLogin } from '../api/authApi';
import { FormError } from './AuthFrame';
import { PasswordField } from './PasswordField';

/** DISCOM and department staff: work email and password. Where to go next is decided by PublicOnly. A picked sample
 * login remounts the form (keyed by the caller), so it starts filled with the password field focused. */
export function StaffSignIn({ login: picked }: { login: string }) {
  const login = useLogin();
  const [values, setValues] = useState({ login: picked, password: '' });
  const [missing, setMissing] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!values.login.trim() || !values.password) {
      setMissing(true);
      return;
    }
    login.mutate({ login: values.login.trim(), password: values.password });
  };
  const failed = login.error ? describeError(login.error, 'Signing in').message : null;
  const set = (key: 'login' | 'password') => (event: { target: { value: string } }) => {
    setMissing(false);
    setValues((v) => ({ ...v, [key]: event.target.value }));
  };

  return (
    <Stack component="form" noValidate onSubmit={submit} sx={{ gap: 2.25 }} aria-busy={login.isPending}>
      <FormError message={missing ? 'Enter your work email and your password.' : failed} />
      <TextField label="Work email" name="username" type="email" autoComplete="username" required fullWidth autoFocus={!picked}
        value={values.login} onChange={set('login')} error={missing && !values.login.trim()}
        slotProps={{ htmlInput: { autoCapitalize: 'none', spellCheck: false, autoCorrect: 'off' } }} />
      <PasswordField label="Password" name="password" autoComplete="current-password" required fullWidth
        value={values.password} onChange={set('password')} error={missing && !values.password} autoFocus={Boolean(picked)} />
      <Button type="submit" variant="contained" size="large" fullWidth disabled={login.isPending}
        startIcon={login.isPending ? <CircularProgress size={18} color="inherit" aria-hidden /> : null} sx={{ mt: 0.5, py: 1.4 }}>
        {login.isPending ? 'Signing in' : 'Sign in'}
      </Button>
    </Stack>
  );
}
