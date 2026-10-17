import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import WebOutlinedIcon from '@mui/icons-material/WebOutlined';
import { Alert, Button, CircularProgress, MenuItem, Skeleton, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';

import { COMPLAINT_STATUSES, ReplyBox, type ComplaintDetail, type ComplaintStatus } from '@/features/complaints';

import { useDraftOption, useReplyOptions } from '../api/actionsApi';
import { useReply } from '../api/consoleApi';
import { OptionCards } from './OptionCards';

function Destination({ complaint }: { complaint: ComplaintDetail }) {
  const whatsapp = complaint.reply_channel === 'whatsapp';
  if (whatsapp && !complaint.whatsapp_ready) {
    return (
      <Alert severity="warning">
        Replies to this complaint go to the consumer on WhatsApp, but WhatsApp is not connected on this server. Your
        reply will be saved and marked as not delivered. Use Send again once WhatsApp is set up.
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

type Wording = 'rules' | 'ai' | 'rules_fallback';

const WORDING: Record<Wording, string> = {
  rules: 'Worded by the rules from this complaint\'s facts, in the consumer\'s language.',
  ai: 'Worded by AI. Every number was checked against this option\'s own figures.',
  rules_fallback: 'The AI wording did not pass the checks, so this is the rules\' wording.',
};

interface DraftRowProps { wording: Wording | null; asks: boolean; pending: boolean; error: string | null; onDraft: () => void }

/** "Draft with AI" for the loaded option, and who worded the text in the box. */
function DraftRow({ wording, asks, pending, error, onDraft }: DraftRowProps) {
  return (
    <Stack sx={{ gap: 0.5 }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button size="small" variant="outlined" onClick={onDraft} disabled={pending}
          startIcon={pending ? <CircularProgress size={14} color="inherit" aria-hidden /> : <AutoAwesomeOutlinedIcon />}>
          {pending ? 'Drafting' : 'Draft with AI'}
        </Button>
        {wording && (
          <Typography variant="caption" aria-live="polite" sx={{ color: 'text.secondary', flex: 1, minWidth: 0 }}>
            {WORDING[wording]}{asks ? ' Sending it also waits for their answer.' : ''}
          </Typography>
        )}
      </Stack>
      {error && <Typography variant="caption" sx={{ color: 'error.main' }}>{error}</Typography>}
    </Stack>
  );
}

interface Loaded { key: string | null; text: string; wording: Wording | null; n: number }

export function ReplyPanel({ complaint }: { complaint: ComplaintDetail }) {
  const reply = useReply(complaint.ticket);
  const options = useReplyOptions(complaint.ticket);
  const ai = useDraftOption(complaint.ticket);
  const [status, setStatus] = useState<ComplaintStatus | ''>('');
  const [loaded, setLoaded] = useState<Loaded>({ key: null, text: '', wording: null, n: 0 });
  const list = options.data?.options ?? [];
  const chosen = list.find((o) => o.key === loaded.key) ?? null;
  const load = (key: string, text: string, wording: Wording) => setLoaded((d) => ({ key, text, wording, n: d.n + 1 }));

  const pick = (key: string) => {
    const option = list.find((o) => o.key === key);
    if (option) load(option.key, option.text, 'rules');
  };
  const draftWithAi = () => {
    if (!chosen) return;
    ai.mutate(chosen.key, { onSuccess: (d) => load(chosen.key, d.text, d.worded_by === 'ai' ? 'ai' : 'rules_fallback') });
  };
  const send = async (body: string) => {
    await reply.mutateAsync({ body, ...(status ? { status } : {}), ...(chosen?.asks ? { asks: chosen.asks } : {}) });
    setStatus('');
    setLoaded((d) => ({ ...d, key: null, wording: null }));
  };

  return (
    <Stack sx={{ gap: 1.5 }}>
      <Destination complaint={complaint} />
      {options.isPending && <Skeleton variant="rounded" height={96} />}
      {options.isError && <Alert severity="warning">Reply options could not be loaded. You can still write a reply.</Alert>}
      {list.length > 0 && (
        <OptionCards label="Replies that fit this complaint" selected={loaded.key} onSelect={pick}
          items={list.map((o) => ({ id: o.key, label: o.label, why: o.why }))} />
      )}
      {chosen && (
        <DraftRow wording={loaded.wording} asks={chosen.asks !== null} pending={ai.isPending}
          error={ai.isError ? ai.error.message : null} onDraft={draftWithAi} />
      )}
      <ReplyBox key={loaded.n} stacked initial={loaded.text} label="Reply to the consumer"
        placeholder="Pick a reply above or write in plain words. The consumer may read this on a phone."
        pending={reply.isPending} error={reply.error?.message ?? null} onSend={send}
        extra={
          <TextField select size="small" label="Then set status" value={status} fullWidth
            onChange={(e) => setStatus(e.target.value as ComplaintStatus | '')}>
            <MenuItem value="">Keep as {complaint.status}</MenuItem>
            {COMPLAINT_STATUSES.filter((x) => x !== complaint.status).map((x) => <MenuItem key={x} value={x}>{x}</MenuItem>)}
          </TextField>
        } />
    </Stack>
  );
}
