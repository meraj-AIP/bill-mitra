import { keyframes } from '@emotion/react';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import MicRoundedIcon from '@mui/icons-material/MicRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { Box, IconButton, InputBase, Stack, Tooltip, Typography } from '@mui/material';
import { useState } from 'react';

import { type RecorderState, useRecorder } from '../hooks/useRecorder';

interface ComposerProps {
  placeholder: string;
  busy: boolean;
  onText: (text: string) => void;
  onAttach: () => void;
  onVoice: (blob: Blob) => void;
}

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
`;

const swap = (shown: boolean) => ({
  position: 'absolute' as const,
  transition: 'transform 180ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 140ms',
  transform: shown ? 'scale(1) rotate(0deg)' : 'scale(0.4) rotate(-30deg)',
  opacity: shown ? 1 : 0,
});

function actionLabels(hasText: boolean, state: RecorderState) {
  const label = hasText ? 'Send' : state === 'recording' ? 'Stop and send voice note' : 'Record a voice question';
  if (state === 'denied') return { label, hint: 'Microphone permission was refused' };
  if (state === 'unsupported') return { label, hint: 'Voice is not supported in this browser' };
  return { label, hint: label };
}

const timer = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

function Recording({ seconds }: { seconds: number }) {
  return (
    <Stack direction="row" sx={{ flex: 1, alignItems: 'center', gap: 1, px: 1.5 }} role="status">
      <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: 'error.main', animation: `${pulse} 1.2s infinite`,
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' } }} />
      <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>{timer(seconds)}</Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary' }} noWrap>Recording. Tap send to finish.</Typography>
    </Stack>
  );
}

export function Composer({ placeholder, busy, onText, onAttach, onVoice }: ComposerProps) {
  const [draft, setDraft] = useState('');
  const recorder = useRecorder(onVoice);
  const recording = recorder.state === 'recording';
  const hasText = draft.trim().length > 0;
  const micBlocked = recorder.state === 'unsupported' || recorder.state === 'denied';

  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    onText(text);
    setDraft('');
  };

  const action = () => {
    if (hasText) submit();
    else if (recording) recorder.stop();
    else void recorder.start();
  };

  const { label, hint } = actionLabels(hasText, recorder.state);

  return (
    <Stack direction="row" sx={{ position: 'relative', px: 1, pt: 0.75, pb: 1, gap: 0.75, alignItems: 'flex-end', flexShrink: 0 }}>
      <Stack direction="row"
        sx={(theme) => ({ flex: 1, minHeight: 46, bgcolor: 'background.paper', borderRadius: '23px', alignItems: 'center', pl: 0.5, pr: 0.5,
          boxShadow: theme.palette.chat.shadow, transition: 'box-shadow 160ms',
          '&:focus-within': { boxShadow: `0 0 0 2px ${theme.palette.chat.accent}` } })}>
        {recording ? <Recording seconds={recorder.seconds} /> : (
          <InputBase value={draft} onChange={(e) => setDraft(e.target.value)} multiline maxRows={5} placeholder={placeholder}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            sx={{ flex: 1, px: 1.25, py: 1.25, fontSize: '0.9375rem', lineHeight: 1.4 }}
            slotProps={{ input: { 'aria-label': 'Message', dir: 'auto' } }} />
        )}
        <Tooltip title="Attach a bill: JPG, PNG, WEBP, HEIC or PDF">
          <span>
            <IconButton onClick={onAttach} disabled={busy || recording} aria-label="Attach a bill photo or PDF"
              sx={(theme) => ({ color: theme.palette.chat.meta })}>
              <AttachFileIcon sx={{ transform: 'rotate(45deg)', fontSize: 22 }} />
            </IconButton>
          </span>
        </Tooltip>
      </Stack>
      <Tooltip title={hint}>
        <span>
          <IconButton onClick={action} aria-label={label} disabled={busy || (!hasText && !recording && micBlocked)}
            sx={(theme) => ({ width: 46, height: 46, bgcolor: recording ? 'error.main' : theme.palette.chat.accent,
              color: theme.palette.chat.onHeader, boxShadow: theme.palette.chat.shadow, transition: 'background-color 180ms, transform 120ms',
              '&:hover': { bgcolor: recording ? 'error.dark' : theme.palette.chat.accentDark },
              '&:active': { transform: 'scale(0.94)' },
              '&.Mui-disabled': { bgcolor: theme.palette.chat.accent, color: theme.palette.chat.onHeader, opacity: 0.5 } })}>
            <SendRoundedIcon sx={{ ...swap(hasText || recording), fontSize: 21, ml: '2px' }} />
            <MicRoundedIcon sx={{ ...swap(!hasText && !recording), fontSize: 23 }} />
          </IconButton>
        </span>
      </Tooltip>
    </Stack>
  );
}
