import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import { Alert, Button } from '@mui/material';

import { useHealth } from '@/shared/api/health';

// No bill details in the link: it is a URL, and the consumer sends the photo in the chat anyway.
const OPENER = 'I want to raise a complaint about my electricity bill.';

/** Complaints are raised and answered on WhatsApp, so a mismatch points there. */
export function ComplainOnWhatsApp() {
  const { data } = useHealth();
  const number = data?.whatsapp_number;
  return (
    <Alert severity="warning" icon={<ChatOutlinedIcon />}
      action={number ? (
        <Button color="inherit" size="small" href={`https://wa.me/${number}?text=${encodeURIComponent(OPENER)}`}
          target="_blank" rel="noopener noreferrer">
          Open WhatsApp
        </Button>
      ) : undefined}>
      Want this corrected? Send this bill to Bill Mitra on WhatsApp and tap Raise complaint. We reply there.
    </Alert>
  );
}
