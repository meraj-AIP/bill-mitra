import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import WebOutlinedIcon from '@mui/icons-material/WebOutlined';
import { Alert, Button, Chip, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, ReplyBox, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';

import { useRequestInfo, useSuggestion, type InfoKind } from '../api/actionsApi';
import { useReply } from '../api/consoleApi';

const ASKS: Array<[InfoKind, string]> = [['meter_photo', 'Meter photo'], ['bill_photo', 'Full bill photo'], ['details', 'More details']];

function Destination({ complaint }: { complaint: ComplaintDetail }) {
  const whatsapp = complaint.reply_channel === 'whatsapp';
  if (whatsapp && !complaint.whatsapp_ready) {
    return (
      <Alert severity="warning">
        This consumer raised the complaint on WhatsApp, but WhatsApp is not connected on this server. Your reply will be
        saved and marked as not delivered. Use Send again once WhatsApp is set up.
      </Alert>
    );
  }
  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', color: 'text.secondary' }}>
      {whatsapp ? <ChatOutlinedIcon fontSize="small" /> : <WebOutlinedIcon fontSize="small" />}
      <Typography variant="body2">
        {whatsapp
          ? 'Your reply goes to the consumer on WhatsApp. Outside 24 hours of their last message it is sent as the approved template.'
          : 'This complaint came from the web chat preview. Your reply is saved here only; the consumer does not receive it.'}
      </Typography>
    </Stack>
  );
}

/** Ask the consumer for something. Their next photo or message in the chat is filed under this complaint. */
function AskFor({ complaint }: { complaint: ComplaintDetail }) {
  const ask = useRequestInfo(complaint.ticket);
  const open = complaint.status === 'Open' || complaint.status === 'In progress';
  if (!open) return null;
  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>Ask the consumer for</Typography>
      {ASKS.map(([kind, label]) => (
        <Chip key={kind} label={label} variant="outlined" clickable disabled={ask.isPending} onClick={() => ask.mutate(kind)} />
      ))}
      {ask.isError && <Typography variant="caption" sx={{ color: 'error.main' }}>{ask.error.message}</Typography>}
    </Stack>
  );
}

export function ReplyPanel({ complaint }: { complaint: ComplaintDetail }) {
  const reply = useReply(complaint.ticket);
  const [status, setStatus] = useState<ComplaintStatus | ''>('');
  const [draft, setDraft] = useState({ text: '', n: 0 });
  const suggestion = useSuggestion(complaint.ticket, true);
  const s = suggestion.data;
  const load = (text: string) => setDraft((d) => ({ text, n: d.n + 1 }));

  const send = async (body: string) => {
    await reply.mutateAsync(status ? { body, status } : { body });
    setStatus('');
  };

  return (
    <Stack sx={{ gap: 1.5 }}>
      <Destination complaint={complaint} />
      <AskFor complaint={complaint} />
      <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <Button size="small" variant="outlined" startIcon={<AutoAwesomeOutlinedIcon />} disabled={!s?.text}
          onClick={() => s?.text && load(s.text)}>
          {suggestion.isPending ? 'Preparing a reply' : 'Use the suggested reply'}
        </Button>
        {s?.quick.map((q) => <Chip key={q} size="small" label={q} variant="outlined" clickable onClick={() => load(q)} sx={{ maxWidth: 280 }} />)}
      </Stack>
      {s?.text && (
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {s.worded_by === 'ai'
            ? 'Figures come from the tariff check; the wording was polished by AI and every number was checked again.'
            : 'Built from the tariff check for this bill, in the consumer\'s language.'}
        </Typography>
      )}
      <ReplyBox key={draft.n} initial={draft.text} label="Reply to the consumer"
        placeholder="Write in plain words. The consumer may read this on a phone."
        pending={reply.isPending} error={reply.error?.message ?? null} onSend={send}
        extra={
          <TextField select size="small" label="Then set status" value={status} sx={{ minWidth: 190 }}
            onChange={(e) => setStatus(e.target.value as ComplaintStatus | '')}>
            <MenuItem value="">Keep as {complaint.status}</MenuItem>
            {COMPLAINT_STATUSES.filter((x) => x !== complaint.status).map((x) => <MenuItem key={x} value={x}>{x}</MenuItem>)}
          </TextField>
        } />
    </Stack>
  );
}
