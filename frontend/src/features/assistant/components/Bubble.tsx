import { keyframes } from '@emotion/react';
import DoneIcon from '@mui/icons-material/Done';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import { Box } from '@mui/material';
import type { ReactNode } from 'react';

import { clockTime } from '@/shared/lib/format';

const enter = keyframes`
  from { opacity: 0; transform: translateY(6px) scale(0.98); }
  to { opacity: 1; transform: none; }
`;

export type Ticks = 'sent' | 'read';

interface BubbleProps {
  side: 'in' | 'out';
  at: Date;
  children: ReactNode;
  /** First bubble of a run from one sender: it gets the tail and a little more space above. */
  first: boolean;
  animate: boolean;
  ticks?: Ticks | undefined;
  /** Media fills the bubble edge to edge. */
  flush?: boolean;
  /** Quick replies or a list button attached under the bubble, matching its width. */
  footer?: ReactNode;
}

function Meta({ at, ticks, flush }: { at: Date; ticks: Ticks | undefined; flush: boolean }) {
  const TickIcon = ticks === 'sent' ? DoneIcon : DoneAllIcon;
  return (
    <Box component="span"
      sx={(theme) => ({
        float: 'right', display: 'inline-flex', alignItems: 'center', gap: 0.375, ml: 1.25, mt: flush ? 0.5 : 0.75,
        mb: flush ? 0 : -0.5, mr: flush ? 0.75 : 0, position: 'relative', top: 2,
        color: theme.palette.chat.meta, fontSize: '0.6875rem', lineHeight: 1, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
      })}>
      {clockTime(at)}
      {ticks && (
        <TickIcon aria-label={ticks === 'read' ? 'Read' : 'Sent'}
          sx={(theme) => ({ fontSize: 15, color: ticks === 'read' ? theme.palette.chat.tick : theme.palette.chat.meta })} />
      )}
    </Box>
  );
}

/** A WhatsApp style bubble: incoming (Bill Mitra) on the left, outgoing (consumer) on the right. */
export function Bubble({ side, at, children, first, animate, ticks, flush = false, footer }: BubbleProps) {
  const out = side === 'out';
  return (
    <Box sx={{ display: 'flex', justifyContent: out ? 'flex-end' : 'flex-start', px: 2.25, mt: first ? 1 : 0.25 }}>
      <Box
        sx={{
          display: 'inline-flex', flexDirection: 'column', gap: 0.375, maxWidth: '82%',
          transformOrigin: out ? 'bottom right' : 'bottom left',
          animation: animate ? `${enter} 240ms cubic-bezier(0.2, 0.8, 0.2, 1)` : 'none',
          '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
        }}
      >
        <Box
          sx={(theme) => {
            const bg = out ? theme.palette.chat.outgoing : theme.palette.chat.incoming;
            return {
              position: 'relative', bgcolor: bg, color: 'text.primary', boxShadow: theme.palette.chat.shadow,
              borderRadius: '10px', [out ? 'borderTopRightRadius' : 'borderTopLeftRadius']: first ? 0 : '10px',
              px: flush ? 0.5 : 1.125, pt: flush ? 0.5 : 0.75, pb: flush ? 0.5 : 0.875,
              fontSize: '0.875rem', lineHeight: 1.45, minWidth: 64,
              '&::after': first ? {
                content: '""', position: 'absolute', top: 0, [out ? 'right' : 'left']: -7, width: 8, height: 13, bgcolor: bg,
                clipPath: out ? 'polygon(0 0, 100% 0, 0 100%)' : 'polygon(0 0, 100% 0, 100% 100%)',
              } : {},
            };
          }}
        >
          {children}
          <Meta at={at} ticks={ticks} flush={flush} />
          <Box component="span" sx={{ display: 'block', clear: 'both' }} />
        </Box>
        {footer}
      </Box>
    </Box>
  );
}
