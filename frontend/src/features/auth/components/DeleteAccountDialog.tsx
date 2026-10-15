import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { useDeleteMe } from '../api/authApi';

const WORD = 'DELETE';

/** Erasing an account cannot be undone, so the person types a word rather than clicking twice by habit. */
export function DeleteAccountDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const remove = useDeleteMe();
  const [typed, setTyped] = useState('');
  const ready = typed.trim().toUpperCase() === WORD;

  const close = () => {
    setTyped('');
    remove.reset();
    onClose();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready) return;
    remove.mutate();
  };

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="xs">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>Delete my account</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2 }}>
            <Typography variant="body2">
              This erases your bills, your chat with the assistant and your bill photos, and signs you out. It cannot be undone.
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Complaints you raised stay with the DISCOM as a department record, without your name or mobile number.
            </Typography>
            {remove.error && <Alert severity="error">{remove.error.message}</Alert>}
            <TextField label={`Type ${WORD} to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} fullWidth autoFocus
              autoComplete="off" slotProps={{ htmlInput: { spellCheck: false, autoCapitalize: 'characters' } }} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={close}>Keep my account</Button>
          <Button type="submit" variant="contained" color="error" disabled={!ready || remove.isPending}
            startIcon={remove.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            Delete account
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
