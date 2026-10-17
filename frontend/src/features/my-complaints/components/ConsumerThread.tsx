import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import { Box, Stack, Typography } from '@mui/material';

import { EmptyState } from '@/shared/components/States';
import { dateTime } from '@/shared/lib/format';

import type { MyMessage } from '../api/types';

function Bubble({ m }: { m: MyMessage }) {
  const mine = m.from === 'you';
  return (
    <Stack component="li" sx={{ alignItems: mine ? 'flex-end' : 'flex-start' }}>
      <Box sx={{ maxWidth: { xs: '92%', sm: '78%' }, px: 2, py: 1.25, borderRadius: 2,
        borderTopRightRadius: mine ? 4 : undefined, borderTopLeftRadius: mine ? undefined : 4,
        bgcolor: mine ? 'info.light' : 'background.paper', border: 1, borderColor: mine ? 'info.light' : 'divider' }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'baseline', mb: 0.25 }}>
          <Typography variant="subtitle2" component="p">{mine ? 'You' : 'Bill Mitra'}</Typography>
          <Typography variant="caption" component="time" dateTime={m.at} sx={{ color: 'text.secondary' }}>{dateTime(m.at)}</Typography>
        </Stack>
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.body}</Typography>
      </Box>
    </Stack>
  );
}

/** The conversation with Bill Mitra. Every reply from the DISCOM side is shown as Bill Mitra. */
export function ConsumerThread({ messages }: { messages: MyMessage[] }) {
  if (messages.length === 0) {
    return <EmptyState icon={<ForumOutlinedIcon />} title="No replies yet" hint="We will reply here. You can come back to this page any time." />;
  }
  return (
    <Stack component="ol" aria-label="Messages" sx={{ listStyle: 'none', m: 0, p: 0, gap: 1.5 }}>
      {messages.map((m, i) => <Bubble key={`${m.at}-${i}`} m={m} />)}
    </Stack>
  );
}
