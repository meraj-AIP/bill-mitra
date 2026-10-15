import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';

import { EmptyState } from '@/shared/components/States';
import { dateTime } from '@/shared/lib/format';

import type { ComplaintMessage } from '../api/types';
import { DELIVERY } from '../model/labels';

type Viewer = 'staff' | 'consumer';

function authorLabel(m: ComplaintMessage, viewer: Viewer): string {
  if (m.author_kind === 'consumer') return viewer === 'consumer' ? 'You' : (m.author_name ?? 'Consumer');
  return m.author_name ?? 'DISCOM officer';
}

function SystemLine({ message }: { message: ComplaintMessage }) {
  return (
    <Stack sx={{ alignItems: 'center', textAlign: 'center', py: 0.5 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', bgcolor: 'grey.100', px: 1.5, py: 0.5, borderRadius: 1, maxWidth: '60ch' }}>
        {message.body}
        <Box component="span" sx={{ ml: 1, opacity: 0.8 }}>{dateTime(message.created_at)}</Box>
      </Typography>
    </Stack>
  );
}

function Delivery({ message, onRetry }: { message: ComplaintMessage; onRetry?: ((id: number) => void) | undefined }) {
  const d = DELIVERY[message.delivery];
  return (
    <Stack sx={{ alignItems: 'flex-end', gap: 0.5, mt: 0.75 }}>
      <Chip size="small" variant="outlined" color={d.tone} label={d.label} />
      {message.delivery === 'failed' && message.delivery_note && (
        <Typography variant="caption" sx={{ color: 'error.dark', textAlign: 'right' }}>{message.delivery_note}</Typography>
      )}
      {message.delivery === 'failed' && onRetry && (
        <Button size="small" variant="outlined" color="error" onClick={() => onRetry(message.id)}>Send again</Button>
      )}
    </Stack>
  );
}

function Photo({ url }: { url: string }) {
  return (
    <Box component="a" href={url} target="_blank" rel="noopener noreferrer" sx={{ display: 'block', mt: 1 }}>
      <Box component="img" src={url} alt="Photo sent by the consumer" loading="lazy"
        sx={{ display: 'block', maxWidth: '100%', maxHeight: 240, borderRadius: 1, border: 1, borderColor: 'divider' }} />
    </Box>
  );
}

function Bubble({ message, viewer, onRetry }: { message: ComplaintMessage; viewer: Viewer; onRetry?: ((id: number) => void) | undefined }) {
  // Your own side sits on the right, as in any chat.
  const mine = (viewer === 'staff') === (message.author_kind === 'officer');
  return (
    <Stack component="li" sx={{ alignItems: mine ? 'flex-end' : 'flex-start' }}>
      <Box sx={{ maxWidth: { xs: '92%', sm: '78%' }, px: 2, py: 1.25, borderRadius: 2,
        borderTopRightRadius: mine ? 4 : undefined, borderTopLeftRadius: mine ? undefined : 4,
        bgcolor: mine ? 'info.light' : 'background.paper', border: 1, borderColor: mine ? 'info.light' : 'divider' }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'baseline', mb: 0.25 }}>
          <Typography variant="subtitle2" component="p">{authorLabel(message, viewer)}</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{dateTime(message.created_at)}</Typography>
        </Stack>
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{message.body}</Typography>
        {message.media_url && <Photo url={message.media_url} />}
        {viewer === 'staff' && message.author_kind === 'officer' && <Delivery message={message} onRetry={onRetry} />}
      </Box>
    </Stack>
  );
}

interface ThreadProps {
  messages: ComplaintMessage[];
  viewer: Viewer;
  /** Offered on officer messages that did not reach the consumer. */
  onRetry?: (id: number) => void;
}

export function MessageThread({ messages, viewer, onRetry }: ThreadProps) {
  if (messages.length === 0) {
    return <EmptyState icon={<ForumOutlinedIcon />} title="No messages yet"
      hint={viewer === 'staff' ? 'Your reply below starts the conversation with the consumer.' : 'An officer will reply here.'} />;
  }
  return (
    <Stack component="ol" aria-label="Messages" sx={{ listStyle: 'none', m: 0, p: 0, gap: 1.5 }}>
      {messages.map((m) => (m.author_kind === 'system'
        ? <Box component="li" key={m.id}><SystemLine message={m} /></Box>
        : <Bubble key={m.id} message={m} viewer={viewer} onRetry={onRetry} />))}
    </Stack>
  );
}
