import { Alert, Box } from '@mui/material';
import { useLayoutEffect, useRef } from 'react';

import { MessageThread, type ComplaintDetail } from '@/features/complaints';

import { useRetry } from '../api/actionsApi';

/**
 * The thread scrolls inside its own box, so a new message moves this box and never the page.
 * Only the box's scrollTop is set; scrollIntoView would drag the whole window down.
 */
export function ThreadPanel({ ticket, messages }: { ticket: string; messages: ComplaintDetail['messages'] }) {
  const box = useRef<HTMLDivElement>(null);
  const retry = useRetry(ticket);
  useLayoutEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [messages.length]);
  return (
    <Box ref={box} sx={{ maxHeight: { xs: 420, md: 520 }, overflowY: 'auto', overscrollBehavior: 'contain', pr: 0.5 }}>
      {retry.isError && <Alert severity="error" sx={{ mb: 1.5 }}>{retry.error.message}</Alert>}
      <MessageThread messages={messages} viewer="staff" onRetry={(id) => retry.mutate(id)} />
    </Box>
  );
}
