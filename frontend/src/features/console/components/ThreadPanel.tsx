import { Alert, Box } from '@mui/material';
import { useLayoutEffect, useRef } from 'react';

import { useAuth } from '@/features/auth';
import { MessageThread, type ComplaintDetail } from '@/features/complaints';

import { useRetry } from '../api/actionsApi';

/**
 * The thread scrolls inside its own box, so a new message moves this box and never the page.
 * Only the box's scrollTop is set; scrollIntoView would drag the whole window down.
 */
interface ThreadPanelProps {
  ticket: string;
  messages: ComplaintDetail['messages'];
  inApp?: boolean;
  /** Height of the scrolling box; the detail page sizes it to the screen. */
  height?: string | Record<string, string | number>;
}

export function ThreadPanel({ ticket, messages, inApp = false, height = { xs: '420px', md: '520px' } }: ThreadPanelProps) {
  const box = useRef<HTMLDivElement>(null);
  const retry = useRetry(ticket);
  const canRetry = useAuth().can('complaints.reply');
  useLayoutEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [messages.length]);
  return (
    <Box ref={box} sx={{ maxHeight: height, overflowY: 'auto', overscrollBehavior: 'contain', pr: 0.5 }}>
      {retry.isError && <Alert severity="error" sx={{ mb: 1.5 }}>{retry.error.message}</Alert>}
      <MessageThread messages={messages} viewer="staff" {...(canRetry ? { onRetry: (id: number) => retry.mutate(id) } : {})} inApp={inApp} />
    </Box>
  );
}
