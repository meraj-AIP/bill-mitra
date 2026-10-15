import DeleteForeverOutlinedIcon from '@mui/icons-material/DeleteForeverOutlined';
import KeyOutlinedIcon from '@mui/icons-material/KeyOutlined';
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';
import { Avatar, Box, ButtonBase, Divider, ListItemIcon, Menu, MenuItem, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { useLogout } from '../api/authApi';
import { useAuth } from '../hooks/useAuth';
import { ROLE_LABEL } from '../model/roles';
import { ChangePasswordDialog } from './ChangePasswordDialog';
import { DeleteAccountDialog } from './DeleteAccountDialog';

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? (parts.at(-1)?.[0] ?? '') : '')).toUpperCase() || '?';
}

export function AccountMenu() {
  const { account } = useAuth();
  const logout = useLogout();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [dialog, setDialog] = useState<'password' | 'delete' | null>(null);
  const menuId = useId();
  if (!account) return null;

  const scope = account.role === 'officer' ? (account.discom ?? 'All DISCOMs') : null;
  return (
    <>
      <ButtonBase onClick={(e) => setAnchor(e.currentTarget)} aria-haspopup="menu" aria-controls={anchor ? menuId : undefined}
        aria-expanded={Boolean(anchor)} aria-label={`Account menu for ${account.name}`}
        sx={{ gap: 1.25, borderRadius: 1.5, py: 0.5, pl: 0.5, pr: { xs: 0.5, sm: 1.25 }, transition: 'background-color 200ms',
          '&:hover': { bgcolor: 'action.hover' }, '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main', outlineOffset: 2 } }}>
        <Avatar variant="rounded" sx={{ width: 34, height: 34, fontSize: '0.8125rem', fontWeight: 600, bgcolor: 'info.light', color: 'primary.main' }}>
          {initials(account.name)}
        </Avatar>
        <Box sx={{ textAlign: 'left', display: { xs: 'none', sm: 'block' }, maxWidth: 180 }}>
          <Typography variant="subtitle2" noWrap component="p">{account.name}</Typography>
          <Typography variant="caption" noWrap component="p" sx={{ color: 'text.secondary' }}>{ROLE_LABEL[account.role]}</Typography>
        </Box>
      </ButtonBase>
      <Menu id={menuId} anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { variant: 'outlined', sx: { minWidth: 240, mt: 0.5 } } }}>
        <Box sx={{ px: 2, py: 1.25 }}>
          <Typography variant="subtitle2">{account.name}</Typography>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
            {ROLE_LABEL[account.role]}{scope ? `, ${scope}` : ''}
          </Typography>
          <Typography variant="caption" component="p" noWrap sx={{ color: 'text.secondary' }}>{account.login}</Typography>
        </Box>
        <Divider />
        <MenuItem onClick={() => { setAnchor(null); setDialog('password'); }}>
          <ListItemIcon><KeyOutlinedIcon fontSize="small" /></ListItemIcon>
          Change password
        </MenuItem>
        <MenuItem onClick={() => { setAnchor(null); logout.mutate(); }} disabled={logout.isPending}>
          <ListItemIcon><LogoutOutlinedIcon fontSize="small" /></ListItemIcon>
          Sign out
        </MenuItem>
        {account.role === 'consumer' && <Divider />}
        {account.role === 'consumer' && (
          <MenuItem onClick={() => { setAnchor(null); setDialog('delete'); }} sx={{ color: 'error.main' }}>
            <ListItemIcon sx={{ color: 'inherit' }}><DeleteForeverOutlinedIcon fontSize="small" /></ListItemIcon>
            Delete my account
          </MenuItem>
        )}
      </Menu>
      <ChangePasswordDialog open={dialog === 'password'} onClose={() => setDialog(null)} />
      {account.role === 'consumer' && <DeleteAccountDialog open={dialog === 'delete'} onClose={() => setDialog(null)} />}
    </>
  );
}
