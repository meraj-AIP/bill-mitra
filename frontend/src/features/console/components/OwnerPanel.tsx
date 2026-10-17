import { Box, Divider, LinearProgress, Paper, Typography } from '@mui/material';
import { useState, type ReactNode } from 'react';

import { useAuth } from '@/features/auth';
import type { ComplaintDetail } from '@/features/complaints';
import { shortDate } from '@/shared/lib/format';

import { SECTION_ID, type Focus } from '../model/focus';
import { HandOffPanel } from './HandOffPanel';
import { StatusControl } from './StatusControl';

function Block({ title, target, children }: { title: string; target: 'handoff' | 'status'; children: ReactNode }) {
  return (
    // The id and tabIndex let AI assist bring this block into view and focus it.
    <Box component="section" id={SECTION_ID[target]} tabIndex={-1} aria-label={title} sx={{ scrollMarginTop: 80, '&:focus': { outline: 'none' } }}>
      <Typography variant="overline" component="h2" sx={{ color: 'text.secondary', display: 'block', mb: 0.75 }}>{title}</Typography>
      {children}
    </Box>
  );
}

/** How much of the promised reply time is used up; past the due time the bar is full and red. */
function Sla({ c }: { c: ComplaintDetail }) {
  // Read once on mount; the page refreshes the complaint on its own, which is soon enough for this bar.
  const [now] = useState(Date.now);
  if (!c.due_at || (c.status !== 'Open' && c.status !== 'In progress')) return null;
  const start = new Date(c.created_at).getTime();
  const due = new Date(c.due_at).getTime();
  const used = Math.min(100, Math.max(0, ((now - start) / Math.max(due - start, 1)) * 100));
  return (
    <Box sx={{ mt: 1.5 }}>
      <LinearProgress variant="determinate" value={used} color={c.overdue ? 'error' : used > 75 ? 'warning' : 'primary'}
        aria-label="Reply time used" sx={{ height: 6, borderRadius: 3 }} />
      <Typography variant="caption" sx={{ color: c.overdue ? 'error.main' : 'text.secondary' }}>
        {c.overdue ? `Was due ${shortDate(c.due_at)}` : `Due ${shortDate(c.due_at)}`}
      </Typography>
    </Box>
  );
}

/** Who holds the complaint and where it stands, with the moves that change either. */
export function OwnerPanel({ complaint: c, focus }: { complaint: ComplaintDetail; focus: Focus | null }) {
  const canReply = useAuth().can('complaints.reply');
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.25 }, display: 'flex', flexDirection: 'column', gap: 1.75 }}>
      <Block title="Owner" target="handoff"><HandOffPanel complaint={c} preset={focus} /></Block>
      <Divider />
      <Block title="Status" target="status">
        {c.kind === 'wrong_reading' || !canReply
          ? <Typography variant="body2">{c.status}{c.kind === 'wrong_reading' ? '. Set by the review case decision.' : ''}</Typography>
          : <StatusControl complaint={c} />}
        <Sla c={c} />
      </Block>
    </Paper>
  );
}
