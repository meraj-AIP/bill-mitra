import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import { Alert, Button, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import { useId, useState, type FormEvent, type ReactNode } from 'react';

import { REPLY_LIMIT } from '../api/types';

const STACKED = { direction: 'column', sx: { gap: 1.5, alignItems: 'stretch' } } as const;
const INLINE = { direction: { xs: 'column', sm: 'row' }, sx: { gap: 1.5, alignItems: { sm: 'center' } } } as const;

interface ReplyBoxProps {
  label: string;
  placeholder: string;
  pending: boolean;
  error: string | null;
  /** Resolves when the message is saved; the box clears then. */
  onSend: (body: string) => Promise<unknown>;
  /** Extra controls shown beside the Send button, such as a status change. */
  extra?: ReactNode;
  /** Lets a caller allow sending with an empty body, for a status-only change. */
  allowEmpty?: boolean;
  /** Starting text. Change the component key to load a new one. */
  initial?: string;
  /** Lays the counter, extras and Send in one column, for a narrow side panel. */
  stacked?: boolean;
}

export function ReplyBox({ label, placeholder, pending, error, onSend, extra, allowEmpty = false, initial = '', stacked }: ReplyBoxProps) {
  const [body, setBody] = useState(initial);
  const counterId = useId();
  const length = body.trim().length;
  const over = body.length > REPLY_LIMIT;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (over || (!allowEmpty && length === 0)) return;
    try {
      await onSend(body.trim());
      setBody('');
    } catch {
      // The mutation error is shown through the error prop.
    }
  };

  return (
    <Stack component="form" onSubmit={(e) => void submit(e)} sx={{ gap: 1.5 }}>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label={label} placeholder={placeholder} multiline minRows={3} maxRows={10} fullWidth value={body}
        onChange={(e) => setBody(e.target.value)} error={over}
        onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void submit(e); }}
        slotProps={{ htmlInput: { 'aria-describedby': counterId } }} />
      <Stack {...(stacked ? STACKED : INLINE)}>
        <Typography id={counterId} variant="caption" aria-live="polite"
          sx={{ color: over ? 'error.main' : 'text.secondary', fontVariantNumeric: 'tabular-nums', flex: 1 }}>
          {body.length} of {REPLY_LIMIT} characters{over ? ', too long to send' : ''}. Ctrl and Enter sends.
        </Typography>
        {extra}
        <Button type="submit" variant="contained" disabled={pending || over || (!allowEmpty && length === 0)}
          startIcon={pending ? <CircularProgress size={16} color="inherit" aria-hidden /> : <SendOutlinedIcon />}>
          {pending ? 'Sending' : 'Send'}
        </Button>
      </Stack>
    </Stack>
  );
}
