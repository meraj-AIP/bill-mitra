import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import { Button, Stack, Typography } from '@mui/material';

import { useCodeChannels } from '../api/authApi';

const OPENER = 'Hi';

/** On a phone, consumers use Bill Mitra in WhatsApp. No sign up there: their number is who they are. */
export function WhatsAppOnly() {
  const number = useCodeChannels().data?.whatsapp_number;
  return (
    <Stack sx={{ gap: 2, alignItems: 'flex-start' }}>
      <Typography variant="body1">
        On your phone, Bill Mitra works in WhatsApp. Send a hi, then a photo of your bill. There is nothing to sign up for:
        we check your number with your DISCOM there.
      </Typography>
      <Button variant="contained" size="large" fullWidth startIcon={<ChatOutlinedIcon />} disabled={!number}
        href={number ? `https://wa.me/${number}?text=${encodeURIComponent(OPENER)}` : undefined} sx={{ py: 1.4 }}>
        Continue on WhatsApp
      </Button>
      {!number && (
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          The WhatsApp number is not set up on this server yet. Open this page on a computer to use the web version.
        </Typography>
      )}
    </Stack>
  );
}
