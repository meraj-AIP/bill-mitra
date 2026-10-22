import FormatQuoteRoundedIcon from '@mui/icons-material/FormatQuoteRounded';
import { Box, Paper, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

export type Tone = 'default' | 'error' | 'warning' | 'success' | 'info';

export interface Tile {
  label: string;
  value: ReactNode;
  /** One short line under the value: the comparison, the source, or why it matters. */
  note?: string | null;
  tone?: Tone;
}

const TONE: Record<Tone, string> = {
  default: 'text.primary', error: 'error.dark', warning: 'warning.dark', success: 'success.dark', info: 'info.dark',
};

/** The few facts that say what a case is, as tiles in one row, so nobody scrolls to find them. */
export function Snapshot({ tiles, quote }: { tiles: Tile[]; quote?: { text: string; meta: string } | null }) {
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', md: `repeat(${tiles.length}, minmax(0, 1fr))` } }}>
        {tiles.map((t, i) => (
          <Box key={t.label} sx={{ px: 2, py: 1.5, minWidth: 0, borderLeft: { md: i ? 1 : 0 }, borderTop: { xs: i > 1 ? 1 : 0, md: 0 },
            borderColor: 'divider' }}>
            <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{t.label}</Typography>
            <Typography variant="h3" component="p" sx={{ color: TONE[t.tone ?? 'default'], fontVariantNumeric: 'tabular-nums', mt: 0.25 }}>
              {t.value}
            </Typography>
            {t.note && <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.25 }}>{t.note}</Typography>}
          </Box>
        ))}
      </Box>
      {quote && (
        <Stack direction="row" sx={{ gap: 1.25, px: 2, py: 1.5, borderTop: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
          <FormatQuoteRoundedIcon sx={{ color: 'text.disabled', mt: 0.25 }} aria-hidden />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body1" sx={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {quote.text}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>{quote.meta}</Typography>
          </Box>
        </Stack>
      )}
    </Paper>
  );
}
