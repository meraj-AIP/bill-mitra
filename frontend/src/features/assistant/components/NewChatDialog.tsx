import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import { useState } from 'react';

import { ErrorNotice } from '@/shared/feedback';

interface NewChatDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}

/** New chat erases the saved conversation on the server, so it asks first. */
export function NewChatDialog({ open, onClose, onConfirm }: NewChatDialogProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const close = () => {
    if (pending) return;
    setError(null);
    onClose();
  };

  const confirm = async () => {
    setPending(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} maxWidth="xs" fullWidth aria-labelledby="new-chat-title">
      <DialogTitle id="new-chat-title" sx={{ pb: 1 }}>Start a new chat?</DialogTitle>
      <DialogContent>
        <DialogContentText variant="body2">
          This deletes your conversation with Bill Mitra from your account, including every message and reply. It cannot be undone.
        </DialogContentText>
        <ErrorNotice error={error} action="Starting a new chat" sx={{ mt: 2 }} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={close} disabled={pending} color="inherit">Keep chat</Button>
        <Button onClick={() => void confirm()} disabled={pending} variant="contained" color="error">
          {pending ? 'Deleting…' : 'Delete and start new'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
