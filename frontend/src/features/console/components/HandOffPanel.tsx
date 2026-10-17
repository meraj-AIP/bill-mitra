import ReplyRoundedIcon from '@mui/icons-material/ReplyRounded';
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded';
import { Box, Button, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { holderOf, type ComplaintDetail, type Person } from '@/features/complaints';
import { dateTime } from '@/shared/lib/format';

import { useAssign, useSendBack } from '../api/actionsApi';
import { usePreset } from '../hooks/usePreset';
import type { Focus } from '../model/focus';
import { NoteForm } from './NoteForm';

type Mode = { kind: 'hand_over'; person: string } | { kind: 'send_back' } | null;

function Holder({ complaint }: { complaint: ComplaintDetail }) {
  const holder = holderOf(complaint);
  const handoff = complaint.handoff;
  return (
    <Stack sx={{ gap: 0.75 }}>
      <Typography variant="body2">
        {holder ? <>With <Box component="span" sx={{ fontWeight: 600 }}>{holder.name}</Box>.</> : 'Not with anyone yet. It waits in the queue for an officer.'}
        {complaint.waiting_on === 'consumer' && ' Waiting on the consumer to answer.'}
      </Typography>
      {handoff && (
        <Box sx={{ p: 1.25, borderRadius: 1, bgcolor: 'grey.50', border: 1, borderColor: 'divider' }}>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
            {handoff.by ? `Handed over by ${handoff.by.name}` : 'Routed here automatically'}{handoff.at ? `, ${dateTime(handoff.at)}` : ''}
          </Typography>
          {handoff.note && (
            <Typography variant="body2" dir="auto" sx={{ mt: 0.25, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{handoff.note}</Typography>
          )}
        </Box>
      )}
    </Stack>
  );
}

/** `sendBackTo` names who gets it back, or is null when this viewer cannot send it back. */
interface ControlsProps { complaint: ComplaintDetail; people: Person[]; sendBackTo: string | null; preset: Focus | null }

/** Hand over and Send back, each opening a short form with a required note. */
function Controls({ complaint, people, sendBackTo, preset }: ControlsProps) {
  const assign = useAssign(complaint.ticket);
  const sendBack = useSendBack(complaint.ticket);
  const [mode, setMode] = useState<Mode>(null);
  usePreset(preset, 'handoff', true, (key) => setMode({ kind: 'hand_over', person: people.some((p) => p.id === key) ? key : '' }));
  const close = () => { setMode(null); assign.reset(); sendBack.reset(); };

  if (mode?.kind === 'hand_over') {
    return (
      <NoteForm key="hand_over" people={people} initialPerson={mode.person} noteLabel="Note for the next person" submitLabel="Hand over"
        pending={assign.isPending} error={assign.error?.message ?? null} onCancel={close}
        onSubmit={(note, person) => assign.mutate({ account_id: person, note }, { onSuccess: close })} />
    );
  }
  if (mode?.kind === 'send_back' && sendBackTo) {
    return (
      <NoteForm key="send_back" noteLabel={`Why it goes back to ${sendBackTo}`} submitLabel="Send back"
        pending={sendBack.isPending} error={sendBack.error?.message ?? null} onCancel={close}
        onSubmit={(note) => sendBack.mutate(note, { onSuccess: close })} />
    );
  }
  return (
    <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
      {people.length > 0 && (
        <Button variant="outlined" startIcon={<SwapHorizRoundedIcon />} onClick={() => setMode({ kind: 'hand_over', person: '' })}>Hand over</Button>
      )}
      {sendBackTo && (
        <Button variant="outlined" startIcon={<ReplyRoundedIcon />} onClick={() => setMode({ kind: 'send_back' })}>Send back to {sendBackTo}</Button>
      )}
    </Stack>
  );
}

/** The server decides who may send back (the holder, when someone handed it to them). */
function sendBackTarget(complaint: ComplaintDetail): string | null {
  if (!complaint.can_return) return null;
  return complaint.handoff?.by?.name ?? 'whoever handed it over';
}

/** Who has the complaint, Hand over with a note, and Send back when it was handed to you. */
export function HandOffPanel({ complaint, preset }: { complaint: ComplaintDetail; preset: Focus | null }) {
  const holder = holderOf(complaint);
  // The server lists people only for accounts allowed to hand over, so an empty list hides the control.
  const people = (complaint.assignable ?? []).filter((p) => p.id !== holder?.id);
  const sendBackTo = sendBackTarget(complaint);
  const open = complaint.status === 'Open' || complaint.status === 'In progress';
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Holder complaint={complaint} />
      {!open && <Typography variant="caption" sx={{ color: 'text.secondary' }}>Closed complaints stay with whoever closed them.</Typography>}
      {open && (people.length > 0 || sendBackTo) && <Controls complaint={complaint} people={people} sendBackTo={sendBackTo} preset={preset} />}
    </Stack>
  );
}
