import { Box, Paper, Tab, Tabs, Typography } from '@mui/material';
import { useState } from 'react';

import { useAuth } from '@/features/auth';
import type { ComplaintDetail } from '@/features/complaints';

import { SECTION_ID, type Focus } from '../model/focus';
import { ReplyPanel } from './ReplyPanel';
import { RequestInfo } from './RequestInfo';

type Work = 'reply' | 'request';

/** Reply and Ask the consumer side by side as tabs, so both sit beside the conversation without scrolling. */
export function WorkPanel({ complaint, focus }: { complaint: ComplaintDetail; focus: Focus | null }) {
  const canReply = useAuth().can('complaints.reply');
  // The officer's last click wins, unless AI assist has named a place since; then the tab follows it.
  const [picked, setPicked] = useState<{ tab: Work; at: number }>({ tab: 'reply', at: 0 });
  const suggested = focus && (focus.target === 'reply' || focus.target === 'request') && focus.n > picked.at ? focus.target : null;
  const tab: Work = suggested ?? picked.tab;
  const setTab = (next: Work) => setPicked({ tab: next, at: focus?.n ?? 0 });

  if (!canReply) {
    return (
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>You can read this complaint. Replying and changing it need the reply permission.</Typography>
      </Paper>
    );
  }
  return (
    <Paper component="aside" variant="outlined" aria-label="Respond" sx={{ overflow: 'hidden' }}>
      <Tabs value={tab} onChange={(_, v: Work) => setTab(v)} variant="fullWidth" sx={{ borderBottom: 1, borderColor: 'divider', minHeight: 44 }}>
        <Tab value="reply" label="Reply" sx={{ minHeight: 44 }} />
        <Tab value="request" label="Ask the consumer" sx={{ minHeight: 44 }} />
      </Tabs>
      <Box id={SECTION_ID.reply} tabIndex={-1} hidden={tab !== 'reply'} sx={{ p: { xs: 2, sm: 2.25 }, '&:focus': { outline: 'none' } }}>
        <ReplyPanel complaint={complaint} preset={focus} />
      </Box>
      <Box id={SECTION_ID.request} tabIndex={-1} hidden={tab !== 'request'} sx={{ p: { xs: 2, sm: 2.25 }, '&:focus': { outline: 'none' } }}>
        <RequestInfo complaint={complaint} preset={focus} />
      </Box>
    </Paper>
  );
}
