import { Alert, Button, CircularProgress, Divider, Link as MuiLink, Stack, TextField, Typography } from '@mui/material';
import { useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useLogin } from '../api/authApi';
import { AuthFrame, FormError } from '../components/AuthFrame';
import { DemoLogins } from '../components/DemoLogins';
import { PasswordField } from '../components/PasswordField';
import { normaliseLogin } from '../model/roles';

export function LoginPage() {
  const login = useLogin();
  const [params] = useSearchParams();
  const deleted = params.get('deleted') === '1';
  const [values, setValues] = useState({ login: '', password: '' });
  const [missing, setMissing] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const pick = (sample: string) => {
    setMissing(false);
    setValues({ login: sample, password: '' });
    passwordRef.current?.focus();
  };

  // Where to go next is decided by PublicOnly once the account is cached.
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!values.login.trim() || !values.password) {
      setMissing(true);
      return;
    }
    login.mutate({ login: normaliseLogin(values.login), password: values.password });
  };

  const error = missing ? 'Enter your email or mobile number and your password.' : (login.error?.message ?? null);
  const set = (key: 'login' | 'password') => (event: { target: { value: string } }) => {
    setMissing(false);
    setValues((v) => ({ ...v, [key]: event.target.value }));
  };

  return (
    <AuthFrame title="Sign in" lead="Consumers use their mobile number. Department staff use their work email."
      titleAction={<DemoLogins onPick={pick} />}
      footer={
        <Stack sx={{ gap: 1.5, alignItems: 'center', textAlign: 'center' }}>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', maxWidth: '44ch' }}>
            DISCOM and department staff: your account is created by the Bill Mitra administrator. Ask them if you cannot sign in.
          </Typography>
          <MuiLink component={Link} to="/privacy" variant="caption" sx={{ fontWeight: 600 }}>Privacy notice</MuiLink>
        </Stack>
      }>
      <Stack component="form" noValidate onSubmit={submit} sx={{ gap: 2.25 }} aria-busy={login.isPending}>
        {deleted && !error && (
          <Alert severity="success" variant="outlined" sx={{ bgcolor: 'success.light' }}>
            Your account and its data have been deleted.
          </Alert>
        )}
        <FormError message={error} />
        <TextField label="Email or mobile number" name="username" autoComplete="username" autoFocus required fullWidth
          value={values.login} onChange={set('login')} error={missing && !values.login.trim()}
          slotProps={{ htmlInput: { autoCapitalize: 'none', spellCheck: false, autoCorrect: 'off' } }} />
        <PasswordField label="Password" name="password" autoComplete="current-password" required fullWidth
          value={values.password} onChange={set('password')} error={missing && !values.password} inputRef={passwordRef} />
        <Button type="submit" variant="contained" size="large" fullWidth disabled={login.isPending}
          startIcon={login.isPending ? <CircularProgress size={18} color="inherit" aria-hidden /> : null}
          sx={{ mt: 0.5, py: 1.4 }}>
          {login.isPending ? 'Signing in' : 'Sign in'}
        </Button>
      </Stack>
      <Divider sx={{ my: 3 }} />
      <Typography variant="body2" sx={{ textAlign: 'center' }}>
        New here?{' '}
        <MuiLink component={Link} to="/register" sx={{ fontWeight: 600 }}>Create an account</MuiLink>
      </Typography>
    </AuthFrame>
  );
}
