import { Box, Paper, Stack, Typography } from '@mui/material';
import { useId, type ReactNode } from 'react';

interface PanelProps {
  title: string;
  caption?: ReactNode;
  aside?: ReactNode;
  /** A coloured top edge for panels that ask the reader to act. */
  tone?: 'primary' | 'warning' | undefined;
  children: ReactNode;
}

export function Panel({ title, caption, aside, tone, children }: PanelProps) {
  const id = useId();
  return (
    <Paper component="section" variant="outlined" aria-labelledby={id}
      sx={{ overflow: 'hidden', borderTop: tone ? 3 : 1, borderTopColor: tone ? `${tone}.main` : 'divider' }}>
      <Stack direction="row" sx={{ px: { xs: 2, sm: 2.5 }, pt: 2, gap: 1.5, alignItems: 'flex-start' }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography id={id} variant="h3" component="h2">{title}</Typography>
          {caption && <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.25 }}>{caption}</Typography>}
        </Box>
        {aside}
      </Stack>
      <Box sx={{ px: { xs: 2, sm: 2.5 }, pt: 1.5, pb: 2.5 }}>{children}</Box>
    </Paper>
  );
}

export function Figure({ label, value, note, strong = false }: { label: string; value: string; note?: string | undefined; strong?: boolean }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography component="p" sx={{ fontSize: strong ? '1.5rem' : '1.125rem', fontWeight: 600, lineHeight: 1.3, fontVariantNumeric: 'tabular-nums',
        color: strong ? 'warning.dark' : 'text.primary' }}>
        {value}
      </Typography>
      {note && <Typography variant="caption" sx={{ color: 'text.secondary' }}>{note}</Typography>}
    </Box>
  );
}
