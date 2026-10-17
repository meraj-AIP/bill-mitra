import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
import { Box, Button, LinearProgress, Paper, Stack, Typography } from '@mui/material';

interface StillReadingProps {
  /** Checking on the job failed even after retries; the read itself carries on at the server. */
  checkFailed: boolean;
  onStartOver: () => void;
}

/** The read hit a passing fault and is queued. Calm, with no timer, because the server retries for minutes. */
export function StillReading({ checkFailed, onStartOver }: StillReadingProps) {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 } }} role="status" aria-live="polite">
      <Stack direction="row" sx={{ gap: 1.5, alignItems: 'flex-start' }}>
        <Box sx={{ color: 'primary.light', pt: 0.25 }}><HourglassEmptyRoundedIcon /></Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h3" component="p">Still reading your bill</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            Reading is taking longer than usual today. We have your photo and keep trying. Your report opens here when it
            is ready, and it will also be in My bills, so you can close this page.
          </Typography>
        </Box>
      </Stack>
      <LinearProgress sx={{ my: 2.5 }} aria-hidden />
      {checkFailed && (
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
          We cannot check on it right now. It will still appear in My bills when it is ready.
        </Typography>
      )}
      <Button size="small" onClick={onStartOver}>Upload a different bill</Button>
    </Paper>
  );
}
