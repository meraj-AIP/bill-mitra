import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import SmsOutlinedIcon from '@mui/icons-material/SmsOutlined';
import { Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';

import type { CodeChannel } from '../api/authApi';
import { CHANNEL_LABEL } from '../model/codes';

const ICON = { sms: <SmsOutlinedIcon fontSize="small" />, whatsapp: <ChatOutlinedIcon fontSize="small" /> };

/** How the code reaches the consumer. Only the ways the server can send right now are offered. */
export function ChannelPicker({ channels, value, onChange }: { channels: CodeChannel[]; value: CodeChannel; onChange: (c: CodeChannel) => void }) {
  return (
    <Stack sx={{ gap: 0.75 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }} id="code-channel">Send the code by</Typography>
      <ToggleButtonGroup exclusive fullWidth value={value} onChange={(_e, v: CodeChannel | null) => v && onChange(v)}
        aria-labelledby="code-channel" sx={{ '& .MuiToggleButton-root': { gap: 1, textTransform: 'none', fontWeight: 600 } }}>
        {channels.map((c) => <ToggleButton key={c} value={c} color="primary">{ICON[c]}{CHANNEL_LABEL[c]}</ToggleButton>)}
      </ToggleButtonGroup>
    </Stack>
  );
}
