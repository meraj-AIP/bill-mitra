import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import { Box, Button, Skeleton, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import type { ComplaintDetail } from '@/features/complaints';

import { useReplyOptions, useRequestInfo, type RequestOption } from '../api/actionsApi';
import { usePreset } from '../hooks/usePreset';
import type { Focus } from '../model/focus';
import { OptionCards } from './OptionCards';

function RequestPreview({ request, pending, onSend }: { request: RequestOption; pending: boolean; onSend: () => void }) {
  return (
    <Stack sx={{ gap: 1 }}>
      <Box sx={{ p: 1.25, borderRadius: 1, bgcolor: 'action.hover' }}>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>The consumer gets, in their language:</Typography>
        <Typography variant="body2" dir="auto" sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>{request.text}</Typography>
      </Box>
      <Button variant="outlined" startIcon={<SendOutlinedIcon />} disabled={pending} onClick={onSend}>
        {pending ? 'Sending' : `Ask for: ${request.label}`}
      </Button>
    </Stack>
  );
}

function AskOutcome({ done, error }: { done: boolean; error: string | null }) {
  if (error) return <Typography variant="caption" sx={{ color: 'error.main' }}>{error}</Typography>;
  return done ? <Typography variant="caption" sx={{ color: 'success.dark' }}>Asked. Their answer will appear in the conversation.</Typography> : null;
}

function NothingToAsk({ complaint }: { complaint: ComplaintDetail }) {
  const waiting = (complaint.requests ?? []).some((r) => r.status === 'open');
  return (
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      {waiting ? 'We are waiting for the consumer to answer what was asked.' : 'Nothing more fits this complaint. Use a reply to ask in your own words.'}
    </Typography>
  );
}

function NotConnected({ complaint }: { complaint: ComplaintDetail }) {
  if (complaint.reply_channel !== 'whatsapp' || complaint.whatsapp_ready) return null;
  return <Typography variant="caption" sx={{ color: 'warning.dark' }}>WhatsApp is not connected here, so the request is saved as not delivered.</Typography>;
}

/** Ask the consumer for something that fits this complaint. Their next photo or message is filed under it. */
export function RequestInfo({ complaint, preset }: { complaint: ComplaintDetail; preset: Focus | null }) {
  const ask = useRequestInfo(complaint.ticket);
  const options = useReplyOptions(complaint.ticket);
  const [kind, setKind] = useState<string | null>(null);
  usePreset(preset, 'request', true, setKind);
  const open = complaint.status === 'Open' || complaint.status === 'In progress';
  if (!open) {
    return <Typography variant="body2" sx={{ color: 'text.secondary' }}>Reopen the complaint to ask the consumer for something.</Typography>;
  }
  if (options.isPending) return <Skeleton variant="rounded" height={72} />;
  const requests = options.data?.requests ?? [];
  if (requests.length === 0) {
    return <NothingToAsk complaint={complaint} />;
  }
  const chosen = requests.find((r) => r.kind === kind) ?? null;
  return (
    <Stack sx={{ gap: 1 }}>
      <NotConnected complaint={complaint} />
      <OptionCards label="What to ask the consumer for" selected={chosen?.kind ?? null} onSelect={setKind}
        disabled={ask.isPending} items={requests.map((r) => ({ id: r.kind, label: r.label, why: r.why }))} />
      {chosen && <RequestPreview request={chosen} pending={ask.isPending} onSend={() => ask.mutate(chosen.kind, { onSuccess: () => setKind(null) })} />}
      <AskOutcome done={ask.isSuccess} error={ask.isError ? ask.error.message : null} />
    </Stack>
  );
}
