import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded';
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography,
} from '@mui/material';
import { createContext, useCallback, useContext, useId, useRef, useState, type ReactNode } from 'react';

export type ConfirmTone = 'default' | 'warning' | 'danger';

export interface ConfirmOptions {
  title: string;
  /** One or two sentences: what happens when they confirm. */
  body?: ReactNode | undefined;
  /** Short lines naming each consequence: who is told, what changes, what cannot be undone. */
  points?: string[] | undefined;
  confirmLabel: string;
  cancelLabel?: string | undefined;
  tone?: ConfirmTone | undefined;
  /** Ask for a note with the action, such as why something is rejected. Required when `min` is set. */
  note?: { label: string; min?: number; max?: number; helper?: string } | undefined;
  /** Destructive actions: the person types this word before the button wakes up. */
  typeToConfirm?: string | undefined;
}

export interface Confirmed { note: string }
type Ask = (options: ConfirmOptions) => Promise<Confirmed | null>;

const ConfirmContext = createContext<Ask | null>(null);

const ICON: Record<ConfirmTone, ReactNode> = {
  default: <HelpOutlineRoundedIcon color="primary" />,
  warning: <WarningAmberRoundedIcon color="warning" />,
  danger: <ErrorOutlineRoundedIcon color="error" />,
};

function Body({ o, note, setNote, typed, setTyped }: {
  o: ConfirmOptions; note: string; setNote: (v: string) => void; typed: string; setTyped: (v: string) => void;
}) {
  return (
    <Stack sx={{ gap: 1.5 }}>
      {o.body && <Typography variant="body1" component="div">{o.body}</Typography>}
      {o.points && o.points.length > 0 && (
        <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'grid', gap: 0.5 }}>
          {o.points.map((p) => <Typography key={p} component="li" variant="body2">{p}</Typography>)}
        </Box>
      )}
      {o.note && (
        <TextField label={o.note.label} value={note} onChange={(e) => setNote(e.target.value)} multiline minRows={2} fullWidth autoFocus
          slotProps={{ htmlInput: { maxLength: o.note.max ?? 500 } }}
          helperText={o.note.helper ?? (o.note.min ? `At least ${o.note.min} characters.` : 'Optional.')} />
      )}
      {o.typeToConfirm && (
        <TextField label={`Type ${o.typeToConfirm} to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} fullWidth
          autoComplete="off" />
      )}
    </Stack>
  );
}

const COLOR: Record<ConfirmTone, 'primary' | 'warning' | 'error'> = { default: 'primary', warning: 'warning', danger: 'error' };

function ConfirmDialog({ o, onClose }: { o: ConfirmOptions; onClose: (value: Confirmed | null) => void }) {
  const [note, setNote] = useState('');
  const [typed, setTyped] = useState('');
  const titleId = useId();
  const tone = o.tone ?? 'default';
  const noteOk = !o.note?.min || note.trim().length >= o.note.min;
  const typedOk = !o.typeToConfirm || typed.trim().toUpperCase() === o.typeToConfirm.toUpperCase();
  // On a dangerous action the safe choice has the focus, so Enter by habit does nothing harmful.
  const focusCancel = tone === 'danger' && !o.note && !o.typeToConfirm;
  return (
    <Dialog open onClose={() => onClose(null)} aria-labelledby={titleId} maxWidth="xs" fullWidth>
      <form onSubmit={(e) => { e.preventDefault(); if (noteOk && typedOk) onClose({ note: note.trim() }); }}>
        <DialogTitle id={titleId} sx={{ display: 'flex', gap: 1.25, alignItems: 'center' }}>{ICON[tone]}{o.title}</DialogTitle>
        <DialogContent><Body o={o} note={note} setNote={setNote} typed={typed} setTyped={setTyped} /></DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={() => onClose(null)} color="inherit" autoFocus={focusCancel}>{o.cancelLabel ?? 'Cancel'}</Button>
          <Button type="submit" variant="contained" color={COLOR[tone]} disabled={!noteOk || !typedOk}
            autoFocus={!focusCancel && !o.note && !o.typeToConfirm}>
            {o.confirmLabel}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** One confirmation dialog for the whole app. `useConfirm()` opens it and resolves with the note, or null on cancel.
 * Each opening is a fresh dialog (keyed), so a note typed for one action never carries into the next. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<{ o: ConfirmOptions; n: number } | null>(null);
  const resolver = useRef<((v: Confirmed | null) => void) | null>(null);
  const ask = useCallback<Ask>((options) => new Promise((resolve) => {
    resolver.current?.(null);
    resolver.current = resolve;
    setOpen((current) => ({ o: options, n: (current?.n ?? 0) + 1 }));
  }), []);
  const close = (value: Confirmed | null) => {
    resolver.current?.(value);
    resolver.current = null;
    setOpen(null);
  };
  return (
    <ConfirmContext.Provider value={ask}>
      {children}
      {open && <ConfirmDialog key={open.n} o={open.o} onClose={close} />}
    </ConfirmContext.Provider>
  );
}

/** `const confirm = useConfirm(); if (await confirm({...})) act();` The result carries the note, if one was asked. */
export function useConfirm(): Ask {
  const ask = useContext(ConfirmContext);
  if (!ask) throw new Error('useConfirm needs ConfirmProvider');
  return ask;
}

/** Thrown from a send handler when the person cancels the confirmation, so a form keeps what they typed. */
export class Cancelled extends Error {
  constructor() {
    super('Cancelled');
  }
}
