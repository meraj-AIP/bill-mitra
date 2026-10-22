import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { isConsumer, type Account } from '@/features/auth';
import type { UnitRef } from '@/shared/api/types';

import { useUpdateAccount, type AccountChanges } from '../api/adminApi';
import { StaffFields } from './StaffFields';
import { ActionError } from '@/shared/feedback';

interface EditAccountDialogProps {
  account: Account;
  /** Nobody changes their own role or units; the server refuses it too. */
  isSelf: boolean;
  onClose: () => void;
}

/** Mount with a key per account so the form starts from that account's values. */
export function EditAccountDialog({ account, isSelf, onClose }: EditAccountDialogProps) {
  const update = useUpdateAccount();
  const staff = !isConsumer(account);
  const [name, setName] = useState(account.name);
  const [role, setRole] = useState(account.role);
  const [scopes, setScopes] = useState<UnitRef[]>(account.scopes);
  const [checked, setChecked] = useState(false);
  const editAccess = staff && !isSelf;
  const nameProblem = checked && !name.trim() ? 'Enter their name.' : null;
  const scopeProblem = checked && editAccess && scopes.length === 0 ? 'Add at least one unit.' : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (!name.trim() || (editAccess && scopes.length === 0)) return;
    const changes: AccountChanges = editAccess
      ? { name: name.trim(), role, scopes: scopes.map((u) => u.unit_id) }
      : { name: name.trim() };
    update.mutate({ id: account.id, changes }, { onSuccess: onClose });
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle>Edit account</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 2, pt: 1 }}>
            <ActionError error={update.error} action="Saving the account" />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>Signs in as {account.login}</Typography>
            <TextField label="Full name" value={name} onChange={(e) => setName(e.target.value)} fullWidth autoFocus
              error={Boolean(nameProblem)} helperText={nameProblem ?? ' '} />
            {editAccess && <StaffFields role={role} scopes={scopes} onRole={setRole} onScopes={setScopes} scopeError={scopeProblem} />}
            {isSelf && <Alert severity="info">You cannot change your own role or units. Ask another administrator.</Alert>}
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
