import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import {
  Alert, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, IconButton, Menu, MenuItem,
} from '@mui/material';
import { useState } from 'react';

import type { Account } from '@/features/auth';

import { useUpdateAccount } from '../api/adminApi';

interface AccountRowActionsProps {
  account: Account;
  isSelf: boolean;
  onEdit: () => void;
  onReset: () => void;
}

/** One menu per row. Deactivating asks again, so a slip of the mouse does not lock someone out. */
export function AccountRowActions({ account, isSelf, onEdit, onReset }: AccountRowActionsProps) {
  const update = useUpdateAccount();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [confirming, setConfirming] = useState(false);
  const setActive = (active: boolean) =>
    update.mutate({ id: account.id, changes: { active } }, { onSuccess: () => setConfirming(false) });
  const pick = (action: () => void) => () => { setAnchor(null); action(); };
  const closeConfirm = () => { setConfirming(false); update.reset(); };

  return (
    <>
      <IconButton size="small" aria-label={`Actions for ${account.name}`} aria-haspopup="menu"
        onClick={(e) => setAnchor(e.currentTarget)} disabled={update.isPending}>
        {update.isPending ? <CircularProgress size={18} aria-hidden /> : <MoreHorizIcon fontSize="small" />}
      </IconButton>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
        <MenuItem onClick={pick(onEdit)}>Edit</MenuItem>
        <MenuItem onClick={pick(onReset)}>Reset password</MenuItem>
        {account.active ? (
          <MenuItem onClick={pick(() => setConfirming(true))} disabled={isSelf} sx={{ color: 'error.main' }}>
            {isSelf ? 'You cannot deactivate yourself' : 'Deactivate'}
          </MenuItem>
        ) : (
          <MenuItem onClick={pick(() => setActive(true))}>Activate</MenuItem>
        )}
      </Menu>
      {update.error && !confirming && <Alert severity="error" sx={{ mt: 1, textAlign: 'left' }}>{update.error.message}</Alert>}
      <Dialog open={confirming} onClose={closeConfirm} maxWidth="xs" fullWidth>
        <DialogTitle>Deactivate {account.name}?</DialogTitle>
        <DialogContent>
          <DialogContentText>They are signed out everywhere and cannot sign in until an administrator activates the account again.</DialogContentText>
          {update.error && <Alert severity="error" sx={{ mt: 2 }}>{update.error.message}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeConfirm} autoFocus>Cancel</Button>
          <Button variant="contained" color="error" onClick={() => setActive(false)} disabled={update.isPending}
            startIcon={update.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            Deactivate
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
