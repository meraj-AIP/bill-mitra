import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';

import type { Account } from '@/features/auth';
import type { Discom } from '@/shared/api/types';

import { useUpdateAccount, type AccountChanges, type StaffRole } from '../api/adminApi';
import { StaffFields } from './StaffFields';

interface EditAccountDialogProps {
  account: Account;
  /** Admins cannot demote themselves; the server refuses it too. */
  isSelf: boolean;
  onClose: () => void;
}

/** Mount with a key per account so the form starts from that account's values. */
export function EditAccountDialog({ account, isSelf, onClose }: EditAccountDialogProps) {
  const update = useUpdateAccount();
  const staff = account.role !== 'consumer';
  const [name, setName] = useState(account.name);
  const [role, setRole] = useState<StaffRole>(account.role === 'admin' ? 'admin' : 'officer');
  const [discom, setDiscom] = useState<Discom | null>(account.discom);
  const [checked, setChecked] = useState(false);
  const nameProblem = checked && !name.trim() ? 'Enter their name.' : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (!name.trim()) return;
    // Consumers have no staff role; the server only takes admin or officer.
    const changes: AccountChanges = staff && !isSelf
      ? { name: name.trim(), role, discom: role === 'admin' ? null : discom }
      : { name: name.trim() };
    update.mutate({ id: account.id, changes }, { onSuccess: onClose });
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>Edit account</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2, pt: 1 }}>
            {update.error && <Alert severity="error">{update.error.message}</Alert>}
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>Signs in as {account.login}</Typography>
            <TextField label="Full name" value={name} onChange={(e) => setName(e.target.value)} fullWidth autoFocus
              error={Boolean(nameProblem)} helperText={nameProblem ?? ' '} />
            {staff && !isSelf && <StaffFields role={role} discom={discom} onRole={setRole} onDiscom={setDiscom} />}
            {isSelf && <Alert severity="info">You cannot change your own role. Ask another administrator.</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={update.isPending}
            startIcon={update.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
            Save changes
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
