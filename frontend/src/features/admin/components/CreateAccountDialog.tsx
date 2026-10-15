import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { MIN_PASSWORD } from '@/features/auth';
import { isStatus } from '@/shared/api/http';

import { useCreateAccount, type NewAccount } from '../api/adminApi';
import { EMAIL_PATTERN, generatePassword } from '../model/labels';
import { InitialPasswordField } from './InitialPasswordField';
import { StaffFields } from './StaffFields';

const fresh = (): NewAccount => ({ role: 'officer', login: '', name: '', discom: null, password: generatePassword() });

function problemsOf(v: NewAccount) {
  return {
    login: EMAIL_PATTERN.test(v.login.trim()) ? null : 'Enter a work email address.',
    name: v.name.trim() ? null : 'Enter their name.',
    password: v.password.length >= MIN_PASSWORD ? null : `Use at least ${MIN_PASSWORD} characters.`,
  };
}

export function CreateAccountDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateAccount();
  const [values, setValues] = useState<NewAccount>(fresh);
  const [checked, setChecked] = useState(false);
  const problems = problemsOf(values);
  const show = (key: keyof typeof problems) => (checked ? problems[key] : null);

  const close = () => {
    setValues(fresh());
    setChecked(false);
    create.reset();
    onClose();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (Object.values(problems).some(Boolean)) return;
    const body = { ...values, login: values.login.trim(), name: values.name.trim(), discom: values.role === 'admin' ? null : values.discom };
    create.mutate(body, { onSuccess: close });
  };

  const patch = (changes: Partial<NewAccount>) => setValues((v) => ({ ...v, ...changes }));
  const error = isStatus(create.error, 409) ? 'An account with this email already exists.' : (create.error?.message ?? null);

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>Create a staff account</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2, pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <StaffFields role={values.role} discom={values.discom} onRole={(role) => patch({ role })} onDiscom={(discom) => patch({ discom })} />
            <TextField label="Work email" type="email" autoComplete="off" value={values.login} fullWidth
              onChange={(e) => patch({ login: e.target.value })} error={Boolean(show('login'))} helperText={show('login') ?? 'They sign in with this.'} />
            <TextField label="Full name" autoComplete="off" value={values.name} fullWidth
              onChange={(e) => patch({ name: e.target.value })} error={Boolean(show('name'))} helperText={show('name') ?? ' '} />
            <InitialPasswordField label="Initial password" value={values.password} onChange={(password) => patch({ password })} error={show('password')} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={close}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={create.isPending}
            startIcon={create.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            Create account
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
