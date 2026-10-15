import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import VerifiedIcon from '@mui/icons-material/Verified';
import { Avatar, Box, Stack, Typography } from '@mui/material';

import type { Language } from '../api/types';
import { UI } from '../model/strings';

export function BrandAvatar({ size }: { size: number }) {
  return (
    <Avatar aria-hidden
      sx={(theme) => ({ width: size, height: size, bgcolor: theme.palette.chat.onHeader, color: 'primary.main',
        fontFamily: theme.typography.h2.fontFamily, fontWeight: 600, fontSize: size * 0.4, letterSpacing: '-0.02em',
        boxShadow: `inset 0 0 0 1.5px ${theme.palette.divider}` })}>
      BM
    </Avatar>
  );
}

interface ChatHeaderProps {
  language: Language;
  busy: boolean;
}

/** The WhatsApp chat header: who you are talking to and whether they are typing. */
export function ChatHeader({ language, busy }: ChatHeaderProps) {
  return (
    <Stack direction="row" component="header"
      sx={(theme) => ({ bgcolor: theme.palette.chat.header, color: theme.palette.chat.onHeader, pl: 1, pr: 2, py: 1, gap: 1, alignItems: 'center', flexShrink: 0 })}>
      <ArrowBackIcon aria-hidden sx={{ fontSize: 20, opacity: 0.85 }} />
      <BrandAvatar size={38} />
      <Box sx={{ flex: 1, minWidth: 0, ml: 0.5 }}>
        <Stack direction="row" sx={{ alignItems: 'center', gap: 0.5 }}>
          <Typography variant="subtitle1" component="p" sx={{ lineHeight: 1.25, fontSize: '1rem' }} noWrap>Bill Mitra</Typography>
          <VerifiedIcon titleAccess="Verified business" sx={(theme) => ({ fontSize: 16, color: theme.palette.chat.tick })} />
        </Stack>
        <Typography variant="caption" component="p" lang={language} aria-live="polite" sx={{ opacity: 0.82, lineHeight: 1.3 }} noWrap>
          {busy ? UI[language].typing : UI[language].online}
        </Typography>
      </Box>
    </Stack>
  );
}
