import { Box, Chip, Stack, Typography } from '@mui/material';

import { PhotoThumb } from '@/shared/components/PhotoGallery';
import { shortDate } from '@/shared/lib/format';

import type { ComplaintRequest } from '../api/types';
import { requestLabel } from '../model/labels';

function Answer({ r }: { r: ComplaintRequest }) {
  const answer = r.answer;
  if (r.status === 'open') return <Chip size="small" color="info" label="Waiting for their answer" />;
  if (!answer) return <Typography variant="caption" sx={{ color: 'success.dark' }}>Answered</Typography>;
  return (
    <Stack direction="row" sx={{ gap: 1.25, alignItems: 'flex-start', mt: 0.75 }}>
      {answer.media_url && (
        <PhotoThumb size="small" src={answer.media_url} alt={`Photo sent for ${requestLabel(r.kind)}, ${shortDate(answer.at)}`}
          caption={`Sent by the consumer for ${requestLabel(r.kind)}, ${shortDate(answer.at)}`} />
      )}
      {answer.body && (
        <Typography variant="body2" dir="auto" sx={{ color: 'text.secondary', overflowWrap: 'anywhere', display: '-webkit-box',
          WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {answer.body}
        </Typography>
      )}
    </Stack>
  );
}

/** What staff asked the consumer for, in the server's order (newest first), each with what came back. */
export function RequestList({ requests }: { requests: ComplaintRequest[] }) {
  if (requests.length === 0) return null;
  return (
    <Stack component="ul" aria-label="Requests to the consumer" sx={{ listStyle: 'none', m: 0, p: 0, gap: 1 }}>
      {requests.map((r) => {
        const received = r.status === 'answered' && r.answer ? `, received ${shortDate(r.answer.at)}` : '';
        return (
          <Box component="li" key={r.id} sx={{ p: 1.25, borderRadius: 1.5, bgcolor: 'grey.50', border: 1, borderColor: 'divider' }}>
            <Stack direction="row" sx={{ gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, flex: 1, minWidth: 0 }}>
                Asked for {requestLabel(r.kind)}{received}
              </Typography>
              <Typography variant="caption" component="time" dateTime={r.created_at} sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                Asked {shortDate(r.created_at)}
              </Typography>
            </Stack>
            {r.note && (
              <Typography variant="caption" component="p" dir="auto" sx={{ color: 'text.secondary', overflowWrap: 'anywhere', mt: 0.25 }}>
                {r.note}
              </Typography>
            )}
            <Box sx={{ mt: 0.75 }}><Answer r={r} /></Box>
          </Box>
        );
      })}
    </Stack>
  );
}
