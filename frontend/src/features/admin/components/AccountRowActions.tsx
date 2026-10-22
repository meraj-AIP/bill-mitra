import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import { CircularProgress, IconButton, Menu, MenuItem } from '@mui/material';
import { useState } from 'react';

import type { Account } from '@/features/auth';
import { reportError, useConfirm } from '@/shared/feedback';

import { useUpdateAccount } from '../api/adminApi';

interface AccountRowActionsProps {
  account: Account;
  isSelf: boolean;
  onEdit: () => void;
  onReset: () => void;
}

/** One menu per row. Deactivating and activating both ask first, since either changes who can sign in. */
export function AccountRowActions({ account, isSelf, onEdit, onReset }: AccountRowActionsProps) {
  const update = useUpdateAccount();
  const confirm = useConfirm();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const pick = (action: () => void) => () => { setAnchor(null); action(); };
  const setActive = async (active: boolean) => {
    const ok = await confirm(active
      ? { title: `Activate ${account.name}?`, confirmLabel: 'Activate', body: 'They can sign in again with their current password.' }
      : { title: `Deactivate ${account.name}?`, confirmLabel: 'Deactivate', tone: 'danger',
        body: 'They are signed out everywhere and cannot sign in until an administrator activates the account again.',
        points: ['Complaints and cases they hold stay with them; hand them over first if they are leaving.'] });
    if (ok) update.mutate({ id: account.id, changes: { active } }, { onError: (e) => reportError(e, active ? 'Activating' : 'Deactivating') });
  };

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
          <MenuItem onClick={pick(() => void setActive(false))} disabled={isSelf} sx={{ color: 'error.main' }}>
            {isSelf ? 'You cannot deactivate yourself' : 'Deactivate'}
          </MenuItem>
        ) : (
          <MenuItem onClick={pick(() => void setActive(true))}>Activate</MenuItem>
        )}
      </Menu>
    </>
  );
}
