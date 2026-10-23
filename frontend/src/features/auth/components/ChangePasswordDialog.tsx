import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { useChangePassword } from '../api/authApi';
import { MIN_PASSWORD, passwordProblem } from '../model/roles';
import { PasswordField } from './PasswordField';
import { ErrorNotice } from '@/shared/feedback';

const EMPTY = { current: '', next: '', confirm: '' };

export function ChangePasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const change = useChangePassword();
  const [values, setValues] = useState(EMPTY);
  const [checked, setChecked] = useState(false);

  const problems = {
    current: values.current ? null : 'Enter your current password.',
    next: passwordProblem(values.next),
    confirm: values.confirm === values.next ? null : 'The two passwords do not match.',
  };
  const show = (key: keyof typeof problems) => (checked ? problems[key] : null);

  const close = () => {
    setValues(EMPTY);
    setChecked(false);
    change.reset();
    onClose();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (Object.values(problems).some(Boolean)) return;
    change.mutate({ current_password: values.current, new_password: values.next });
  };

  const set = (key: keyof typeof EMPTY) => (event: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [key]: event.target.value }));

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="xs">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>Change password</DialogTitle>
        <DialogContent>
          {change.isSuccess ? (
            <Alert severity="success">Password changed. You stay signed in here; other devices are signed out.</Alert>
          ) : (
            <Stack sx={{ gap: 1, pt: 1 }}>
              <ErrorNotice error={change.error} action="The password change" sx={{ mb: 1 }} />
              <PasswordField label="Current password" autoComplete="current-password" autoFocus value={values.current}
                onChange={set('current')} error={Boolean(show('current'))} helperText={show('current') ?? ' '} fullWidth />
              <PasswordField label="New password" autoComplete="new-password" value={values.next} onChange={set('next')}
                error={Boolean(show('next'))} helperText={show('next') ?? `At least ${MIN_PASSWORD} characters.`} fullWidth />
              <PasswordField label="Confirm new password" autoComplete="new-password" value={values.confirm} onChange={set('confirm')}
                error={Boolean(show('confirm'))} helperText={show('confirm') ?? ' '} fullWidth />
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={close}>{change.isSuccess ? 'Done' : 'Cancel'}</Button>
          {!change.isSuccess && (
            <Button type="submit" variant="contained" disabled={change.isPending}
              startIcon={change.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
              Change password
            </Button>
          )}
        </DialogActions>
      </Box>
    </Dialog>
  );
}
