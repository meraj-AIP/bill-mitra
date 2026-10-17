import AddAPhotoOutlinedIcon from '@mui/icons-material/AddAPhotoOutlined';
import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import { Alert, Box, Button, CircularProgress, Paper, Stack, TextField, Typography } from '@mui/material';
import { useRef, useState, type ChangeEvent } from 'react';

import { useFilePreview } from '@/shared/hooks/useFilePreview';

import { useSendPhoto } from '../api/myComplaintsApi';

const CAPTION_LIMIT = 300;
// Phone photos are shrunk before upload, so this only stops files no phone camera makes.
const MAX_BYTES = 20_000_000;

function problemWith(file: File): string | null {
  if (!file.type.startsWith('image/')) return 'Please choose a photo. Other files cannot be sent here.';
  return file.size > MAX_BYTES ? 'This photo is too large. Please choose a smaller one.' : null;
}

function Preview({ url, name }: { url: string; name: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <Box sx={{ p: 2, borderRadius: 1, bgcolor: 'grey.100' }}>
        <Typography variant="body2">{name}</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>This phone cannot show a preview of this photo. You can still send it.</Typography>
      </Box>
    );
  }
  return (
    <Box component="img" src={url} alt="The photo you are about to send" onError={() => setFailed(true)}
      sx={{ display: 'block', width: '100%', maxHeight: { xs: 280, sm: 340 }, objectFit: 'contain', borderRadius: 1, bgcolor: 'grey.100' }} />
  );
}

/** Pick a photo, see it, then Send or Choose another. Nothing leaves the phone before Send. */
export function PhotoReply({ ticket }: { ticket: string }) {
  const input = useRef<HTMLInputElement>(null);
  const { preview, show, clear } = useFilePreview();
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const send = useSendPhoto(ticket);

  const choose = () => input.current?.click();
  const picked = (event: ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0];
    // Clearing the value lets the same photo be picked again after Remove.
    event.target.value = '';
    if (!next) return;
    const issue = problemWith(next);
    setProblem(issue);
    send.reset();
    if (issue) return;
    setFile(next);
    show(next);
  };
  const remove = () => { setFile(null); setCaption(''); clear(); send.reset(); };
  const submit = () => {
    if (!file || caption.length > CAPTION_LIMIT) return;
    send.mutate({ file, body: caption.trim() }, { onSuccess: remove });
  };

  return (
    <Stack sx={{ gap: 1.5 }}>
      <input ref={input} type="file" accept="image/*" hidden onChange={picked} aria-hidden tabIndex={-1} />
      {problem && <Alert severity="warning">{problem}</Alert>}
      {!preview && (
        <Box>
          <Button variant="outlined" startIcon={<AddAPhotoOutlinedIcon />} onClick={choose}>Add a photo</Button>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.75 }}>
            You will see the photo before it is sent.
          </Typography>
        </Box>
      )}
      {preview && (
        <Paper variant="outlined" sx={{ p: 1.5 }}>
          <Stack sx={{ gap: 1.5 }}>
            <Preview key={preview.url} url={preview.url} name={preview.name} />
            <TextField size="small" label="Add a line (optional)" value={caption} onChange={(e) => setCaption(e.target.value)}
              error={caption.length > CAPTION_LIMIT} helperText={`${caption.length} of ${CAPTION_LIMIT} characters`} />
            {send.error && <Alert severity="error">{send.error.message}</Alert>}
            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1 }}>
              <Button variant="contained" onClick={submit} disabled={send.isPending || caption.length > CAPTION_LIMIT}
                startIcon={send.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : <SendOutlinedIcon />}>
                {send.isPending ? 'Sending' : 'Send'}
              </Button>
              <Button variant="outlined" onClick={choose} disabled={send.isPending}>Choose another</Button>
              <Button onClick={remove} disabled={send.isPending}>Remove</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
