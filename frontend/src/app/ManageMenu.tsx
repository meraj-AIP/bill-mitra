import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Button, ListItemText, Menu, MenuItem } from '@mui/material';
import { useId, useState } from 'react';
import { Link } from 'react-router-dom';

import type { NavItem } from './nav';

interface ManageMenuProps {
  items: NavItem[];
  /** The item whose page is open, so the menu reads as the current section. */
  active: string | false;
}

/** Admin pages in one menu, so the tabs only hold the work done every day. */
export function ManageMenu({ items, active }: ManageMenuProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const menuId = useId();
  const on = active !== false;
  return (
    <>
      <Button onClick={(e) => setAnchor(e.currentTarget)} endIcon={<ExpandMoreRoundedIcon />}
        aria-haspopup="menu" aria-controls={anchor ? menuId : undefined} aria-expanded={Boolean(anchor)}
        sx={{ minHeight: 44, borderRadius: 0, px: { xs: 1.25, sm: 2 }, fontSize: '0.875rem', whiteSpace: 'nowrap',
          color: on ? 'primary.main' : 'text.secondary', borderBottom: 2, borderColor: on ? 'primary.main' : 'transparent',
          '&:hover': { color: 'text.primary', bgcolor: 'transparent' } }}>
        Admin
      </Button>
      <Menu id={menuId} anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }} transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { variant: 'outlined', sx: { minWidth: 280, mt: 0.5 } } }}>
        {items.map((item) => (
          <MenuItem key={item.to} component={Link} to={item.to} selected={active === item.to} onClick={() => setAnchor(null)}
            sx={{ py: 1 }}>
            <ListItemText primary={item.label} secondary={item.hint}
              slotProps={{ primary: { variant: 'subtitle2' }, secondary: { variant: 'caption' } }} />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
