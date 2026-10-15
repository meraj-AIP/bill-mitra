import { keyframes } from '@emotion/react';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { Badge, Box, Button, IconButton, Skeleton, Stack, Typography } from '@mui/material';
import type { Theme } from '@mui/material/styles';

const pill = (theme: Theme) => ({
  bgcolor: theme.palette.chat.incoming,
  boxShadow: theme.palette.chat.shadow,
  borderRadius: '8px',
  px: 1.25,
  py: 0.375,
});

/** Day separator. It sticks to the top while that day is on screen. */
export function DayChip({ label }: { label: string }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', position: 'sticky', top: 8, zIndex: 1, my: 1.25, pointerEvents: 'none' }}>
      <Typography variant="caption" component="p" sx={(theme) => ({ ...pill(theme), color: theme.palette.chat.meta, fontWeight: 500 })}>
        {label}
      </Typography>
    </Box>
  );
}

export function SavedNotice() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', px: 3, pt: 1.5, pb: 0.5 }}>
      <Typography variant="caption" component="p"
        sx={(theme) => ({ bgcolor: theme.palette.chat.notice, color: 'text.secondary', borderRadius: '8px', px: 1.5, py: 0.75,
          textAlign: 'center', maxWidth: 300, lineHeight: 1.5 })}>
        <LockOutlinedIcon sx={{ fontSize: 12, verticalAlign: '-1px', mr: 0.5 }} />
        Your chat is saved to your account. Starting a new chat deletes it.
      </Typography>
    </Box>
  );
}

interface LoadEarlierProps {
  loading: boolean;
  failed: boolean;
  onLoad: () => void;
}

export function LoadEarlier({ loading, failed, onLoad }: LoadEarlierProps) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', pt: 1.5 }}>
      <Button size="small" onClick={onLoad} disabled={loading}
        sx={(theme) => ({ ...pill(theme), py: 0.5, color: failed ? 'error.main' : theme.palette.chat.quickReply, '&:hover': { bgcolor: 'grey.50' } })}>
        {loading ? 'Loading earlier messages…' : failed ? 'Could not load. Try again' : 'Load earlier messages'}
      </Button>
    </Box>
  );
}

const bounce = keyframes`
  0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
  30% { transform: translateY(-3px); opacity: 1; }
`;

export function TypingBubble({ label }: { label: string }) {
  return (
    <Box sx={{ px: 2.25, mt: 1 }} role="status" aria-label={label}>
      <Stack direction="row"
        sx={(theme) => ({ display: 'inline-flex', gap: 0.5, px: 1.5, py: 1.25, bgcolor: theme.palette.chat.incoming,
          boxShadow: theme.palette.chat.shadow, borderRadius: '10px', borderTopLeftRadius: 0 })}>
        {[0, 1, 2].map((i) => (
          <Box key={i} sx={(theme) => ({ width: 7, height: 7, borderRadius: '50%', bgcolor: theme.palette.chat.meta,
            animation: `${bounce} 1.2s ${i * 0.16}s infinite ease-in-out`,
            '@media (prefers-reduced-motion: reduce)': { animation: 'none', opacity: 0.6 } })} />
        ))}
      </Stack>
    </Box>
  );
}

export function ThreadSkeleton() {
  const shapes: Array<[boolean, number, number]> = [[false, 62, 54], [true, 44, 38], [false, 70, 76], [true, 36, 38], [false, 55, 54]];
  return (
    <Stack sx={{ gap: 1.25, px: 2.25, pt: 3 }} aria-label="Loading your chat" role="status">
      {shapes.map(([out, width, height], i) => (
        <Skeleton key={i} variant="rounded"
          sx={{ alignSelf: out ? 'flex-end' : 'flex-start', width: `${width}%`, height, borderRadius: '10px', bgcolor: 'action.selected' }} />
      ))}
    </Stack>
  );
}

interface JumpToLatestProps {
  unread: number;
  onJump: () => void;
}

export function JumpToLatest({ unread, onJump }: JumpToLatestProps) {
  const label = unread > 0 ? `Scroll to latest, ${unread} new` : 'Scroll to latest';
  return (
    <Badge badgeContent={unread} max={9} overlap="circular"
      sx={(theme) => ({ position: 'absolute', right: 14, bottom: 12, zIndex: 2,
        '& .MuiBadge-badge': { bgcolor: theme.palette.chat.accent, color: theme.palette.chat.onHeader, fontWeight: 700 } })}>
      <IconButton onClick={onJump} aria-label={label}
        sx={(theme) => ({ width: 40, height: 40, bgcolor: theme.palette.chat.incoming, color: theme.palette.chat.meta,
          boxShadow: theme.shadows[3], '&:hover': { bgcolor: 'grey.50' } })}>
        <KeyboardArrowDownIcon />
      </IconButton>
    </Badge>
  );
}
