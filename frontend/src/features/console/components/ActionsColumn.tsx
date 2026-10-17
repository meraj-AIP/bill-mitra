import { Box, Divider, Paper, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { useAuth } from '@/features/auth';
import type { ComplaintDetail } from '@/features/complaints';

import { AssignControl } from './AssignControl';
import { ReplyPanel } from './ReplyPanel';
import { RequestInfo } from './RequestInfo';
import { StatusControl } from './StatusControl';

function Section({ title, caption, children }: { title: string; caption?: string; children: ReactNode }) {
  return (
    <Box component="section" sx={{ px: { xs: 2, sm: 2.5 }, py: 2.25 }}>
      <Typography variant="h4" component="h2">{title}</Typography>
      {caption && <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.25 }}>{caption}</Typography>}
      <Box sx={{ mt: 1.5 }}>{children}</Box>
    </Box>
  );
}

/** Every action on the complaint in one place. The server checks each permission again. */
export function ActionsColumn({ complaint }: { complaint: ComplaintDetail }) {
  const { can } = useAuth();
  const canReply = can('complaints.reply');
  const people = can('complaints.assign') ? complaint.assignable : undefined;
  return (
    <Paper component="aside" variant="outlined" aria-label="Actions" sx={{ overflow: 'hidden' }}>
      {!canReply && (
        <Section title="Actions">
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>You can read this complaint. Replying and changing it need the reply permission.</Typography>
        </Section>
      )}
      {canReply && (
        <>
          <Section title="Reply">
            <ReplyPanel complaint={complaint} />
          </Section>
          <Divider />
          <Section title="Status" caption="The consumer gets a short message about the change.">
            <StatusControl complaint={complaint} />
          </Section>
          <Divider />
          <Section title="Ask the consumer" caption="Their next photo or message is filed under this complaint.">
            <RequestInfo complaint={complaint} />
          </Section>
        </>
      )}
      {people && (
        <>
          <Divider />
          <Section title="Assign">
            <AssignControl complaint={complaint} people={people} />
          </Section>
        </>
      )}
    </Paper>
  );
}
