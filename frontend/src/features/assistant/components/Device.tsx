import BatteryFullIcon from '@mui/icons-material/BatteryFull';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import WifiIcon from '@mui/icons-material/Wifi';
import { Box, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { clockTime } from '@/shared/lib/format';

import { useNow } from '../hooks/useNow';

function StatusBar() {
  const now = useNow();
  return (
    <Stack direction="row" aria-hidden
      sx={(theme) => ({ display: { xs: 'none', md: 'flex' }, position: 'relative', height: 38, px: 3.5, alignItems: 'center',
        justifyContent: 'space-between', bgcolor: theme.palette.chat.header, color: theme.palette.chat.onHeader, flexShrink: 0 })}>
      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums', letterSpacing: '0.01em' }}>
        {clockTime(now)}
      </Typography>
      <Box sx={(theme) => ({ position: 'absolute', left: '50%', top: 9, transform: 'translateX(-50%)', width: 92, height: 24,
        borderRadius: 12, bgcolor: theme.palette.chat.island })} />
      <Stack direction="row" sx={{ gap: 0.5, alignItems: 'center', '& svg': { fontSize: 15 } }}>
        <SignalCellularAltIcon />
        <WifiIcon />
        <BatteryFullIcon sx={{ transform: 'rotate(90deg)' }} />
      </Stack>
    </Stack>
  );
}

/**
 * A phone on desktop, so the jury sees the chat the way it lands on WhatsApp.
 * On a real phone the chat simply fills the width.
 */
export function Device({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={(theme) => ({
        position: 'relative', width: '100%', height: 'calc(100dvh - 200px)', minHeight: 460,
        [theme.breakpoints.up('md')]: {
          width: 392, height: 'min(820px, calc(100dvh - 230px))', minHeight: 620, p: '11px', borderRadius: '54px',
          bgcolor: theme.palette.chat.bezel,
          boxShadow: `${theme.palette.chat.elevation}, inset 0 0 0 1.5px ${theme.palette.chat.bezelEdge}, inset 0 0 0 4px ${theme.palette.chat.bezel}`,
          // Side keys, drawn as slim bars just outside the frame.
          '&::before, &::after': { content: '""', position: 'absolute', width: 3, borderRadius: 2, bgcolor: theme.palette.chat.bezelEdge },
          '&::before': { left: -3, top: 150, height: 56 },
          '&::after': { right: -3, top: 190, height: 84 },
        },
      })}
    >
      <Box
        sx={(theme) => ({
          height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', bgcolor: theme.palette.chat.wallpaper,
          borderTop: 1, borderBottom: 1, borderColor: 'divider',
          [theme.breakpoints.up('md')]: { borderRadius: '44px', border: 0 },
        })}
      >
        <StatusBar />
        {children}
        <Box aria-hidden sx={(theme) => ({ display: { xs: 'none', md: 'block' }, alignSelf: 'center', width: 124, height: 4.5, borderRadius: 3,
          bgcolor: theme.palette.text.primary, opacity: 0.85, mb: 1, mt: 0.25, flexShrink: 0 })} />
      </Box>
    </Box>
  );
}
