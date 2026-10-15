import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import ReplyIcon from '@mui/icons-material/Reply';
import { Button, ListItemText, Menu, MenuItem, Stack } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import { useState } from 'react';

import type { ReplyButton } from '../api/types';

const optionSx = (theme: Theme) => ({
  bgcolor: theme.palette.chat.incoming,
  color: theme.palette.chat.quickReply,
  boxShadow: theme.palette.chat.shadow,
  borderRadius: '10px',
  py: 0.875,
  fontWeight: 500,
  fontSize: '0.875rem',
  transition: 'background-color 160ms, transform 120ms',
  '&:hover': { bgcolor: 'grey.50' },
  '&:active': { transform: 'scale(0.985)' },
  '&.Mui-disabled': { bgcolor: theme.palette.chat.incoming, color: 'text.disabled' },
  '& .MuiButton-startIcon': { mr: 0.75 },
});

interface ReplyButtonsProps {
  buttons: ReplyButton[];
  rtl: boolean;
  disabled: boolean;
  onReply: (button: ReplyButton) => void;
}

/** WhatsApp quick replies: up to three, attached under the message they belong to. */
export function ReplyButtons({ buttons, rtl, disabled, onReply }: ReplyButtonsProps) {
  return (
    <Stack sx={{ gap: 0.375 }}>
      {buttons.map((button) => (
        <Button key={button.id} onClick={() => onReply(button)} disabled={disabled} dir={rtl ? 'rtl' : undefined}
          startIcon={<ReplyIcon sx={{ fontSize: 18 }} />} sx={optionSx}>
          {button.title}
        </Button>
      ))}
    </Stack>
  );
}

interface ListReplyProps {
  label: string;
  rows: Array<{ id: string; title: string; description?: string | null }>;
  rtl: boolean;
  disabled: boolean;
  onReply: (button: ReplyButton) => void;
}

/** WhatsApp list message: one button that opens up to ten choices. */
export function ListReply({ label, rows, rtl, disabled, onReply }: ListReplyProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  return (
    <>
      <Button startIcon={<FormatListBulletedIcon sx={{ fontSize: 18 }} />} onClick={(e) => setAnchor(e.currentTarget)}
        disabled={disabled} dir={rtl ? 'rtl' : undefined} aria-haspopup="menu" sx={optionSx}>
        {label}
      </Button>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}
        slotProps={{ paper: { sx: { minWidth: 260, maxWidth: 340, borderRadius: 2 } } }}>
        {rows.map((row) => (
          <MenuItem key={row.id} dir={rtl ? 'rtl' : undefined}
            onClick={() => {
              setAnchor(null);
              onReply({ id: row.id, title: row.title });
            }}>
            <ListItemText primary={row.title} secondary={row.description ?? undefined} />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
