import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { MIN_PASSWORD, type Account } from '@/features/auth';

import { useResetPassword } from '../api/adminApi';
import { generatePassword } from '../model/labels';
import { InitialPasswordField } from './InitialPasswordField';

export function ResetPasswordDialog({ account, onClose }: { account: Account; onClose: () => void }) {
  const reset = useResetPassword();
  const [password, setPassword] = useState(generatePassword);
  const [checked, setChecked] = useState(false);
  const problem = checked && password.length < MIN_PASSWORD ? `Use at least ${MIN_PASSWORD} characters.` : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (password.length < MIN_PASSWORD) return;
    reset.mutate({ id: account.id, password });
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>Reset password</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2, pt: 1 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              For {account.name} ({account.login}). They are signed out everywhere and use this password next time.
            </Typography>
            {reset.error && <Alert severity="error">{reset.error.message}</Alert>}
            {reset.isSuccess && <Alert severity="success">Password reset. Copy it now if you have not; it is not shown again.</Alert>}
            <InitialPasswordField label="New password" value={password} onChange={setPassword} error={problem} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose}>{reset.isSuccess ? 'Done' : 'Cancel'}</Button>
          {!reset.isSuccess && (
            <Button type="submit" variant="contained" disabled={reset.isPending}
              startIcon={reset.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
              Reset password
            </Button>
          )}
        </DialogActions>
      </Box>
    </Dialog>
  );
}
