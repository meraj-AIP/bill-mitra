import { Button, Checkbox, CircularProgress, Divider, FormControlLabel, FormHelperText, InputAdornment, Link as MuiLink, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { isStatus } from '@/shared/api/http';

import { useRegister } from '../api/authApi';
import { AuthFrame, FormError } from '../components/AuthFrame';
import { PasswordField } from '../components/PasswordField';
import { MIN_PASSWORD, MOBILE_PATTERN, passwordProblem } from '../model/roles';

type Field = 'name' | 'mobile' | 'password' | 'confirm';
type Values = Record<Field, string> & { consent: boolean };

function validate(v: Values): Partial<Record<Field | 'consent', string>> {
  const problems: Partial<Record<Field | 'consent', string>> = {};
  if (!v.name.trim()) problems.name = 'Enter your name.';
  if (!MOBILE_PATTERN.test(v.mobile)) problems.mobile = 'Enter a 10 digit mobile number starting with 6, 7, 8 or 9.';
  const weak = passwordProblem(v.password);
  if (weak) problems.password = weak;
  if (v.confirm !== v.password) problems.confirm = 'The two passwords do not match.';
  if (!v.consent) problems.consent = 'Please read and agree to the privacy notice to continue.';
  return problems;
}

export function RegisterPage() {
  const register = useRegister();
  const [values, setValues] = useState<Values>({ name: '', mobile: '', password: '', confirm: '', consent: false });
  const [checked, setChecked] = useState(false);
  const problems = checked ? validate(values) : {};

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (Object.keys(validate(values)).length > 0) return;
    register.mutate({ name: values.name.trim(), mobile: values.mobile, password: values.password, consent: true });
  };

  const set = (key: Field) => (event: { target: { value: string } }) => {
    const value = key === 'mobile' ? event.target.value.replace(/\D/g, '').slice(0, 10) : event.target.value;
    setValues((v) => ({ ...v, [key]: value }));
  };
  const taken = isStatus(register.error, 409);
  const fieldProps = (key: Field, helper?: string) => ({
    value: values[key], onChange: set(key), error: Boolean(problems[key]), helperText: problems[key] ?? helper ?? ' ', fullWidth: true, required: true,
  });

  return (
    <AuthFrame title="Create your account" lead="For electricity consumers in Telangana. You will sign in with your mobile number.">
      <Stack component="form" noValidate onSubmit={submit} sx={{ gap: 1 }} aria-busy={register.isPending}>
        <FormError message={taken ? 'This mobile number already has an account.' : (register.error?.message ?? null)}>
          {taken && <MuiLink component={Link} to="/login" sx={{ fontWeight: 600 }}>Sign in instead</MuiLink>}
        </FormError>
        <TextField label="Your name" name="name" autoComplete="name" autoFocus {...fieldProps('name')} />
        <TextField label="Mobile number" name="mobile" type="tel" autoComplete="tel-national" {...fieldProps('mobile')}
          slotProps={{
            htmlInput: { inputMode: 'numeric', maxLength: 10, pattern: '[6-9][0-9]{9}' },
            input: { startAdornment: <InputAdornment position="start">+91</InputAdornment> },
          }} />
        <PasswordField label="Password" name="new-password" autoComplete="new-password"
          {...fieldProps('password', `At least ${MIN_PASSWORD} characters.`)} />
        <PasswordField label="Confirm password" name="confirm-password" autoComplete="new-password" {...fieldProps('confirm')} />
        <FormControlLabel sx={{ alignItems: 'flex-start', mr: 0 }}
          control={<Checkbox checked={values.consent} sx={{ mt: -0.75 }} required
            onChange={(e) => setValues((v) => ({ ...v, consent: e.target.checked }))} />}
          label={
            <Typography variant="body2">
              I agree to the{' '}
              <MuiLink component={Link} to="/privacy" target="_blank" rel="noopener" sx={{ fontWeight: 600 }}>privacy notice</MuiLink>
              , which says what Bill Mitra keeps and for how long.
            </Typography>
          } />
        <FormHelperText error sx={{ mt: -0.5, mb: 0.5, minHeight: '1.25em' }}>{problems.consent ?? ' '}</FormHelperText>
        <Button type="submit" variant="contained" size="large" fullWidth disabled={register.isPending}
          startIcon={register.isPending ? <CircularProgress size={18} color="inherit" aria-hidden /> : null}
          sx={{ mt: 0.5, py: 1.4 }}>
          {register.isPending ? 'Creating your account' : 'Create account'}
        </Button>
      </Stack>
      <Divider sx={{ my: 3 }} />
      <Typography variant="body2" sx={{ textAlign: 'center' }}>
        Already have an account?{' '}
        <MuiLink component={Link} to="/login" sx={{ fontWeight: 600 }}>Sign in</MuiLink>
      </Typography>
    </AuthFrame>
  );
}
