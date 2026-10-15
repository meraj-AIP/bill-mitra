import AttachFileIcon from '@mui/icons-material/AttachFile';
import { Box, Chip, Stack, Typography } from '@mui/material';
import type { Theme } from '@mui/material/styles';

import type { Language } from '../api/types';
import { isRtl, UI } from '../model/strings';
import { BrandAvatar } from './ChatHeader';
import { WaText } from './WaText';

interface WelcomeCardProps {
  language: Language;
  busy: boolean;
  onAttach: () => void;
  onText: (text: string) => void;
}

const chipSx = (theme: Theme) => ({
  height: 'auto', py: 0.75, px: 0.5, borderRadius: '18px', fontWeight: 500, fontSize: '0.8125rem',
  borderColor: 'divider', color: theme.palette.chat.quickReply, bgcolor: 'background.paper',
  '& .MuiChip-label': { whiteSpace: 'normal' },
  '& .MuiChip-icon': { color: theme.palette.chat.quickReply },
});

/**
 * First screen of an empty chat. Page chrome rather than a message, so it never has to fit
 * WhatsApp's types; it plays the part of the business profile card WhatsApp shows at the top of a new chat.
 */
export function WelcomeCard({ language, busy, onAttach, onText }: WelcomeCardProps) {
  const ui = UI[language];
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', px: 2.5, pt: 2 }}>
      <Stack lang={language}
        sx={(theme) => ({ alignItems: 'center', textAlign: 'center', gap: 1.25, width: '100%', maxWidth: 320, p: 2.5,
          bgcolor: theme.palette.chat.incoming, borderRadius: '14px', boxShadow: theme.palette.chat.shadow })}>
        <BrandAvatar size={52} />
        <Box>
          <Typography variant="subtitle1" component="p">Bill Mitra</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Electricity bill help, Government of Telangana</Typography>
        </Box>
        <Typography component="div" variant="body2" sx={{ color: 'text.primary', fontSize: '0.875rem' }}>
          <WaText text={ui.welcome} rtl={isRtl(language)} />
        </Typography>
        <Stack sx={{ gap: 0.75, width: '100%', mt: 0.5 }} dir={isRtl(language) ? 'rtl' : undefined}>
          <Chip icon={<AttachFileIcon sx={{ transform: 'rotate(45deg)', fontSize: 18 }} />} label={ui.attach} onClick={onAttach}
            disabled={busy} variant="outlined" sx={chipSx} />
          {ui.suggestions.map((text) => (
            <Chip key={text} label={text} onClick={() => onText(text)} disabled={busy} variant="outlined" sx={chipSx} />
          ))}
        </Stack>
      </Stack>
    </Box>
  );
}
