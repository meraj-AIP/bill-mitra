import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { Box, Collapse, IconButton, List, ListItemButton, ListItemText, Tooltip, Typography } from '@mui/material';
import { useId, useState } from 'react';

import { useDemoLogins } from '../api/authApi';

/** Hidden behind an info button until asked for. Picking one fills the login only; the password is always typed. */
export function DemoLogins({ onPick }: { onPick: (login: string) => void }) {
  const { data } = useDemoLogins();
  const [open, setOpen] = useState(false);
  const listId = useId();
  if (!data?.length) return null;
  return (
    <Box sx={{ mt: 2.5 }}>
      <Tooltip title={open ? 'Hide sample logins' : 'Sample logins'}>
        <IconButton size="small" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls={listId}
          aria-label={open ? 'Hide sample logins' : 'Show sample logins'}
          sx={{ color: open ? 'primary.main' : 'text.secondary' }}>
          <InfoOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Collapse in={open}>
        <Box id={listId} sx={{ mt: 1, border: 1, borderColor: 'divider', borderRadius: 1.5 }}>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', px: 2, pt: 1.25 }}>
            For demos. Pick a role to fill its login, then type the demo password.
          </Typography>
          <List dense disablePadding>
            {data.map((d) => (
              <ListItemButton key={d.role} onClick={() => onPick(d.login)}>
                <ListItemText primary={d.role_name} secondary={d.login}
                  slotProps={{ secondary: { sx: { fontFamily: 'monospace' } } }} />
              </ListItemButton>
            ))}
          </List>
        </Box>
      </Collapse>
    </Box>
  );
}
