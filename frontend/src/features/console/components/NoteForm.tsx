import { Button, CircularProgress, MenuItem, Stack, TextField } from '@mui/material';
import { useState, type FormEvent } from 'react';

import type { Person } from '@/features/complaints';
import { SendStatus, type SendState } from '@/shared/components/SendStatus';

import { HANDOFF_NOTE } from '../api/actionsApi';

interface NoteFormProps {
  /** Shown as a picker when the note goes with a person. */
  people?: Person[];
  initialPerson?: string;
  noteLabel: string;
  submitLabel: string;
  state: SendState;
  onSubmit: (note: string, personId: string) => void;
  onCancel: () => void;
}

function PersonPicker({ people, value, onChange, missing }: { people: Person[]; value: string; onChange: (id: string) => void; missing: boolean }) {
  return (
    <TextField select size="small" label="Hand over to" value={value} required fullWidth onChange={(e) => onChange(e.target.value)}
      error={missing} helperText={missing ? 'Choose who takes it next.' : undefined}>
      {people.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
    </TextField>
  );
}

/** A required note, and a person when one is needed. The server checks the same limits. */
export function NoteForm({ people, initialPerson = '', noteLabel, submitLabel, state, onSubmit, onCancel }: NoteFormProps) {
  const [person, setPerson] = useState(initialPerson);
  const [note, setNote] = useState('');
  const [tried, setTried] = useState(false);
  const length = note.trim().length;
  const noteOk = length >= HANDOFF_NOTE.min && note.length <= HANDOFF_NOTE.max;
  const personOk = !people || Boolean(person);

  const pending = state.isPending;
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    setTried(true);
    if (noteOk && personOk) onSubmit(note.trim(), person);
  };
  const short = tried && length < HANDOFF_NOTE.min;

  return (
    <Stack component="form" onSubmit={submit} noValidate sx={{ gap: 1.5 }}>
      {people && <PersonPicker people={people} value={person} onChange={setPerson} missing={tried && !person} />}
      <TextField size="small" label={noteLabel} value={note} required multiline minRows={2} maxRows={6} fullWidth
        onChange={(e) => setNote(e.target.value)} error={short || note.length > HANDOFF_NOTE.max}
        helperText={short ? `Write at least ${HANDOFF_NOTE.min} characters so the next person knows why.` : `${note.length} of ${HANDOFF_NOTE.max} characters`} />
      <SendStatus state={state} />
      <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
        <Button type="submit" variant="contained" disabled={pending}
          startIcon={pending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
          {pending ? 'Saving' : submitLabel}
        </Button>
        <Button onClick={onCancel} disabled={pending}>Cancel</Button>
      </Stack>
    </Stack>
  );
}
