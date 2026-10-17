import { Chip, Stack, Typography } from '@mui/material';

import type { ComplaintDetail } from '@/features/complaints';

import { useRequestInfo, type InfoKind } from '../api/actionsApi';

const ASKS: Array<[InfoKind, string]> = [['meter_photo', 'Meter photo'], ['bill_photo', 'Full bill photo'], ['details', 'More details']];

/** Ask the consumer for something. Their next photo or message in the chat is filed under this complaint. */
export function RequestInfo({ complaint }: { complaint: ComplaintDetail }) {
  const ask = useRequestInfo(complaint.ticket);
  const open = complaint.status === 'Open' || complaint.status === 'In progress';
  if (!open) {
    return <Typography variant="body2" sx={{ color: 'text.secondary' }}>Reopen the complaint to ask the consumer for something.</Typography>;
  }
  return (
    <Stack sx={{ gap: 1 }}>
      <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
        {ASKS.map(([kind, label]) => (
          <Chip key={kind} label={label} variant="outlined" clickable disabled={ask.isPending} onClick={() => ask.mutate(kind)} />
        ))}
      </Stack>
      {ask.isSuccess && <Typography variant="caption" sx={{ color: 'success.dark' }}>Asked. Their answer will appear in the conversation.</Typography>}
      {ask.isError && <Typography variant="caption" sx={{ color: 'error.main' }}>{ask.error.message}</Typography>}
    </Stack>
  );
}
