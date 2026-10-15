import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import MicNoneOutlinedIcon from '@mui/icons-material/MicNoneOutlined';
import PhotoCameraOutlinedIcon from '@mui/icons-material/PhotoCameraOutlined';
import TextsmsOutlinedIcon from '@mui/icons-material/TextsmsOutlined';
import { Box, ButtonBase, Divider, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

/** Questions people really ask after sending a bill, in the two languages most of them use. */
const QUESTIONS: Array<{ text: string; lang: 'te' | 'en' }> = [
  { text: 'బిల్లు ఇంత ఎక్కువ ఎందుకు వచ్చింది?', lang: 'te' },
  { text: 'Why is my bill so high?', lang: 'en' },
  { text: 'వచ్చే నెల ఎంత రావచ్చు?', lang: 'te' },
  { text: 'What if I use 230 units?', lang: 'en' },
  { text: 'కరెంటు ఎలా ఆదా చేయాలి?', lang: 'te' },
  { text: 'When is the last date to pay?', lang: 'en' },
];

const CAN_SEND: Array<{ icon: ReactNode; title: string; hint: string }> = [
  { icon: <PhotoCameraOutlinedIcon />, title: 'Bill photo', hint: 'A clear picture of the printed bill' },
  { icon: <DescriptionOutlinedIcon />, title: 'PDF bill', hint: 'The e-bill from SMS or email' },
  { icon: <MicNoneOutlinedIcon />, title: 'Voice note', hint: 'Speak in any of the four languages' },
  { icon: <TextsmsOutlinedIcon />, title: 'Text', hint: 'Type a question about your bill' },
];

function Heading({ children }: { children: ReactNode }) {
  return <Typography variant="overline" component="h2" sx={{ color: 'text.secondary', display: 'block', mb: 1.25 }}>{children}</Typography>;
}

interface AsideRailProps {
  staff: boolean;
  busy: boolean;
  onText: (text: string) => void;
}

export function AsideRail({ staff, busy, onText }: AsideRailProps) {
  return (
    <Stack component="aside" aria-label="Ways to use Bill Mitra" sx={{ gap: 3.5, width: '100%', maxWidth: 300 }}>
      <Box>
        <Heading>Ask about your bill</Heading>
        <Stack sx={{ gap: 0.75, alignItems: 'flex-start' }}>
          {QUESTIONS.map((q) => (
            <ButtonBase key={q.text} lang={q.lang} onClick={() => onText(q.text)} disabled={busy}
              sx={{ px: 1.5, py: 0.875, borderRadius: '18px', border: 1, borderColor: 'divider', bgcolor: 'background.paper',
                typography: 'body2', color: 'text.primary', textAlign: 'left', transition: 'border-color 160ms, background-color 160ms, transform 120ms',
                '&:hover': { borderColor: 'primary.light', bgcolor: 'action.hover' }, '&:active': { transform: 'translateY(1px)' },
                '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main', outlineOffset: 2 }, '&.Mui-disabled': { opacity: 0.5 } }}>
              {q.text}
            </ButtonBase>
          ))}
        </Stack>
      </Box>
      <Box>
        <Heading>What you can send</Heading>
        <Stack sx={{ gap: 1.5 }}>
          {CAN_SEND.map((item) => (
            <Stack key={item.title} direction="row" sx={{ gap: 1.5, alignItems: 'flex-start' }}>
              <Box sx={{ display: 'grid', placeItems: 'center', width: 32, height: 32, borderRadius: 1, bgcolor: 'info.light', color: 'primary.main',
                flexShrink: 0, '& svg': { fontSize: 18 } }}>
                {item.icon}
              </Box>
              <Box>
                <Typography variant="subtitle2" component="p">{item.title}</Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{item.hint}</Typography>
              </Box>
            </Stack>
          ))}
        </Stack>
      </Box>
      <Divider />
      <Stack direction="row" sx={{ gap: 1, color: 'text.secondary' }}>
        <LockOutlinedIcon sx={{ fontSize: 16, mt: '2px' }} />
        <Typography variant="caption">
          {staff
            ? 'You are signed in as staff. This preview shows exactly what a consumer gets on WhatsApp.'
            : 'Your chat is saved to your account so you can pick it up later. Starting a new chat deletes it.'}
        </Typography>
      </Stack>
    </Stack>
  );
}
