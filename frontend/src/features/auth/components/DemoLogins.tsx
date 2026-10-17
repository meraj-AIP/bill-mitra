import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { IconButton, List, ListItemButton, ListItemText, Popover, Tooltip, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { useDemoLogins } from '../api/authApi';

/** An info button on the title row; its popover lists one login per role. Picking one fills the login only, the
 * password is always typed. Shows nothing when the server has no demo logins. */
export function DemoLogins({ onPick }: { onPick: (login: string) => void }) {
  const { data } = useDemoLogins();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const listId = useId();
  if (!data?.length) return null;
  const open = Boolean(anchor);
  return (
    <>
      <Tooltip title="Sample logins">
        <IconButton size="small" onClick={(e) => setAnchor(open ? null : e.currentTarget)} aria-expanded={open}
          aria-controls={open ? listId : undefined} aria-haspopup="dialog" aria-label="Show sample logins"
          sx={{ color: open ? 'primary.main' : 'text.secondary' }}>
          <InfoOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Popover id={listId} open={open} anchorEl={anchor} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { variant: 'outlined', sx: { mt: 0.5, width: 300, maxWidth: 'calc(100vw - 32px)' } } }}>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', px: 2, pt: 1.5, pb: 0.5 }}>
          Pick a role to fill its login, then type the password.
        </Typography>
        <List dense disablePadding sx={{ pb: 0.5 }}>
          {data.map((d) => (
            <ListItemButton key={d.role} onClick={() => { setAnchor(null); onPick(d.login); }}>
              <ListItemText primary={d.role_name} secondary={d.login}
                slotProps={{ secondary: { sx: { fontFamily: 'monospace' } } }} />
            </ListItemButton>
          ))}
        </List>
      </Popover>
    </>
  );
}
