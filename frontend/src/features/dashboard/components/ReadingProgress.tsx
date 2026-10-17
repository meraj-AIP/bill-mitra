import CheckIcon from '@mui/icons-material/Check';
import { Box, CircularProgress, LinearProgress, Paper, Stack, Typography } from '@mui/material';

import type { Sending } from '../hooks/useBillUpload';
import { useElapsed } from '../hooks/useElapsed';
import { READING_STAGES } from '../model/labels';

function StageMark({ state }: { state: 'done' | 'active' | 'waiting' }) {
  if (state === 'done') return <CheckIcon sx={{ fontSize: 18, color: 'success.main' }} />;
  if (state === 'active') return <CircularProgress size={16} thickness={5} />;
  return <Box sx={{ width: 10, height: 10, borderRadius: '50%', border: 1.5, borderColor: 'grey.400', m: '4px' }} />;
}

/** Upload progress is real, so it gets a percentage. Offline and retrying say so instead. */
function SendingLine({ sending }: { sending: Sending }) {
  const percent = Math.round(sending.progress * 100);
  const text = sending.paused ? 'You are offline. Your bill will be sent when the connection is back.'
    : sending.retrying ? 'The connection dropped. Trying again.'
      : `Sending your bill, ${percent}%`;
  return (
    <Box sx={{ mt: 2, mb: 2.5 }}>
      <Typography variant="body2" sx={{ color: sending.paused || sending.retrying ? 'warning.dark' : 'text.secondary' }}>{text}</Typography>
      <LinearProgress variant="determinate" value={percent} sx={{ mt: 1 }} aria-label="Upload progress" />
    </Box>
  );
}

/** Reading stages follow elapsed time, not real progress, so there is no percentage to make up. */
export function ReadingProgress({ sending }: { sending: Sending | null }) {
  const uploading = sending !== null && (sending.progress < 1 || sending.paused || sending.retrying);
  const seconds = useElapsed();
  const active = READING_STAGES.findLastIndex((s) => seconds >= s.from);
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 } }} role="status" aria-live="polite">
      <Typography variant="h3" component="p">
        Reading your bill
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
        This usually takes 10 to 40 seconds. Please keep this page open.
      </Typography>
      {sending && uploading ? <SendingLine sending={sending} /> : <LinearProgress sx={{ my: 2.5 }} aria-hidden />}
      <Stack component="ol" sx={{ gap: 1.5, m: 0, p: 0, listStyle: 'none' }}>
        {READING_STAGES.map((stage, i) => {
          const state = i < active ? 'done' : i === active ? 'active' : 'waiting';
          return (
            <Stack component="li" key={stage.label} direction="row" sx={{ gap: 1.5, alignItems: 'center' }}>
              <Box sx={{ width: 20, display: 'grid', placeItems: 'center' }}>
                <StageMark state={state} />
              </Box>
              <Typography variant="body2" sx={{ fontWeight: state === 'active' ? 600 : 400,
                color: state === 'waiting' ? 'text.secondary' : 'text.primary' }}>
                {stage.label}
              </Typography>
            </Stack>
          );
        })}
      </Stack>
      <Typography variant="caption" sx={{ display: 'block', mt: 2.5, color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>
        {seconds} s so far{seconds > 45 ? '. Taking longer than usual, still working.' : ''}
      </Typography>
    </Paper>
  );
}
