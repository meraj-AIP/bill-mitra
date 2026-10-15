import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import { Box, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { EmptyState } from '@/shared/components/States';

import type { TraceTurn as Turn } from '../model/conversation';
import { TraceTurn } from './TraceTurn';

const SHOWN = 8;

interface TracePanelProps {
  turns: Turn[];
  /** Saved messages are on screen; their steps were not stored, so say so. */
  hasHistory: boolean;
}

/** What happened behind each reply, step by step. Web only: a WhatsApp user never sees this. */
export function TracePanel({ turns, hasHistory }: TracePanelProps) {
  // Newest turn is open unless the reader closed it; older ones are closed unless opened.
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const recent = turns.slice(-SHOWN).reverse();

  return (
    <Stack component="aside" aria-label="Behind the reply" sx={{ gap: 1.5, width: '100%' }}>
      <Box>
        <Typography variant="overline" component="p" sx={{ color: 'primary.light' }}>Staff only</Typography>
        <Typography variant="h3" component="h2">Behind the reply</Typography>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.5, maxWidth: '44ch' }}>
          Rules work out every rupee. AI reads the photo and words the answer, and each figure it writes is checked.
        </Typography>
      </Box>
      {hasHistory && (
        <Typography variant="caption" component="p" sx={{ color: 'text.disabled' }}>
          Steps show for messages sent in this visit. Saved messages keep their text, not their steps.
        </Typography>
      )}
      {recent.length === 0 && (
        <EmptyState icon={<AccountTreeOutlinedIcon />} title="Nothing yet" hint="Send a message and each step will show here as it runs." />
      )}
      {recent.map((turn, index) => {
        const open = toggled[turn.id] ?? index === 0;
        return <TraceTurn key={turn.id} turn={turn} open={open} onToggle={() => setToggled((t) => ({ ...t, [turn.id]: !open }))} />;
      })}
    </Stack>
  );
}
