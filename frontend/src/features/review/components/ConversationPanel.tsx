import { Box, Button, CircularProgress, FormControlLabel, Radio, RadioGroup, Stack, TextField, Typography } from '@mui/material';
import { useLayoutEffect, useRef, useState, type FormEvent } from 'react';

import { MessageThread, RequestList } from '@/features/complaints';

import { useAskConsumer } from '../api/reviewApi';
import type { CaseDetail, RequestKind } from '../api/types';
import { CASE_SECTION, REQUEST_KIND } from '../model/labels';
import { Panel } from './Panel';
import { useConfirm } from '@/shared/feedback';

const NOTE_LIMIT = 500;

/** Asking for more is the other way to move a case, so it sits beside the decision. */
export function AskConsumer({ c }: { c: CaseDetail }) {
  const ask = useAskConsumer(c.ticket);
  const [kind, setKind] = useState<RequestKind>('earlier_bills');
  const [note, setNote] = useState('');
  const needsNote = kind === 'note' && !note.trim();
  const confirm = useConfirm();
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (needsNote || note.length > NOTE_LIMIT) return;
    if (!(await confirm({ title: `Ask the consumer for ${REQUEST_KIND[kind].label.toLowerCase()}?`, confirmLabel: 'Send request',
      body: note.trim() ? `With your line: \u201c${note.trim()}\u201d` : REQUEST_KIND[kind].hint,
      points: [`They are messaged on ${c.channel === 'whatsapp' ? 'WhatsApp' : 'the web app'}, in their language.`,
        'Their next photo or message is filed under this case.'] }))) return;
    ask.mutate(note.trim() ? { kind, note: note.trim() } : { kind }, { onSuccess: () => setNote('') });
  };
  return (
    <Stack component="form" onSubmit={(e) => void submit(e)} id={CASE_SECTION.ask} tabIndex={-1}
      sx={{ gap: 1.5, scrollMarginTop: 80, '&:focus': { outline: 'none' } }}>
      <RadioGroup row value={kind} onChange={(e) => setKind(e.target.value as RequestKind)} aria-label="What to ask for">
        {(Object.keys(REQUEST_KIND) as RequestKind[]).map((k) => (
          <FormControlLabel key={k} value={k} control={<Radio size="small" />} label={REQUEST_KIND[k].label} />
        ))}
      </RadioGroup>
      <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1 }}>{REQUEST_KIND[kind].hint}. The consumer is messaged on {c.channel === 'whatsapp' ? 'WhatsApp' : 'the web app'} in their language.</Typography>
      <TextField size="small" multiline minRows={2} label={kind === 'note' ? 'What do you need to know?' : 'Add a line (optional)'}
        value={note} onChange={(e) => setNote(e.target.value)} error={note.length > NOTE_LIMIT}
        helperText={`${note.length} of ${NOTE_LIMIT} characters`} />
      <Button type="submit" variant="contained" size="large" fullWidth disabled={ask.isPending || needsNote}
        startIcon={ask.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
        Send request
      </Button>
    </Stack>
  );
}

/** The case thread and what is still asked of the consumer. It scrolls in its own box, so new messages never move
 * the page. Asking for more lives in the action panel. */
export function ConversationPanel({ c }: { c: CaseDetail }) {
  const box = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [c.messages.length]);
  const open = c.requests.filter((r) => r.status === 'open').length;
  return (
    <Panel title="Conversation" caption={open ? `${open} ${open === 1 ? 'request is' : 'requests are'} waiting on the consumer.` : 'Messages with the consumer on this case. Select a photo to see it full size.'}>
      {c.requests.length > 0 && <Box sx={{ mb: 2 }}><RequestList requests={c.requests} /></Box>}
      <Box ref={box} tabIndex={0} aria-label="Conversation messages"
        sx={{ maxHeight: 420, overflowY: 'auto', overscrollBehavior: 'contain', pr: 0.5, borderRadius: 1 }}>
        <MessageThread messages={c.messages} viewer="staff" />
      </Box>
    </Panel>
  );
}
