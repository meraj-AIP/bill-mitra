import { Box, Divider, Paper, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { useAuth } from '@/features/auth';
import type { ComplaintDetail } from '@/features/complaints';

import { SECTION_ID, type Focus, type FocusTarget } from '../model/focus';
import { HandOffPanel } from './HandOffPanel';
import { ReplyPanel } from './ReplyPanel';
import { RequestInfo } from './RequestInfo';
import { StatusControl } from './StatusControl';

function Section({ title, caption, target, children }: { title: string; caption?: string; target?: FocusTarget; children: ReactNode }) {
  return (
    // tabIndex lets AI assist move focus here; scroll margin keeps the heading clear of the app bar.
    <Box component="section" id={target ? SECTION_ID[target] : undefined} tabIndex={target ? -1 : undefined}
      sx={{ px: { xs: 2, sm: 2.5 }, py: 2.25, scrollMarginTop: 80, '&:focus': { outline: 'none' },
        '&:focus-visible': { outline: 2, outlineColor: 'primary.main', outlineOffset: -2 } }}>
      <Typography variant="h4" component="h2">{title}</Typography>
      {caption && <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.25 }}>{caption}</Typography>}
      <Box sx={{ mt: 1.5 }}>{children}</Box>
    </Box>
  );
}

/** Every action on the complaint in one place. The server checks each permission again. */
export function ActionsColumn({ complaint, focus }: { complaint: ComplaintDetail; focus: Focus | null }) {
  const { can } = useAuth();
  const canReply = can('complaints.reply');
  return (
    <Paper component="aside" variant="outlined" aria-label="Actions" sx={{ overflow: 'hidden' }}>
      {!canReply && (
        <Section title="Actions">
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>You can read this complaint. Replying and changing it need the reply permission.</Typography>
        </Section>
      )}
      {canReply && (
        <>
          <Section title="Reply" target="reply">
            <ReplyPanel complaint={complaint} preset={focus} />
          </Section>
          <Divider />
          <Section title="Status" caption="The consumer gets a short message about the change." target="status">
            <StatusControl complaint={complaint} />
          </Section>
          <Divider />
          <Section title="Ask the consumer" caption="Their next photo or message is filed under this complaint." target="request">
            <RequestInfo complaint={complaint} preset={focus} />
          </Section>
        </>
      )}
      <Divider />
      <Section title="Who has it" caption="A hand over needs a short note for the next person." target="handoff">
        <HandOffPanel complaint={complaint} preset={focus} />
      </Section>
    </Paper>
  );
}
