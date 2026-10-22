import { Badge, Box, Paper, Stack, Tab, Tabs } from '@mui/material';
import { useState } from 'react';

import {
  ComplaintEvidence, ComplaintFacts, ComplaintTimeline, RequestList, type ComplaintDetail, type ComplaintRequest,
} from '@/features/complaints';
import { Panel } from '@/shared/components/Panel';
import { EmptyState } from '@/shared/components/States';

import { ThreadPanel } from './ThreadPanel';

type Section = 'conversation' | 'bill' | 'requests' | 'timeline' | 'record';

// Long threads scroll inside their box, so the tabs above stay in reach.
const THREAD_HEIGHT = { xs: '420px', md: '560px' };

function Requests({ requests, waiting }: { requests: ComplaintRequest[]; waiting: number }) {
  if (!requests.length) return <Panel title="Requests to the consumer"><EmptyState title="Nothing asked yet" hint="Use Ask the consumer to request a photo, a receipt or more details." /></Panel>;
  return (
    <Panel title="Requests to the consumer" caption={waiting ? `${waiting} waiting for an answer.` : 'Everything asked has been answered.'}>
      <RequestList requests={requests} />
    </Panel>
  );
}

/** Everything on file, one section at a time: the conversation first, then the bill and its check, the requests,
 * the timeline and what we hold. Tabs keep each a click away instead of folded under the page. */
export function CaseFile({ complaint: c, requests }: { complaint: ComplaintDetail; requests: ComplaintRequest[] }) {
  const [section, setSection] = useState<Section>('conversation');
  const waiting = requests.filter((r) => r.status === 'open').length;
  const count = (n: number) => (n ? ` (${n})` : '');
  return (
    <Stack sx={{ gap: 1.5, minWidth: 0 }}>
      <Paper variant="outlined" sx={{ px: 1 }}>
        <Tabs value={section} onChange={(_, v: Section) => setSection(v)} variant="scrollable" scrollButtons={false} aria-label="Case file"
          sx={{ minHeight: 44, '& .MuiTab-root': { minHeight: 44, px: 1.5 } }}>
          <Tab value="conversation" label={`Conversation${count(c.messages.length)}`} />
          <Tab value="bill" label={c.bill || c.media_url ? 'Bill and check' : 'Bill (none)'} />
          <Tab value="requests" label={
            <Badge color="info" variant="dot" invisible={!waiting} sx={{ '& .MuiBadge-dot': { right: -6 } }}>{`Requests${count(requests.length)}`}</Badge>
          } />
          <Tab value="timeline" label="Timeline" />
          <Tab value="record" label="What we hold" />
        </Tabs>
      </Paper>
      <Box role="tabpanel" aria-label={section}>
        {section === 'conversation' && (
          <Panel title="Conversation" caption={waiting ? `${waiting} ${waiting === 1 ? 'request is' : 'requests are'} waiting for the consumer.` : undefined}>
            <ThreadPanel ticket={c.ticket} messages={c.messages} inApp={c.source === 'consumer_web'} height={THREAD_HEIGHT} />
          </Panel>
        )}
        {section === 'bill' && <ComplaintEvidence complaint={c} staff />}
        {section === 'requests' && <Requests requests={requests} waiting={waiting} />}
        {section === 'timeline' && <ComplaintTimeline complaint={c} />}
        {section === 'record' && <ComplaintFacts complaint={c} />}
      </Box>
    </Stack>
  );
}
